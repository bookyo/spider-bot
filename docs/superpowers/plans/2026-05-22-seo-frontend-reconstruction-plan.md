# SEO 前端重构 — 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 对 acg-video-frontend 进行 SEO 结构性重构，覆盖语义 HTML 骨架、结构化数据 JSON-LD、面包屑导航、内链优化、播放页 SSR 内容拆分

**架构：** 以 layout 层为中心扩展语义骨架，新增纯函数 JSON-LD 生成库，将播放页内容拆分到 Server Component 中渲染，新增相关推荐和内链组件。所有改动兼容现有 Tailwind 设计系统。

**技术栈：** Next.js 15 (App Router)、React 19、Tailwind CSS 3、TypeScript

**规格：** `docs/superpowers/specs/2026-05-22-seo-frontend-reconstruction-design.md`

---

## 文件变更总览

| 操作 | 文件 | 职责 |
|------|------|------|
| 新增 | `frontend/lib/json-ld.ts` | JSON-LD 生成函数库（WebSite/BreadcrumbList/VideoObject/ItemList） |
| 新增 | `frontend/components/breadcrumb.tsx` | 语义面包屑组件 + 同步 JSON-LD |
| 新增 | `frontend/components/site-header.tsx` | 语义化 Header + 导航栏 |
| 新增 | `frontend/components/site-footer.tsx` | Footer + 内链网络 |
| 新增 | `frontend/components/related-anime.tsx` | 播放页相关推荐 |
| 修改 | `frontend/app/layout.tsx` | 添加 Header/Footer/语义骨架 + WebSite JSON-LD |
| 修改 | `frontend/app/page.tsx` | 适配新 Layout，添加 ItemList JSON-LD |
| 修改 | `frontend/components/player-shell.tsx` | 简化接口，移除 SEO 相关元信息渲染 |
| 修改 | `frontend/app/play/[id]/page.tsx` | 拆分 SSR 内容，嵌入简化 PlayerShell |
| 修改 | `frontend/app/genre/[genre]/page.tsx` | 添加 ItemList JSON-LD |
| 修改 | `frontend/app/year/[year]/page.tsx` | 添加 ItemList JSON-LD |
| 修改 | `frontend/app/sitemap.ts` | 增大 page_size |
| 修改 | `frontend/next.config.ts` | 添加 images remotePatterns |

---

### 任务 1：JSON-LD 生成函数库

**文件：**
- 创建：`frontend/lib/json-ld.ts`

- [ ] **步骤 1：编写 `json-ld.ts` 中的 generateWebsiteJsonLd 函数**

```typescript
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
```

- [ ] **步骤 2：编写 `json-ld.ts` 中的 generateBreadcrumbJsonLd 函数**

```typescript
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

export function generateBreadcrumbJsonLd(items: Array<{ label: string; href?: string; }>): JsonLdBreadcrumbList {
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
```

- [ ] **步骤 3：编写 `json-ld.ts` 中的 generateVideoObjectJsonLd 函数**

```typescript
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
```

- [ ] **步骤 4：编写 `json-ld.ts` 中的 generateItemListJsonLd 函数**

```typescript
export interface JsonLdItemList {
  '@context': 'https://schema.org';
  '@type': 'ItemList';
  name: string;
  itemListElement: Array<{ '@type': 'ListItem'; position: number; url: string; }>;
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
```

- [ ] **步骤 5：验证 JSON-LD 函数输出**

新建临时验证脚本或在代码中确认：
```typescript
const website = generateWebsiteJsonLd('https://vbot.reelbit.cc');
JSON.parse(JSON.stringify(website)); // 应无报错
const breadcrumb = generateBreadcrumbJsonLd([{ label: '首页', href: '/' }, { label: '冒险' }]);
JSON.parse(JSON.stringify(breadcrumb)); // 应无报错
```

---

### 任务 2：面包屑组件

**文件：**
- 创建：`frontend/components/breadcrumb.tsx`

