from __future__ import annotations

import base64
import json
import mimetypes
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import re
from urllib.parse import urlparse, urlunparse

import requests


def extract_metadata(image_path: Path) -> Dict[str, str]:
  """Extract vinyl metadata via HTTP OCR endpoint or local CLI."""
  payload = {}

  http_endpoint = os.getenv('VINYL_OCR_HTTP_URL')
  if http_endpoint:
    payload = _run_http_ocr(http_endpoint, image_path)

  if not payload:
    command = os.getenv('VINYL_OCR_COMMAND')
    if command:
      payload = _run_command_ocr(command, image_path)

  return payload or {}


def _run_http_ocr(endpoint: str, image_path: Path) -> Dict[str, str]:
  endpoint = _normalize_http_endpoint(endpoint)
  try:
    encoded_image, mime_type = _encode_image(image_path)
  except OSError:
    return {}

  prompt = os.getenv(
      'VINYL_OCR_PROMPT',
      (
          'You are an expert archivist for vinyl records. '
          'Carefully read the artwork text and respond ONLY with compact JSON using the following schema: '
          '{"artist":"","composer":"","record_name":"","catalog_number":"","label":"","year":"","location":"","notes":""}. '
          'Fill in empty strings when data is missing, keep the original capitalization for names, and do not add commentary.'
      )
  )

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
                      'text': prompt
                  }
              ]
          }
      ]
  }

  try:
    response = requests.post(endpoint, json=payload, timeout=60)
  except requests.RequestException as exc:
    print(f'[OCR] HTTP request failed: {exc}')
    return {}

  if response.status_code >= 400:
    print(f'[OCR] HTTP error {response.status_code}: {response.text}')
    return {}

  parsed_payload = _extract_response_payload(response)
  print(f'[OCR] Raw response: {parsed_payload}')
  return _normalize_metadata(parsed_payload)


def _run_command_ocr(command_template: str, image_path: Path) -> Dict[str, str]:
  formatted_command = command_template.format(image=str(image_path))
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

  try:
    parsed = json.loads(payload)
  except json.JSONDecodeError:
    parsed = _parse_key_value_payload(payload)

  return _normalize_metadata(parsed)


def _normalize_metadata(parsed: Optional[Any]) -> Dict[str, str]:
  if not parsed:
    return {}
  if isinstance(parsed, str):
    parsed = _parse_json_string(parsed)
    if parsed is None:
      parsed = _parse_key_value_payload(parsed or '')
  return {
      'artist': parsed.get('artist', ''),
      'composer': parsed.get('composer', ''),
      'record_name': parsed.get('record_name') or parsed.get('title', ''),
      'catalog_number': parsed.get('catalog_number', ''),
      'label': parsed.get('label', ''),
      'year': parsed.get('year', ''),
      'location': parsed.get('location', ''),
      'notes': parsed.get('notes', '')
  }


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
  return data


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


def _normalize_http_endpoint(endpoint: str) -> str:
  if not endpoint:
    return endpoint
  parsed = urlparse(endpoint)
  path = parsed.path or ''
  if path in ('', '/'):
    parsed = parsed._replace(path='/v1/chat/completions')
  return urlunparse(parsed)
