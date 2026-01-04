from __future__ import annotations

from typing import Dict, List, Optional

from ..llm_client import LLMClient
from .strategies import (
    EnrichmentStrategy,
    HeuristicEnrichmentStrategy,
    LLMEnrichmentStrategy
)


class MetadataEnricher:
  """Augment vinyl metadata using a staged pipeline."""

  def __init__(self, strategies: Optional[List[EnrichmentStrategy]] = None):
    if strategies is not None:
      self.strategies = strategies
    else:
      self.strategies = [
          LLMEnrichmentStrategy(LLMClient()),
          HeuristicEnrichmentStrategy()
      ]

  def enrich(self, metadata: Dict[str, str], ocr_payloads: List[Dict[str, str]]) -> Dict[str, str]:
    metadata.setdefault('key_signature', '')
    metadata.setdefault('genre', '')
    metadata.setdefault('composer_code', '')

    for strategy in self.strategies:
      strategy.apply(metadata, ocr_payloads)
    return metadata
