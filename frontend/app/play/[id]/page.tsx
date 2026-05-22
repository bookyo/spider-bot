import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { PlayerShell } from '@/components/player-shell';
import { Breadcrumb } from '@/components/breadcrumb';
import { RelatedAnime } from '@/components/related-anime';
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
          <Link
            href="/"
            className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-parchment/80 transition hover:border-white/20 hover:text-parchment"
          >
            返回首页
          </Link>
        </div>

        {/* SSR 元信息 */}
        <div className="mx-auto w-full max-w-[1600px] px-4 pt-6 md:px-8 xl:px-10">
          <div className="mb-2 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.24em] text-ash">
            <span>聚合源</span>
            <span>{anime.year || '未知年代'}</span>
            <span>{anime.total_episode_count || 0} 集</span>
          </div>
          <h1 className="text-3xl font-semibold text-parchment md:text-4xl">{anime.title || '未命名作品'}</h1>
          {anime.original_title && anime.original_title !== anime.title ? (
            <p className="mt-2 text-sm text-ash">{anime.original_title}</p>
          ) : null}
          {anime.synopsis ? (
            <p className="mt-4 max-w-3xl text-sm leading-7 text-parchment/75">{anime.synopsis}</p>
          ) : null}
        </div>

        {/* 播放器 */}
        <PlayerShell
          id={anime._id}
          title={anime.title || ''}
          posterUrl={poster || ''}
          playSources={anime.play_sources}
        />

        {/* 相关推荐 */}
        <div className="mx-auto w-full max-w-[1600px] px-4 md:px-8 xl:px-10">
          <RelatedAnime genres={anime.genres} year={anime.year} excludeId={anime._id} />
        </div>
      </>
    );
  } catch {
    notFound();
  }
}
