from __future__ import annotations

import re
import json
from typing import Dict, List, Optional
from abc import ABC, abstractmethod

from .llm_client import LLMClient


KEY_PATTERN = re.compile(
    r'([A-G](?:[#♯]|[b♭])?\s*(?:-?\s*(?:Dur|Moll|Major|Minor))|in\s+[A-G](?:[#♯]|[b♭])?\s+(?:major|minor))',
    re.IGNORECASE
)
CLASSICAL_HINTS = [
    'concerto', 'konzert', 'symphony', 'sinfonie', 'sonata', 'suite',
    'prelude', 'requiem', 'oratorio', 'kv ', 'opus', 'op.', 'kv.', 'k.', 'catalogue'
]
CLASSICAL_LABELS = [
    'deutsche grammophon', 'dg ', 'harmonia mundi', 'philips', 'emi classics',
    'sony classical', 'naxos', 'telarc', 'decca', 'archiv produktion', 'ecm new series'
]
CLASSICAL_COMPOSERS = {
    'mozart', 'beethoven', 'bach', 'brahms', 'schubert', 'schumann', 'chopin',
    'liszt', 'haydn', 'tchaikovsky', 'vivaldi', 'handel', 'debussy', 'ravel',
    'mendelssohn', 'strauss', 'mahler', 'wagner', 'prokofiev', 'stravinsky',
    'saint-saens', 'satie', 'dvorak', 'berlioz', 'rachmaninoff'
}


