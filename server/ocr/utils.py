from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

import requests


def _dict_to_plain_text(value: Any, indent: int = 0) -> str:
  """Flatten nested JSON-like objects into readable key/value text."""
  if isinstance(value, dict):
    lines = []
    for key, item in value.items():
      nested = _dict_to_plain_text(item, indent + 2)
      prefix = ' ' * indent
      if '\n' in nested:
        lines.append(f"{prefix}{key}:\n{nested}")
      else:
        lines.append(f"{prefix}{key}: {nested}")
    return '\n'.join(lines).strip()
  if isinstance(value, list):
    parts = [
        _dict_to_plain_text(item, indent + 2) for item in value if item is not None
    ]
    return '\n'.join(part for part in parts if part).strip()
  if value is None:
    return ''
  return str(value).strip()


def _normalize_metadata(parsed: Optional[Any]) -> Dict[str, str]:
  base = {
      'artist': '',
      'composer': '',
      'record_name': '',
      'catalog_number': '',
      'label': '',
      'year': '',
      'location': '',
      'notes': '',
      'raw_text': ''
  }
  if not parsed:
    return base

  if isinstance(parsed, str):
    text = parsed.strip()
    base['raw_text'] = text
    return base

  if isinstance(parsed, dict):
    text = _dict_to_plain_text(parsed)
    base['raw_text'] = text
    return base

  text = _dict_to_plain_text(parsed)
  base['raw_text'] = text
  return base


def _extract_response_payload(response: requests.Response) -> Any:
  try:
    data = response.json()
  except ValueError:
    return response.text.strip()

  if isinstance(data, dict):
    if 'choices' in data:
      choice = data['choices'][0]
      message = choice.get('message') or {}
      content = message.get('content')
      if isinstance(content, list):
        # Assume OpenAI-style multi-part content
        for part in content:
          if isinstance(part, dict) and part.get('type') == 'text':
            return part.get('text', '').strip()
      if isinstance(content, str):
        return content.strip()
      if 'text' in choice:
        return choice['text']
    if 'message' in data and isinstance(data['message'], dict):
      text = data['message'].get('content')
      if isinstance(text, str):
        return text.strip()
    if 'text' in data and isinstance(data['text'], str):
      return data['text'].strip()
    return _dict_to_plain_text(data)
  if isinstance(data, list):
    return _dict_to_plain_text(data)
  return str(data).strip()


def _log_raw_text(normalized: Dict[str, str], fallback: Any) -> None:
  raw_text = (normalized.get('raw_text') or '').strip()
  if raw_text:
    print(f'[OCR] Raw response: {raw_text}')
  else:
    print(f'[OCR] Raw response: {fallback}')
