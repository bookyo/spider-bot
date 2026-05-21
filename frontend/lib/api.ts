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

function isAbsoluteUrl(value: string) {
  return /^[a-z][a-z\d+\-.]*:\/\//i.test(value) || value.startsWith('//');
}

function normalizePosterValue(value?: string | null) {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return '';
  }
  if (isAbsoluteUrl(normalized)) {
    return normalized;
  }
  if (/^\/https?:\/\//i.test(normalized)) {
    return normalized.slice(1);
  }
  return normalized;
}

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
    search_url_template?: string;
    search_title_limit?: number;
    search_pagination_max_pages?: number;
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

export async function deleteAdminSource(apiKey: string, sourceId: string) {
  return adminFetch<{ ok: boolean; deleted_id: string }>(`/api/admin/sources/${sourceId}`, apiKey, {
    method: 'DELETE',
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

export async function runAdminDoubanBackfill(apiKey: string) {
  return adminFetch<{ started: boolean; status?: string; reason?: string; output?: string; matched?: number; updated?: number; failed?: number }>('/api/admin/tasks/douban-backfill/run', apiKey, {
    method: 'POST',
  });
}

// --- 采集源管理 API ---

import {
  CollectSource,
  CollectTask,
  CollectTimingTask,
  CollectRangeOption,
  CollectTypeBinding,
} from '@/lib/types';

export async function getCollectSources(apiKey: string) {
  return adminFetch<{ data: CollectSource[] }>('/api/admin/collect/sources', apiKey);
}

export async function createCollectSource(
  apiKey: string,
  payload: {
    name: string;
    url: string;
    type: 'json' | 'xml';
    appid?: string;
    appkey?: string;
    bind?: boolean;
    status?: boolean;
  },
) {
  return adminFetch<CollectSource>('/api/admin/collect/sources', apiKey, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateCollectSource(
  apiKey: string,
  sourceId: string,
  payload: Partial<CollectSource>,
) {
  return adminFetch<CollectSource>(`/api/admin/collect/sources/${sourceId}`, apiKey, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteCollectSource(apiKey: string, sourceId: string) {
  return adminFetch<{ ok: boolean }>(`/api/admin/collect/sources/${sourceId}`, apiKey, {
    method: 'DELETE',
  });
}

export async function testCollectSource(apiKey: string, sourceId: string) {
  return adminFetch<{ ok: boolean; message: string; preview?: string }>(
    `/api/admin/collect/sources/${sourceId}/test`,
    apiKey,
    { method: 'POST' },
  );
}

export async function runCollectSource(
  apiKey: string,
  sourceId: string,
  range: string = 'today',
) {
  return adminFetch<{
    ok: boolean;
    message: string;
    task_id: string;
    task: CollectTask;
  }>(`/api/admin/collect/sources/${sourceId}/run`, apiKey, {
    method: 'POST',
    body: JSON.stringify({ range }),
  });
}

export async function getCollectTasks(apiKey: string, sourceId?: string) {
  const params = sourceId ? `?source_id=${sourceId}` : '';
  return adminFetch<{ data: CollectTask[] }>(`/api/admin/collect/tasks${params}`, apiKey);
}

export async function getCollectTask(apiKey: string, taskId: string) {
  return adminFetch<{ data: CollectTask }>(`/api/admin/collect/tasks/${taskId}`, apiKey);
}

export async function getCollectRanges(apiKey: string) {
  return adminFetch<{ options: CollectRangeOption[] }>('/api/admin/collect/ranges', apiKey);
}

export async function getCollectTimingTasks(apiKey: string) {
  return adminFetch<{ data: CollectTimingTask[] }>('/api/admin/collect/timing', apiKey);
}

export async function updateCollectTimingTask(
  apiKey: string,
  taskId: number,
  payload: Partial<CollectTimingTask>,
) {
  return adminFetch<{ ok: boolean; data: CollectTimingTask }>(`/api/admin/collect/timing/${taskId}`, apiKey, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function runCollectTimingTask(apiKey: string, taskId: number) {
  return adminFetch<{
    ok: boolean;
    message: string;
    data: { queued: number; range: string };
  }>(`/api/admin/collect/timing/${taskId}/run`, apiKey, {
    method: 'POST',
  });
}

export async function getCollectBindings(apiKey: string, sourceId: string) {
  return adminFetch<{
    source: CollectSource;
    bindings: CollectTypeBinding[];
    local_types: Array<{ name: string; count: number }>;
    remote_type_error: string;
  }>(`/api/admin/collect/sources/${sourceId}/bindings`, apiKey);
}

export async function saveCollectBindings(
  apiKey: string,
  sourceId: string,
  bindings: Array<{ sourceTypeId: string; sourceTypeName: string; localType: string }>,
) {
  return adminFetch<{ ok: boolean }>(
    `/api/admin/collect/sources/${sourceId}/bindings`,
    apiKey,
    {
      method: 'POST',
      body: JSON.stringify({ bindings }),
    },
  );
}

function appendWebp(url: string): string {
  if (!url) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}format=webp`;
}

export function resolvePosterUrl(posterLocal?: string | null, posterRemote?: string | null) {
  const normalizedLocal = normalizePosterValue(posterLocal);
  if (normalizedLocal) {
    if (isAbsoluteUrl(normalizedLocal)) {
      return appendWebp(normalizedLocal);
    }
    const normalized = normalizedLocal.startsWith('/') ? normalizedLocal : `/${normalizedLocal}`;
    return `${PUBLIC_API_BASE}${normalized}?format=webp`;
  }
  const remote = normalizePosterValue(posterRemote);
  return remote ? appendWebp(remote) : remote;
}
