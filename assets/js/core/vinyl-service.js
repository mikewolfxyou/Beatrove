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

    const response = await fetch(`${this.apiBaseUrl}/vinyls`, {
      headers: { 'Accept': 'application/json' }
    });

    if (!response.ok) {
      throw new Error(`Vinyl API error: ${response.status}`);
    }

    const payload = await response.json();
    const vinyls = Array.isArray(payload.vinyls) ? payload.vinyls : [];

    const tracks = [];
    const grouped = {};
    const seen = new Set();

    vinyls.forEach(vinyl => {
      const track = this.recordToTrack(vinyl);
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

  recordToTrack(vinyl) {
    const works = Array.isArray(vinyl.records) ? vinyl.records : (Array.isArray(vinyl.works) ? vinyl.works : []);
    const primary = works[0] || vinyl;
    const artist = SecurityUtils.sanitizeText(primary.artist || primary.composer || 'Unknown Artist');
    const title = SecurityUtils.sanitizeText(primary.record_name || primary.catalog_number || 'Untitled Record');
    const composer = SecurityUtils.sanitizeText(primary.composer || '');
    const year = SecurityUtils.sanitizeText(primary.year || '');
    const label = SecurityUtils.sanitizeText(primary.label || vinyl.label || 'Vinyl');
    const location = SecurityUtils.sanitizeText(primary.location || '');
    const catalog = SecurityUtils.sanitizeText(primary.catalog_number || '');
    const notes = SecurityUtils.sanitizeText(primary.notes || '');
    const keySignature = SecurityUtils.sanitizeText(primary.key_signature || '');
    const genre = SecurityUtils.sanitizeText(primary.genre || '');
    const recordId = SecurityUtils.sanitizeText(vinyl.id || '');
    const composerCode = SecurityUtils.sanitizeText(primary.composer_code || '');
    const coverUrls = Array.isArray(vinyl.cover_image_urls) ? vinyl.cover_image_urls : (vinyl.cover_image_url ? [vinyl.cover_image_url] : []);
    const normalizedCoverUrls = coverUrls.map(url => this.normalizeImageUrl(url));
    const coverImageUrl = normalizedCoverUrls[0] || '';
    const display = `${artist} - ${title}`;
    const resolvedKey = keySignature || this.extractKeyFromRecord(primary);
    const resolvedGenre = genre || this.deriveGenre(primary);

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
        ocr: vinyl.raw_ocr_json || {},
        coverImages: normalizedCoverUrls,
        keySignature: resolvedKey,
        composerCode,
        recordId,
        works
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
