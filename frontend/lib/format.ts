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
  const value = String(raw || '').trim();
  if (!value) {
    return '正片';
  }

  const numbered = value.match(/^第\s*0*(\d+(?:\.\d+)?)\s*[集话話期]?$/);
  if (numbered) {
    return numbered[1];
  }

  const plainNumber = value.match(/^0*(\d+(?:\.\d+)?)$/);
  if (plainNumber) {
    return plainNumber[1];
  }

  return value;
}

export function formatCompactNumber(value?: number | null) {
  const numericValue = Number(value || 0);
  const absoluteValue = Math.abs(numericValue);

  if (absoluteValue < 1000) {
    return String(numericValue);
  }

  const units = [
    { value: 1_000_000_000, suffix: 'b' },
    { value: 1_000_000, suffix: 'm' },
    { value: 1_000, suffix: 'k' },
  ];
  const unit = units.find((item) => absoluteValue >= item.value);
  if (!unit) {
    return String(numericValue);
  }

  const compact = numericValue / unit.value;
  const precision = Math.abs(compact) >= 100 ? 0 : Math.abs(compact) >= 10 ? 1 : 2;
  return `${compact.toFixed(precision).replace(/\.0+$|(\.\d*[1-9])0+$/, '$1')}${unit.suffix}`;
}

export function sortEpisodes<T extends { episode?: string | null }>(episodes: T[]) {
  return [...episodes].sort((left, right) => {
    const leftNum = Number(String(left.episode || '').match(/\d+(\.\d+)?/)?.[0] || Number.NaN);
    const rightNum = Number(String(right.episode || '').match(/\d+(\.\d+)?/)?.[0] || Number.NaN);

    if (Number.isFinite(leftNum) && Number.isFinite(rightNum)) {
      return rightNum - leftNum;
    }

    return String(right.episode || '').localeCompare(String(left.episode || ''), 'zh-Hans-CN', {
      numeric: true,
      sensitivity: 'base',
    });
  });
}
