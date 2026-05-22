// 1. WebSite + SearchAction
export interface JsonLdWebSite {
  '@context': 'https://schema.org';
  '@type': 'WebSite';
  url: string;
  potentialAction: {
    '@type': 'SearchAction';
    target: {
      '@type': 'EntryPoint';
      urlTemplate: string;
    };
    'query-input': 'required name=search_term_string';
  };
}

export function generateWebsiteJsonLd(siteUrl: string): JsonLdWebSite {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    url: siteUrl,
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${siteUrl}/?keyword={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  };
}

// 2. BreadcrumbList
export interface JsonLdBreadcrumbItem {
  '@type': 'ListItem';
  position: number;
  name: string;
  item?: string;
}

export interface JsonLdBreadcrumbList {
  '@context': 'https://schema.org';
  '@type': 'BreadcrumbList';
  itemListElement: JsonLdBreadcrumbItem[];
}

export function generateBreadcrumbJsonLd(items: Array<{ label: string; href?: string }>): JsonLdBreadcrumbList {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.label,
      ...(item.href ? { item: item.href } : {}),
    })),
  };
}

// 3. VideoObject
export interface JsonLdVideoObject {
  '@context': 'https://schema.org';
  '@type': 'VideoObject';
  name: string;
  description: string;
  thumbnailUrl: string;
  contentUrl?: string;
  duration?: string;
  datePublished?: string;
  author?: string;
  genre?: string[];
}

export function generateVideoObjectJsonLd(params: {
  name: string;
  description: string;
  thumbnailUrl: string;
  contentUrl?: string;
  datePublished?: string;
  author?: string;
  genre?: string[];
}): JsonLdVideoObject {
  const result: JsonLdVideoObject = {
    '@context': 'https://schema.org',
    '@type': 'VideoObject',
    name: params.name,
    description: params.description?.slice(0, 500) || '',
    thumbnailUrl: params.thumbnailUrl,
  };
  if (params.contentUrl) result.contentUrl = params.contentUrl;
  if (params.datePublished) result.datePublished = params.datePublished;
  if (params.author) result.author = params.author;
  if (params.genre?.length) result.genre = params.genre;
  return result;
}

// 4. ItemList
export interface JsonLdItemList {
  '@context': 'https://schema.org';
  '@type': 'ItemList';
  name: string;
  itemListElement: Array<{ '@type': 'ListItem'; position: number; url: string }>;
}

export function generateItemListJsonLd(name: string, items: Array<{ url: string }>): JsonLdItemList {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name,
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      url: item.url,
    })),
  };
}

// 5. 校验工具
export function validateJsonLd(obj: unknown): boolean {
  try {
    JSON.parse(JSON.stringify(obj));
    return true;
  } catch {
    return false;
  }
}
