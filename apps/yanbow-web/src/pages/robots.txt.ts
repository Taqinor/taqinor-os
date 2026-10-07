import type { APIRoute } from 'astro';

/**
 * robots.txt servi à la demande (YBW11) — garantit aussi qu'un bundle serveur
 * existe (le Worker enveloppe l'app). Quand le site est FERMÉ, la porte de
 * lancement du Worker (YBW12) répond à la place avec `Disallow: /`.
 * Aucun sitemap tant qu'aucun domaine n'est posé (YBW75).
 */
export const prerender = false;

export const GET: APIRoute = () =>
  new Response('User-agent: *\nAllow: /\n', {
    headers: { 'content-type': 'text/plain; charset=utf-8' },
  });
