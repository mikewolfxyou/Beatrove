from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

import ast
import os
import requests
import re

from server.llm_client import LLMClient, _strip_markdown_fences


def _build_prompt(ocr_text: str) -> str:
  return (
      'You are a vinyl archivist. Produce a SINGLE JSON object and nothing else. '
      'Do not output markdown, code fences, comments, or extra text. '
      'The JSON object must use keys {"artist":"","composer":"","record_name":"","catalog_number":"","label":"","year":"","location":"","notes":"","genre":"","key_signature":"","composer_code":""}. '
      'If multiple distinct works or performer groups are present, include a REQUIRED "records" array with one object per work using the same keys '
      '(artist=performer, composer=composer). Each item in "records" must be a standalone record (no nesting, no sub-records, no grouped fields). '
      'When multiple works are present, set the top-level fields to empty strings and put ALL works only inside "records". '
      'Treat each record as independent; do not imply relationships between records. '
      'Only use information explicitly present in the OCR text. Do NOT guess, infer, or add details not written in OCR. '
      'If a field is missing in OCR, use an empty string. '
      'For titles/notes, prefer English if present; otherwise use German if present; otherwise pick one other language. '
      'Use only ONE language per record and do not mix languages across fields for the same record. '
      'Keep catalog numbers verbatim, normalize names, capture liner-note highlights in notes, and use empty strings when unsure. '
      'In notes, include a concise, numbered list of works with performers and movements when available (from OCR only). '
      'If you cannot comply, return {}.\n\n'
      'Required JSON shape example (do not copy values; use OCR text only):\n'
      '{"artist":"","composer":"","record_name":"","catalog_number":"","label":"","year":"","location":"","notes":"","genre":"","key_signature":"","composer_code":"","records":[{"artist":"","composer":"","record_name":"","catalog_number":"","label":"","year":"","location":"","notes":"","genre":"","key_signature":"","composer_code":""}]}\n\n'
      'Manual Hints:\n'
      '- Artist: \n'
      '- Composer: \n'
      '- Record Name: \n'
      '- Catalog Number: \n'
      '- Label: \n'
      '- Year: \n'
      '- Location: \n'
      '- Notes: \n\n'
      f'OCR Transcripts:\nOCR #1:\n{ocr_text.strip()}'
  )


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
    return str(data).strip()
  return str(data).strip()


def _parse_loose_json(text: str) -> dict | None:
  cleaned = text.strip()
  candidates = [cleaned]
  if '```' in cleaned:
    fence_match = re.findall(r'```(?:json)?\s*(.*?)```', cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
      candidates.extend(part.strip() for part in fence_match if part.strip())
  brace_match = re.findall(r'\{.*\}', cleaned, flags=re.DOTALL)
  if brace_match:
    candidates.extend(part.strip() for part in brace_match)
  candidates.append(_strip_markdown_fences(cleaned))

  for candidate in candidates:
    try:
      parsed = LLMClient()._parse_json_payload(candidate)
      if parsed:
        return parsed
    except Exception:
      pass
    try:
      value = ast.literal_eval(candidate)
      if isinstance(value, dict):
        return value
    except (ValueError, SyntaxError):
      continue
  return None


def main() -> int:
  parser = argparse.ArgumentParser(
      description='Send a fixed OCR transcript to the local LLM using the same prompt as the API.'
  )
  parser.add_argument(
      'ocr_path',
      type=Path,
      help='Path to a text file containing the OCR transcript.'
  )
  parser.add_argument(
      '--print-prompt',
      action='store_true',
      help='Print the prompt before sending it to the LLM.'
  )
  parser.add_argument(
      '--model',
      help='Override the LLM model name (defaults to LLM_MODEL env).'
  )
  parser.add_argument(
      '--endpoint',
      help='Override the LLM endpoint URL (defaults to LLM_ENDPOINT env).'
  )
  parser.add_argument(
      '--gemini',
      action='store_true',
      help='Send the prompt to Gemini generateContent instead of the local LLM endpoint.'
  )
  parser.add_argument(
      '--debug',
      action='store_true',
      help='Print raw HTTP response details from the LLM endpoint.'
  )
  parser.add_argument(
      '--dump-raw',
      type=Path,
      help='Write the raw HTTP response body to a file.'
  )
  args = parser.parse_args()

  ocr_text = args.ocr_path.read_text(encoding='utf-8')
  prompt = _build_prompt(ocr_text)

  if args.print_prompt:
    print(prompt)
    print('\n---\n')

  client = LLMClient()
  if args.model:
    client.model = args.model
  if args.endpoint:
    client.endpoint = args.endpoint

  if args.gemini:
    api_key = os.getenv('GEMINI_API_KEY', '')
    model = (
        args.model
        or os.getenv('GEMINI_LLM_MODEL', '')
        or os.getenv('VINYL_OCR_GEMINI_MODEL', '')
    )
    if not api_key or not model:
      print('[LLM] GEMINI_API_KEY and GEMINI_LLM_MODEL (or --model) are required.')
      return 1
    endpoint = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{model}:generateContent'
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
            'temperature': 0.0,
            'maxOutputTokens': client.max_tokens
        }
    }
    try:
      response = requests.post(
          endpoint,
          params={'key': api_key},
          json=payload,
          timeout=client.timeout
      )
    except requests.RequestException as exc:
      print(f'[LLM] Gemini request failed: {exc}')
      return 1
    if response.status_code >= 400:
      print(f'[LLM] Gemini error {response.status_code}: {response.text}')
      return 1
    extracted = _extract_gemini_text(response)
    if args.dump_raw:
      args.dump_raw.write_text(response.text, encoding='utf-8')
    if args.debug:
      print(response.text)
      print('\n[LLM] Extracted text:')
      print(extracted)
    parsed = _parse_loose_json(extracted)
    if parsed:
      print(parsed)
      return 0
    print('[LLM] No enrichment response received or parsing failed.')
    return 0
  if args.debug or args.dump_raw:
    payload = {
        'model': client.model,
        'prompt': prompt,
        'temperature': client.temperature,
        'top_p': client.top_p,
        'max_tokens': client.max_tokens,
        'stream': False
    }
    try:
      response = requests.post(client.endpoint, json=payload, timeout=client.timeout)
    except requests.RequestException as exc:
      print(f'[LLM] Request failed: {exc}')
      return 1
    if args.dump_raw:
      args.dump_raw.write_text(response.text, encoding='utf-8')
    if args.debug:
      print(f'[LLM] HTTP {response.status_code}')
      print(response.text)
    extracted = client._extract_text(response)
    if args.debug and extracted:
      print('\n[LLM] Extracted text:')
      print(extracted)
    parsed = client._parse_json_payload(extracted) if extracted else None
    if parsed:
      print(parsed)
      return 0

  result = client.derive_metadata(prompt)
  if not result:
    print('[LLM] No enrichment response received or parsing failed.')
    return 1

  print(result)
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
