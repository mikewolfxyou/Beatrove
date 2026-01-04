import unittest

from server import ocr_pipeline


class FakeResponse:
  def __init__(self, payload):
    self._payload = payload

  def json(self):
    if isinstance(self._payload, Exception):
      raise self._payload
    return self._payload


class OcrPipelineTests(unittest.TestCase):

  def test_normalize_metadata_from_string(self):
    result = ocr_pipeline._normalize_metadata('Side A\nTrack 1')
    self.assertEqual(result['raw_text'], 'Side A\nTrack 1')
    self.assertTrue(all(value == '' for key, value in result.items() if key != 'raw_text'))

  def test_normalize_metadata_from_dict_flattens_to_text(self):
    payload = {
        'artist': 'Tamas Vasary',
        'notes': 'Berceuse Des-dur op. 57',
        'details': {'label': 'Deutsche Grammophon', 'year': '1962'}
    }
    result = ocr_pipeline._normalize_metadata(payload)
    text = result['raw_text']
    self.assertIn('artist: Tamas Vasary', text)
    self.assertIn('label: Deutsche Grammophon', text)
    self.assertEqual(result['notes'], '')

  def test_extract_response_payload_prefers_choice_text(self):
    payload = {
        'choices': [
            {
                'message': {
                    'content': [
                        {'type': 'text', 'text': 'Concerto in D Minor'}
                    ]
                }
            }
        ]
    }
    response = FakeResponse(payload)
    self.assertEqual(ocr_pipeline._extract_response_payload(response), 'Concerto in D Minor')

  def test_extract_response_payload_flattens_plain_dict(self):
    payload = {'artist': 'Frederic Chopin', 'record_name': 'Polonaise op. 53'}
    response = FakeResponse(payload)
    text = ocr_pipeline._extract_response_payload(response)
    self.assertIn('artist: Frederic Chopin', text)
    self.assertIn('record_name: Polonaise op. 53', text)


if __name__ == '__main__':
  unittest.main()
