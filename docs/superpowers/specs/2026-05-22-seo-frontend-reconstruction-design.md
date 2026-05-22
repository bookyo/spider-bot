# SEO 前端重构设计方案

- **项目**: spider-for-acg / acg-video-frontend
- **日期**: 2026-05-22
- **域名**: vbot.reelbit.cc
- **方案**: 结构性重构（方案 B）
- **范围**: 全栈实现

---

## 1. 当前状态与问题

### 已覆盖的 SEO 基础 ✅
- SSR 页面架构（Next.js App Router）
- 基础 Metadata / OpenGraph / Twitter Cards
- Robots.txt + Sitemap.xml
- 语言声明 `zh-CN`
- `generateMetadata` 动态 meta
- ISR (`revalidate`) 策略

### 关键缺失 ❌
- **结构化数据 (JSON-LD)**: 无 VideoObject、BreadcrumbList、WebSite 标记
- **语义 HTML 骨架**: 无 `<header>`/`<nav>`/`<footer>` 语义标签
- **面包屑导航**: 所有页面都没有
- **播放页内容在客户端渲染**: H1、简介、剧集列表在 Client Component 中，搜索引擎抓不到
- **无网站导航栏**: 用户无法在页面间跳转
- **无相关推荐内链**: 内部链接矩阵缺失
- **Sitemap 只取 200 条**: 超过 200 部动漫不会被 sitemap 收录
- **使用原生 `<img>`**: 而非 `next/image`，无自动优化
- **缺少 `next.config.ts` 配置**: 无 images / headers 配置

---

## 2. 设计方案

### 2.1 语义 HTML 骨架 + 全局导航

#### Layout 层修改

**当前结构:**
```html
<body>
  {children}
</body>
```

**改造后结构:**
```html
<body>
  <header>
    <nav>
      <a href="/">vbot.reelbit.cc</a>
      <a href="/">首页</a>
      <a href="/?keyword=">搜索</a>
    </nav>
  </header>

  <main>{children}</main>

  <footer>
    <div>© vbot.reelbit.cc</div>
    <nav>分类链接、年份链接、About</nav>
  </footer>
</body>
```

#### 新增组件

**`components/site-header.tsx`** (Server Component)
- 左侧：站点名 logo（链接到首页）
- 右侧：导航链接
- 响应式：小屏折叠

**`components/site-footer.tsx`** (Server Component)
- 版权信息
- 分类链接网格（来自 `getAnimeFilters()`）
- 年份链接列表
- About 链接

#### Layout.tsx 改动
- 包裹 `<Header>` + `<main>` + `<Footer>`
- 各页面当前的 `<main>` 改为内层 `<section>` 或 `<div>`
- 注入 WebSite JSON-LD

---

### 2.2 播放页 SSR 内容拆分

#### 问题
`play/[id]/page.tsx` 只返回 `<PlayerShell />`（Client Component），H1、synopsis、评分、元信息全部在客户端渲染。

#### 拆分方案

**改造后结构:**
```
play/[id]/page.tsx (Server Component)
  ├── <Breadcrumb items={...} />
  ├── <article>
  │     ├── <h1>{anime.title}</h1>
  │     ├── <p>年份 / 导演 / 评分 / 分类</p>
  │     ├── <p>{anime.synopsis}</p>
  │     └── <script type="application/ld+json">VideoObject</script>
  ├── <PlayerShell>  ← 只保留播放器和选集交互
  │     ├── <video />
  │     └── 线路切换 / 选集列表
  └── <RelatedAnime genres={...} year={...} />
```

**PlayerShell 接口简化:**
```tsx
// 当前: 接收完整 AnimeDetail
// 改造后: 只接收播放必需字段
interface PlayerShellProps {
  id: string;
  title: string;
  poster: string;
  playSources: PlaySource[];
}

function PlayerShell({ id, title, poster, playSources }: PlayerShellProps) {
  // 视频播放 + 线路切换 + 选集选择
}
```

---

### 2.3 结构化数据 JSON-LD

新增 `lib/json-ld.ts`，包含纯函数生成各类型 JSON-LD。

#### WebSite + SearchAction（Layout 层，所有页面）
```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "url": "https://vbot.reelbit.cc",
  "potentialAction": {
    "@type": "SearchAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "https://vbot.reelbit.cc/?keyword={search_term_string}"
    },
    "query-input": "required name=search_term_string"
  }
}
```

#### BreadcrumbList（所有页面，与 Breadcrumb 组件同步）
```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "首页", "item": "https://vbot.reelbit.cc/" },
    { "@type": "ListItem", "position": 2, "name": "冒险", "item": "https://vbot.reelbit.cc/genre/%E5%86%92%E9%99%A9" },
    { "@type": "ListItem", "position": 3, "name": "钢之炼金术师" }
  ]
}
```

