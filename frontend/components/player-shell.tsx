'use client';

import Hls from 'hls.js';
import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimeDetail, Episode, PlaySource } from '@/lib/types';
import { formatEpisodeLabel, formatSourceLabel, sortEpisodes, cn } from '@/lib/format';
import { resolvePosterUrl } from '@/lib/api';
import { PosterImage } from '@/components/poster-image';

interface PlayerPreference {
  sourceId?: string | null;
  episode?: string | null;
  episodeUrl?: string | null;
}

const preferenceKey = (animeId: string) => `acg:player:${animeId}`;

function buildSourceSignature(source: PlaySource, index: number) {
  return source.source_id || source.provider_id || `src-${index}`;
}

function pickInitialPlayback(anime: AnimeDetail) {
  const sources = anime.play_sources.map((source) => ({
    ...source,
    episodes: sortEpisodes(source.episodes || []),
  }));
  return sources;
}

export function PlayerShell({ anime }: { anime: AnimeDetail }) {
  const preparedSources = useMemo(() => pickInitialPlayback(anime), [anime]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [selectedSourceIndex, setSelectedSourceIndex] = useState(0);
  const [selectedEpisodeUrl, setSelectedEpisodeUrl] = useState<string | null>(null);

  const selectedSource = preparedSources[selectedSourceIndex];
  const selectedEpisode =
    selectedSource?.episodes.find((episode) => episode.url === selectedEpisodeUrl) ||
    selectedSource?.episodes[0] ||
    null;

  useEffect(() => {
    if (!preparedSources.length) {
      return;
    }

    const raw = window.localStorage.getItem(preferenceKey(anime._id));
    let preference: PlayerPreference | null = null;
    if (raw) {
      try {
        preference = JSON.parse(raw) as PlayerPreference;
      } catch {
        preference = null;
      }
    }

    if (preference?.sourceId) {
      const matchedIndex = preparedSources.findIndex(
        (source, index) => buildSourceSignature(source, index) === preference?.sourceId,
      );
      if (matchedIndex >= 0) {
        const preferredSource = preparedSources[matchedIndex];
        const matchedEpisode =
          preferredSource.episodes.find(
            (episode) =>
              (preference?.episodeUrl && episode.url === preference.episodeUrl) ||
              (preference?.episode && episode.episode === preference.episode),
          ) ||
          preferredSource.episodes[0] ||
          null;
        setSelectedSourceIndex(matchedIndex);
        setSelectedEpisodeUrl(matchedEpisode?.url || null);
        return;
      }
    }

    setSelectedSourceIndex(0);
    setSelectedEpisodeUrl(preparedSources[0]?.episodes[0]?.url || null);
  }, [anime._id, preparedSources]);

  useEffect(() => {
    if (!selectedSource || !selectedEpisode) {
      return;
    }

    window.localStorage.setItem(
      preferenceKey(anime._id),
      JSON.stringify({
        sourceId: buildSourceSignature(selectedSource, selectedSourceIndex),
        episode: selectedEpisode.episode,
        episodeUrl: selectedEpisode.url,
      } satisfies PlayerPreference),
    );
  }, [anime._id, selectedEpisode, selectedSource, selectedSourceIndex]);

  useEffect(() => {
    const video = videoRef.current;
    const streamUrl = selectedEpisode?.url;
    if (!video || !streamUrl) {
      return;
    }

    let hls: Hls | null = null;
    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = streamUrl;
    } else if (Hls.isSupported()) {
      hls = new Hls({
        enableWorker: true,
      });
      hls.loadSource(streamUrl);
      hls.attachMedia(video);
    } else {
      video.src = streamUrl;
    }

    return () => {
      if (hls) {
        hls.destroy();
      }
      video.pause();
      video.removeAttribute('src');
      video.load();
    };
  }, [selectedEpisode?.url]);

  const poster = resolvePosterUrl(anime.poster_local, anime.poster_url);
  const currentSourceLabel = selectedSource ? formatSourceLabel(selectedSource, selectedSourceIndex) : '暂无线路';

  return (
    <div className="min-h-screen bg-grain">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-8 px-4 py-6 md:px-8 xl:px-10">
        <div className="rounded-[30px] border border-white/10 bg-black/30 p-3 shadow-card md:p-4">
          <div className="overflow-hidden rounded-[24px] bg-black">
            <div className="aspect-video w-full">
              <video
                ref={videoRef}
                className="h-full w-full bg-black object-contain"
                controls
                playsInline
                poster={poster || undefined}
              />
            </div>
          </div>
        </div>

        <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_340px]">
          <section className="min-w-0 rounded-[30px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-4 border-b border-white/10 pb-5">
              <div>
                <div className="mb-2 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.24em] text-ash">
                  <span>{'聚合源'}</span>
                  <span>{anime.year || '未知年代'}</span>
                  <span>{anime.total_episode_count || 0} 集</span>
                </div>
                <h1 className="text-3xl font-semibold text-parchment md:text-4xl">{anime.title || '未命名作品'}</h1>
                {anime.original_title && anime.original_title !== anime.title ? (
                  <p className="mt-2 text-sm text-ash">{anime.original_title}</p>
                ) : null}
              </div>
              <div className="rounded-full border border-ember/30 bg-ember/10 px-4 py-2 text-xs text-parchment/80">
                当前播放：{currentSourceLabel} / {formatEpisodeLabel(selectedEpisode?.episode)}
              </div>
            </div>

            <div className="mb-6">
              <div className="mb-3 text-xs uppercase tracking-[0.28em] text-ash">播放源</div>
              <div className="scrollbar-thin flex gap-3 overflow-x-auto pb-1">
                {preparedSources.map((source, index) => {
                  const active = index === selectedSourceIndex;
                  return (
                    <button
                      key={buildSourceSignature(source, index)}
                      type="button"
                      onClick={() => {
                        setSelectedSourceIndex(index);
                        setSelectedEpisodeUrl(source.episodes[0]?.url || null);
                      }}
                      className={cn(
                        'min-w-fit rounded-2xl border px-4 py-3 text-left transition',
                        active
                          ? 'border-ember bg-ember/20 text-parchment'
                          : 'border-white/10 bg-white/[0.03] text-ash hover:border-white/20 hover:text-parchment',
                      )}
                    >
                      <div className="text-sm font-medium">{formatSourceLabel(source, index)}</div>
                      <div className="mt-1 text-[11px] uppercase tracking-[0.18em] opacity-80">
                        {source.episode_count || source.episodes.length} 集
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <div className="mb-3 text-xs uppercase tracking-[0.28em] text-ash">分集列表</div>
              <div className="scrollbar-thin max-h-[30rem] overflow-y-auto pr-1">
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7">
                  {(selectedSource?.episodes || []).map((episode: Episode) => {
                    const active = episode.url === selectedEpisode?.url;
                    return (
                      <button
                        key={episode.url}
                        type="button"
                        onClick={() => setSelectedEpisodeUrl(episode.url)}
                        className={cn(
                          'rounded-2xl border px-3 py-3 text-sm transition',
                          active
                            ? 'border-ember bg-ember text-black'
                            : 'border-white/10 bg-white/[0.03] text-parchment/80 hover:border-white/20 hover:bg-white/[0.06]',
                        )}
                      >
                        {episode.episode || '正片'}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </section>

          <aside className="rounded-[30px] border border-white/10 bg-white/[0.04] p-5 shadow-card xl:sticky xl:top-6 xl:h-fit">
            <div className="overflow-hidden rounded-[24px] border border-white/10 bg-black/30">
              <div className="aspect-[3/4]">
                <PosterImage src={poster || ''} alt={anime.title || 'poster'} />
              </div>
            </div>

            <div className="mt-5 space-y-4">
              <div>
                <div className="mb-1 text-xs uppercase tracking-[0.24em] text-ash">影片信息</div>
                <div className="text-lg font-semibold">{anime.title}</div>
              </div>

              <dl className="space-y-3 text-sm text-parchment/80">
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-ash">年份</dt>
                  <dd>{anime.year || '未知'}</dd>
                </div>
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-ash">导演</dt>
                  <dd className="text-right">{anime.director || '未知'}</dd>
                </div>
                {anime.douban_rating != null ? (
                  <div className="flex items-start justify-between gap-4">
                    <dt className="text-ash">豆瓣评分</dt>
                    <dd>{anime.douban_rating}</dd>
                  </div>
                ) : null}
                {anime.imdb_rating != null ? (
                  <div className="flex items-start justify-between gap-4">
                    <dt className="text-ash">IMDB评分</dt>
                    <dd>{anime.imdb_rating}</dd>
                  </div>
                ) : null}
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-ash">线路数</dt>
                  <dd>{preparedSources.length}</dd>
                </div>
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-ash">总集数</dt>
                  <dd>{anime.total_episode_count || 0}</dd>
                </div>
              </dl>

              {!!anime.genres?.length && (
                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">分类</div>
                  <div className="flex flex-wrap gap-2">
                    {anime.genres.map((genre) => (
                      <span key={genre} className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-parchment/85">
                        {genre}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {anime.synopsis ? (
                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">简介</div>
                  <p className="text-sm leading-7 text-parchment/75">{anime.synopsis}</p>
                </div>
              ) : null}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