- [ ] **步骤 1：创建 Breadcrumb Server Component**

```tsx
import { generateBreadcrumbJsonLd } from '@/lib/json-ld';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  if (items.length <= 1) return null;

  const jsonLd = generateBreadcrumbJsonLd(items);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <nav aria-label="Breadcrumb" className="mb-4">
        <ol className="flex flex-wrap items-center gap-1.5 text-xs text-ash">
          {items.map((item, index) => {
            const isLast = index === items.length - 1;
            return (
              <li key={index} className="flex items-center gap-1.5">
                {index > 0 && (
                  <svg className="h-3 w-3 text-ash/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
                {item.href && !isLast ? (
                  <a href={item.href} className="transition hover:text-parchment">
                    {item.label}
                  </a>
                ) : (
                  <span className={isLast ? 'text-parchment/60' : 'text-ash'}>{item.label}</span>
                )}
              </li>
            );
          })}
        </ol>
      </nav>
    </>
  );
}
```

- [ ] **步骤 2：验证组件输出符合预期**

`npm run build` 无报错即可。

---

### 任务 3：Header + Footer 组件

**文件：**
- 创建：`frontend/components/site-header.tsx`
- 创建：`frontend/components/site-footer.tsx`

- [ ] **步骤 1：创建 SiteHeader Server Component**

```tsx
import Link from 'next/link';

export function SiteHeader() {
  return (
    <header className="border-b border-white/10 bg-coal/80 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-4 md:px-8 xl:px-10">
        <Link href="/" className="font-[var(--font-display)] text-xl uppercase tracking-[0.08em] text-parchment transition hover:text-ember">
          ACG Video Index
        </Link>
        <nav>
          <ul className="flex items-center gap-6 text-sm text-ash">
            <li>
              <Link href="/" className="transition hover:text-parchment">
                首页
              </Link>
            </li>
            <li>
              <Link href="/?keyword=" className="transition hover:text-parchment">
                搜索
              </Link>
            </li>
          </ul>
        </nav>
      </div>
    </header>
  );
}
```

- [ ] **步骤 2：创建 SiteFooter Server Component**

```tsx
import Link from 'next/link';
import { getAnimeFilters } from '@/lib/server-api';

async function SiteFooterInner() {
  let genres: string[] = [];
  let years: number[] = [];
  try {
    const filters = await getAnimeFilters();
    genres = filters.genres.slice(0, 15);
    years = filters.years.slice(0, 10);
  } catch {
    // 静默降级
  }

  return (
    <footer className="mt-20 border-t border-white/10 bg-coal">
      <div className="mx-auto max-w-[1600px] px-4 py-12 md:px-8 xl:px-10">
        <div className="grid gap-10 md:grid-cols-3">
          <div>
            <div className="font-[var(--font-display)] text-lg uppercase tracking-[0.08em] text-parchment">
              ACG Video Index
            </div>
            <p className="mt-3 text-sm leading-6 text-ash">
              收录可直接播放的动漫内容，支持分类、年份和片名快速筛选。
            </p>
          </div>

          {genres.length > 0 && (
            <div>
              <div className="mb-3 text-xs uppercase tracking-[0.24em] text-ash">分类</div>
              <div className="flex flex-wrap gap-2">
                {genres.map((genre) => (
                  <Link
                    key={genre}
                    href={`/genre/${encodeURIComponent(genre)}`}
                    className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-ash transition hover:border-ember/40 hover:text-parchment"
                  >
                    {genre}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {years.length > 0 && (
            <div>
              <div className="mb-3 text-xs uppercase tracking-[0.24em] text-ash">年份</div>
              <div className="flex flex-wrap gap-2">
                {years.map((year) => (
                  <Link
                    key={year}
                    href={`/year/${encodeURIComponent(String(year))}`}
                    className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-ash transition hover:border-ember/40 hover:text-parchment"
                  >
                    {year}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="mt-10 border-t border-white/5 pt-6 text-center text-xs text-ash/60">
          &copy; {new Date().getFullYear()} vbot.reelbit.cc
        </div>
      </div>
    </footer>
  );
}

export function SiteFooter() {
  return <SiteFooterInner />;
}
```

