import { resolvePosterUrl, PUBLIC_API_BASE } from './api';

function assertEqual(actual: string, expected: string, label: string) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${expected}, got ${actual}`);
  }
}

const cdnUrl = 'https://cdn.example.com/api/processed/public/file/poster.jpg';
assertEqual(resolvePosterUrl(cdnUrl, 'https://fallback.example.com/remote.jpg'), cdnUrl, 'cdn absolute url');
assertEqual(
  resolvePosterUrl('/https://cdn.example.com/api/processed/public/file/poster.jpg', 'https://fallback.example.com/remote.jpg'),
  cdnUrl,
  'slash-prefixed absolute url',
);
assertEqual(
  resolvePosterUrl('/posters/local.jpg', 'https://fallback.example.com/remote.jpg'),
  `${PUBLIC_API_BASE}/posters/local.jpg`,
  'local poster path',
);
