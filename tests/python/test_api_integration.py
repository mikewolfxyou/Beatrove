import io
import json
import os
import importlib
import tempfile
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings('ignore', category=DeprecationWarning, module=r'fastapi\.routing')
warnings.filterwarnings('ignore', category=DeprecationWarning, module=r'starlette\._utils')
warnings.filterwarnings('ignore', category=ResourceWarning, module=r'anyio\._backends\._asyncio')
warnings.filterwarnings('ignore', category=ResourceWarning, module=r'copyreg')

from fastapi.testclient import TestClient

import server.database as database
import server.app as app_module


class VinylApiIntegrationTests(unittest.TestCase):

  def setUp(self):
    os.environ['LLM_ENDPOINT'] = ''
    os.environ['LLM_PROVIDER'] = ''
    os.environ['GEMINI_API_KEY'] = ''
    os.environ['GEMINI_LLM_MODEL'] = ''
    self.temp_dir = tempfile.TemporaryDirectory()
    database.DB_PATH = Path(self.temp_dir.name) / 'vinyl.db'
    database.init_db()
    self.app_module = importlib.reload(app_module)
    # Prevent external OCR calls during tests
    self.app_module.extract_metadata = lambda _: {'raw_text': 'Test OCR payload'}
    self.fixture_dir = Path(__file__).resolve().parents[1] / 'fixtures'

  def tearDown(self):
    self.temp_dir.cleanup()

  def test_create_and_fetch_record(self):
    files = {
        'covers': ('cover.jpg', io.BytesIO(b'fake image data'), 'image/jpeg')
    }
    data = {
        'artist': 'Integration Artist',
        'record_name': 'Integration Suite',
        'catalog_number': 'INT-001'
    }

    with TestClient(self.app_module.app) as client:
      response = client.post('/api/v1/vinyls', files=files, data=data)
      self.assertEqual(response.status_code, 201)
      payload = response.json()['vinyl']
      self.assertEqual(payload['artist'], 'Integration Artist')
      self.assertEqual(payload['catalog_number'], 'INT-001')
      record_id = payload['id']

      fetch_response = client.get(f'/api/v1/vinyls/{record_id}')
      self.assertEqual(fetch_response.status_code, 200)
      fetched = fetch_response.json()['vinyl']
      self.assertEqual(fetched['artist'], 'Integration Artist')
      self.assertTrue(fetched['cover_image_paths'])
      self.assertEqual(len(fetched.get('records') or []), 1)

      list_response = client.get('/api/v1/vinyls')
      self.assertEqual(list_response.status_code, 200)
      vinyls = list_response.json()['vinyls']
      self.assertEqual(len(vinyls), 1)

  def test_create_vinyl_with_multiple_works(self):
    fixture_path = self.fixture_dir / 'llm_records.json'
    payload = json.loads(fixture_path.read_text(encoding='utf-8'))

    def fake_enrich(metadata, _ocr_payloads):
      metadata['records'] = payload['records']
      return metadata

    self.app_module.metadata_enricher.enrich = fake_enrich

    files = {
        'covers': ('cover.jpg', io.BytesIO(b'fake image data'), 'image/jpeg')
    }
    data = {
        'record_name': 'Multi Work Vinyl'
    }

    with TestClient(self.app_module.app) as client:
      response = client.post('/api/v1/vinyls', files=files, data=data)
      self.assertEqual(response.status_code, 201)
      vinyl = response.json()['vinyl']
      self.assertEqual(len(vinyl.get('records') or []), 3)

      list_response = client.get('/api/v1/vinyls')
      self.assertEqual(list_response.status_code, 200)
      vinyls = list_response.json()['vinyls']
      self.assertEqual(len(vinyls), 1)
      self.assertEqual(len(vinyls[0].get('records') or []), 3)

      search_response = client.get('/api/v1/works/search', params={
          'record_name': 'Quartettsatz c-moll D. 703'
      })
      self.assertEqual(search_response.status_code, 200)
      work = search_response.json()['work']
      self.assertIsNotNone(work)
      self.assertEqual(work['artist'], 'Amadeus-Quartett')


if __name__ == '__main__':
  unittest.main()
