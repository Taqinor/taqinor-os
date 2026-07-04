// En-têtes de sécurité (W315) : chaque document HTML doit sortir durci
// (CSP/HSTS/Referrer-Policy/Permissions-Policy/nosniff), sans casser /api et
// les assets hashés.
import { describe, expect, it } from 'vitest';

// @ts-expect-error — module JS pur sans déclaration de types (copié dans dist/server au build)
import {
  applySecurityHeaders,
  CONTENT_SECURITY_POLICY,
  STRICT_TRANSPORT_SECURITY,
  REFERRER_POLICY,
  PERMISSIONS_POLICY,
} from '../worker/headers.mjs';

const html = () =>
  new Response('<!doctype html><title>x</title>', {
    headers: { 'content-type': 'text/html; charset=utf-8' },
  });

describe('applySecurityHeaders', () => {
  it('ajoute tous les en-têtes de sécurité sur un document HTML (GET)', () => {
    const res = applySecurityHeaders({ method: 'GET' }, html());
    expect(res.headers.get('Content-Security-Policy')).toBe(CONTENT_SECURITY_POLICY);
    expect(res.headers.get('Strict-Transport-Security')).toBe(STRICT_TRANSPORT_SECURITY);
    expect(res.headers.get('Referrer-Policy')).toBe(REFERRER_POLICY);
    expect(res.headers.get('Permissions-Policy')).toBe(PERMISSIONS_POLICY);
    expect(res.headers.get('X-Content-Type-Options')).toBe('nosniff');
  });

  it('applique aussi sur HEAD', () => {
    const res = applySecurityHeaders({ method: 'HEAD' }, html());
    expect(res.headers.get('Content-Security-Policy')).toBe(CONTENT_SECURITY_POLICY);
  });

  it("la CSP autorise MapTiler (tuiles + geocodage) et l'API taqinor, interdit le framing", () => {
    expect(CONTENT_SECURITY_POLICY).toContain("frame-ancestors 'none'");
    expect(CONTENT_SECURITY_POLICY).toContain('https://api.maptiler.com');
    expect(CONTENT_SECURITY_POLICY).toContain('https://api.taqinor.ma');
    // PVGIS est proxyé côté serveur uniquement (src/lib/roofEstimate.ts) —
    // jamais appelé depuis le navigateur, donc absent de connect-src.
    expect(CONTENT_SECURITY_POLICY).not.toContain('jrc.ec.europa.eu');
  });

  it("l'en-tête HSTS couvre 1 an et les sous-domaines", () => {
    expect(STRICT_TRANSPORT_SECURITY).toContain('max-age=31536000');
    expect(STRICT_TRANSPORT_SECURITY).toContain('includeSubDomains');
  });

  it('NE touche PAS les réponses non-HTML (ex. /api JSON) — renvoyées telles quelles', () => {
    const json = new Response('{"ok":true}', { headers: { 'content-type': 'application/json' } });
    const res = applySecurityHeaders({ method: 'GET' }, json);
    expect(res).toBe(json);
    expect(res.headers.get('Content-Security-Policy')).toBeNull();
  });

  it('NE touche PAS un asset hashé (JS, en-têtes de cache/format préservés)', () => {
    const asset = new Response('console.log(1)', {
      headers: { 'content-type': 'application/javascript', 'cache-control': 'public, max-age=31536000, immutable' },
    });
    const res = applySecurityHeaders({ method: 'GET' }, asset);
    expect(res).toBe(asset);
    expect(res.headers.get('Content-Security-Policy')).toBeNull();
  });

  it('laisse passer les POST de documents inchangés (jamais durci sur soumission)', () => {
    const doc = html();
    const res = applySecurityHeaders({ method: 'POST' }, doc);
    expect(res).toBe(doc);
    expect(res.headers.get('Content-Security-Policy')).toBeNull();
  });

  it('préserve le corps et le statut de la réponse', () => {
    const res = applySecurityHeaders({ method: 'GET' }, new Response('<!doctype html><title>x</title>', {
      status: 404,
      headers: { 'content-type': 'text/html; charset=utf-8' },
    }));
    expect(res.status).toBe(404);
  });
});
