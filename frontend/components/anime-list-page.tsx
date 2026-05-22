import Link from 'next/link';
import { AnimeCard } from '@/components/anime-card';
import { AnimeFilterBar } from '@/components/anime-filter-bar';
import { getAnimeFilters, getAnimeList } from '@/lib/server-api';
import { generateItemListJsonLd } from '@/lib/json-ld';

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';

interface AnimeListPageProps {
  genre?: string;
  year?: string;
  keyword?: string;
  page: number;
  heading: React.ReactNode;
  subheading?: React.ReactNode;
  basePath: string;
}

export async function AnimeListPage({
  genre = '',
  year = '',
  keyword = '',
  page,
  heading,
  subheading,
  basePath,
}: AnimeListPageProps) {
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

  const [list, filters] = await Promise.all([getAnimeList(params), getAnimeFilters()]);

  const itemListJsonLd = generateItemListJsonLd(
    '筛选结果',
    list.data.map((a) => ({ url: `${siteUrl}/play/${a._id}` })),
  );

  const buildPageUrl = (pageNum: number) => {
    const qs = new URLSearchParams();
    if (keyword) qs.set('keyword', keyword);
    if (pageNum > 1) qs.set('page', String(pageNum));
    const query = qs.toString();
    return query ? `${basePath}?${query}` : basePath;
  };

  return (
    <section className="min-h-screen bg-grain pb-20">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListJsonLd) }}
      />
      <div className="mx-auto max-w-[1600px] px-4 pt-10 md:px-8 xl:px-10">
        <div className="flex flex-col gap-2">
          <div className="mb-4 inline-flex rounded-full border border-ember/30 bg-ember/10 px-4 py-2 text-xs uppercase tracking-[0.3em] text-parchment/80">
            ACG Video Index
          </div>
          <h1 className="font-[var(--font-display)] text-4xl uppercase leading-none tracking-[0.02em] text-parchment md:text-5xl">
            {heading}
          </h1>
          {subheading && (
            <p className="text-sm leading-7 text-parchment/72 md:text-base">{subheading}</p>
          )}
        </div>
      </div>

      <section className="mx-auto max-w-[1600px] px-4 py-8 md:px-8 xl:px-10">
        <AnimeFilterBar
          filters={filters}
          defaultGenre={genre}
          defaultYear={year}
          defaultKeyword={keyword}
        />

        <div className="mt-6 flex items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-ash">播放库</div>
            <h2 className="mt-2 text-2xl font-semibold text-parchment">筛选结果</h2>
          </div>
          <div className="text-sm text-ash">
            第 {list.meta.page} / {list.meta.total_pages} 页
          </div>
        </div>

        {list.data.length === 0 ? (
          <div className="mt-12 rounded-[28px] border border-white/10 bg-white/[0.04] p-10 text-center shadow-card">
            <p className="text-parchment/60">没有找到匹配的动漫</p>
            <Link href="/" className="mt-4 inline-flex rounded-full bg-ember px-5 py-3 text-sm font-semibold text-black">
              返回首页
            </Link>
          </div>
        ) : (
          <>
            <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7">
              {list.data.map((anime) => (
                <AnimeCard key={anime._id} anime={anime} />
              ))}
            </div>

            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              {page > 1 ? (
                <Link
                  href={buildPageUrl(page - 1)}
                  className="rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm text-parchment/80 transition hover:border-white/20 hover:text-parchment"
                >
                  上一页
                </Link>
              ) : null}

              {page < list.meta.total_pages ? (
                <Link
                  href={buildPageUrl(page + 1)}
                  className="rounded-full bg-ember px-5 py-3 text-sm font-semibold text-black transition hover:brightness-110"
                >
                  下一页
                </Link>
              ) : null}
            </div>
          </>
        )}
      </section>
    </section>
  );
}
