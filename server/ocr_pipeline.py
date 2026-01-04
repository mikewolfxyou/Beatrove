from __future__ import annotations

import base64
import json
import mimetypes
import os
import shlex
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import re
from urllib.parse import urlparse, urlunparse

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


class OCRProvider(ABC):
  """Strategy interface for OCR extraction."""

  @property
  @abstractmethod
  def available(self) -> bool:
    raise NotImplementedError

  @abstractmethod
  def extract(self, image_path: Path) -> Dict[str, str]:
    raise NotImplementedError


class HTTPOCRProvider(OCRProvider):
  def __init__(self):
    endpoint = os.getenv('VINYL_OCR_HTTP_URL', '')
    self.endpoint = _normalize_http_endpoint(endpoint)
    self.prompt = os.getenv(
        'VINYL_OCR_PROMPT',
        (
            'You are an expert archivist for vinyl records. Carefully transcribe every word from the sleeve images, including multi-page track lists, liner notes, catalog numbers, and multi-language text. '
            'Return the COMPLETE transcription as plain text only—no JSON, no summaries, no paraphrasing, no commentary. '
            'If multiple languages appear, include them verbatim and note the language inline. '
            'Preserve capitalization, diacritics, punctuation, and layout cues when possible (e.g., track numbers, sides, catalog codes). '
            'Do not omit any names, movements, or credits, even if they repeat. '
            'The transcription will be processed by another system to extract structured metadata.'
        )
    )

  @property
  def available(self) -> bool:
    return bool(self.endpoint)

  def extract(self, image_path: Path) -> Dict[str, str]:
    try:
      encoded_image, mime_type = _encode_image(image_path)
    except OSError:
      return {}

    payload = {
        'model': _get_env('VINYL_OCR_MODEL', 'nanonets/Nanonets-OCR2-3B'),
        'temperature': _get_float_env('VINYL_OCR_TEMPERATURE', 0.0),
        'max_tokens': _get_int_env('VINYL_OCR_MAX_TOKENS', 15000),
        'messages': [
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:{mime_type};base64,{encoded_image}'
                        }
                    },
                    {
                        'type': 'text',
                        'text': self.prompt
                    }
                ]
            }
        ]
    }

    try:
      response = requests.post(self.endpoint, json=payload, timeout=60)
    except requests.RequestException as exc:
      print(f'[OCR] HTTP request failed: {exc}')
      return {}

    if response.status_code >= 400:
      print(f'[OCR] HTTP error {response.status_code}: {response.text}')
      return {}

    parsed_payload = _extract_response_payload(response)
    normalized = _normalize_metadata(parsed_payload)
    _log_raw_text(normalized, parsed_payload)
    return normalized


class CommandOCRProvider(OCRProvider):
  def __init__(self):
    self.command_template = os.getenv('VINYL_OCR_COMMAND')

  @property
  def available(self) -> bool:
    return bool(self.command_template)

  def extract(self, image_path: Path) -> Dict[str, str]:
    formatted_command = self.command_template.format(image=str(image_path))
    try:
      result = subprocess.run(
          shlex.split(formatted_command),
          capture_output=True,
          text=True,
          check=False
      )
    except OSError:
      return {}

    payload = result.stdout.strip() or result.stderr.strip()
    if not payload:
      return {}

    normalized = _normalize_metadata(payload)
    _log_raw_text(normalized, payload)
    return normalized


def extract_metadata(image_path: Path) -> Dict[str, str]:
  """Extract vinyl metadata via registered OCR providers."""
  for provider in _get_providers():
    if not provider.available:
      continue
    payload = provider.extract(image_path)
    if payload:
      return payload
  return {}


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


def _parse_key_value_payload(payload: str) -> Dict[str, str]:
  """Fallback parser that reads simple `key: value` lines."""
  data: Dict[str, str] = {}
  for line in payload.splitlines():
    if ':' not in line:
      continue
    key, value = line.split(':', 1)
    data[key.strip().lower()] = value.strip()
  return data


def _parse_json_string(text: str) -> Optional[Dict[str, str]]:
  if not text:
    return None

  clean = text.strip()
  # Remove Markdown code fences (```json ... ```)
  if clean.startswith('```'):
    clean = re.sub(r'^```[a-zA-Z0-9]*\s*', '', clean)
    clean = clean.rstrip('`').rstrip()
    if clean.endswith('```'):
      clean = clean[:-3].strip()

  try:
    return json.loads(clean)
  except json.JSONDecodeError:
    return None


def _encode_image(image_path: Path) -> Tuple[str, str]:
  data = image_path.read_bytes()
  encoded = base64.b64encode(data).decode('ascii')
  mime_type = mimetypes.guess_type(image_path.name)[0] or 'image/jpeg'
  return encoded, mime_type


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


def _get_env(key: str, default: str) -> str:
  return os.getenv(key, default)


def _get_float_env(key: str, default: float) -> float:
  raw = os.getenv(key)
  try:
    return float(raw) if raw is not None else default
  except ValueError:
    return default


def _get_int_env(key: str, default: int) -> int:
  raw = os.getenv(key)
  try:
    return int(raw) if raw is not None else default
  except ValueError:
    return default


def _get_providers() -> List[OCRProvider]:
  return [HTTPOCRProvider(), CommandOCRProvider()]


def _log_raw_text(normalized: Dict[str, str], fallback: Any) -> None:
  raw_text = (normalized.get('raw_text') or '').strip()
  if raw_text:
    print(f'[OCR] Raw response: {raw_text}')
  else:
    print(f'[OCR] Raw response: {fallback}')


def _normalize_http_endpoint(endpoint: str) -> str:
  if not endpoint:
    return endpoint
  parsed = urlparse(endpoint)
  path = parsed.path or ''
  if path in ('', '/'):
    parsed = parsed._replace(path='/v1/chat/completions')
  return urlunparse(parsed)
