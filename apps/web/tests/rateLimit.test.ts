// Limiteur de débit anti-spam des endpoints de lead (ERR112). Best-effort,
// en mémoire, horloge injectable → testable de façon déterministe.
import { afterEach, describe, expect, it } from 'vitest';
import {
  DEFAULT_RATE_LIMIT,
  DEFAULT_WINDOW_MS,
  clientIpFromRequest,
  rateLimit,
  resetRateLimit,
} from '../src/lib/rateLimit';

afterEach(() => resetRateLimit());

describe('rateLimit — fenêtre glissante par clé', () => {
  it('autorise jusqu’à la limite, bloque au-delà', () => {
    let t = 1_000_000;
    const now = () => t;
    for (let i = 0; i < DEFAULT_RATE_LIMIT; i++) {
      expect(rateLimit('ip:1.2.3.4', { now }).allowed).toBe(true);
    }
    const blocked = rateLimit('ip:1.2.3.4', { now });
    expect(blocked.allowed).toBe(false);
    expect(blocked.remaining).toBe(0);
    expect(blocked.retryAfterSec).toBeGreaterThan(0);
  });

  it('rouvre après la fenêtre', () => {
    let t = 0;
    const now = () => t;
    const opts = { limit: 2, windowMs: 1000, now };
    expect(rateLimit('k', opts).allowed).toBe(true);
    expect(rateLimit('k', opts).allowed).toBe(true);
    expect(rateLimit('k', opts).allowed).toBe(false); // 3e dans la fenêtre
    t = 1001; // fenêtre écoulée
    expect(rateLimit('k', opts).allowed).toBe(true);
  });

  it('isole les clés (IP/endpoint différents = buckets indépendants)', () => {
    const now = () => 0;
    const opts = { limit: 1, windowMs: 1000, now };
    expect(rateLimit('a', opts).allowed).toBe(true);
    expect(rateLimit('a', opts).allowed).toBe(false);
    // Autre clé : non affectée.
    expect(rateLimit('b', opts).allowed).toBe(true);
  });

  it('décompte les requêtes restantes', () => {
    const now = () => 0;
    const r1 = rateLimit('rem', { limit: 3, now });
    expect(r1.remaining).toBe(2);
    const r2 = rateLimit('rem', { limit: 3, now });
    expect(r2.remaining).toBe(1);
  });

  it('expose des défauts raisonnables (humain OK, script bloqué)', () => {
    expect(DEFAULT_RATE_LIMIT).toBeGreaterThanOrEqual(5);
    expect(DEFAULT_WINDOW_MS).toBe(60_000);
  });
});

describe('clientIpFromRequest', () => {
  it('préfère CF-Connecting-IP (posée par Cloudflare, non falsifiable)', () => {
    const req = new Request('https://taqinor.ma/api/simulate', {
      headers: { 'cf-connecting-ip': '41.2.3.4', 'x-forwarded-for': '9.9.9.9' },
    });
    expect(clientIpFromRequest(req)).toBe('41.2.3.4');
  });

  it('retombe sur la 1re IP de X-Forwarded-For (dev local)', () => {
    const req = new Request('https://taqinor.ma/api/simulate', {
      headers: { 'x-forwarded-for': '10.0.0.1, 9.9.9.9' },
    });
    expect(clientIpFromRequest(req)).toBe('10.0.0.1');
  });

  it('clé partagée "unknown" sans IP identifiable (fail-safe)', () => {
    const req = new Request('https://taqinor.ma/api/simulate');
    expect(clientIpFromRequest(req)).toBe('unknown');
  });
});
