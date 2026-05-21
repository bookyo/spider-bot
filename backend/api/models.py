"""Pydantic 响应模型"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class EpisodeOut(BaseModel):
    episode: Optional[str] = None
    url: str


class PlaySourceOut(BaseModel):
    domain: str
    source_name: Optional[str] = None
    provider_id: Optional[str] = None
    source_id: Optional[str] = None
    episodes: list[EpisodeOut] = []
    quality: Optional[str] = None
    raw_url: Optional[str] = None
    episode_count: Optional[int] = None
    latest_episode: Optional[str] = None
    new_episode_count: Optional[int] = None
    added_at: Optional[datetime] = None
    last_episode_update: Optional[datetime] = None


class PlaySourcePublic(BaseModel):
    """播放源公开信息 — 对外暴露时不包含内部域名/原始URL"""
    source_name: Optional[str] = None
    provider_id: Optional[str] = None
    source_id: Optional[str] = None
    episodes: list[EpisodeOut] = []
    quality: Optional[str] = None
    episode_count: Optional[int] = None
    latest_episode: Optional[str] = None
    new_episode_count: Optional[int] = None
    added_at: Optional[datetime] = None
    last_episode_update: Optional[datetime] = None


class AnimeListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias='_id')
    title: Optional[str] = None
    original_title: Optional[str] = None
    aliases: list[str] = []
    year: Optional[int] = None
    director: Optional[str] = None
    poster_url: Optional[str] = None
    poster_local: Optional[str] = None
    douban_rating: Optional[float] = None
    imdb_rating: Optional[float] = None
    genres: list[str] = []
    source_domain: Optional[str] = None
    site_type: Optional[str] = None
    quality_score: Optional[float] = None
    latest_episode: Optional[str] = None
    total_episode_count: Optional[int] = None
    incremental_found: Optional[bool] = None
    new_episode_count: Optional[int] = None
    last_incremental_check: Optional[datetime] = None
    incremental_priority: Optional[float] = None
    play_source_count: int = 0
    discovered_at: Optional[datetime] = None


class AnimeDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias='_id')
    title: Optional[str] = None
    original_title: Optional[str] = None
    aliases: list[str] = []
    year: Optional[int] = None
    director: Optional[str] = None
    voice_actors: list[str] = []
    synopsis: Optional[str] = None
    poster_url: Optional[str] = None
    poster_local: Optional[str] = None
    douban_rating: Optional[float] = None
    imdb_rating: Optional[float] = None
    source_urls: list[str] = []
    source_domain: Optional[str] = None
    extractor_name: Optional[str] = None
    extractor_confidence: Optional[float] = None
    site_type: Optional[str] = None
    quality_score: Optional[float] = None
    latest_episode: Optional[str] = None
    total_episode_count: Optional[int] = None
    new_episode_count: Optional[int] = None
    incremental_found: Optional[bool] = None
    last_incremental_check: Optional[datetime] = None
    incremental_priority: Optional[float] = None
    genres: list[str] = []
    play_sources: list[PlaySourceOut] = []
    discovered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AnimeDetailPublic(BaseModel):
    """动画详情公开版 — 用于播放页，剥离 source_urls / source_domain / play_sources.domain"""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias='_id')
    title: Optional[str] = None
    original_title: Optional[str] = None
    aliases: list[str] = []
    year: Optional[int] = None
    director: Optional[str] = None
    voice_actors: list[str] = []
    synopsis: Optional[str] = None
    poster_url: Optional[str] = None
    poster_local: Optional[str] = None
    douban_rating: Optional[float] = None
    imdb_rating: Optional[float] = None
    extractor_name: Optional[str] = None
    extractor_confidence: Optional[float] = None
    site_type: Optional[str] = None
    quality_score: Optional[float] = None
    latest_episode: Optional[str] = None
    total_episode_count: Optional[int] = None
    new_episode_count: Optional[int] = None
    incremental_found: Optional[bool] = None
    last_incremental_check: Optional[datetime] = None
    incremental_priority: Optional[float] = None
    genres: list[str] = []
    play_sources: list[PlaySourcePublic] = []
    discovered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DomainItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias='_id')
    domain: str
    source: Optional[str] = None
    is_anime_site: bool = False
    status: Optional[str] = None
    site_type: Optional[str] = None
    last_error: Optional[str] = None
    retry_count: Optional[int] = None
    priority_score: Optional[float] = None
    total_crawls: Optional[int] = None
    success_crawls: Optional[int] = None
    success_rate: Optional[float] = None
    total_anime_found: Optional[int] = None
    avg_quality_score: Optional[float] = None
    health_score: Optional[float] = None
    last_crawled: Optional[datetime] = None
    discovered_at: Optional[datetime] = None


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class AnimeListResponse(BaseModel):
    data: list[AnimeListItem]
    meta: PaginationMeta


class AnimeFiltersResponse(BaseModel):
    years: list[int] = []
    genres: list[str] = []


class DomainListResponse(BaseModel):
    data: list[DomainItem]
    meta: PaginationMeta


class StatsResponse(BaseModel):
    total_anime: int
    total_domains: int
    anime_sites: int
    pending_domains: int
    total_play_sources: int
    year_distribution: dict[str, int]
    top_genres: list[dict]
    healthy_domains: int
    failed_domains: int
    avg_anime_quality: float
    quality_distribution: dict[str, int]
