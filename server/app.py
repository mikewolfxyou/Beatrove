from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import (
    delete_record as delete_record_from_db,
    delete_vinyl,
    fetch_record,
    fetch_records,
    fetch_vinyl,
    fetch_vinyls,
    find_existing_work,
    init_db,
    insert_record,
    insert_vinyl,
)
from .metadata import MetadataEnricher
from .ocr import extract_metadata


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
metadata_enricher = MetadataEnricher()


@app.get(f'{API_PREFIX}/records')
def list_records():
  records = [hydrate_record(record) for record in fetch_records()]
  return {'records': records}


@app.get(f'{API_PREFIX}/vinyls')
def list_vinyls():
  vinyls = [hydrate_vinyl(vinyl) for vinyl in fetch_vinyls()]
  return {'vinyls': vinyls}


@app.get(f'{API_PREFIX}/records/{{record_id}}')
def get_record(record_id: str):
  record = fetch_record(record_id)
  if not record:
    raise HTTPException(status_code=404, detail='Record not found')
  return {'record': hydrate_record(record)}


@app.get(f'{API_PREFIX}/vinyls/{{vinyl_id}}')
def get_vinyl(vinyl_id: str):
  vinyl = fetch_vinyl(vinyl_id)
  if not vinyl:
    raise HTTPException(status_code=404, detail='Vinyl not found')
  return {'vinyl': hydrate_vinyl(vinyl)}


@app.get(f'{API_PREFIX}/works/search')
def find_work(
    artist: Optional[str] = None,
    record_name: Optional[str] = None,
    catalog_number: Optional[str] = None
):
  work = find_existing_work(_clean_text(artist), _clean_text(record_name), _clean_text(catalog_number))
  if not work:
    return {'work': None}
  return {'work': work}


@app.post(f'{API_PREFIX}/records', status_code=201)
async def create_record(
    covers: List[UploadFile] = File(...),
    artist: Optional[str] = Form(None),
    composer: Optional[str] = Form(None),
    record_name: Optional[str] = Form(None),
    catalog_number: Optional[str] = Form(None),
    composer_code: Optional[str] = Form(None),
    label: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    genre: Optional[str] = Form(None),
    key_signature: Optional[str] = Form(None)
):
  if not covers:
    raise HTTPException(status_code=400, detail='At least one cover image is required')

  record_id = str(uuid4())
  manual_values = {
      'artist': _clean_text(artist),
      'composer': _clean_text(composer),
      'record_name': _clean_text(record_name),
      'catalog_number': _clean_text(catalog_number),
      'composer_code': _clean_text(composer_code),
      'label': _clean_text(label),
      'year': _clean_text(year),
      'location': _clean_text(location),
      'notes': _clean_text(notes),
      'genre': _clean_text(genre),
      'key_signature': _clean_text(key_signature)
  }

  saved_images: List[str] = []
  ocr_payloads: List[Dict[str, str]] = []

  for upload in covers:
    saved_path, data_url = await save_cover_image(record_id, upload)
    if data_url:
      saved_images.append(data_url)
    try:
      payload = extract_metadata(saved_path) if saved_path else {}
      if payload:
        ocr_payloads.append(payload)
    finally:
      if saved_path:
        try:
          saved_path.unlink()
        except FileNotFoundError:
          pass

  metadata = merge_metadata(manual_values, ocr_payloads, None)
  combined_paths = saved_images
  combined_raw = ocr_payloads

  payload: Dict[str, str] = {
      'artist': metadata['artist'],
      'composer': metadata['composer'],
      'record_name': metadata['record_name'],
      'catalog_number': metadata['catalog_number'],
      'composer_code': metadata['composer_code'],
      'label': metadata['label'],
      'year': metadata['year'],
      'location': metadata['location'],
      'notes': metadata['notes'],
      'genre': metadata['genre'],
      'key_signature': metadata['key_signature'],
      'cover_image_path': json.dumps(combined_paths, ensure_ascii=False),
      'raw_ocr_json': json.dumps(combined_raw, ensure_ascii=False)
  }

  payload['id'] = record_id
  record = insert_record(payload)
  return JSONResponse({'record': hydrate_record(record)}, status_code=201)


