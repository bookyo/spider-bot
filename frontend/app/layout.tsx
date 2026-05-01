import type { Metadata } from 'next';
import { Bebas_Neue, Noto_Sans_SC } from 'next/font/google';
import '@/app/globals.css';

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
  title: {
    default: '视频机器人bot 自动收集视频',
    template: '%s',
  },
  description: '视频机器人bot 自动收集视频',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" data-scroll-behavior="smooth">
      <body className={`${displayFont.variable} ${bodyFont.variable} bg-coal font-[var(--font-body)] text-parchment antialiased`}>
        {children}
      </body>
    </html>
  );
}
