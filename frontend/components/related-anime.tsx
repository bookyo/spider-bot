import Link from 'next/link';
import { AnimeCard } from '@/components/anime-card';
import { getAnimeList } from '@/lib/server-api';

interface RelatedAnimeProps {
  genres: string[];
  year?: number | null;
  excludeId: string;
}

export async function RelatedAnime({ genres, year, excludeId }: RelatedAnimeProps) {
  if (!genres?.length) return null;

  const params = new URLSearchParams({
    page: '1',
    page_size: '6',
    playable_only: 'true',
    sort_by: 'discovered_at',
    sort_order: 'desc',
  });

  // 用第一个分类找同类作品
  params.set('genre', genres[0]);

  // 可选：限定同年代 ±2 年
  if (year) {
    const rangeStart = year - 2;
    const rangeEnd = year + 2;
    params.set('year', `${rangeStart}-${rangeEnd}`);
  }

  try {
    const list = await getAnimeList(params);
    const related = list.data.filter((a) => a._id !== excludeId).slice(0, 4);

    if (related.length === 0) return null;

    return (
      <section className="mt-12">
        <h2 className="mb-4 text-xs uppercase tracking-[0.24em] text-ash">相关推荐</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {related.map((anime) => (
            <AnimeCard key={anime._id} anime={anime} />
          ))}
        </div>
        <div className="mt-6 text-center">
          <Link
            href={`/genre/${encodeURIComponent(genres[0])}`}
            className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-5 py-2.5 text-sm text-ash transition hover:border-white/20 hover:text-parchment"
          >
            浏览更多 {genres[0]} 作品
          </Link>
        </div>
      </section>
    );
  } catch {
    return null;
  }
}
