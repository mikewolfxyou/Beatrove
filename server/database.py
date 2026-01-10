from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
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
  """Initialize the SQLite database with the vinyl tables."""
  _ensure_db_path()
  with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vinyls (
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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vinyl_works (
          id TEXT PRIMARY KEY,
          vinyl_id TEXT NOT NULL,
          work_index INTEGER,
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
          created_at TEXT,
          updated_at TEXT,
          FOREIGN KEY (vinyl_id) REFERENCES vinyls(id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    _migrate_records_to_vinyls(conn)


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


def serialize_work_row(row: sqlite3.Row) -> Dict[str, Any]:
  if row is None:
    return {}
  return dict(row)


def insert_record(record: Dict[str, Any]) -> Dict[str, Any]:
  """Insert a new record into the database and return it."""
  now = datetime.now(timezone.utc).isoformat()
  timestamps = {
      'created_at': now,
      'updated_at': now
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


def insert_vinyl(vinyl: Dict[str, Any], works: List[Dict[str, Any]]) -> Dict[str, Any]:
  now = datetime.now(timezone.utc).isoformat()
  vinyl_payload = {**vinyl, 'created_at': now, 'updated_at': now}
  work_rows = []
  with get_connection() as conn:
    columns = ', '.join(vinyl_payload.keys())
    placeholders = ', '.join(['?'] * len(vinyl_payload))
    conn.execute(
        f'INSERT INTO vinyls ({columns}) VALUES ({placeholders})',
        list(vinyl_payload.values())
    )

    for index, work in enumerate(works):
      work_payload = {**work, 'vinyl_id': vinyl_payload['id'], 'work_index': index, 'created_at': now, 'updated_at': now}
      work_columns = ', '.join(work_payload.keys())
      work_placeholders = ', '.join(['?'] * len(work_payload))
      conn.execute(
          f'INSERT INTO vinyl_works ({work_columns}) VALUES ({work_placeholders})',
          list(work_payload.values())
      )
      work_rows.append(work_payload)
    conn.commit()

    vinyl_row = conn.execute('SELECT * FROM vinyls WHERE id = ?', (vinyl_payload['id'],)).fetchone()
    work_rows = conn.execute(
        'SELECT * FROM vinyl_works WHERE vinyl_id = ? ORDER BY work_index ASC',
        (vinyl_payload['id'],)
    ).fetchall()

  vinyl_data = serialize_row(vinyl_row)
  vinyl_data['works'] = [serialize_work_row(row) for row in work_rows]
  return vinyl_data


def update_record(record_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
  """Update an existing record and return the new value."""
  if not updates:
    return fetch_record(record_id)

  updates = {key: value for key, value in updates.items() if value is not None}
  updates['updated_at'] = datetime.now(timezone.utc).isoformat()

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


def fetch_vinyl(vinyl_id: str) -> Optional[Dict[str, Any]]:
  with get_connection() as conn:
    vinyl_row = conn.execute('SELECT * FROM vinyls WHERE id = ?', (vinyl_id,)).fetchone()
    if not vinyl_row:
      return None
    work_rows = conn.execute(
        'SELECT * FROM vinyl_works WHERE vinyl_id = ? ORDER BY work_index ASC',
        (vinyl_id,)
    ).fetchall()
  vinyl = serialize_row(vinyl_row)
  vinyl['works'] = [serialize_work_row(row) for row in work_rows]
  return vinyl


def fetch_vinyls(limit: Optional[int] = None) -> List[Dict[str, Any]]:
  query = 'SELECT * FROM vinyls ORDER BY created_at DESC'
  params: Iterable[Any] = []
  if limit:
    query += ' LIMIT ?'
    params = [limit]

  with get_connection() as conn:
    vinyl_rows = conn.execute(query, params).fetchall()
    vinyls = [serialize_row(row) for row in vinyl_rows]
    vinyl_ids = [row['id'] for row in vinyl_rows]
    works_map: Dict[str, List[Dict[str, Any]]] = {vid: [] for vid in vinyl_ids}
    if vinyl_ids:
      placeholders = ', '.join(['?'] * len(vinyl_ids))
      work_rows = conn.execute(
          f'SELECT * FROM vinyl_works WHERE vinyl_id IN ({placeholders}) ORDER BY work_index ASC',
          vinyl_ids
      ).fetchall()
      for row in work_rows:
        work = serialize_work_row(row)
        works_map.setdefault(work['vinyl_id'], []).append(work)

  for vinyl in vinyls:
    vinyl['works'] = works_map.get(vinyl['id'], [])
  return vinyls


def delete_record(record_id: str) -> bool:
  with get_connection() as conn:
    cursor = conn.execute('DELETE FROM records WHERE id = ?', (record_id,))
    conn.commit()
    return cursor.rowcount > 0


def delete_vinyl(vinyl_id: str) -> bool:
  with get_connection() as conn:
    conn.execute('DELETE FROM vinyl_works WHERE vinyl_id = ?', (vinyl_id,))
    cursor = conn.execute('DELETE FROM vinyls WHERE id = ?', (vinyl_id,))
    conn.commit()
    return cursor.rowcount > 0


def find_existing_work(artist: str, record_name: str, catalog_number: str) -> Optional[Dict[str, Any]]:
  conditions = []
  params: List[Any] = []

  if catalog_number:
    conditions.append('(catalog_number IS NOT NULL AND catalog_number != "" AND LOWER(catalog_number) = LOWER(?))')
    params.append(catalog_number)

  if artist and record_name:
    conditions.append('(LOWER(artist) = LOWER(?) AND LOWER(record_name) = LOWER(?))')
    params.extend([artist, record_name])
  elif record_name:
    conditions.append('(LOWER(record_name) = LOWER(?))')
    params.append(record_name)
  elif artist:
    conditions.append('(LOWER(artist) = LOWER(?))')
    params.append(artist)

  if not conditions:
    return None

  query = f"""
    SELECT * FROM vinyl_works
    WHERE {' OR '.join(conditions)}
    ORDER BY created_at DESC
    LIMIT 1
  """
  with get_connection() as conn:
    row = conn.execute(query, params).fetchone()
  return serialize_work_row(row) if row else None


def _migrate_records_to_vinyls(conn: sqlite3.Connection) -> None:
  vinyl_count = conn.execute('SELECT COUNT(1) FROM vinyls').fetchone()[0]
  if vinyl_count:
    return
  has_records = conn.execute(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='records'"
  ).fetchone()
  if not has_records:
    return
  rows = conn.execute('SELECT * FROM records').fetchall()
  if not rows:
    return
  now = datetime.now(timezone.utc).isoformat()
  for row in rows:
    record = dict(row)
    conn.execute(
        """
        INSERT INTO vinyls (
          id, artist, composer, record_name, catalog_number, composer_code, label, year,
          location, notes, genre, key_signature, cover_image_path, raw_ocr_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.get('id'),
            record.get('artist'),
            record.get('composer'),
            record.get('record_name'),
            record.get('catalog_number'),
            record.get('composer_code'),
            record.get('label'),
            record.get('year'),
            record.get('location'),
            record.get('notes'),
            record.get('genre'),
            record.get('key_signature'),
            record.get('cover_image_path'),
            record.get('raw_ocr_json'),
            record.get('created_at') or now,
            record.get('updated_at') or now
        )
    )
    conn.execute(
        """
        INSERT INTO vinyl_works (
          id, vinyl_id, work_index, artist, composer, record_name, catalog_number, composer_code, label, year,
          location, notes, genre, key_signature, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.get('id'),
            record.get('id'),
            0,
            record.get('artist'),
            record.get('composer'),
            record.get('record_name'),
            record.get('catalog_number'),
            record.get('composer_code'),
            record.get('label'),
            record.get('year'),
            record.get('location'),
            record.get('notes'),
            record.get('genre'),
            record.get('key_signature'),
            record.get('created_at') or now,
            record.get('updated_at') or now
        )
    )