> **注意：** `SiteFooterInner` 是 async 函数直接导出会导致 Next.js 警告。这里用一个同步的 `SiteFooter` wrapper 导出，内部调用 `SiteFooterInner`（实际在 layout 中使用时会自动处理 async）。

---

### 任务 4：Layout 骨架重构

**文件：**
- 修改：`frontend/app/layout.tsx`

- [ ] **步骤 1：修改 layout.tsx，添加语义骨架 + 全局导航 + WebSite JSON-LD**

```tsx
import type { Metadata } from 'next';
import { Bebas_Neue, Noto_Sans_SC } from 'next/font/google';
import '@/app/globals.css';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { generateWebsiteJsonLd } from '@/lib/json-ld';

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';

const displayFont = Bebas_Neue({
  subsets: ['latin'],
  variable: '--font-display',
  weight: '400',
});

const bodyFont = Noto_Sans_SC({
  subsets: ['latin'],
  variable: '--font-body',
  weight: ['400', '500', '700'],
});

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: '视频机器人bot 自动收集视频',
    template: '%s - 视频机器人',
  },
  description: '视频机器人bot 自动收集视频，自动发现、自动补齐、自动播放。',
  applicationName: '视频机器人',
  category: 'entertainment',
  authors: [{ name: '视频机器人' }],
  creator: '视频机器人',
  publisher: '视频机器人',
  alternates: {
    canonical: '/',
  },
  openGraph: {
    type: 'website',
    locale: 'zh_CN',
    url: '/',
    siteName: '视频机器人',
    title: '视频机器人bot 自动收集视频',
    description: '视频机器人bot 自动收集视频，自动发现、自动补齐、自动播放。',
    images: [],
  },
  twitter: {
    card: 'summary_large_image',
    title: '视频机器人bot 自动收集视频',
    description: '视频机器人bot 自动收集视频，自动发现、自动补齐、自动播放。',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-image-preview': 'large',
      'max-snippet': -1,
      'max-video-preview': -1,
    },
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const websiteJsonLd = generateWebsiteJsonLd(siteUrl);

  return (
    <html lang="zh-CN" data-scroll-behavior="smooth">
      <body className={`${displayFont.variable} ${bodyFont.variable} bg-coal font-[var(--font-body)] text-parchment antialiased`}>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />
        <SiteHeader />
        <main>{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
```

> **变更要点：**
> - 包裹 `<SiteHeader />` + `<main>` + `<SiteFooter />`
> - `metadata` 中移除 `images: undefined` → `images: []`（避免 Next.js warning）
> - 注入 WebSite JSON-LD script
> - 子页面 `<main>` 需要改为 `<section>` 或 `<div>`

- [ ] **步骤 2：`npm run build` 确认编译通过**

---

### 任务 5：首页适配 + ItemList JSON-LD

**文件：**
- 修改：`frontend/app/page.tsx`

- [ ] **步骤 1：将首页的 `<main>` 改为 `<section>`，添加 ItemList JSON-LD**

在文件顶部的 import 部分追加：
```typescript
import { generateItemListJsonLd } from '@/lib/json-ld';
```

在 `return` 之前（`const [list, filters, stats]` 之后），生成 JSON-LD 数据：
```typescript
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
const itemListJsonLd = generateItemListJsonLd(
  keyword || genre || year ? '筛选结果' : '最新可播内容',
  list.data.map((anime) => ({
    url: `${siteUrl}/play/${anime._id}`,
  })),
);
```

将 `<main>` 改为 `<section>`（因为 layout 已提供 `<main>`）：
```diff
- <main className="min-h-screen bg-grain pb-20">
+ <section className="min-h-screen bg-grain pb-20">
```

