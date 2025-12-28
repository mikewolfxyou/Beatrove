from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import (
    fetch_record,
    fetch_records,
    find_existing_record,
    init_db,
    insert_record,
    update_record,
)
from .ocr_pipeline import extract_metadata


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

API_PREFIX = '/api/v1'

app = FastAPI(title='Beatrove Vinyl API', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.mount('/uploads', StaticFiles(directory=UPLOAD_DIR), name='uploads')

# Initialize DB on startup
init_db()


@app.get(f'{API_PREFIX}/records')
def list_records():
  records = [hydrate_record(record) for record in fetch_records()]
  return {'records': records}


@app.get(f'{API_PREFIX}/records/{{record_id}}')
def get_record(record_id: str):
  record = fetch_record(record_id)
  if not record:
    raise HTTPException(status_code=404, detail='Record not found')
  return {'record': hydrate_record(record)}


@app.post(f'{API_PREFIX}/records', status_code=201)
async def create_record(
    covers: List[UploadFile] = File(...),
    artist: Optional[str] = Form(None),
    composer: Optional[str] = Form(None),
    record_name: Optional[str] = Form(None),
    catalog_number: Optional[str] = Form(None),
    label: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
  if not covers:
    raise HTTPException(status_code=400, detail='At least one cover image is required')

  record_id = str(uuid4())
  manual_values = {
      'artist': _clean_text(artist),
      'composer': _clean_text(composer),
      'record_name': _clean_text(record_name),
      'catalog_number': _clean_text(catalog_number),
      'label': _clean_text(label),
      'year': _clean_text(year),
      'location': _clean_text(location),
      'notes': _clean_text(notes)
  }

  saved_paths: List[Path] = []
  ocr_payloads: List[Dict[str, str]] = []

  for upload in covers:
    saved_path = await save_cover_image(record_id, upload)
    saved_paths.append(saved_path)
    payload = extract_metadata(saved_path)
    if payload:
      ocr_payloads.append(payload)

  relative_paths = [str(path.relative_to(BASE_DIR)) for path in saved_paths]

  dedupe_reference = merge_metadata(manual_values, ocr_payloads, None)
  existing = find_existing_record(dedupe_reference['artist'], dedupe_reference['record_name'], dedupe_reference['catalog_number'])
  existing_raw = _ensure_list(existing.get('raw_ocr_json')) if existing else []
  existing_cover_paths = list(existing.get('cover_image_paths') or []) if existing else []

  metadata = merge_metadata(manual_values, ocr_payloads, existing)

  combined_paths = existing_cover_paths + relative_paths
  combined_raw = existing_raw + ocr_payloads

  payload: Dict[str, str] = {
      'artist': metadata['artist'],
      'composer': metadata['composer'],
      'record_name': metadata['record_name'],
      'catalog_number': metadata['catalog_number'],
      'label': metadata['label'],
      'year': metadata['year'],
      'location': metadata['location'],
      'notes': metadata['notes'],
      'cover_image_path': json.dumps(combined_paths, ensure_ascii=False),
      'raw_ocr_json': json.dumps(combined_raw, ensure_ascii=False)
  }

  if existing:
    record = update_record(existing['id'], payload)
    return {'record': hydrate_record(record)}

  payload['id'] = record_id
  record = insert_record(payload)
  return JSONResponse({'record': hydrate_record(record)}, status_code=201)


async def save_cover_image(prefix: str, upload: UploadFile) -> Path:
  suffix = Path(upload.filename or '').suffix.lower() or '.jpg'
  dest_path = UPLOAD_DIR / f'{prefix}_{uuid4().hex}{suffix}'
  content = await upload.read()
  dest_path.write_bytes(content)
  return dest_path


def hydrate_record(record: Dict[str, str]) -> Dict[str, str]:
  cover_paths = record.get('cover_image_paths') or []
  cover_urls = [f"/uploads/{Path(path).name}" for path in cover_paths if path]
  if cover_urls:
    record['cover_image_url'] = cover_urls[0]
  record['cover_image_urls'] = cover_urls
  return record


def merge_metadata(manual: Dict[str, str], ocr_payloads: List[Dict[str, str]], existing: Optional[Dict[str, str]]) -> Dict[str, str]:
  result: Dict[str, str] = {}
  fields = ['artist', 'composer', 'record_name', 'catalog_number', 'label', 'year', 'location', 'notes']
  for field in fields:
    value = manual.get(field)
    if value:
      result[field] = value
      continue
    from_ocr = _first_non_empty(ocr_payloads, field)
    if from_ocr:
      result[field] = from_ocr
      continue
    if existing:
      existing_val = _clean_text(existing.get(field))
      if existing_val:
        result[field] = existing_val
        continue
    result[field] = ''
  return result


def _first_non_empty(payloads: List[Dict[str, str]], field: str) -> str:
  for payload in payloads:
    value = _clean_text(payload.get(field))
    if value:
      return value
  return ''


def _clean_text(value: Optional[str]) -> str:
  if value is None:
    return ''
  return str(value).strip()


def _ensure_list(value: Optional[object]) -> List[Dict[str, str]]:
  if value is None:
    return []
  if isinstance(value, list):
    return value
  return [value]
