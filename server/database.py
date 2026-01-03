from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'vinyl.db'


@dataclass
class VinylRecord:
  id: str
  artist: str = ''
  composer: str = ''
  record_name: str = ''
  catalog_number: str = ''
  composer_code: str = ''
  label: str = ''
  year: str = ''
  location: str = ''
  notes: str = ''
  genre: str = ''
  key_signature: str = ''
  cover_image_path: str = ''
  raw_ocr_json: str = ''
  created_at: str = ''
  updated_at: str = ''

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)


def _ensure_db_path() -> None:
  DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
  cursor = conn.execute(f'PRAGMA table_info({table})')
  columns = {row[1] for row in cursor.fetchall()}
  if column not in columns:
    conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def init_db() -> None:
  """Initialize the SQLite database with the vinyl records table."""
  _ensure_db_path()
  with sqlite3.connect(DB_PATH) as conn:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
          id TEXT PRIMARY KEY,
          artist TEXT,
          composer TEXT,
          record_name TEXT,
          catalog_number TEXT,
          composer_code TEXT,
          label TEXT,
          year TEXT,
          location TEXT,
          notes TEXT,
          genre TEXT,
          key_signature TEXT,
          cover_image_path TEXT,
          raw_ocr_json TEXT,
          created_at TEXT,
          updated_at TEXT
        )
        """
    )
    _ensure_column(conn, 'records', 'genre', 'TEXT')
    _ensure_column(conn, 'records', 'key_signature', 'TEXT')
    _ensure_column(conn, 'records', 'composer_code', 'TEXT')
    conn.commit()


@contextmanager
def get_connection():
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  try:
    yield conn
  finally:
    conn.close()


def serialize_row(row: sqlite3.Row) -> Dict[str, Any]:
  """Convert a sqlite row into a serializable dict."""
  if row is None:
    return {}
  data = dict(row)
  raw_payload = data.get('raw_ocr_json')
  if raw_payload:
    try:
      data['raw_ocr_json'] = json.loads(raw_payload)
    except json.JSONDecodeError:
      pass
  cover_payload = data.get('cover_image_path')
  cover_paths = []
  if cover_payload:
    try:
      parsed = json.loads(cover_payload)
      if isinstance(parsed, list):
        cover_paths = parsed
      elif isinstance(parsed, str):
        cover_paths = [parsed]
    except json.JSONDecodeError:
      cover_paths = [cover_payload]
  data['cover_image_paths'] = cover_paths
  if cover_paths:
    data['cover_image_path'] = cover_paths[0]
  return data


def insert_record(record: Dict[str, Any]) -> Dict[str, Any]:
  """Insert a new record into the database and return it."""
  timestamps = {
      'created_at': datetime.utcnow().isoformat(),
      'updated_at': datetime.utcnow().isoformat()
  }
  payload = {**record, **timestamps}

  with get_connection() as conn:
    columns = ', '.join(payload.keys())
    placeholders = ', '.join(['?'] * len(payload))
    conn.execute(
        f'INSERT INTO records ({columns}) VALUES ({placeholders})',
        list(payload.values())
    )
    conn.commit()

    cursor = conn.execute('SELECT * FROM records WHERE id = ?', (record['id'],))
    row = cursor.fetchone()

  return serialize_row(row)


def update_record(record_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
  """Update an existing record and return the new value."""
  if not updates:
    return fetch_record(record_id)

  updates = {key: value for key, value in updates.items() if value is not None}
  updates['updated_at'] = datetime.utcnow().isoformat()

  with get_connection() as conn:
    assignments = ', '.join([f'{key} = ?' for key in updates.keys()])
    conn.execute(
        f'UPDATE records SET {assignments} WHERE id = ?',
        [*updates.values(), record_id]
    )
    conn.commit()

    cursor = conn.execute('SELECT * FROM records WHERE id = ?', (record_id,))
    row = cursor.fetchone()

  return serialize_row(row) if row else None


def fetch_record(record_id: str) -> Optional[Dict[str, Any]]:
  with get_connection() as conn:
    cursor = conn.execute('SELECT * FROM records WHERE id = ?', (record_id,))
    row = cursor.fetchone()
  return serialize_row(row) if row else None


def find_existing_record(artist: str, record_name: str, catalog_number: str) -> Optional[Dict[str, Any]]:
  """Find a record matching the provided identifiers."""
  query = """
    SELECT * FROM records
    WHERE
      (LOWER(artist) = LOWER(?) AND LOWER(record_name) = LOWER(?))
      OR (catalog_number IS NOT NULL AND catalog_number != '' AND LOWER(catalog_number) = LOWER(?))
    ORDER BY created_at DESC
    LIMIT 1
  """
  with get_connection() as conn:
    cursor = conn.execute(query, (artist or '', record_name or '', catalog_number or ''))
    row = cursor.fetchone()
  return serialize_row(row) if row else None


def fetch_records(limit: Optional[int] = None) -> List[Dict[str, Any]]:
  query = 'SELECT * FROM records ORDER BY created_at DESC'
  params: Iterable[Any] = []
  if limit:
    query += ' LIMIT ?'
    params = [limit]

  with get_connection() as conn:
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

  return [serialize_row(row) for row in rows]


def delete_record(record_id: str) -> bool:
  with get_connection() as conn:
    cursor = conn.execute('DELETE FROM records WHERE id = ?', (record_id,))
    conn.commit()
    return cursor.rowcount > 0
