'use client';

import { useRouter } from 'next/navigation';
import { FormEvent, useCallback } from 'react';
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

  const handleSubmit = useCallback(
    (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const formData = new FormData(e.currentTarget);
      const genre = (formData.get('genre') as string || '').trim();
      const year = (formData.get('year') as string || '').trim();
      const keyword = (formData.get('keyword') as string || '').trim();

      // Build clean SEO-friendly URL
      let path = '/';
      if (genre) {
        path = `/genre/${encodeURIComponent(genre)}`;
        if (year) {
          path += `/year/${encodeURIComponent(year)}`;
        }
      } else if (year) {
        path = `/year/${encodeURIComponent(year)}`;
      }

      const params = new URLSearchParams();
      if (keyword) params.set('keyword', keyword);
      const qs = params.toString();
      router.push(qs ? `${path}?${qs}` : path);
    },
    [router],
  );

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-[30px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6"
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_220px_220px_160px]">
        <label className="block">
          <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">搜索</div>
          <input
            type="text"
            name="keyword"
            defaultValue={defaultKeyword}
            placeholder="片名 / 导演 / 声优"
            className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition placeholder:text-ash focus:border-ember/60"
          />
        </label>

        <label className="block">
          <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">年份</div>
          <select
            name="year"
            defaultValue={String(defaultYear)}
            className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none focus:border-ember/60"
          >
            <option value="">全部年份</option>
            {filters.years.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">分类</div>
          <select
            name="genre"
            defaultValue={defaultGenre}
            className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none focus:border-ember/60"
          >
            <option value="">全部分类</option>
            {filters.genres.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-end gap-3">
          <button
            type="submit"
            className="w-full rounded-2xl bg-ember px-4 py-3 text-sm font-semibold text-black transition hover:brightness-110"
          >
            应用筛选
          </button>
        </div>
      </div>
    </form>
  );
}
