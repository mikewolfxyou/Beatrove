from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

import requests


class LLMClient:
  """Simple HTTP client for the local LLM completions endpoint."""

  def __init__(self):
    self.provider = os.getenv('LLM_PROVIDER', 'http').lower()
    self.endpoint = os.getenv('LLM_ENDPOINT')
    self.model = os.getenv('LLM_MODEL', 'beatrove-local-metadata')
    self.temperature = _get_float_env('LLM_TEMPERATURE', 0.0)
    self.top_p = _get_float_env('LLM_TOP_P', 1.0)
    self.timeout = _get_float_env('LLM_TIMEOUT_SECONDS', 60.0)
    self.max_retries = int(os.getenv('LLM_MAX_RETRIES', '2'))
    self.max_tokens = int(os.getenv('LLM_MAX_TOKENS', '512'))
    self.gemini_api_key = os.getenv('GEMINI_API_KEY', '')
    self.gemini_model = os.getenv('GEMINI_LLM_MODEL', '')

  @property
  def available(self) -> bool:
    if self.provider == 'gemini':
      return bool(self.gemini_api_key and self.gemini_model)
    return bool(self.endpoint)

  def derive_metadata(self, prompt: str) -> Dict[str, str]:
    """Send a prompt to the LLM endpoint and parse JSON output."""
    if not self.available:
      return {}

    if self.provider == 'gemini':
      return self._derive_with_gemini(prompt)

    payload = {
        'model': self.model,
        'prompt': prompt,
        'temperature': self.temperature,
        'top_p': self.top_p,
        'max_tokens': self.max_tokens,
        'stream': False
    }

    for _ in range(self.max_retries):
      try:
        response = requests.post(self.endpoint, json=payload, timeout=self.timeout)
      except requests.RequestException as exc:
        print(f'[LLM] Request failed: {exc}')
        continue

      if response.status_code >= 400:
        print(f'[LLM] Error {response.status_code}: {response.text}')
        continue

      text = self._extract_text(response)
      if not text:
        continue

      parsed = self._parse_json_payload(text)
      if parsed:
        return parsed

    return {}

  def _derive_with_gemini(self, prompt: str) -> Dict[str, str]:
    endpoint = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{self.gemini_model}:generateContent'
    )
    payload = {
        'contents': [
            {
                'role': 'user',
                'parts': [
                    {
                        'text': prompt
                    }
                ]
            }
        ],
        'generationConfig': {
            'temperature': self.temperature,
            'maxOutputTokens': self.max_tokens,
            'topP': self.top_p
        }
    }

    for _ in range(self.max_retries):
      try:
        response = requests.post(
            endpoint,
            params={'key': self.gemini_api_key},
            json=payload,
            timeout=self.timeout
        )
      except requests.RequestException as exc:
        print(f'[LLM] Gemini request failed: {exc}')
        continue

      if response.status_code >= 400:
        print(f'[LLM] Gemini error {response.status_code}: {response.text}')
        continue

      text = self._extract_gemini_text(response)
      if not text:
        continue

      parsed = self._parse_json_payload(text)
      if parsed:
        return parsed

    return {}

  def _extract_gemini_text(self, response: requests.Response) -> str:
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
    return response.text.strip()

  def _extract_text(self, response: requests.Response) -> str:
    try:
      data = response.json()
    except ValueError:
      return response.text.strip()

    if isinstance(data, dict):
      if 'choices' in data:
        choice = data['choices'][0] if data['choices'] else {}
        if isinstance(choice, dict):
          if 'text' in choice and isinstance(choice['text'], str):
            return choice['text'].strip()
          message = choice.get('message') or {}
          content = message.get('content')
          if isinstance(content, str):
            return content.strip()
          if isinstance(content, list):
            for part in content:
              if isinstance(part, dict) and part.get('type') == 'text':
                text = part.get('text')
                if isinstance(text, str):
                  return text.strip()
      text_field = data.get('text')
      if isinstance(text_field, str):
        return text_field.strip()
    return response.text.strip()

  def _parse_json_payload(self, text: str) -> Optional[Dict[str, str]]:
    clean_text = text.strip()
    clean_text = _strip_markdown_fences(clean_text)
    try:
      parsed = json.loads(clean_text)
      if isinstance(parsed, dict):
        return parsed
    except json.JSONDecodeError:
      pass

    # Attempt to locate JSON object inside the string
    match = re.search(r'\{.*\}', clean_text, re.DOTALL)
    if match:
      try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
          return parsed
      except json.JSONDecodeError:
        return None
    return None


def _strip_markdown_fences(text: str) -> str:
  if text.startswith('```'):
    text = re.sub(r'^```[a-zA-Z0-9]*\s*', '', text)
    if text.endswith('```'):
      text = text[:-3]
  return text.strip()


def _get_float_env(key: str, default: float) -> float:
  raw = os.getenv(key)
  try:
    return float(raw) if raw is not None else default
  except ValueError:
    return default
