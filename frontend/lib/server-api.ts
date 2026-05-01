import 'server-only';

import { AnimeDetail, AnimeFiltersResponse, AnimeListResponse, StatsResponse } from '@/lib/types';

const INTERNAL_API_BASE = process.env.API_BASE_URL || 'http://127.0.0.1:8000';
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || '';

async function serverApiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${INTERNAL_API_BASE}${path}`, {
    headers: INTERNAL_API_KEY ? { 'x-api-key': INTERNAL_API_KEY } : undefined,
    next: { revalidate: 30 },
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${path}`);
  }

  return response.json() as Promise<T>;
}

export async function getAnimeList(params: URLSearchParams) {
  return serverApiFetch<AnimeListResponse>(`/api/anime?${params.toString()}`);
}

export async function getAnimeFilters() {
  return serverApiFetch<AnimeFiltersResponse>('/api/anime/filters?playable_only=true');
}

export async function getAnimeDetail(id: string) {
  return serverApiFetch<AnimeDetail>(`/api/anime/${id}`);
}

export async function getStats() {
  return serverApiFetch<StatsResponse>('/api/stats');
}
