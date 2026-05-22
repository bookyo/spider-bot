import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { PlayerShell } from '@/components/player-shell';
import { Breadcrumb } from '@/components/breadcrumb';
import { RelatedAnime } from '@/components/related-anime';
import { resolvePosterUrl } from '@/lib/api';
import { getAnimeDetail } from '@/lib/server-api';
import { generateBreadcrumbJsonLd, generateVideoObjectJsonLd } from '@/lib/json-ld';
import { stripHtmlToText } from '@/lib/text';

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
    const cleanSynopsis = stripHtmlToText(anime.synopsis);
    const metaDescription = cleanSynopsis
      ? cleanSynopsis.slice(0, 120)
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
    const cleanSynopsis = stripHtmlToText(anime.synopsis);
    const firstEpisodeUrl = anime.play_sources?.[0]?.episodes?.[0]?.url || undefined;
    const canonicalUrl = `/play/${id}`;
    const publishedDate = anime.year ? `${anime.year}-01-01` : undefined;

    const breadcrumbItems = [
      { label: '首页', href: '/' },
      ...(anime.genres?.[0]
        ? [{ label: anime.genres[0], href: `/genre/${encodeURIComponent(anime.genres[0])}` }]
        : []),
      { label: anime.title || '视频' },
    ];
    const breadcrumbJsonLd = generateBreadcrumbJsonLd(breadcrumbItems);

    const videoObjectJsonLd = generateVideoObjectJsonLd({
      name: anime.title || '',
      description: cleanSynopsis,
      thumbnailUrl: poster || '',
      url: canonicalUrl,
      embedUrl: canonicalUrl,
      contentUrl: firstEpisodeUrl,
      uploadDate: anime.updated_at || anime.discovered_at || undefined,
      datePublished: publishedDate,
      author: anime.director || undefined,
      genre: anime.genres || undefined,
    });

    return (
      <>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(videoObjectJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
        />

        <div className="mx-auto w-full max-w-[1600px] px-4 pt-4 md:px-8 xl:px-10">
          <Breadcrumb items={breadcrumbItems} />
        </div>

        <div className="mx-auto w-full max-w-[1600px] px-4 pt-6 md:px-8 xl:px-10">
          <PlayerShell
            id={anime._id}
            title={anime.title}
            originalTitle={anime.original_title}
            posterUrl={poster || ''}
            year={anime.year}
            director={anime.director}
            doubanRating={anime.douban_rating}
            imdbRating={anime.imdb_rating}
            genres={anime.genres}
            totalEpisodeCount={anime.total_episode_count}
            playSources={anime.play_sources}
          />
        </div>

        <div className="mx-auto w-full max-w-[1600px] px-4 pt-5 md:px-8 xl:px-10">
          <section className="rounded-[24px] border border-white/10 bg-white/[0.04] p-5 shadow-card md:rounded-[28px] md:p-6">
            <div className="max-w-5xl">
              <div className="text-[11px] uppercase tracking-[0.26em] text-ash">作品简介</div>
              <h1 className="mt-3 text-2xl font-semibold leading-tight text-parchment md:text-3xl">
                {anime.title || '未命名作品'}
              </h1>
              {anime.original_title && anime.original_title !== anime.title ? (
                <p className="mt-2 break-all text-sm text-ash">{anime.original_title}</p>
              ) : null}
              <p className="mt-4 text-sm leading-8 text-parchment/76 md:text-base md:leading-8">
                {cleanSynopsis || '暂无简介'}
              </p>
            </div>
          </section>
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
