// WJ29 — « Être contacté » / « Demander un rappel » : logique PURE du proxy
// /api/proposition-contact (aucun DOM, aucun réseau). Le contrat central :
// la dégradation est TOUJOURS propre (404 backend pas encore construit / 5xx /
// panne réseau -> même message honnête qui renvoie vers WhatsApp), jamais une
// erreur technique brute affichée au client.
import { describe, expect, it } from 'vitest';
import {
  contactEndpoint,
  buildContactBody,
  normalizeContactResponse,
} from '../src/lib/proposition';

describe('WJ29 — contactEndpoint (URL backend attendue)', () => {
  it('construit la même convention que /accept/ avec /contact/', () => {
    expect(contactEndpoint('https://api.taqinor.ma', 'abc123')).toBe(
      'https://api.taqinor.ma/api/django/ventes/proposal/abc123/contact/',
    );
  });

  it('base vide → repli https://api.taqinor.ma', () => {
    expect(contactEndpoint('', 'tok')).toBe(
      'https://api.taqinor.ma/api/django/ventes/proposal/tok/contact/',
    );
  });

  it('trailing slash sur la base → normalisé (pas de double slash)', () => {
    expect(contactEndpoint('https://api.taqinor.ma/', 'tok')).toBe(
      'https://api.taqinor.ma/api/django/ventes/proposal/tok/contact/',
    );
  });

  it('token encodé (path segment sûr)', () => {
    expect(contactEndpoint('https://api.taqinor.ma', 'a/b c')).toBe(
      'https://api.taqinor.ma/api/django/ventes/proposal/a%2Fb%20c/contact/',
    );
  });
});

describe('WJ29 — buildContactBody (normalisation du canal + message)', () => {
  it('canal valide (rappel/whatsapp/question) préservé', () => {
    expect(buildContactBody({ channel: 'rappel' })).toEqual({ channel: 'rappel', message: '' });
    expect(buildContactBody({ channel: 'whatsapp' })).toEqual({ channel: 'whatsapp', message: '' });
    expect(buildContactBody({ channel: 'question', message: 'Une question' })).toEqual({
      channel: 'question',
      message: 'Une question',
    });
  });

  it('canal invalide → repli "rappel"', () => {
    // @ts-expect-error — on teste volontairement une entrée hors-contrat
    expect(buildContactBody({ channel: 'autre' }).channel).toBe('rappel');
  });

  it('message trim + tronqué à 2000 caractères (jamais d’inondation de l’upstream)', () => {
    const long = 'x'.repeat(3000);
    const out = buildContactBody({ channel: 'rappel', message: `  ${long}  ` });
    expect(out.message.length).toBe(2000);
    expect(out.message.startsWith('x')).toBe(true);
  });

  it('message absent → chaîne vide (jamais undefined)', () => {
    expect(buildContactBody({ channel: 'rappel' }).message).toBe('');
  });
});

describe('WJ29 — normalizeContactResponse (dégradation TOUJOURS propre)', () => {
  it('2xx backend → confirmation client honnête', () => {
    const r = normalizeContactResponse(200, false);
    expect(r.ok).toBe(true);
    expect(r.degraded).toBe(false);
    expect(r.detail).toMatch(/rappelons/i);
  });

  it('404 (route de contact pas encore construite côté backend, QJ27) → dégradé propre', () => {
    const r = normalizeContactResponse(404, false);
    expect(r.ok).toBe(false);
    expect(r.degraded).toBe(true);
    expect(r.detail).toMatch(/whatsapp/i);
    expect(r.detail).not.toMatch(/404|error|exception/i);
  });

  it('5xx backend → dégradé propre, même message honnête', () => {
    const r = normalizeContactResponse(500, false);
    expect(r.ok).toBe(false);
    expect(r.degraded).toBe(true);
    expect(r.detail).toMatch(/whatsapp/i);
  });

  it('panne réseau (fetch a levé) → dégradé propre, jamais de détail technique', () => {
    const r = normalizeContactResponse(0, true);
    expect(r.ok).toBe(false);
    expect(r.degraded).toBe(true);
    expect(r.detail).toMatch(/whatsapp/i);
  });

  it('networkError=true l’emporte même si le status ressemble à un succès', () => {
    const r = normalizeContactResponse(200, true);
    expect(r.ok).toBe(false);
    expect(r.degraded).toBe(true);
  });
});
