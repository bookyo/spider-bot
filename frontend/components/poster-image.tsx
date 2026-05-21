'use client';

import { useState, useRef, useEffect } from 'react';

interface PosterImageProps {
  src: string;
  alt: string;
  imgClassName?: string;
}

export function PosterImage({ src, alt, imgClassName = '' }: PosterImageProps) {
  const [loaded, setLoaded] = useState(false);
  const [errored, setErrored] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  // 如果图片已在浏览器缓存中（complete），直接标记已加载
  useEffect(() => {
    if (imgRef.current?.complete) {
      setLoaded(true);
    }
  }, []);

  if (!src || errored) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-white/5 text-sm text-ash">
        暂无海报
      </div>
    );
  }

  return (
    <div className="relative h-full w-full overflow-hidden">
      {/* 占位——图片加载前显示，加载后渐隐 */}
      <div
        className={`absolute inset-0 flex items-center justify-center bg-white/5 text-sm text-ash transition-opacity duration-300 ${loaded ? 'pointer-events-none opacity-0' : 'opacity-100'}`}
      >
        暂无海报
      </div>
      {/* 图片——加载后渐入 */}
      <img
        ref={imgRef}
        src={src}
        alt={alt}
        loading="lazy"
        className={`h-full w-full object-cover transition duration-500 ${loaded ? 'opacity-100' : 'opacity-0'} ${imgClassName}`}
        onLoad={() => setLoaded(true)}
        onError={() => setErrored(true)}
      />
    </div>
  );
}
