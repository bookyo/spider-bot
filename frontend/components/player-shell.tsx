'use client';

import Hls from 'hls.js';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Episode, PlaySource } from '@/lib/types';
import { formatEpisodeLabel, formatSourceLabel, sortEpisodes, cn } from '@/lib/format';

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
  title: string;
  posterUrl: string;
  playSources: PlaySource[];
}

export function PlayerShell({ id, title, posterUrl, playSources }: PlayerShellProps) {
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

  return (
    <>
      <div className="mx-auto w-full max-w-[1600px] px-4 md:px-8 xl:px-10">
        <div className="rounded-[30px] border border-white/10 bg-black/30 p-3 shadow-card md:p-4">
          <div className="overflow-hidden rounded-[24px] bg-black">
            <div className="aspect-video w-full">
              <video
                ref={videoRef}
                className="h-full w-full bg-black object-contain"
                controls
                playsInline
                poster={posterUrl || undefined}
              />
            </div>
          </div>
        </div>

        {/* 播放源 + 剧集列表 */}
        <section className="mt-6 rounded-[30px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-4 border-b border-white/10 pb-5">
            <div>
              <div className="mb-2 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.24em] text-ash">
                <span>聚合源</span>
                <span>{preparedSources.length} 线路</span>
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
      </div>
    </>
  );
}

export type { PlaySource, Episode } from '@/lib/types';
