import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '管理台',
  description: 'Video Hub 管理台',
  robots: {
    index: false,
    follow: false,
  },
};

export default function AdminLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
