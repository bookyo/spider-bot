import {
  generateBreadcrumbJsonLd,
  generateVideoObjectJsonLd,
} from './json-ld';

function assert(condition: unknown, message: string) {
  if (!condition) {
    throw new Error(message);
  }
}

const breadcrumb = generateBreadcrumbJsonLd([
  { label: '首页', href: 'https://example.com/' },
  { label: '剧情', href: 'https://example.com/genre/%E5%89%A7%E6%83%85' },
  { label: '测试视频' },
]);

assert(breadcrumb['@type'] === 'BreadcrumbList', 'breadcrumb type');
assert(
  breadcrumb.itemListElement[1]?.item === 'https://example.com/genre/%E5%89%A7%E6%83%85',
  'breadcrumb item url',
);

const videoObject = generateVideoObjectJsonLd({
  name: '测试视频',
  description: '这是一个用于测试的简介',
  thumbnailUrl: 'https://example.com/poster.jpg',
  url: 'https://example.com/play/abc',
  embedUrl: 'https://example.com/play/abc',
  contentUrl: 'https://cdn.example.com/test.m3u8',
  uploadDate: '2026-05-22T12:00:00.000Z',
  author: '测试导演',
  genre: ['剧情'],
});

assert(videoObject['@type'] === 'VideoObject', 'video object type');
assert(videoObject.url === 'https://example.com/play/abc', 'video object url');
assert(videoObject.embedUrl === 'https://example.com/play/abc', 'video object embed url');
assert(videoObject.uploadDate === '2026-05-22T12:00:00.000Z', 'video object uploadDate');
assert(Array.isArray(videoObject.thumbnailUrl), 'video object thumbnail array');
assert(videoObject.author?.['@type'] === 'Person', 'video object author type');
