'use client';

import Hls from 'hls.js';
import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Episode, PlaySource } from '@/lib/types';
import { formatEpisodeLabel, formatSourceLabel, sortEpisodes, cn } from '@/lib/format';
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

export interface PlayerShellProps {
  id: string;
  title?: string | null;
  originalTitle?: string | null;
  posterUrl: string;
  year?: number | null;
  director?: string | null;
  doubanRating?: number | null;
  imdbRating?: number | null;
  genres?: string[];
  totalEpisodeCount?: number | null;
  playSources: PlaySource[];
}

export function PlayerShell({
  id,
  title,
  originalTitle,
  posterUrl,
  year,
  director,
  doubanRating,
  imdbRating,
  genres = [],
  totalEpisodeCount,
  playSources,
}: PlayerShellProps) {
  const preparedSources = useMemo(
    () =>
      playSources.map((source) => ({
        ...source,
        episodes: sortEpisodes(source.episodes || []),
      })),
    [playSources],
  );

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

    const raw = window.localStorage.getItem(preferenceKey(id));
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
  }, [id, preparedSources]);

  useEffect(() => {
    if (!selectedSource || !selectedEpisode) {
      return;
    }

    window.localStorage.setItem(
      preferenceKey(id),
      JSON.stringify({
        sourceId: buildSourceSignature(selectedSource, selectedSourceIndex),
        episode: selectedEpisode.episode,
        episodeUrl: selectedEpisode.url,
      } satisfies PlayerPreference),
    );
  }, [id, selectedEpisode, selectedSource, selectedSourceIndex]);

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

  const currentSourceLabel = selectedSource
    ? formatSourceLabel(selectedSource, selectedSourceIndex)
    : '暂无线路';
  const lineCount = preparedSources.length;

  const infoItems = [
    { label: '年份', value: year || '未知' },
    { label: '导演', value: director || '未知' },
    { label: '线路数', value: lineCount },
    { label: '总集数', value: totalEpisodeCount || 0 },
  ];

  if (doubanRating != null) {
    infoItems.unshift({ label: '豆瓣', value: doubanRating });
  }
  if (imdbRating != null) {
    infoItems.splice(Math.min(infoItems.length, 2), 0, { label: 'IMDB', value: imdbRating });
  }

  const displayTitle = title || originalTitle || '未命名作品';

  return (
    <div>
      <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_320px] xl:items-start xl:gap-6 2xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          <div className="rounded-[24px] border border-white/10 bg-black/35 p-2 shadow-card md:rounded-[28px] md:p-3">
            <div className="overflow-hidden rounded-[24px] bg-black">
              <div className="aspect-video w-full">
                <video
                  ref={videoRef}
                  className="h-full w-full bg-black object-cover"
                  controls
                  playsInline
                  poster={posterUrl || undefined}
                />
              </div>
            </div>
          </div>

          <section className="mt-5 rounded-[24px] border border-white/10 bg-white/[0.04] p-4 shadow-card md:rounded-[28px] md:p-5">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-4 border-b border-white/10 pb-5">
              <div>
                <div className="mb-2 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.24em] text-ash">
                  <span>聚合源</span>
                  <span>{lineCount} 线路</span>
                </div>
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

          <section className="mt-5 rounded-[24px] border border-white/10 bg-white/[0.04] p-4 shadow-card md:hidden">
            <div className="grid gap-4">
              <div className="mx-auto w-full max-w-[190px] overflow-hidden rounded-[18px] border border-white/10 bg-black/30">
                <div className="aspect-[3/4]">
                  <PosterImage src={posterUrl || ''} alt={displayTitle} />
                </div>
              </div>

              <div className="min-w-0">
                <h2 className="text-xl font-semibold leading-snug text-parchment">{displayTitle}</h2>
                {originalTitle ? (
                  <p className="mt-1 break-all text-sm text-ash">{originalTitle}</p>
                ) : null}

                <div className="mt-4 grid grid-cols-2 gap-3 rounded-[20px] border border-white/10 bg-black/20 p-4">
                  {infoItems.map((item) => (
                    <div key={item.label} className="min-w-0">
                      <div className="text-[11px] uppercase tracking-[0.18em] text-ash">{item.label}</div>
                      <div className="mt-1 truncate text-sm text-parchment/88">{item.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {!!genres.length && (
              <div className="mt-5 flex flex-wrap gap-2">
                {genres.map((genre) => (
                  <Link
                    key={genre}
                    href={`/genre/${encodeURIComponent(genre)}`}
                    className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-parchment/85 transition hover:border-ember/50 hover:bg-ember/10 hover:text-parchment"
                  >
                    {genre}
                  </Link>
                ))}
              </div>
            )}
          </section>
        </div>

        <aside className="hidden xl:block xl:sticky xl:top-6">
          <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-4 shadow-card">
            <div className="mx-auto max-w-[220px] overflow-hidden rounded-[20px] border border-white/10 bg-black/30 2xl:max-w-[240px]">
              <div className="aspect-[3/4]">
                <PosterImage src={posterUrl || ''} alt={displayTitle} />
              </div>
            </div>

            <div className="mt-5">
              <h2 className="line-clamp-2 text-xl font-semibold leading-snug text-parchment">
                {displayTitle}
              </h2>
              {originalTitle ? (
                <p className="mt-1 break-all text-sm text-ash">{originalTitle}</p>
              ) : null}

              <div className="mt-4 grid grid-cols-2 gap-3 rounded-[20px] border border-white/10 bg-black/20 p-4">
                {infoItems.map((item) => (
                  <div key={item.label} className="min-w-0">
                    <div className="text-[11px] uppercase tracking-[0.18em] text-ash">{item.label}</div>
                    <div className="mt-1 truncate text-sm text-parchment/88">{item.value}</div>
                  </div>
                ))}
              </div>

              {!!genres.length && (
                <div className="mt-5 flex flex-wrap gap-2">
                  {genres.map((genre) => (
                    <Link
                      key={genre}
                      href={`/genre/${encodeURIComponent(genre)}`}
                      className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-parchment/85 transition hover:border-ember/50 hover:bg-ember/10 hover:text-parchment"
                    >
                      {genre}
                    </Link>
                  ))}
                </div>
              )}

              <div className="mt-5 rounded-[20px] border border-ember/20 bg-ember/[0.06] px-4 py-3 text-xs text-parchment/70">
                当前播放：{currentSourceLabel} / {formatEpisodeLabel(selectedEpisode?.episode)}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

export type { PlaySource, Episode } from '@/lib/types';
