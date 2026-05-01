import Link from 'next/link';
import { AnimeListItem } from '@/lib/types';
import { resolvePosterUrl } from '@/lib/api';

export function AnimeCard({ anime }: { anime: AnimeListItem }) {
  const poster = resolvePosterUrl(anime.poster_local, anime.poster_url);

  return (
    <Link
      href={`/play/${anime._id}`}
      className="group relative overflow-hidden rounded-[28px] border border-white/10 bg-white/5 shadow-card transition duration-300 hover:-translate-y-1 hover:border-ember/50 hover:bg-white/8"
    >
      <div className="aspect-[3/4] overflow-hidden bg-gradient-to-b from-white/5 to-white/[0.02]">
        {poster ? (
          <img
            src={poster}
            alt={anime.title || 'anime poster'}
            className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.04]"
          />
        ) : (
          <div className="flex h-full items-center justify-center bg-white/5 text-sm text-ash">暂无海报</div>
        )}
      </div>

      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/82 to-transparent px-4 pb-4 pt-10">
        <div className="mb-2 flex items-center justify-between text-[11px] uppercase tracking-[0.24em] text-ash">
          <span>{anime.year || '未知年代'}</span>
          <span>{anime.play_source_count} 线路</span>
        </div>
        <h3 className="line-clamp-2 text-lg font-semibold text-parchment">{anime.title || '未命名作品'}</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {(anime.genres || []).slice(0, 3).map((genre) => (
            <span key={genre} className="rounded-full border border-white/10 bg-white/8 px-2.5 py-1 text-[11px] text-parchment/80">
              {genre}
            </span>
          ))}
        </div>
      </div>
    </Link>
  );
}
