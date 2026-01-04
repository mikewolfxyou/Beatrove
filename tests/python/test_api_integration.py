import io
import importlib
import tempfile
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings('ignore', category=DeprecationWarning, module=r'fastapi\.routing')
warnings.filterwarnings('ignore', category=DeprecationWarning, module=r'starlette\._utils')
warnings.filterwarnings('ignore', category=ResourceWarning, module=r'anyio\._backends\._asyncio')

from fastapi.testclient import TestClient

import server.database as database
import server.app as app_module


class VinylApiIntegrationTests(unittest.TestCase):

  def setUp(self):
    self.temp_dir = tempfile.TemporaryDirectory()
    database.DB_PATH = Path(self.temp_dir.name) / 'vinyl.db'
    database.init_db()
    self.app_module = importlib.reload(app_module)
    # Prevent external OCR calls during tests
    self.app_module.extract_metadata = lambda _: {'raw_text': 'Test OCR payload'}

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
      response = client.post('/api/v1/records', files=files, data=data)
      self.assertEqual(response.status_code, 201)
      payload = response.json()['record']
      self.assertEqual(payload['artist'], 'Integration Artist')
      self.assertEqual(payload['catalog_number'], 'INT-001')
      record_id = payload['id']

      fetch_response = client.get(f'/api/v1/records/{record_id}')
      self.assertEqual(fetch_response.status_code, 200)
      fetched = fetch_response.json()['record']
      self.assertEqual(fetched['artist'], 'Integration Artist')
      self.assertTrue(fetched['cover_image_paths'])

      list_response = client.get('/api/v1/records')
      self.assertEqual(list_response.status_code, 200)
      records = list_response.json()['records']
      self.assertEqual(len(records), 1)


if __name__ == '__main__':
  unittest.main()
