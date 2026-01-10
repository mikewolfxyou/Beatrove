from __future__ import annotations

import base64
import mimetypes
import os
import shlex
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Tuple

from urllib.parse import urlparse, urlunparse

import requests

from .utils import (
    _dict_to_plain_text,
    _extract_response_payload,
    _log_raw_text,
    _normalize_metadata,
)


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


class GeminiOCRProvider(OCRProvider):

  def __init__(self):
    self.api_key = os.getenv('GEMINI_API_KEY', '')
    self.model = os.getenv('VINYL_OCR_GEMINI_MODEL', 'gemini-1.5-flash')
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
    return bool(self.api_key)

  def extract(self, image_path: Path) -> Dict[str, str]:
    try:
      encoded_image, mime_type = _encode_image(image_path)
    except OSError:
      return {}

    endpoint = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{self.model}:generateContent'
    )
    payload = {
        'contents': [
            {
                'role': 'user',
                'parts': [
                    {
                        'text': self.prompt
                    },
                    {
                        'inline_data': {
                            'mime_type': mime_type,
                            'data': encoded_image
                        }
                    }
                ]
            }
        ],
        'generationConfig': {
            'temperature': _get_float_env('VINYL_OCR_TEMPERATURE', 0.0),
            'maxOutputTokens': _get_int_env('VINYL_OCR_MAX_TOKENS', 15000)
        }
    }

    try:
      response = requests.post(
          endpoint,
          params={'key': self.api_key},
          json=payload,
          timeout=60
      )
    except requests.RequestException as exc:
      print(f'[OCR] Gemini request failed: {exc}')
      return {}

    if response.status_code >= 400:
      print(f'[OCR] Gemini error {response.status_code}: {response.text}')
      return {}

    parsed_payload = _extract_gemini_text(response)
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


def _encode_image(image_path: Path) -> Tuple[str, str]:
  data = image_path.read_bytes()
  encoded = base64.b64encode(data).decode('ascii')
  mime_type = mimetypes.guess_type(image_path.name)[0] or 'image/jpeg'
  return encoded, mime_type


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


def _extract_gemini_text(response: requests.Response) -> str:
  try:
    data = response.json()
  except ValueError:
    return response.text.strip()

  if isinstance(data, dict):
    candidates = data.get('candidates')
    if isinstance(candidates, list) and candidates:
      content = candidates[0].get('content') or {}
      parts = content.get('parts')
      if isinstance(parts, list):
        texts = []
        for part in parts:
          if isinstance(part, dict) and isinstance(part.get('text'), str):
            texts.append(part['text'])
        if texts:
          return '\n'.join(texts).strip()
    return _dict_to_plain_text(data).strip()
  return _dict_to_plain_text(data).strip()
