from __future__ import annotations

import re
from typing import Dict, List

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


def extract_key(metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> str:
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


def infer_genre(metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> str:
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


def extract_composer_code(metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> str:
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
