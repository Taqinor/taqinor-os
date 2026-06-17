// Cache-on-deploy des documents HTML (W33) : un déploiement ne doit jamais
// servir une page périmée, tout en laissant /api et les assets hashés intacts.
import { describe, expect, it } from 'vitest';

// @ts-expect-error — module JS pur sans déclaration de types (copié dans dist/server au build)
import { applyHtmlCacheControl, HTML_CACHE_CONTROL } from '../worker/cache.mjs';

const html = (cc?: string) =>
  new Response('<!doctype html><title>x</title>', {
    headers: { 'content-type': 'text/html; charset=utf-8', ...(cc ? { 'cache-control': cc } : {}) },
  });

describe('applyHtmlCacheControl', () => {
  it('force la revalidation des documents HTML (GET)', () => {
    const res = applyHtmlCacheControl({ method: 'GET' }, html());
    expect(res.headers.get('cache-control')).toBe(HTML_CACHE_CONTROL);
    expect(HTML_CACHE_CONTROL).toContain('max-age=0');
    expect(HTML_CACHE_CONTROL).toContain('must-revalidate');
  });

  it('écrase un Cache-Control HTML trop long déjà présent', () => {
    const res = applyHtmlCacheControl({ method: 'HEAD' }, html('public, max-age=86400'));
    expect(res.headers.get('cache-control')).toBe(HTML_CACHE_CONTROL);
  });

  it('NE touche PAS les réponses non-HTML (ex. /api JSON) — renvoyées telles quelles', () => {
    const json = new Response('{"ok":true}', { headers: { 'content-type': 'application/json' } });
    const res = applyHtmlCacheControl({ method: 'GET' }, json);
    expect(res).toBe(json);
    expect(res.headers.get('cache-control')).toBeNull();
  });

  it('NE touche PAS un asset hashé (JS, cache long immutable préservé)', () => {
    const asset = new Response('console.log(1)', {
      headers: { 'content-type': 'application/javascript', 'cache-control': 'public, max-age=31536000, immutable' },
    });
    const res = applyHtmlCacheControl({ method: 'GET' }, asset);
    expect(res).toBe(asset);
    expect(res.headers.get('cache-control')).toBe('public, max-age=31536000, immutable');
  });

  it('laisse passer les POST de documents inchangés (jamais de cache sur soumission)', () => {
    const doc = html();
    const res = applyHtmlCacheControl({ method: 'POST' }, doc);
    expect(res).toBe(doc);
    expect(res.headers.get('cache-control')).toBeNull();
  });
});
