import type { MetadataRoute } from 'next';

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
const apiBase = process.env.API_BASE_URL || 'http://127.0.0.1:8000';
const internalApiKey = process.env.INTERNAL_API_KEY || '';

async function fetchAnimeIds() {
  try {
    const response = await fetch(`${apiBase}/api/anime?playable_only=true&page=1&page_size=200&sort_by=discovered_at&sort_order=desc`, {
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

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const animeList = await fetchAnimeIds();
  const animeUrls = animeList.map((item: { _id: string; updated_at?: string | null }) => ({
    url: `${siteUrl}/play/${item._id}`,
    lastModified: item.updated_at ? new Date(item.updated_at) : new Date(),
    changeFrequency: 'weekly' as const,
    priority: 0.8,
  }));

  return [
    {
      url: `${siteUrl}/`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1,
    },
    ...animeUrls,
  ];
}
