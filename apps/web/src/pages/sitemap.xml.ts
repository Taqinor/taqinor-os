/**
 * GET /sitemap.xml — index de sitemap standard (HTTP 200).
 *
 * L'intégration @astrojs/sitemap émet `/sitemap-index.xml` + `/sitemap-0.xml`
 * (la vraie liste des URL publiques, déjà filtrée des pages privées /preview/*
 * et des pages de travail noindex). Mais `/sitemap.xml` — l'URL que beaucoup
 * d'outils et de robots tentent par défaut — restait en 404. Ce point d'accès
 * pré-rendu renvoie un <sitemapindex> valide qui pointe vers `/sitemap-0.xml`,
 * restant ainsi synchronisé avec @astrojs/sitemap (aucune liste d'URL dupliquée
 * à maintenir ici). robots.txt référence désormais cette URL.
 */
export const prerender = true;

import type { APIRoute } from 'astro';

const SITE = 'https://taqinor.ma';

export const GET: APIRoute = () => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>${SITE}/sitemap-0.xml</loc>
  </sitemap>
</sitemapindex>
`;
  return new Response(xml, {
    status: 200,
    headers: { 'content-type': 'application/xml' },
  });
};
