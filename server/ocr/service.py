from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .providers import CommandOCRProvider, HTTPOCRProvider, OCRProvider


def extract_metadata(image_path: Path) -> Dict[str, str]:
  """Extract vinyl metadata via registered OCR providers."""
  for provider in _get_providers():
    if not provider.available:
      continue
    payload = provider.extract(image_path)
    if payload:
      return payload
  return {}


def _get_providers() -> List[OCRProvider]:
  return [HTTPOCRProvider(), CommandOCRProvider()]
