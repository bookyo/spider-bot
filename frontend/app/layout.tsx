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
    default: 'Video Hub - 在线视频聚合',
    template: '%s - Video Hub',
  },
  description: '聚合多源在线视频，自动发现、自动补齐、免登录在线播放。',
  applicationName: 'Video Hub',
  category: 'entertainment',
  authors: [{ name: 'Video Hub' }],
  creator: 'Video Hub',
  publisher: 'Video Hub',
  alternates: {
    canonical: '/',
  },
  openGraph: {
    type: 'website',
    locale: 'zh_CN',
    url: '/',
    siteName: 'Video Hub',
    title: 'Video Hub - 在线视频聚合',
    description: '聚合多源在线视频，自动发现、自动补齐、免登录在线播放。',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Video Hub - 在线视频聚合',
    description: '聚合多源在线视频，自动发现、自动补齐、免登录在线播放。',
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
