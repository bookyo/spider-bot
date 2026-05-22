import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { PlayerShell } from '@/components/player-shell';
import { Breadcrumb } from '@/components/breadcrumb';
import { RelatedAnime } from '@/components/related-anime';
import { PosterImage } from '@/components/poster-image';
import { resolvePosterUrl } from '@/lib/api';
import { getAnimeDetail } from '@/lib/server-api';
import { generateVideoObjectJsonLd } from '@/lib/json-ld';

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;

  try {
    const anime = await getAnimeDetail(id);
    const title = anime.title || '视频播放';
    const siteTitle = `${title} 在线观看`;
    const metaDescription = anime.synopsis
      ? `${anime.synopsis.slice(0, 120)}`
      : `观看「${title}」${anime.year ? `${anime.year}年` : ''}${anime.genres?.length ? `【${anime.genres.join(' / ')}】` : ''}全集，免登录在线播放。`;
    const poster = resolvePosterUrl(anime.poster_local, anime.poster_url);
    const images = poster ? [{ url: poster, width: 600, height: 800 }] : undefined;
    return {
      title: siteTitle,
      description: metaDescription,
      alternates: {
        canonical: `/play/${id}`,
      },
      openGraph: {
        type: 'video.other',
        title: siteTitle,
        description: metaDescription,
        url: `/play/${id}`,
        images,
      },
      twitter: {
        card: 'summary_large_image',
        title: siteTitle,
        description: metaDescription,
        images: poster ? [poster] : undefined,
      },
    };
  } catch {
    return {
      title: '视频在线观看',
      description: '免登录在线播放动漫，海量资源持续更新。',
    };
  }
}

export default async function PlayPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  try {
    const anime = await getAnimeDetail(id);
    const poster = resolvePosterUrl(anime.poster_local, anime.poster_url);
    const firstEpisodeUrl = anime.play_sources?.[0]?.episodes?.[0]?.url || undefined;

    const breadcrumbItems = [
      { label: '首页', href: '/' },
      ...(anime.genres?.[0]
        ? [{ label: anime.genres[0], href: `/genre/${encodeURIComponent(anime.genres[0])}` }]
        : []),
      { label: anime.title || '视频' },
    ];

    const videoObjectJsonLd = generateVideoObjectJsonLd({
      name: anime.title || '',
      description: anime.synopsis || '',
      thumbnailUrl: poster || '',
      contentUrl: firstEpisodeUrl,
      datePublished: anime.year ? String(anime.year) : undefined,
      author: anime.director || undefined,
      genre: anime.genres || undefined,
    });

    return (
      <>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(videoObjectJsonLd) }}
        />

        <div className="mx-auto w-full max-w-[1600px] px-4 pt-4 md:px-8 xl:px-10">
          <Breadcrumb items={breadcrumbItems} />
        </div>

        {/* 播放器 */}
        <PlayerShell
          id={anime._id}
          title={anime.title || ''}
          posterUrl={poster || ''}
          playSources={anime.play_sources}
        />

        {/* SSR 侧边栏信息（播放源下方，移动端自然顺序） */}
        <div className="mx-auto w-full max-w-[1600px] px-4 pt-6 md:px-8 xl:px-10">
          <div className="flex flex-col gap-4 rounded-[30px] border border-white/10 bg-white/[0.04] p-5 shadow-card sm:flex-row md:p-6">
            {poster && (
              <div className="w-full shrink-0 overflow-hidden rounded-[20px] border border-white/10 bg-black/30 sm:w-[140px]">
                <div className="aspect-[3/4] sm:aspect-[2/3]">
                  <PosterImage src={poster} alt={anime.title || 'poster'} />
                </div>
              </div>
            )}
            <div className="flex flex-1 flex-col justify-center gap-3">
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-parchment/80">
                {anime.douban_rating != null && (
                  <span>
                    <span className="text-ash">豆瓣</span> {anime.douban_rating}
                  </span>
                )}
                {anime.imdb_rating != null && (
                  <span>
                    <span className="text-ash">IMDB</span> {anime.imdb_rating}
                  </span>
                )}
                <span>
                  <span className="text-ash">年份</span> {anime.year || '未知'}
                </span>
                <span>
                  <span className="text-ash">导演</span> {anime.director || '未知'}
                </span>
                <span>
                  <span className="text-ash">线路</span> {anime.play_sources?.length || 0} ·{' '}
                  <span className="text-ash">总集数</span> {anime.total_episode_count || 0}
                </span>
              </div>
              {!!anime.genres?.length && (
                <div className="flex flex-wrap gap-2">
                  {anime.genres.map((genre) => (
                    <Link
                      key={genre}
                      href={`/genre/${encodeURIComponent(genre)}`}
                      className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-parchment/85 transition hover:border-ember/50 hover:bg-ember/10 hover:text-parchment"
                    >
                      {genre}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* SSR H1 + synopsis（卡牌风格） */}
        <div className="mx-auto w-full max-w-[1600px] px-4 pt-6 md:px-8 xl:px-10">
          <div className="rounded-[30px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:p-6">
            <h1 className="text-2xl font-semibold text-parchment md:text-3xl">{anime.title || '未命名作品'}</h1>
            {anime.original_title && anime.original_title !== anime.title ? (
              <p className="mt-1 text-sm text-ash">{anime.original_title}</p>
            ) : null}
            {anime.synopsis ? (
              <p className="mt-3 max-w-3xl text-sm leading-7 text-parchment/75">{anime.synopsis}</p>
            ) : null}
          </div>
        </div>

        {/* 相关推荐 */}
        <div className="mx-auto w-full max-w-[1600px] px-4 pb-20 pt-6 md:px-8 xl:px-10">
          <RelatedAnime genres={anime.genres} year={anime.year} excludeId={anime._id} />
        </div>
      </>
    );
  } catch {
    notFound();
  }
}
