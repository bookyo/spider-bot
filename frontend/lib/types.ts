export interface Episode {
  episode: string | null;
  url: string;
}

export interface PlaySource {
  source_name?: string | null;
  provider_id?: string | null;
  source_id?: string | null;
  episodes: Episode[];
  quality?: string | null;
  raw_url?: string | null;
  episode_count?: number | null;
  latest_episode?: string | null;
  new_episode_count?: number | null;
}

export interface AnimeListItem {
  _id: string;
  title?: string | null;
  original_title?: string | null;
  aliases: string[];
  year?: number | null;
  director?: string | null;
  poster_url?: string | null;
  poster_local?: string | null;
  douban_rating?: number | null;
  imdb_rating?: number | null;
  genres: string[];
  source_domain?: string | null;
  site_type?: string | null;
  quality_score?: number | null;
  latest_episode?: string | null;
  total_episode_count?: number | null;
  incremental_found?: boolean | null;
  new_episode_count?: number | null;
  last_incremental_check?: string | null;
  incremental_priority?: number | null;
  play_source_count: number;
  discovered_at?: string | null;
}

export interface AnimeDetail extends AnimeListItem {
  voice_actors: string[];
  synopsis?: string | null;
  source_urls: string[];
  extractor_name?: string | null;
  extractor_confidence?: number | null;
  play_sources: PlaySource[];
  updated_at?: string | null;
  douban_rating?: number | null;
  imdb_rating?: number | null;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface AnimeListResponse {
  data: AnimeListItem[];
  meta: PaginationMeta;
}

export interface AnimeFiltersResponse {
  years: number[];
  genres: string[];
}

export interface StatsResponse {
  total_anime: number;
  total_domains: number;
  anime_sites: number;
  pending_domains: number;
  total_play_sources: number;
  year_distribution: Record<string, number>;
  top_genres: Array<{ genre: string; count: number }>;
  healthy_domains: number;
  failed_domains: number;
  avg_anime_quality: number;
  quality_distribution: Record<string, number>;
}

export interface AdminSettings {
  _id: string;
  auto_incremental_enabled: boolean;
  incremental_interval_minutes: number;
  incremental_limit: number;
  incremental_min_hours: number;
  auto_discover_enabled: boolean;
  auto_source_discovery_enabled: boolean;
  source_discovery_interval_minutes: number;
  crawler_proxy_url?: string | null;
  douban_backfill_enabled?: boolean;
  douban_backfill_interval_minutes?: number;
  douban_backfill_limit?: number;
  douban_search_url?: string | null;
  douban_backfill_timeout_seconds?: number;
  last_incremental_started_at?: string | null;
  last_incremental_finished_at?: string | null;
  last_incremental_status?: string | null;
  last_incremental_output?: string | null;
  last_source_discovery_started_at?: string | null;
  last_source_discovery_finished_at?: string | null;
  last_source_discovery_status?: string | null;
  last_source_discovery_output?: string | null;
  last_douban_backfill_started_at?: string | null;
  last_douban_backfill_finished_at?: string | null;
  last_douban_backfill_status?: string | null;
  last_douban_backfill_output?: string | null;
  updated_at?: string | null;
}

export interface CrawlSource {
  _id: string;
  name: string;
  domain?: string | null;
  seed_url?: string | null;
  homepage_url?: string | null;
  category_pages?: string[];
  recent_pages?: string[];
  search_url_template?: string | null;
  search_title_limit?: number | null;
  search_pagination_max_pages?: number | null;
  douban_backfill_timeout_seconds?: number | null;
  max_depth: number;
  discovery_max_depth?: number;
  enabled: boolean;
  notes?: string | null;
  source_type: string;
  last_run_at?: string | null;
  last_run_status?: string | null;
  last_run_output?: string | null;
  last_discovery_at?: string | null;
  last_discovery_status?: string | null;
  last_discovery_output?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AdminOverview {
  settings: Omit<AdminSettings, '_id'>;
  source_count: number;
  enabled_source_count: number;
}

// --- 采集源管理 ---

export interface CollectSource {
  _id: string;
  name: string;
  url: string;
  type: 'json' | 'xml';
  mid: number;
  appid: string;
  appkey: string;
  bind: boolean;
  status: boolean;
  filter: {
    area: string;
    year: string;
    class: string;
    type: any[];
  };
  last_collect?: string | null;
  collect_num: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CollectTask {
  _id: string;
  collect_source: string;
  source_name: string;
  range: string;
  trigger: 'manual' | 'scheduler';
  active_key: string | null;
  status: 'pending' | 'running' | 'success' | 'failed';
  queue_position: number;
  processed: number;
  created: number;
  updated: number;
  skipped: number;
  pages: number;
  current_name: string;
  message: string;
  heartbeat_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  logs: Array<{ at: string; text: string }>;
  result: any | null;
  reused_existing?: boolean;
  enqueue_message?: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CollectTimingTask {
  id: number;
  status: number;
  name: string;
  des: string;
  file: string;
  param: { type: string };
  weeks: string;
  hours: string;
  monthdays?: string;
  runtime: number | null;
}

export interface CollectRangeOption {
  key: string;
  label: string;
}

export interface CollectTypeBinding {
  source_type_id: string;
  source_type_name: string;
  local_type: string;
  local_type_resolved?: any;
}