在 `<section>` 内，任何位置（推荐在顶部）添加 JSON-LD:
```tsx
<script
  type="application/ld+json"
  dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListJsonLd) }}
/>
```

末尾 `</main>` → `</section>`。

- [ ] **步骤 2：`npm run build` 确认编译通过**

---

### 任务 6：相关推荐组件

**文件：**
- 创建：`frontend/components/related-anime.tsx`

- [ ] **步骤 1：创建 RelatedAnime Server Component**

```tsx
import Link from 'next/link';
import { AnimeCard } from '@/components/anime-card';
import { getAnimeList } from '@/lib/server-api';

interface RelatedAnimeProps {
  genres: string[];
  year?: number | null;
  excludeId: string;
}

export async function RelatedAnime({ genres, year, excludeId }: RelatedAnimeProps) {
  if (!genres?.length) return null;

  const params = new URLSearchParams({
    page: '1',
    page_size: '6',
    playable_only: 'true',
    sort_by: 'discovered_at',
    sort_order: 'desc',
  });

  // 用第一个分类找同类作品
  params.set('genre', genres[0]);

  // 可选：限定同年代 ±2 年
  if (year) {
    const rangeStart = year - 2;
    const rangeEnd = year + 2;
    params.set('year', `${rangeStart}-${rangeEnd}`);
  }

  try {
    const list = await getAnimeList(params);
    const related = list.data.filter((a) => a._id !== excludeId).slice(0, 4);

    if (related.length === 0) return null;

    return (
      <section className="mt-12">
        <h2 className="mb-4 text-xs uppercase tracking-[0.24em] text-ash">相关推荐</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {related.map((anime) => (
            <AnimeCard key={anime._id} anime={anime} />
          ))}
        </div>
        <div className="mt-6 text-center">
          <Link
            href={`/genre/${encodeURIComponent(genres[0])}`}
            className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-5 py-2.5 text-sm text-ash transition hover:border-white/20 hover:text-parchment"
          >
            浏览更多 {genres[0]} 作品
          </Link>
        </div>
      </section>
    );
  } catch {
    return null;
  }
}
```

- [ ] **步骤 2：`npm run build` 确认编译通过**

---

### 任务 7：PlayerShell 接口简化

**文件：**
- 修改：`frontend/components/player-shell.tsx`

- [ ] **步骤 1：简化 PlayerShell props 类型，移除 SEO 相关内容的渲染**

```diff
- export function PlayerShell({ anime }: { anime: AnimeDetail }) {
+ export interface PlayerShellProps {
+   id: string;
+   title: string;
+   posterUrl: string;
+   playSources: PlaySource[];
+ }
+
+ export function PlayerShell({ id, title, posterUrl, playSources }: PlayerShellProps) {
```

修改内部引用：
- 所有 `anime._id` → `id`
- 所有 `anime.title` → `title`
- 所有用于 poster 的 `resolvePosterUrl(anime.poster_local, anime.poster_url)` → `posterUrl`
- 所有 `anime.play_sources` → `playSources`

**移除整个 aside 侧边栏**（第 223-291 行，Poster 展示 + 元信息 + 评分 + 分类 + synopsis），这些移到 page.tsx 的 Server Component 中。

**保留**：
- 视频播放器
- 播放源切换
- 选集列表
- "返回首页" 链接（可考虑移到 page.tsx）

- [ ] **步骤 2：验证简化后的 PlayerShell 编译通过**

```bash
npm run build
```

---

### 任务 8：播放页 SSR 重构

**文件：**
- 修改：`frontend/app/play/[id]/page.tsx`

- [ ] **步骤 1：重构 play/[id]/page.tsx，拆分为 Server 渲染 + Client 播放器**

