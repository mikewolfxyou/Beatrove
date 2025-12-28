/**
 * VinylService - Fetches vinyl metadata from the auxiliary ingestion API
 */

'use strict';

import { CONFIG, SecurityUtils } from './security-utils.js';

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
    const coverUrls = Array.isArray(record.cover_image_urls) ? record.cover_image_urls : (record.cover_image_url ? [record.cover_image_url] : []);
    const normalizedCoverUrls = coverUrls.map(url => this.normalizeImageUrl(url));
    const coverImageUrl = normalizedCoverUrls[0] || '';
    const display = `${artist} - ${title}`;

    return {
      artist,
      title,
      key: composer,
      bpm: '',
      trackTime: '',
      year,
      absPath: location,
      genre: label,
      recordLabel: label,
      energyLevel: null,
      display,
      filename: display,
      coverImageUrl,
      vinyl: {
        composer,
        catalogNumber: catalog,
        notes,
        ocr: record.raw_ocr_json || {},
        coverImages: normalizedCoverUrls
      }
    };
  }

  normalizeImageUrl(url = '') {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return url;
    }
    if (!this.imageBaseUrl) {
      return url;
    }
    const trimmed = url.startsWith('/') ? url : `/${url}`;
    return `${this.imageBaseUrl}${trimmed}`;
  }
}