#### VideoObject（播放页）

> `duration` 字段为可选：当前后端未提供片长数据，若无则不在 JSON-LD 中输出。
> `contentUrl` 取第一个可播放剧集的 URL，若无可用剧集则略过该字段。

```json
{
  "@context": "https://schema.org",
  "@type": "VideoObject",
  "name": "{anime.title}",
  "description": "{anime.synopsis}",
  "thumbnailUrl": "{poster}",
  "contentUrl": "{firstPlayableEpisodeUrl}",
  "duration": "{durationIfAvailable}",
  "datePublished": "{anime.year}",
  "author": "{anime.director}",
  "genre": ["{genres}"]
}
```

#### ItemList（首页、分类页、年份页）
```json
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "最新可播内容",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "url": "/play/{id1}" },
    { "@type": "ListItem", "position": 2, "url": "/play/{id2}" }
  ]
}
```

---

### 2.4 面包屑导航

新增 `components/breadcrumb.tsx`（Server Component）。

```tsx
interface BreadcrumbItem {
  label: string;
  href?: string;  // 最后一项无 href（当前页）
}

function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  // 视觉: <nav aria-label="Breadcrumb"><ol><li>...
  // JSON-LD: 同步注入 BreadcrumbList script tag
}
```

**各页面面包屑路径:**

| 页面 | 面包屑 |
|------|--------|
| 首页 `/` | 首页 |
| 分类页 `/genre/冒险` | 首页 > 冒险 |
| 年份页 `/year/2024` | 首页 > 2024年 |
| 播放页 `/play/xxx` | 首页 > 分类 > 片名 |
| 播放页（无分类）| 首页 > 视频 |

---

### 2.5 内链优化 + 相关推荐

#### Footer 链接网络（components/site-footer.tsx）
- 除版权信息外，渲染分类和年份链接
- 分类列表：从 `getAnimeFilters().genres` 获取
- 年份列表：从 `getAnimeFilters().years` 获取
- 出现在所有页面 → 爬虫可以从任意页面发现全站内容

#### 播放页相关推荐（components/related-anime.tsx，Server Component）
- 从当前动漫的 `genres` 和 `year` 构造 API 查询
- 返回同类型作品 4-6 个
- 复用 `AnimeCard` 组件
- 显示在 PlayerShell 下方

---

### 2.6 Sitemap 扩展 + 配置优化

#### sitemap.ts
- 增大 `page_size` 到 1000（或后端支持的最大值）
- 如有大量数据，使用 sitemap index 拆分

#### next.config.ts
```ts
const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' }, // 根据实际 poster 域名调整
    ],
  },
};
```

---

### 2.7 测试策略

1. **SSR 输出验证**: `curl <page> | grep` 确认 H1、synopsis、JSON-LD、breadcrumb 出现在初始 HTML
2. **JSON-LD 格式校验**: 所有 `<script type="application/ld+json">` 内容为合法 JSON
3. **功能回归**: 播放、选集切换、过滤搜索、分页功能无退化
4. **构建验证**: `npm run build` 编译无报错

---

## 3. 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `frontend/app/layout.tsx` | 添加 Header/Footer、语义标签 |
| 修改 | `frontend/app/page.tsx` | 移除独立 `<main>`，添加 ItemList JSON-LD |
| 修改 | `frontend/app/play/[id]/page.tsx` | 拆分 SSR 内容 + PlayerShell 接口简化 |
| 修改 | `frontend/app/genre/[genre]/page.tsx` | 添加 ItemList JSON-LD |
| 修改 | `frontend/app/year/[year]/page.tsx` | 添加 ItemList JSON-LD |
| 修改 | `frontend/app/sitemap.ts` | 扩展 page_size |
| 修改 | `frontend/next.config.ts` | 添加 images 配置 |
| 新增 | `frontend/components/site-header.tsx` | 语义化 Header + 导航 |
| 新增 | `frontend/components/site-footer.tsx` | Footer + 内链网格 |
| 新增 | `frontend/components/breadcrumb.tsx` | 面包屑组件 |
| 新增 | `frontend/components/related-anime.tsx` | 相关推荐 |
| 新增 | `frontend/lib/json-ld.ts` | JSON-LD 生成函数 |
| 修改 | `frontend/components/player-shell.tsx` | 简化接口，移除 SEO 相关内容 |
| 新增 | `frontend/components/anime-info.tsx` | (可选) 播放页元信息 Server Component |

---

## 4. 不纳入本次范围

- `/search` 独立搜索页面（方案 C）
- `/genre/[genre]/year/[year]` 组合路由（方案 C）
- `next/image` 海报优化（方案 C，需大量改动 PosterImage 组件）
- `/about` / `/privacy` 信任页面（方案 C）
- Sitemap index 分页（视数据量而定，若 < 50000 条则单文件足够）