```tsx
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
    const poster = resolvePosterUrl(anime.poster_local, anime.poster_url);
    const firstEpisodeUrl = anime.play_sources?.[0]?.episodes?.[0]?.url || undefined;

    const breadcrumbItems = [
      { label: '首页', href: '/' },
      ...(anime.genres?.[0] ? [{ label: anime.genres[0], href: `/genre/${encodeURIComponent(anime.genres[0])}` }] : []),
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
          <Link href="/" className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-parchment/80 transition hover:border-white/20 hover:text-parchment">
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
          <RelatedAnime
            genres={anime.genres}
            year={anime.year}
            excludeId={anime._id}
          />
        </div>
      </>
    );
  } catch {
    notFound();
  }
}
```

> **关键变更：**
> - H1、年份、synopsis 现在在 Server Component 中渲染 → 对搜索引擎可见
> - Breadcrumb 组件的 SSR 输出包含 JSON-LD
> - VideoObject JSON-LD 在服务端注入
> - PlayerShell 的接口被简化，只接收播放必需字段
> - sidebar（侧边栏元信息）由于视觉复杂度，简化为只在基本信息区展示

- [ ] **步骤 2：`npm run build` 确认编译通过**

---

### 任务 9：分类/年份页 JSON-LD

**文件：**
- 修改：`frontend/app/genre/[genre]/page.tsx`
- 修改：`frontend/app/year/[year]/page.tsx`

- [ ] **步骤 1：在分类页添加 ItemList JSON-LD**

在 `GenrePage` 函数中，获取 `list` 和 `filters` 之后，`return` 之前添加：

```typescript
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
const itemListJsonLd = generateItemListJsonLd(
  `${decodedGenre} 分类动漫`,
  list.data.map((a) => ({ url: `${siteUrl}/play/${a._id}` })),
);
```

在 `return` 的 JSX 中，`<main>` 内顶部添加：
```tsx
<script
  type="application/ld+json"
  dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListJsonLd) }}
/>
```

需要 import:
```typescript
import { generateItemListJsonLd } from '@/lib/json-ld';
```

`AnimeListPage` 组件内部需要调整：在 `AnimeListPage` 函数中接收并渲染 `itemListJsonLd`，或者在 `GenrePage` 中通过 prop 传递。

更简单的方式：**在 `AnimeListPage` 组件内部生成 ItemList JSON-LD**，避免改动 props 接口。

修改 `components/anime-list-page.tsx`：在 JSX 中添加：
```tsx
<script
  type="application/ld+json"
  dangerouslySetInnerHTML={{
    __html: JSON.stringify(generateItemListJsonLd('筛选结果', list.data.map(a => ({ url: `${siteUrl}/play/${a._id}` }))))
  }}
/>
```

- [ ] **步骤 2：同样在年份页添加 ItemList JSON-LD**

与步骤 1 相同。如果改为在 `AnimeListPage` 内部统一处理，则一步覆盖分类页和年份页。

- [ ] **步骤 3：`npm run build` 确认编译通过**

---

### 任务 10：Sitemap 扩展 + next.config 配置

**文件：**
- 修改：`frontend/app/sitemap.ts`
- 修改：`frontend/next.config.ts`

- [ ] **步骤 1：扩大 sitemap page_size**

```diff
- const response = await fetch(`${apiBase}/api/anime?playable_only=true&page=1&page_size=200&sort_by=discovered_at&sort_order=desc`, {
+ const response = await fetch(`${apiBase}/api/anime?playable_only=true&page=1&page_size=1000&sort_by=discovered_at&sort_order=desc`, {
```

- [ ] **步骤 2：添加 images 配置到 next.config.ts**

```typescript
import type { NextConfig } from 'next';
import path from 'node:path';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, '..'),
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
};

export default nextConfig;
```

- [ ] **步骤 3：`npm run build` 确认编译通过**

---

## 4. 不纳入本实现计划

- 独立搜索页面 `/search`
- `/genre/[genre]/year/[year]` 组合路由
- `next/image` 海报优化（PosterImage 组件到 `next/image` 迁移）
- `/about` / `/privacy` 信任页面
- Sitemap index 分页（当数据量超过 50,000 条时再考虑）
