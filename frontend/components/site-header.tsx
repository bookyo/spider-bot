import Link from 'next/link';

export function SiteHeader() {
  return (
    <header className="border-b border-white/10 bg-coal/80 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-4 md:px-8 xl:px-10">
        <Link
          href="/"
          className="font-[var(--font-display)] text-xl uppercase tracking-[0.08em] text-parchment transition hover:text-ember"
        >
          Video Hub
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
