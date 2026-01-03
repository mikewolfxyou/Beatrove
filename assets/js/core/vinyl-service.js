/**
 * VinylService - Fetches vinyl metadata from the auxiliary ingestion API
 */

'use strict';

import { CONFIG, SecurityUtils } from './security-utils.js';

const KEY_SIGNATURE_PATTERNS = [
  /([A-G](?:#|♯|b|♭)?)[-\s]*(Dur|Moll)/i,
  /([A-G](?:#|♯|b|♭)?)\s*(Major|Minor)/i,
  /in\s+([A-G](?:#|♯|b|♭)?)\s+(major|minor)/i
];

const CLASSICAL_KEYWORDS = [
  'concerto',
  'konzert',
  'symphony',
  'sinfonie',
  'sonata',
  'suite',
  'requiem',
  'prelude',
  'oratorio',
  'op.',
  'opus',
  'kv ',
  'kv.',
  'k ',
  'k.'
];

const CLASSICAL_LABEL_HINTS = [
  'deutsche grammophon',
  'harmonia mundi',
  'sony classical',
  'emi classics',
  'philips',
  'decca',
  'telarc',
  'archiv',
  'ecm new series',
  'naxos',
  'dg '
];

const CLASSICAL_COMPOSERS = new Set([
  'mozart',
  'beethoven',
  'bach',
  'brahms',
  'schubert',
  'schumann',
  'chopin',
  'liszt',
  'haydn',
  'tchaikovsky',
  'vivaldi',
  'handel',
  'debussy',
  'ravel',
  'mendelssohn',
  'strauss',
  'mahler',
  'wagner',
  'prokofiev',
  'stravinsky',
  'saint-saens',
  'satie',
  'dvorak',
  'berlioz',
  'rachmaninoff'
]);

export class VinylService {
  constructor(options = {}) {
    this.apiBaseUrl = options.apiBaseUrl || CONFIG?.VINYL_MODE?.API_BASE_URL || '';
    this.imageBaseUrl = options.imageBaseUrl || CONFIG?.VINYL_MODE?.IMAGE_BASE_URL || '';
    this.enabled = Boolean(options.enabled ?? CONFIG?.VINYL_MODE?.ENABLED);
  }

  isEnabled() {
    return this.enabled && Boolean(this.apiBaseUrl);
  }

  async fetchTrackState() {
    if (!this.isEnabled()) {
      return null;
    }

    const response = await fetch(`${this.apiBaseUrl}/records`, {
      headers: { 'Accept': 'application/json' }
    });

    if (!response.ok) {
      throw new Error(`Vinyl API error: ${response.status}`);
    }

    const payload = await response.json();
    const records = Array.isArray(payload.records) ? payload.records : [];

    const tracks = [];
    const grouped = {};
    const seen = new Set();

    records.forEach(record => {
      const track = this.recordToTrack(record);
      const key = track.display.toLowerCase();
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      tracks.push(track);
      if (!grouped[track.artist]) {
        grouped[track.artist] = [];
      }
      grouped[track.artist].push(track);
    });

    return {
      grouped,
      totalTracks: tracks.length,
      duplicateTracks: [],
      tracksForUI: tracks,
      energyLevels: {}
    };
  }

  recordToTrack(record) {
    const artist = SecurityUtils.sanitizeText(record.artist || record.composer || 'Unknown Artist');
    const title = SecurityUtils.sanitizeText(record.record_name || record.catalog_number || 'Untitled Record');
    const composer = SecurityUtils.sanitizeText(record.composer || '');
    const year = SecurityUtils.sanitizeText(record.year || '');
    const label = SecurityUtils.sanitizeText(record.label || 'Vinyl');
    const location = SecurityUtils.sanitizeText(record.location || '');
    const catalog = SecurityUtils.sanitizeText(record.catalog_number || '');
    const notes = SecurityUtils.sanitizeText(record.notes || '');
    const keySignature = SecurityUtils.sanitizeText(record.key_signature || '');
    const genre = SecurityUtils.sanitizeText(record.genre || '');
    const recordId = SecurityUtils.sanitizeText(record.id || '');
    const composerCode = SecurityUtils.sanitizeText(record.composer_code || '');
    const coverUrls = Array.isArray(record.cover_image_urls) ? record.cover_image_urls : (record.cover_image_url ? [record.cover_image_url] : []);
    const normalizedCoverUrls = coverUrls.map(url => this.normalizeImageUrl(url));
    const coverImageUrl = normalizedCoverUrls[0] || '';
    const display = `${artist} - ${title}`;
    const resolvedKey = keySignature || this.extractKeyFromRecord(record);
    const resolvedGenre = genre || this.deriveGenre(record);

    return {
      artist,
      title,
      composer,
      composerCode,
      key: resolvedKey || composer,
      bpm: '',
      trackTime: '',
      year,
      absPath: location,
      genre: resolvedGenre,
      recordLabel: label,
      energyLevel: null,
      display,
      filename: display,
      coverImageUrl,
      recordId,
      vinyl: {
        composer,
        catalogNumber: catalog,
        notes,
        ocr: record.raw_ocr_json || {},
        coverImages: normalizedCoverUrls,
        keySignature: resolvedKey,
        composerCode,
        recordId
      }
    };
  }

  normalizeImageUrl(url = '') {
    if (!url) return '';
    if (url.startsWith('data:')) {
      return url;
    }
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return url;
    }
    if (!this.imageBaseUrl) {
      return url;
    }
    const trimmed = url.startsWith('/') ? url : `/${url}`;
    return `${this.imageBaseUrl}${trimmed}`;
  }

  extractKeyFromRecord(record) {
    const ocrSnippets = [];
    if (Array.isArray(record.raw_ocr_json)) {
      record.raw_ocr_json.forEach(payload => {
        if (payload && typeof payload === 'object') {
          if (payload.record_name) ocrSnippets.push(payload.record_name);
          if (payload.notes) ocrSnippets.push(payload.notes);
        }
      });
    }

    const sources = [
      record.record_name,
      record.notes,
      record.key_signature,
      ocrSnippets.join(' ')
    ].filter(Boolean);

    const haystack = sources.join(' ').trim();
    if (!haystack) {
      return '';
    }

    for (const pattern of KEY_SIGNATURE_PATTERNS) {
      const match = haystack.match(pattern);
      if (match) {
        return this.normalizeKeyFragment(match).trim();
      }
    }
    return '';
  }

  normalizeKeyFragment(match) {
    if (!match) {
      return '';
    }
    const noteRaw = match[1] || '';
    const suffixRaw = match[2] || '';
    const note = noteRaw.replace('♯', '#').replace('♭', 'b').toUpperCase();
    const suffix = (suffixRaw || '').toLowerCase();
    if (!note) {
      return '';
    }
    if (!suffix) {
      return note;
    }
    if (suffix.includes('dur') || suffix.includes('major')) {
      return `${note} Major`;
    }
    if (suffix.includes('moll') || suffix.includes('minor')) {
      return `${note} Minor`;
    }
    return `${note} ${suffixRaw.trim()}`;
  }

  deriveGenre(record) {
    const explicitGenre = SecurityUtils.sanitizeText(record.genre || '');
    if (explicitGenre) {
      return explicitGenre;
    }

    const label = (record.label || '').toLowerCase();
    if (CLASSICAL_LABEL_HINTS.some(hint => label.includes(hint))) {
      return 'Classical';
    }

    const composer = (record.composer || '').toLowerCase();
    if (CLASSICAL_COMPOSERS.has(composer)) {
      return 'Classical';
    }

    const recordName = (record.record_name || '').toLowerCase();
    if (CLASSICAL_KEYWORDS.some(term => recordName.includes(term))) {
      return 'Classical';
    }

    const notes = (record.notes || '').toLowerCase();
    if (CLASSICAL_KEYWORDS.some(term => notes.includes(term))) {
      return 'Classical';
    }

    return '';
  }
}
