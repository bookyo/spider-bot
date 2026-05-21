import type { Metadata } from 'next';
import Link from 'next/link';
import { AnimeListPage } from '@/components/anime-list-page';

interface Props {
  params: Promise<{ genre: string; year: string }>;
  searchParams: Promise<{ page?: string; keyword?: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { genre, year } = await params;
  const decodedGenre = decodeURIComponent(genre);
  const displayTitle = `${year} 年 ${decodedGenre} 动漫`;
  const displayDescription = `浏览${year}年「${decodedGenre}」分类的可播放动漫，按片名快速筛选，海量资源在线点播。`;
  const canonicalGenre = encodeURIComponent(decodedGenre);
  const canonicalYear = encodeURIComponent(year);

  return {
    title: displayTitle,
    description: displayDescription,
    alternates: {
      canonical: `/genre/${canonicalGenre}/year/${canonicalYear}`,
    },
    openGraph: {
      title: displayTitle,
      description: displayDescription,
      url: `/genre/${canonicalGenre}/year/${canonicalYear}`,
    },
    twitter: {
      title: displayTitle,
      description: displayDescription,
    },
  };
}

export const revalidate = 3600;

export default async function GenreYearPage({ params, searchParams }: Props) {
  const { genre, year } = await params;
  const sp = await searchParams;
  const decodedGenre = decodeURIComponent(genre);
  const page = Number(sp.page || 1);
  const keyword = sp.keyword || '';
  const basePath = `/genre/${encodeURIComponent(decodedGenre)}/year/${encodeURIComponent(year)}`;

  return (
    <AnimeListPage
      genre={decodedGenre}
      year={year}
      keyword={keyword}
      page={page}
      basePath={basePath}
      heading={
        <>
          <span className="text-ember">{decodedGenre}</span>{' '}
          <Link href="/" className="text-ash/60 transition hover:text-ember">
            ·
          </Link>{' '}
          <span className="text-parchment/60">{year}</span>
        </>
      }
      subheading={`浏览 ${year} 年「${decodedGenre}」分类下所有可播放动漫，支持按片名进一步筛选。`}
    />
  );
}
