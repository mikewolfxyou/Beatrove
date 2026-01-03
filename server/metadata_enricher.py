from __future__ import annotations

import re
import json
from typing import Dict, List

from .llm_client import LLMClient


class MetadataEnricher:
  """Augment vinyl metadata using heuristics and optional LLM support."""

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

  def __init__(self):
    self.llm_client = LLMClient()

  def enrich(self, metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> Dict[str, str]:
    if 'key_signature' not in metadata:
      metadata['key_signature'] = ''
    if 'genre' not in metadata:
      metadata['genre'] = ''
    if 'composer_code' not in metadata:
      metadata['composer_code'] = ''

    llm_result = self._run_llm(metadata, ocr_payloads)

    if llm_result:
      metadata['key_signature'] = metadata['key_signature'] or llm_result.get('key_signature', '')
      metadata['genre'] = metadata['genre'] or llm_result.get('genre', '')
      metadata['composer_code'] = metadata.get('composer_code') or llm_result.get('composer_code', '')
      # Allow LLM to refine record name if it extracted a cleaner one
      metadata['record_name'] = llm_result.get('record_name') or metadata.get('record_name', '')

    heuristic_key = self._extract_key(metadata)
    heuristic_genre = self._infer_genre(metadata)
    heuristic_code = self._extract_composer_code(metadata, ocr_payloads)

    if not metadata['key_signature'] and heuristic_key:
      metadata['key_signature'] = heuristic_key

    if not metadata['genre'] and heuristic_genre:
      metadata['genre'] = heuristic_genre

    if not metadata['composer_code'] and heuristic_code:
      metadata['composer_code'] = heuristic_code

    return metadata

  def _run_llm(self, metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> Dict[str, str]:
    if not self.llm_client.available:
      return {}

    snippets = []
    for payload in ocr_payloads:
      for key in ('notes', 'record_name'):
        text = payload.get(key)
        if text:
          snippets.append(text)
    snippet_text = '\n'.join(snippets[-8:])
    raw_payload_snippets = '\n'.join(
        f'{idx + 1}. {json.dumps(payload, ensure_ascii=False)}'
        for idx, payload in enumerate(ocr_payloads[-5:])
    )

    prompt = (
        'You are a vinyl archivist. Normalize the provided information and respond ONLY with JSON using keys '
        '{"record_name":"","key_signature":"","genre":"","composer_code":""}. '
        'Record name should retain catalog info, key_signature should be in English (e.g., "A Major"), '
        'composer_code should capture catalogue identifiers like KV, BWV, Hob., D, Op., etc., '
        'and genre should be a concise style such as "Classical", "Baroque", "Jazz", or "Electronic". '
        'If you are unsure, use an empty string. Prefer data extracted from the OCR payloads listed below.\n\n'
        f'Artist: {metadata.get("artist") or ""}\n'
        f'Composer: {metadata.get("composer") or ""}\n'
        f'Record Name: {metadata.get("record_name") or ""}\n'
        f'Label: {metadata.get("label") or ""}\n'
        f'Year: {metadata.get("year") or ""}\n'
        f'OCR Notes:\n{snippet_text}\n'
        f'OCR JSON Payloads:\n{raw_payload_snippets}'
    )
    result = self.llm_client.derive_metadata(prompt)
    if result:
      print(f'[LLM] Raw enrichment response: {json.dumps(result, ensure_ascii=False)}')
    else:
      print('[LLM] No enrichment response received or parsing failed.')
    return result

  def _extract_key(self, metadata: Dict[str, str]) -> str:
    candidates = ' '.join(filter(None, [
        metadata.get('key_signature', ''),
        metadata.get('record_name', ''),
        metadata.get('notes', '')
    ]))
    match = self.KEY_PATTERN.search(candidates)
    if not match:
      return ''
    fragment = match.group(0)
    return self._normalize_key(fragment)

  def _normalize_key(self, fragment: str) -> str:
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

  def _infer_genre(self, metadata: Dict[str, str]) -> str:
    explicit_genre = metadata.get('genre')
    if explicit_genre:
      return explicit_genre

    label = (metadata.get('label') or '').lower()
    if any(hint in label for hint in self.CLASSICAL_LABELS):
      return 'Classical'

    composer = (metadata.get('composer') or '').lower()
    if composer in self.CLASSICAL_COMPOSERS:
      return 'Classical'

    record_name = (metadata.get('record_name') or '').lower()
    if any(hint in record_name for hint in self.CLASSICAL_HINTS):
      return 'Classical'

    notes = (metadata.get('notes') or '').lower()
    if any(hint in notes for hint in self.CLASSICAL_HINTS):
      return 'Classical'

    return ''

  def _extract_composer_code(self, metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> str:
    text_sources = [
      metadata.get('composer_code', ''),
      metadata.get('record_name', ''),
      metadata.get('notes', ''),
      *(payload.get('record_name', '') for payload in ocr_payloads),
      *(payload.get('notes', '') for payload in ocr_payloads)
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
