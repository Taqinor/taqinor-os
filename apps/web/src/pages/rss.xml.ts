/**
 * GET /rss.xml — flux RSS 2.0 du blog (W132), fabriqué à la main.
 *
 * AUCUNE dépendance (@astrojs/rss volontairement écarté) : on lit la collection
 * `blog` via l'API content du cœur d'Astro et on sérialise un RSS 2.0 valide.
 * Seuls les articles PUBLIÉS (draft=false) sont inclus, du plus récent au plus
 * ancien. Le Content-Type est `application/rss+xml`.
 */
export const prerender = true;

import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';

const SITE = 'https://taqinor.ma';
const TITLE = 'Taqinor — Blog';
const DESCRIPTION =
  'Actualités solaires au Maroc, retours de chantier et nouveautés d’équipement, par Taqinor.';

/** Échappe les caractères réservés XML (texte et attributs). */
function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

export const GET: APIRoute = async () => {
  const posts = (await getCollection('blog', ({ data }) => !data.draft && data.pubDate.getTime() <= Date.now())).sort(
    (a, b) => b.data.pubDate.getTime() - a.data.pubDate.getTime(),
  );

  const items = posts
    .map((post) => {
      const link = `${SITE}/blog/${post.id}`;
      const categories = post.data.tags
        .map((tag) => `      <category>${escapeXml(tag)}</category>`)
        .join('\n');
      return `    <item>
      <title>${escapeXml(post.data.title)}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <description>${escapeXml(post.data.description)}</description>
      <pubDate>${post.data.pubDate.toUTCString()}</pubDate>
${categories}
    </item>`;
    })
    .join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(TITLE)}</title>
    <link>${SITE}/blog</link>
    <atom:link href="${SITE}/rss.xml" rel="self" type="application/rss+xml" />
    <description>${escapeXml(DESCRIPTION)}</description>
    <language>fr-MA</language>
    <lastBuildDate>${(posts[0]?.data.pubDate ?? new Date()).toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>
`;

  return new Response(xml, {
    status: 200,
    headers: { 'content-type': 'application/rss+xml; charset=utf-8' },
  });
};
