import unittest

from server.metadata import (
    EnrichmentStrategy,
    HeuristicEnrichmentStrategy,
    MetadataEnricher
)


class FakeLLMStrategy(EnrichmentStrategy):

  def __init__(self, payload):
    self.payload = payload
    self.calls = 0

  def apply(self, metadata, _ocr_payloads):
    self.calls += 1
    for key, value in self.payload.items():
      metadata[key] = value


class MetadataEnricherTests(unittest.TestCase):

  def test_enrich_uses_ocr_transcript_for_key_genre_and_code(self):
    enricher = MetadataEnricher(strategies=[HeuristicEnrichmentStrategy()])
    metadata = {
        'artist': '',
        'composer': '',
        'record_name': '',
        'catalog_number': '',
        'label': '',
        'year': '',
        'location': '',
        'notes': '',
        'genre': '',
        'key_signature': '',
        'composer_code': ''
    }
    ocr_payloads = [{
        'raw_text': (
            'Side A\n'
            'Piano Concerto in D minor KV 466\n'
            'Wolfgang Amadeus Mozart\n'
            'Deutsche Grammophon'
        )
    }]

    enriched = enricher.enrich(metadata, ocr_payloads)

    self.assertEqual(enriched['genre'], 'Classical')
    self.assertEqual(enriched['key_signature'], 'D Minor')
    self.assertTrue(enriched['composer_code'].lower().startswith('kv'))

  def test_enrich_prefers_llm_output_for_missing_fields(self):
    payload = {
        'artist': 'LLM Artist',
        'composer': 'LLM Composer',
        'record_name': 'LLM Record',
        'catalog_number': 'LLM-001',
        'label': 'LLM Label',
        'year': '1982',
        'location': 'Berlin',
        'notes': 'LLM summary',
        'genre': 'Experimental',
        'key_signature': 'C Major',
        'composer_code': 'Op. 12'
    }
    fake_strategy = FakeLLMStrategy(payload)
    enricher = MetadataEnricher(strategies=[fake_strategy])

    metadata = {
        'artist': '',
        'composer': '',
        'record_name': '',
        'catalog_number': '',
        'label': '',
        'year': '',
        'location': '',
        'notes': '',
        'genre': '',
        'key_signature': '',
        'composer_code': ''
    }

    enriched = enricher.enrich(metadata, [])

    self.assertEqual(fake_strategy.calls, 1)
    self.assertEqual(enriched['artist'], 'LLM Artist')
    self.assertEqual(enriched['composer'], 'LLM Composer')
    self.assertEqual(enriched['record_name'], 'LLM Record')
    self.assertEqual(enriched['catalog_number'], 'LLM-001')
    self.assertEqual(enriched['label'], 'LLM Label')
    self.assertEqual(enriched['year'], '1982')
    self.assertEqual(enriched['location'], 'Berlin')
    self.assertEqual(enriched['notes'], 'LLM summary')
    self.assertEqual(enriched['genre'], 'Experimental')
    self.assertEqual(enriched['key_signature'], 'C Major')
    self.assertEqual(enriched['composer_code'], 'Op. 12')


if __name__ == '__main__':
  unittest.main()
