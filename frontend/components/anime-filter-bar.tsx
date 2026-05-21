'use client';

import { useRouter } from 'next/navigation';
import { FormEvent, useCallback, useRef } from 'react';
import { AnimeFiltersResponse } from '@/lib/types';

interface AnimeFilterBarProps {
  filters: AnimeFiltersResponse;
  defaultGenre?: string;
  defaultYear?: string | number;
  defaultKeyword?: string;
}

export function AnimeFilterBar({
  filters,
  defaultGenre = '',
  defaultYear = '',
  defaultKeyword = '',
}: AnimeFilterBarProps) {
  const router = useRouter();
  const keywordRef = useRef<HTMLInputElement>(null);

  const currentYear = String(defaultYear);

  const getKeyword = useCallback(() => keywordRef.current?.value.trim() || '', []);

  const buildPath = (genre: string, year: string, keyword: string): string => {
    let path = '/';
    if (genre) {
      path = `/genre/${encodeURIComponent(genre)}`;
      if (year) {
        path += `/year/${encodeURIComponent(year)}`;
      }
    } else if (year) {
      path = `/year/${encodeURIComponent(year)}`;
    }

    const qs = new URLSearchParams();
    if (keyword) qs.set('keyword', keyword);
    const queryString = qs.toString();
    return queryString ? `${path}?${queryString}` : path;
  };

  const handleGenreClick = (genre: string) => {
    const keyword = getKeyword();
    // 切换分类时保持当前年份不变，由 buildPath 决定最终路径
    router.push(buildPath(genre, currentYear, keyword));
  };

  const handleYearClick = (year: string) => {
    const keyword = getKeyword();
    // 切换年份时保持当前分类不变，由 buildPath 决定最终路径
    router.push(buildPath(defaultGenre, year, keyword));
  };

  const handleSubmit = useCallback(
    (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const keyword = getKeyword();
      router.push(buildPath(defaultGenre, currentYear, keyword));
    },
    [defaultGenre, currentYear, getKeyword, router],
  );

  const chipBase =
    'shrink-0 cursor-pointer rounded-full border px-3 py-1.5 text-sm whitespace-nowrap transition';

  return (
    <div className="rounded-[30px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
      {/* 搜索行 — 保持不变 */}
      <form onSubmit={handleSubmit}>
        <div className="flex items-end gap-3">
          <label className="block flex-1">
            <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">搜索</div>
            <input
              ref={keywordRef}
              type="text"
              name="keyword"
              defaultValue={defaultKeyword}
              placeholder="片名 / 导演 / 声优"
              className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition placeholder:text-ash focus:border-ember/60"
            />
          </label>
          <button
            type="submit"
            className="shrink-0 rounded-2xl bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110"
          >
            搜索
          </button>
        </div>
      </form>

      {/* 分类横条 */}
      <div className="mt-5 flex items-center gap-2 overflow-x-auto scrollbar-thin pb-1">
        <span className="shrink-0 text-xs uppercase tracking-[0.24em] text-ash">分类</span>
        <button
          onClick={() => handleGenreClick('')}
          className={`${chipBase} ${
            !defaultGenre
              ? 'border-ember bg-ember/15 text-ember'
              : 'border-white/10 bg-white/[0.03] text-ash hover:border-white/20 hover:text-parchment'
          }`}
        >
          全部
        </button>
        {filters.genres.map((item) => (
          <button
            key={item}
            onClick={() => handleGenreClick(item)}
            className={`${chipBase} ${
              defaultGenre === item
                ? 'border-ember bg-ember/15 text-ember'
                : 'border-white/10 bg-white/[0.03] text-ash hover:border-white/20 hover:text-parchment'
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      {/* 年份横条 */}
      <div className="mt-3 flex items-center gap-2 overflow-x-auto scrollbar-thin pb-1">
        <span className="shrink-0 text-xs uppercase tracking-[0.24em] text-ash">年份</span>
        <button
          onClick={() => handleYearClick('')}
          className={`${chipBase} ${
            !currentYear
              ? 'border-ember bg-ember/15 text-ember'
              : 'border-white/10 bg-white/[0.03] text-ash hover:border-white/20 hover:text-parchment'
          }`}
        >
          全部
        </button>
        {filters.years.map((item) => (
          <button
            key={item}
            onClick={() => handleYearClick(String(item))}
            className={`${chipBase} ${
              currentYear === String(item)
                ? 'border-ember bg-ember/15 text-ember'
                : 'border-white/10 bg-white/[0.03] text-ash hover:border-white/20 hover:text-parchment'
            }`}
          >
            {item}
          </button>
        ))}
      </div>
    </div>
  );
}
