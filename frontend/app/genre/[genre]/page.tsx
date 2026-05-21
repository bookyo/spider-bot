import type { Metadata } from 'next';
import Link from 'next/link';
import { AnimeListPage } from '@/components/anime-list-page';

interface Props {
  params: Promise<{ genre: string }>;
  searchParams: Promise<{ page?: string; keyword?: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { genre } = await params;
  const decodedGenre = decodeURIComponent(genre);
  const displayTitle = `${decodedGenre} 分类动漫`;
  const displayDescription = `浏览${decodedGenre}分类的可播放动漫，按片名、年份快速筛选，海量资源在线点播。`;
  const canonicalGenre = encodeURIComponent(decodedGenre);

  return {
    title: displayTitle,
    description: displayDescription,
    alternates: {
      canonical: `/genre/${canonicalGenre}`,
    },
    openGraph: {
      title: displayTitle,
      description: displayDescription,
      url: `/genre/${canonicalGenre}`,
    },
    twitter: {
      title: displayTitle,
      description: displayDescription,
    },
  };
}

export const revalidate = 3600;

export default async function GenrePage({ params, searchParams }: Props) {
  const { genre } = await params;
  const sp = await searchParams;
  const decodedGenre = decodeURIComponent(genre);
  const page = Number(sp.page || 1);
  const keyword = sp.keyword || '';
  const baseGenrePath = `/genre/${encodeURIComponent(decodedGenre)}`;

  return (
    <AnimeListPage
      genre={decodedGenre}
      keyword={keyword}
      page={page}
      basePath={baseGenrePath}
      heading={
        <>
          分类{' '}
          <Link href="/" className="text-ash/60 transition hover:text-ember">
            ·
          </Link>{' '}
          <span className="text-ember">{decodedGenre}</span>
        </>
      }
      subheading={`浏览「${decodedGenre}」分类下所有可播放动漫，支持按年份和片名进一步筛选。`}
    />
  );
}
