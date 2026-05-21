'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AnimeListItem } from '@/lib/types';
import { resolvePosterUrl } from '@/lib/api';
import { PosterImage } from '@/components/poster-image';

export function AnimeCard({ anime }: { anime: AnimeListItem }) {
  const router = useRouter();
  const poster = resolvePosterUrl(anime.poster_local, anime.poster_url);

  const handleGenreClick = (e: React.MouseEvent | React.KeyboardEvent, genre: string) => {
    if ('key' in e && e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    e.stopPropagation();
    router.push(`/genre/${encodeURIComponent(genre)}`);
  };

  const handleYearClick = (e: React.MouseEvent | React.KeyboardEvent) => {
    if ('key' in e && e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    e.stopPropagation();
    if (anime.year) {
      router.push(`/year/${anime.year}`);
    }
  };

  return (
    <Link
      href={`/play/${anime._id}`}
      className="group relative overflow-hidden rounded-[28px] border border-white/10 bg-white/5 shadow-card transition duration-300 hover:-translate-y-1 hover:border-ember/50 hover:bg-white/8"
    >
      <div className="aspect-[3/4] overflow-hidden bg-gradient-to-b from-white/5 to-white/[0.02]">
        <PosterImage
          src={poster}
          alt={anime.title || 'anime poster'}
          imgClassName="group-hover:scale-[1.04]"
        />
      </div>

      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/82 to-transparent px-4 pb-4 pt-10">
        <div className="mb-2 flex items-center justify-between text-[11px] uppercase tracking-[0.24em] text-ash">
          {anime.year ? (
            <span
              className="cursor-pointer transition hover:text-parchment/80"
              onClick={handleYearClick}
              role="link"
              tabIndex={0}
              onKeyDown={(e) => handleYearClick(e)}
            >
              {anime.year}
            </span>
          ) : (
            <span>未知年代</span>
          )}
          <span>{anime.play_source_count} 线路</span>
        </div>
        <h3 className="line-clamp-2 text-lg font-semibold text-parchment">{anime.title || '未命名作品'}</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {(anime.genres || []).filter((g) => g.length > 1).slice(0, 3).map((genre) => (
            <span
              key={genre}
              className="cursor-pointer rounded-full border border-white/10 bg-white/8 px-2.5 py-1 text-[11px] text-parchment/80 transition hover:border-ember/40 hover:text-parchment"
              onClick={(e) => handleGenreClick(e, genre)}
              role="link"
              tabIndex={0}
              onKeyDown={(e) => handleGenreClick(e, genre)}
            >
              {genre}
            </span>
          ))}
        </div>
      </div>
    </Link>
  );
}
