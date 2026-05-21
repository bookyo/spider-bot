import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { PlayerShell } from '@/components/player-shell';
import { resolvePosterUrl } from '@/lib/api';
import { getAnimeDetail } from '@/lib/server-api';

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
    const metaDescription =
      anime.synopsis
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
    return (
      <>
        <div className="mx-auto w-full max-w-[1600px] px-4 pt-4 md:px-8 xl:px-10">
          <Link href="/" className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-parchment/80 transition hover:border-white/20 hover:text-parchment">
            返回首页
          </Link>
        </div>
        <PlayerShell anime={anime} />
      </>
    );
  } catch {
    notFound();
  }
}
