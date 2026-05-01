import { PlaySource } from '@/lib/types';

export function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ');
}

export function formatSourceLabel(source: PlaySource, index: number) {
  if (source.source_name && !source.source_name.startsWith('source-')) {
    return source.source_name;
  }

  const provider = source.provider_id?.replace(/^provider:/, '');
  if (provider) {
    return provider;
  }

  return `线路 ${index + 1}`;
}

export function formatEpisodeLabel(raw?: string | null) {
  if (!raw) {
    return '正片';
  }
  return /^第/.test(raw) ? raw : `第 ${raw} 集`;
}

export function sortEpisodes<T extends { episode?: string | null }>(episodes: T[]) {
  return [...episodes].sort((left, right) => {
    const leftNum = Number(String(left.episode || '').match(/\d+(\.\d+)?/)?.[0] || Number.NaN);
    const rightNum = Number(String(right.episode || '').match(/\d+(\.\d+)?/)?.[0] || Number.NaN);

    if (Number.isFinite(leftNum) && Number.isFinite(rightNum)) {
      return leftNum - rightNum;
    }

    return String(left.episode || '').localeCompare(String(right.episode || ''));
  });
}
