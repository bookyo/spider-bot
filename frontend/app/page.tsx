import type { Metadata } from 'next';
import Link from 'next/link';
import { AnimeCard } from '@/components/anime-card';
import { formatCompactNumber } from '@/lib/format';
import { getAnimeFilters, getAnimeList, getStats } from '@/lib/server-api';

export const metadata: Metadata = {
  title: '首页',
  description: '视频机器人bot 自动收集视频，按片名、年份和分类查找可播放动漫。',
  alternates: {
    canonical: '/',
  },
  openGraph: {
    title: '视频机器人bot 自动收集视频',
    description: '视频机器人bot 自动收集视频，按片名、年份和分类查找可播放动漫。',
    url: '/',
  },
  twitter: {
    title: '视频机器人bot 自动收集视频',
    description: '视频机器人bot 自动收集视频，按片名、年份和分类查找可播放动漫。',
  },
};

type SearchParamValue = string | string[] | undefined;

function firstValue(value: SearchParamValue) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, SearchParamValue>>;
}) {
  const paramsObj = await searchParams;
  const page = Number(firstValue(paramsObj.page) || 1);
  const keyword = firstValue(paramsObj.keyword) || '';
  const genre = firstValue(paramsObj.genre) || '';
  const year = firstValue(paramsObj.year) || '';

  const params = new URLSearchParams({
    page: String(page),
    page_size: '24',
    playable_only: 'true',
    sort_by: 'discovered_at',
    sort_order: 'desc',
  });

  if (keyword) params.set('keyword', keyword);
  if (genre) params.set('genre', genre);
  if (year) params.set('year', year);

  const [list, filters, stats] = await Promise.all([getAnimeList(params), getAnimeFilters(), getStats()]);

  return (
    <main className="min-h-screen bg-grain pb-20">
      <section className="border-b border-white/10">
        <div className="mx-auto max-w-[1600px] px-4 py-10 md:px-8 xl:px-10 xl:py-14">
          <div className="grid gap-10 xl:grid-cols-[1.2fr_0.8fr] xl:items-end">
            <div>
              <div className="mb-4 inline-flex rounded-full border border-ember/30 bg-ember/10 px-4 py-2 text-xs uppercase tracking-[0.3em] text-parchment/80">
                ACG Video Index
              </div>
              <h1 className="max-w-4xl font-[var(--font-display)] text-6xl uppercase leading-none tracking-[0.02em] text-parchment md:text-8xl">
                Stream anime
                <span className="block text-ember">without dead links</span>
              </h1>
              <p className="mt-5 max-w-2xl text-sm leading-7 text-parchment/72 md:text-base">
                收录可直接播放的动漫内容，支持按片名、年份和分类快速筛选。点击海报即可进入播放页，继续观看你想看的集数。
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-2">
              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card">
                <div className="text-xs uppercase tracking-[0.24em] text-ash">可播动漫</div>
                <div className="mt-4 text-4xl font-semibold text-parchment">{formatCompactNumber(list.meta.total)}</div>
              </div>
              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card">
                <div className="text-xs uppercase tracking-[0.24em] text-ash">总线路</div>
                <div className="mt-4 text-4xl font-semibold text-parchment">{formatCompactNumber(stats.total_play_sources)}</div>
              </div>
              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card">
                <div className="text-xs uppercase tracking-[0.24em] text-ash">动漫站点</div>
                <div className="mt-4 text-4xl font-semibold text-parchment">{formatCompactNumber(stats.anime_sites)}</div>
              </div>
              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-card">
                <div className="text-xs uppercase tracking-[0.24em] text-ash">平均质量</div>
                <div className="mt-4 text-4xl font-semibold text-parchment">{stats.avg_anime_quality.toFixed(2)}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1600px] px-4 py-8 md:px-8 xl:px-10">
        <form className="rounded-[30px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_220px_220px_160px]">
            <label className="block">
              <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">搜索</div>
              <input
                type="text"
                name="keyword"
                defaultValue={keyword}
                placeholder="片名 / 导演 / 声优"
                className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-parchment outline-none transition placeholder:text-ash focus:border-ember/60"
              />
            </label>

            <label className="block">
              <div className="mb-2 text-xs uppercase tracking-[0.24em] text-ash">年份</div>
              <select
                name="year"
                defaultValue={year}
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
                defaultValue={genre}
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

        <div className="mt-8 flex items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-ash">播放库</div>
            <h2 className="mt-2 text-2xl font-semibold text-parchment">
              {keyword || genre || year ? '筛选结果' : '最新可播内容'}
            </h2>
          </div>
          <div className="text-sm text-ash">
            第 {list.meta.page} / {list.meta.total_pages} 页
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7">
          {list.data.map((anime) => (
            <AnimeCard key={anime._id} anime={anime} />
          ))}
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          {page > 1 ? (
            <Link
              href={`/?${new URLSearchParams({
                ...(keyword ? { keyword } : {}),
                ...(genre ? { genre } : {}),
                ...(year ? { year } : {}),
                page: String(page - 1),
              }).toString()}`}
              className="rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm text-parchment/80 transition hover:border-white/20 hover:text-parchment"
            >
              上一页
            </Link>
          ) : null}

          {page < list.meta.total_pages ? (
            <Link
              href={`/?${new URLSearchParams({
                ...(keyword ? { keyword } : {}),
                ...(genre ? { genre } : {}),
                ...(year ? { year } : {}),
                page: String(page + 1),
              }).toString()}`}
              className="rounded-full bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110"
            >
              下一页
            </Link>
          ) : null}
        </div>
      </section>
    </main>
  );
}
