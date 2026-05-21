import type { Metadata } from 'next';
import Link from 'next/link';
import { AnimeListPage } from '@/components/anime-list-page';

interface Props {
  params: Promise<{ year: string }>;
  searchParams: Promise<{ page?: string; keyword?: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { year } = await params;
  const displayTitle = `${year} 年动漫`;
  const displayDescription = `浏览${year}年的可播放动漫，按分类、片名快速筛选，海量资源在线点播。`;

  return {
    title: displayTitle,
    description: displayDescription,
    alternates: {
      canonical: `/year/${encodeURIComponent(year)}`,
    },
    openGraph: {
      title: displayTitle,
      description: displayDescription,
      url: `/year/${encodeURIComponent(year)}`,
    },
    twitter: {
      title: displayTitle,
      description: displayDescription,
    },
  };
}

export const revalidate = 3600;

export default async function YearPage({ params, searchParams }: Props) {
  const { year } = await params;
  const sp = await searchParams;
  const page = Number(sp.page || 1);
  const keyword = sp.keyword || '';

  return (
    <AnimeListPage
      year={year}
      keyword={keyword}
      page={page}
      basePath={`/year/${encodeURIComponent(year)}`}
      heading={
        <>
          年份{' '}
          <Link href="/" className="text-ash/60 transition hover:text-ember">
            ·
          </Link>{' '}
          <span className="text-ember">{year}</span>
        </>
      }
      subheading={`浏览 ${year} 年所有可播放动漫，支持按分类和片名进一步筛选。`}
    />
  );
}
