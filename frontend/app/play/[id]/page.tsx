import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { PlayerShell } from '@/components/player-shell';
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
    const description = `${title} - 免费在线观看online - 视频机器人`;
    const poster = anime.poster_local || anime.poster_url || '';
    const images = poster ? [{ url: poster }] : undefined;
    return {
      title: `${title} - 免费在线观看online - 视频机器人`,
      description,
      alternates: {
        canonical: `/play/${id}`,
      },
      openGraph: {
        type: 'video.other',
        title: `${title} - 免费在线观看online - 视频机器人`,
        description,
        url: `/play/${id}`,
        images,
      },
      twitter: {
        card: 'summary_large_image',
        title: `${title} - 免费在线观看online - 视频机器人`,
        description,
        images: poster ? [poster] : undefined,
      },
    };
  } catch {
    return {
      title: '免费在线观看online - 视频机器人',
      description: '免费在线观看online - 视频机器人',
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
