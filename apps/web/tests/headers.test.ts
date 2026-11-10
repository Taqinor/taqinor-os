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

  it("la CSP autorise MapTiler + Mapbox (tuiles + geocodage) et l'API taqinor, interdit le framing", () => {
    expect(CONTENT_SECURITY_POLICY).toContain("frame-ancestors 'none'");
    expect(CONTENT_SECURITY_POLICY).toContain('https://api.maptiler.com');
    expect(CONTENT_SECURITY_POLICY).toContain('https://api.taqinor.ma');
    // Mapbox : tuiles satellite HD chargées dès que PUBLIC_MAPBOX_TOKEN est
    // défini (buildSatelliteStyle) — doit figurer en img-src ET connect-src,
    // sinon le navigateur bloque toutes les tuiles et la carte reste vide.
    const csp = CONTENT_SECURITY_POLICY;
    const imgSrc = csp.split(';').find((d) => d.trim().startsWith('img-src')) ?? '';
    const connectSrc = csp.split(';').find((d) => d.trim().startsWith('connect-src')) ?? '';
    expect(imgSrc).toContain('https://api.mapbox.com');
    expect(connectSrc).toContain('https://api.mapbox.com');
    // WJCSP — MapLibre rend le repère maison et le contour du toit (sources
    // GeoJSON rp9-*) dans un web worker créé depuis un blob:. Sans worker-src
    // le repli est script-src (sans blob:) : worker bloqué en silence, le
    // client ne VOIT jamais ni son repère ni son tracé (régression W315,
    // invisible ~7 semaines). Le nginx de l'ERP porte la même directive.
    expect(CONTENT_SECURITY_POLICY).toContain("worker-src 'self' blob:");
    // PVGIS est proxyé côté serveur uniquement (src/lib/roofEstimate.ts) —
    // jamais appelé depuis le navigateur, donc absent de connect-src.
    expect(CONTENT_SECURITY_POLICY).not.toContain('jrc.ec.europa.eu');
  });

  it('la CSP autorise le pixel Meta (script fbevents.js + événements /tr)', () => {
    const directive = (name: string) =>
      CONTENT_SECURITY_POLICY.split(';').find((d) => d.trim().startsWith(name)) ?? '';
    expect(directive('script-src')).toContain('https://connect.facebook.net');
    expect(directive('img-src')).toContain('https://www.facebook.com');
    expect(directive('connect-src')).toContain('https://www.facebook.com');
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

describe('WAUD5 — Cloudflare Web Analytics autorisé par la CSP', () => {
  const directive = (nom: string) => CONTENT_SECURITY_POLICY.split('; ').find((d: string) => d.startsWith(`${nom} `)) ?? '';
  it('script-src et connect-src portent les deux hôtes', () => {
    expect(directive('script-src')).toContain('https://static.cloudflareinsights.com');
    expect(directive('connect-src')).toContain('https://cloudflareinsights.com');
  });
});

describe('WAUD13 — repli formulaire du pixel Meta (pages arabes à URL longue)', () => {
  const directive = (nom: string) => CONTENT_SECURITY_POLICY.split('; ').find((d: string) => d.startsWith(`${nom} `)) ?? '';
  it('form-action et frame-src autorisent www.facebook.com, et lui seul', () => {
    expect(directive('form-action').split(' ')).toEqual(['form-action', "'self'", 'https://api.taqinor.ma', 'https://www.facebook.com']);
    expect(directive('frame-src')).toContain('https://www.facebook.com');
    expect(CONTENT_SECURITY_POLICY).not.toMatch(/\*\.facebook\.com/);
  });
  it('frame-ancestors reste fermé', () => {
    expect(directive('frame-ancestors')).toBe("frame-ancestors 'none'");
  });
});

describe('ADCG55 — widget partenaire /embed/* affichable en iframe tierce', () => {
  const get = (chemin: string) =>
    applySecurityHeaders({ method: 'GET', url: `https://taqinor.ma${chemin}` }, html());
  const sans = (csp: string) => csp.split('; ').filter((d: string) => !d.startsWith('frame-ancestors '));
  it('/embed/* : frame-ancestors https: sans X-Frame-Options ; le reste du site reste fermé', () => {
    const embed = get('/embed/estimation');
    const csp = embed.headers.get('Content-Security-Policy') ?? '';
    expect(csp).toContain('frame-ancestors https:');
    expect(csp).not.toContain("frame-ancestors 'none'");
    expect(embed.headers.get('X-Frame-Options')).toBeNull();
    expect(sans(csp)).toEqual(sans(CONTENT_SECURITY_POLICY));
    for (const chemin of ['/', '/devis/mon-toit', '/embedded']) {
      const res = get(chemin);
      expect(res.headers.get('Content-Security-Policy')).toBe(CONTENT_SECURITY_POLICY);
      expect(res.headers.get('X-Frame-Options')).toBe('DENY');
    }
  });
});