@app.post(f'{API_PREFIX}/vinyls', status_code=201)
async def create_vinyl(
    covers: List[UploadFile] = File(...),
    artist: Optional[str] = Form(None),
    composer: Optional[str] = Form(None),
    record_name: Optional[str] = Form(None),
    catalog_number: Optional[str] = Form(None),
    composer_code: Optional[str] = Form(None),
    label: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    genre: Optional[str] = Form(None),
    key_signature: Optional[str] = Form(None)
):
  if not covers:
    raise HTTPException(status_code=400, detail='At least one cover image is required')

  vinyl_id = str(uuid4())
  manual_values = {
      'artist': _clean_text(artist),
      'composer': _clean_text(composer),
      'record_name': _clean_text(record_name),
      'catalog_number': _clean_text(catalog_number),
      'composer_code': _clean_text(composer_code),
      'label': _clean_text(label),
      'year': _clean_text(year),
      'location': _clean_text(location),
      'notes': _clean_text(notes),
      'genre': _clean_text(genre),
      'key_signature': _clean_text(key_signature)
  }

  saved_images: List[str] = []
  ocr_payloads: List[Dict[str, str]] = []

  for upload in covers:
    saved_path, data_url = await save_cover_image(vinyl_id, upload)
    if data_url:
      saved_images.append(data_url)
    try:
      payload = extract_metadata(saved_path) if saved_path else {}
      if payload:
        ocr_payloads.append(payload)
    finally:
      if saved_path:
        try:
          saved_path.unlink()
        except FileNotFoundError:
          pass

  metadata = merge_metadata(manual_values, ocr_payloads, None)
  works = _build_works(metadata, manual_values)

  vinyl_payload: Dict[str, str] = {
      'id': vinyl_id,
      'artist': metadata.get('artist', ''),
      'composer': metadata.get('composer', ''),
      'record_name': metadata.get('record_name', ''),
      'catalog_number': metadata.get('catalog_number', ''),
      'composer_code': metadata.get('composer_code', ''),
      'label': metadata.get('label', ''),
      'year': metadata.get('year', ''),
      'location': metadata.get('location', ''),
      'notes': metadata.get('notes', ''),
      'genre': metadata.get('genre', ''),
      'key_signature': metadata.get('key_signature', ''),
      'cover_image_path': json.dumps(saved_images, ensure_ascii=False),
      'raw_ocr_json': json.dumps(ocr_payloads, ensure_ascii=False)
  }

  vinyl = insert_vinyl(vinyl_payload, works)
  return JSONResponse({'vinyl': hydrate_vinyl(vinyl)}, status_code=201)


@app.delete(f'{API_PREFIX}/records/{{record_id}}', status_code=204)
async def delete_record(record_id: str):
  existing = fetch_record(record_id)
  if not existing:
    raise HTTPException(status_code=404, detail='Record not found')
  delete_record_from_db(record_id)
  return Response(status_code=204)


@app.delete(f'{API_PREFIX}/vinyls/{{vinyl_id}}', status_code=204)
async def delete_vinyl_record(vinyl_id: str):
  existing = fetch_vinyl(vinyl_id)
  if not existing:
    raise HTTPException(status_code=404, detail='Vinyl not found')
  delete_vinyl(vinyl_id)
  return Response(status_code=204)


async def save_cover_image(prefix: str, upload: UploadFile) -> Tuple[Optional[Path], str]:
  filename = upload.filename or ''
  suffix = Path(filename).suffix.lower() or '.jpg'
  content = await upload.read()
  dest_path: Optional[Path] = None
  if content:
    dest_path = UPLOAD_DIR / f'{prefix}_{uuid4().hex}{suffix}'
    dest_path.write_bytes(content)
  mime_type = mimetypes.guess_type(filename)[0] or 'image/jpeg'
  encoded = base64.b64encode(content or b'').decode('ascii') if content else ''
  data_url = f'data:{mime_type};base64,{encoded}' if encoded else ''
  return dest_path, data_url


def hydrate_record(record: Dict[str, str]) -> Dict[str, str]:
  cover_paths = record.get('cover_image_paths') or []
  cover_urls = []
  for path in cover_paths:
    if not path:
      continue
    if isinstance(path, str) and path.startswith('data:'):
      cover_urls.append(path)
    else:
      cover_urls.append(f"/uploads/{Path(path).name}")
  if cover_urls:
    record['cover_image_url'] = cover_urls[0]
  record['cover_image_urls'] = cover_urls
  return record


def hydrate_vinyl(vinyl: Dict[str, str]) -> Dict[str, str]:
  cover_paths = vinyl.get('cover_image_paths') or []
  cover_urls = []
  for path in cover_paths:
    if not path:
      continue
    if isinstance(path, str) and path.startswith('data:'):
      cover_urls.append(path)
    else:
      cover_urls.append(f"/uploads/{Path(path).name}")
  if cover_urls:
    vinyl['cover_image_url'] = cover_urls[0]
  vinyl['cover_image_urls'] = cover_urls
  vinyl['records'] = vinyl.get('works', [])
  return vinyl


def merge_metadata(manual: Dict[str, str], ocr_payloads: List[Dict[str, str]], existing: Optional[Dict[str, str]]) -> Dict[str, str]:
  result: Dict[str, str] = {}
  fields = ['artist', 'composer', 'record_name', 'catalog_number', 'composer_code', 'label', 'year', 'location', 'notes', 'genre', 'key_signature']
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
  return metadata_enricher.enrich(result, ocr_payloads)


def _build_works(metadata: Dict[str, str], manual: Dict[str, str]) -> List[Dict[str, str]]:
  fields = [
      'artist',
      'composer',
      'record_name',
      'catalog_number',
      'composer_code',
      'label',
      'year',
      'location',
      'notes',
      'genre',
      'key_signature'
  ]
  works = []
  records = metadata.get('records')
  if isinstance(records, list) and records:
    for record in records:
      if not isinstance(record, dict):
        continue
      works.append({field: _clean_text(record.get(field)) for field in fields})
  if not works:
    works.append({field: _clean_text(metadata.get(field) or manual.get(field)) for field in fields})
  return works


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
