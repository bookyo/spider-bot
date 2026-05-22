import type { MetadataRoute } from 'next';

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
const apiBase = process.env.API_BASE_URL || 'http://127.0.0.1:8000';
const internalApiKey = process.env.INTERNAL_API_KEY || '';

async function fetchAnimeIds() {
  try {
    const response = await fetch(`${apiBase}/api/anime?playable_only=true&page=1&page_size=10000&sort_by=discovered_at&sort_order=desc`, {
      headers: internalApiKey ? { 'x-api-key': internalApiKey } : undefined,
      next: { revalidate: 300 },
    });
    if (!response.ok) {
      return [];
    }
    const payload = await response.json();
    return Array.isArray(payload?.data) ? payload.data : [];
  } catch {
    return [];
  }
}

async function fetchFilterOptions() {
  try {
    const response = await fetch(`${apiBase}/api/anime/filters?playable_only=true`, {
      headers: internalApiKey ? { 'x-api-key': internalApiKey } : undefined,
      next: { revalidate: 600 },
    });
    if (!response.ok) {
      return { genres: [], years: [] };
    }
    return response.json() as Promise<{ genres: string[]; years: number[] }>;
  } catch {
    return { genres: [], years: [] };
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [animeList, filterOptions] = await Promise.all([fetchAnimeIds(), fetchFilterOptions()]);

  const animeUrls = animeList.map((item: { _id: string; updated_at?: string | null }) => ({
    url: `${siteUrl}/play/${item._id}`,
    lastModified: item.updated_at ? new Date(item.updated_at) : new Date(),
    changeFrequency: 'weekly' as const,
    priority: 0.8,
  }));

  const genreUrls = filterOptions.genres.map((genre: string) => ({
    url: `${siteUrl}/genre/${encodeURIComponent(genre)}`,
    lastModified: new Date(),
    changeFrequency: 'daily' as const,
    priority: 0.7,
  }));

  const yearUrls = filterOptions.years.map((year: number) => ({
    url: `${siteUrl}/year/${encodeURIComponent(String(year))}`,
    lastModified: new Date(),
    changeFrequency: 'daily' as const,
    priority: 0.7,
  }));

  return [
    {
      url: `${siteUrl}/`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1,
    },
    ...genreUrls,
    ...yearUrls,
    ...animeUrls,
  ];
}