class EnrichmentStrategy(ABC):

  @abstractmethod
  def apply(self, metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> None:
    raise NotImplementedError


class LLMEnrichmentStrategy(EnrichmentStrategy):

  def __init__(self, llm_client: LLMClient):
    self.llm_client = llm_client

  def apply(self, metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> None:
    result = self._run_llm(metadata, ocr_payloads)
    if not result:
      return

    prioritized_fields = [
        'artist',
        'composer',
        'catalog_number',
        'label',
        'year',
        'location',
        'genre',
        'key_signature',
        'composer_code'
    ]
    for field in prioritized_fields:
      candidate = result.get(field)
      if candidate and not metadata.get(field):
        metadata[field] = candidate
    record_name_candidate = result.get('record_name')
    if record_name_candidate:
      metadata['record_name'] = record_name_candidate
    llm_notes = result.get('notes')
    if llm_notes and not metadata.get('notes'):
      metadata['notes'] = llm_notes

  def _run_llm(self, metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> Dict[str, str]:
    if not self.llm_client.available:
      return {}

    ocr_texts = []
    for payload in ocr_payloads:
      text = payload.get('notes') or payload.get('raw_text')
      if text:
        ocr_texts.append(text.strip())
    ocr_section = '\n\n'.join(
        f'OCR #{idx + 1}:\n{text}' for idx, text in enumerate(ocr_texts[-5:], start=1)
    )

    prompt = (
        'You are a vinyl archivist. Using the OCR transcripts below, produce structured metadata and respond ONLY with JSON '
        'using keys {"artist":"","composer":"","record_name":"","catalog_number":"","label":"","year":"","location":"","notes":"","genre":"","key_signature":"","composer_code":""}. '
        'Keep catalog numbers verbatim, normalize names, capture any liner-note highlights in notes, and use empty strings when unsure. '
        'Use the manual hints when they are present but otherwise rely on the OCR content.\n\n'
        f'Manual Hints:\n'
        f'- Artist: {metadata.get("artist") or ""}\n'
        f'- Composer: {metadata.get("composer") or ""}\n'
        f'- Record Name: {metadata.get("record_name") or ""}\n'
        f'- Catalog Number: {metadata.get("catalog_number") or ""}\n'
        f'- Label: {metadata.get("label") or ""}\n'
        f'- Year: {metadata.get("year") or ""}\n'
        f'- Location: {metadata.get("location") or ""}\n'
        f'- Notes: {metadata.get("notes") or ""}\n\n'
        f'OCR Transcripts:\n{ocr_section}'
    )
    result = self.llm_client.derive_metadata(prompt)
    if result:
      print(f'[LLM] Raw enrichment response: {json.dumps(result, ensure_ascii=False)}')
    else:
      print('[LLM] No enrichment response received or parsing failed.')
    return result


class HeuristicEnrichmentStrategy(EnrichmentStrategy):

  def apply(self, metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> None:
    metadata['key_signature'] = metadata.get('key_signature') or _extract_key(metadata, ocr_payloads)
    metadata['genre'] = metadata.get('genre') or _infer_genre(metadata, ocr_payloads)
    metadata['composer_code'] = metadata.get('composer_code') or _extract_composer_code(metadata, ocr_payloads)


class MetadataEnricher:
  """Augment vinyl metadata using a staged pipeline."""

  def __init__(self, strategies: Optional[List[EnrichmentStrategy]] = None):
    if strategies is not None:
      self.strategies = strategies
    else:
      self.strategies = [
          LLMEnrichmentStrategy(LLMClient()),
          HeuristicEnrichmentStrategy()
      ]

  def enrich(self, metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> Dict[str, str]:
    metadata.setdefault('key_signature', '')
    metadata.setdefault('genre', '')
    metadata.setdefault('composer_code', '')

    for strategy in self.strategies:
      strategy.apply(metadata, ocr_payloads)
    return metadata


def _extract_key(metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> str:
  candidates = ' '.join(filter(None, [
      metadata.get('key_signature', ''),
      metadata.get('record_name', ''),
      metadata.get('notes', ''),
      *(payload.get('raw_text', '') for payload in ocr_payloads)
  ]))
  match = KEY_PATTERN.search(candidates)
  if not match:
    return ''
  fragment = match.group(0)
  return _normalize_key(fragment)


def _normalize_key(fragment: str) -> str:
  clean = fragment.strip()
  clean = clean.replace('♯', '#').replace('♭', 'b')
  clean = clean.replace('-', ' ')
  clean_lower = clean.lower()

  base_note_match = re.search(r'[A-G](?:#|b)?', clean, re.IGNORECASE)
  if not base_note_match:
    return clean.title()
  note = base_note_match.group(0).upper()
  suffix = 'Major'
  if 'moll' in clean_lower or 'minor' in clean_lower:
    suffix = 'Minor'
  return f'{note} {suffix}'


def _infer_genre(metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> str:
  explicit_genre = metadata.get('genre')
  if explicit_genre:
    return explicit_genre

  label = (metadata.get('label') or '').lower()
  if any(hint in label for hint in CLASSICAL_LABELS):
    return 'Classical'

  composer = (metadata.get('composer') or '').lower()
  if composer in CLASSICAL_COMPOSERS:
    return 'Classical'

  record_name = (metadata.get('record_name') or '').lower()
  if any(hint in record_name for hint in CLASSICAL_HINTS):
    return 'Classical'

  notes = ' '.join(filter(None, [
      (metadata.get('notes') or '').lower(),
      ' '.join((payload.get('raw_text') or '').lower() for payload in ocr_payloads)
  ]))
  if any(hint in notes for hint in CLASSICAL_HINTS):
    return 'Classical'

  return ''


def _extract_composer_code(metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> str:
  text_sources = [
      metadata.get('composer_code', ''),
      metadata.get('record_name', ''),
      metadata.get('notes', ''),
      *(payload.get('record_name', '') for payload in ocr_payloads),
      *(payload.get('notes', '') for payload in ocr_payloads),
      *(payload.get('raw_text', '') for payload in ocr_payloads)
  ]
  code_pattern = re.compile(
      r'\b(?:KV|K\.\s?V\.?|K\.|BWV|Hob\.|Op\.|No\.|D|S\.|HWV|Wq|BuxWV|RV|L|MWV|Kk|P\.)\s*[0-9IVX\-]+[a-zA-Z0-9\- ]*',
      re.IGNORECASE
  )
  for text in text_sources:
    if not text:
      continue
    match = code_pattern.search(text)
    if match:
      return match.group(0).strip()
  return ''
