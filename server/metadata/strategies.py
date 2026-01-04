from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Dict, List

from ..llm_client import LLMClient
from .heuristics import extract_composer_code, extract_key, infer_genre


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
    metadata['key_signature'] = metadata.get('key_signature') or extract_key(metadata, ocr_payloads)
    metadata['genre'] = metadata.get('genre') or infer_genre(metadata, ocr_payloads)
    metadata['composer_code'] = metadata.get('composer_code') or extract_composer_code(metadata, ocr_payloads)
