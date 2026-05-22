import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-grain px-4">
      <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-10 text-center shadow-card">
        <div className="font-[var(--font-display)] text-6xl uppercase text-ember">404</div>
        <h1 className="mt-4 text-2xl font-semibold text-parchment">没有找到这个页面</h1>
        <p className="mt-3 text-sm leading-7 text-ash">这个视频可能已经被删除，或者当前 ID 不存在。</p>
        <Link href="/" className="mt-6 inline-flex rounded-full bg-ember px-5 py-3 text-sm font-semibold text-black">
          返回首页
        </Link>
      </div>
    </main>
  );
}
