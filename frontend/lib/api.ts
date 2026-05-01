import {
  AdminOverview,
  AdminSettings,
  AnimeDetail,
  AnimeFiltersResponse,
  AnimeListResponse,
  CrawlSource,
  StatsResponse,
} from '@/lib/types';

const INTERNAL_API_BASE = process.env.API_BASE_URL || 'http://127.0.0.1:8000';
export const PUBLIC_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || INTERNAL_API_BASE;

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${INTERNAL_API_BASE}${path}`, {
    next: { revalidate: 30 },
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${path}`);
  }

  return response.json() as Promise<T>;
}

export async function getAnimeList(params: URLSearchParams) {
  return apiFetch<AnimeListResponse>(`/api/anime?${params.toString()}`);
}

export async function getAnimeFilters() {
  return apiFetch<AnimeFiltersResponse>('/api/anime/filters?playable_only=true');
}

export async function getAnimeDetail(id: string) {
  return apiFetch<AnimeDetail>(`/api/anime/${id}`);
}

export async function getStats() {
  return apiFetch<StatsResponse>('/api/stats');
}

async function adminFetch<T>(path: string, apiKey: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${PUBLIC_API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      ...(init?.headers || {}),
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    const payload = await response.text();
    throw new Error(payload || `Admin API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function getAdminOverview(apiKey: string) {
  return adminFetch<AdminOverview>('/api/admin/overview', apiKey);
}

export async function getAdminSettings(apiKey: string) {
  return adminFetch<AdminSettings>('/api/admin/settings', apiKey);
}

export async function updateAdminSettings(apiKey: string, payload: Partial<AdminSettings>) {
  return adminFetch<AdminSettings>('/api/admin/settings', apiKey, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function getAdminSources(apiKey: string) {
  return adminFetch<{ data: CrawlSource[] }>('/api/admin/sources', apiKey);
}

export async function createAdminSource(
  apiKey: string,
  payload: {
    name: string;
    domain?: string;
    seed_url?: string;
    homepage_url?: string;
    category_pages?: string[];
    recent_pages?: string[];
    max_depth: number;
    discovery_max_depth?: number;
    enabled: boolean;
    notes?: string;
  },
) {
  return adminFetch<CrawlSource>('/api/admin/sources', apiKey, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateAdminSource(apiKey: string, sourceId: string, payload: Partial<CrawlSource>) {
  return adminFetch<CrawlSource>(`/api/admin/sources/${sourceId}`, apiKey, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function runAdminSource(apiKey: string, sourceId: string) {
  return adminFetch<{ ok: boolean; pid: number; started_at: string }>(`/api/admin/sources/${sourceId}/crawl`, apiKey, {
    method: 'POST',
  });
}

export async function runAdminIncremental(apiKey: string) {
  return adminFetch<{ started: boolean; status?: string; reason?: string; output?: string }>('/api/admin/tasks/incremental/run', apiKey, {
    method: 'POST',
  });
}

export async function runAdminSourceDiscovery(apiKey: string) {
  return adminFetch<{ started: boolean; status?: string; reason?: string; output?: string }>('/api/admin/tasks/source-discovery/run', apiKey, {
    method: 'POST',
  });
}

export function resolvePosterUrl(posterLocal?: string | null, posterRemote?: string | null) {
  if (posterLocal) {
    const normalized = posterLocal.startsWith('/') ? posterLocal : `/${posterLocal}`;
    return `${PUBLIC_API_BASE}${normalized}`;
  }
  return posterRemote || '';
}
