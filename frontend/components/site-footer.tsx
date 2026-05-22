import Link from 'next/link';
import { getAnimeFilters } from '@/lib/server-api';

export async function SiteFooter() {
  let genres: string[] = [];
  let years: number[] = [];

  try {
    const filters = await getAnimeFilters();
    genres = filters.genres.slice(0, 15);
    years = filters.years.slice(0, 10);
  } catch {
    // 静默降级，footer 在不加载到数据时只显示版权信息
  }

  return (
    <footer className="mt-20 border-t border-white/10 bg-coal">
      <div className="mx-auto max-w-[1600px] px-4 py-12 md:px-8 xl:px-10">
        <div className="grid gap-10 md:grid-cols-3">
          <div>
            <div className="font-[var(--font-display)] text-lg uppercase tracking-[0.08em] text-parchment">
              ACG Video Index
            </div>
            <p className="mt-3 text-sm leading-6 text-ash">
              收录可直接播放的动漫内容，支持分类、年份和片名快速筛选。
            </p>
          </div>

          {genres.length > 0 && (
            <div>
              <div className="mb-3 text-xs uppercase tracking-[0.24em] text-ash">分类</div>
              <div className="flex flex-wrap gap-2">
                {genres.map((genre) => (
                  <Link
                    key={genre}
                    href={`/genre/${encodeURIComponent(genre)}`}
                    className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-ash transition hover:border-ember/40 hover:text-parchment"
                  >
                    {genre}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {years.length > 0 && (
            <div>
              <div className="mb-3 text-xs uppercase tracking-[0.24em] text-ash">年份</div>
              <div className="flex flex-wrap gap-2">
                {years.map((year) => (
                  <Link
                    key={year}
                    href={`/year/${encodeURIComponent(String(year))}`}
                    className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-ash transition hover:border-ember/40 hover:text-parchment"
                  >
                    {year}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="mt-10 border-t border-white/5 pt-6 text-center text-xs text-ash/60">
          &copy; {new Date().getFullYear()} vbot.reelbit.cc
        </div>
      </div>
    </footer>
  );
}
