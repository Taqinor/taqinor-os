// @vitest-environment jsdom
//
// AACQ44 (C-AACQ-044) — la garde de consentement est portée par `appareilId()`
// lui-même : sans `tq_consent` = 'granted', la fonction rend '' sans écrire ni
// le cookie `tq_appareil` ni la clé localStorage. Ce test exerce la VRAIE
// `appareilId()` avec ses stockages PAR DÉFAUT (localStorage et document.cookie
// de jsdom), puis le corps réel de `buildQuestionnairePostBody`.
//
// Test-du-test : retirer la lecture de `tq_consent` dans `appareilId()` ⇒
// « refus : aucune écriture » rouge (cookie et localStorage écrits).
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { appareilId, isPlausibleUuid } from '../src/lib/visite';
import { buildQuestionnairePostBody } from '../src/lib/questionnaire';

function effacer(): void {
  document.cookie = 'tq_appareil=; Max-Age=0; path=/';
  localStorage.removeItem('tq_appareil');
  localStorage.removeItem('tq_consent');
}

function aucuneEcriture(): void {
  expect(document.cookie).not.toContain('tq_appareil');
  expect(localStorage.getItem('tq_appareil')).toBeNull();
}

describe('appareilId — garde de consentement (AACQ44)', () => {
  beforeEach(effacer);
  afterEach(effacer);

  it('refus : aucune écriture', () => {
    localStorage.setItem('tq_consent', 'denied');
    expect(appareilId()).toBe('');
    aucuneEcriture();
    // CLAUSE PERSISTANCE : un second appel (rechargement) n'écrit toujours rien.
    expect(appareilId()).toBe('');
    aucuneEcriture();
    // Le corps du questionnaire ne transmet aucun identifiant.
    const body = buildQuestionnairePostBody('contact', { ville: 'Fès' }, null, appareilId());
    expect(body).not.toHaveProperty('appareil_id');
  });

  it('absent : aucune écriture', () => {
    expect(appareilId()).toBe('');
    aucuneEcriture();
    expect(appareilId()).toBe('');
    aucuneEcriture();
  });

  it('accord : identifiant stable', () => {
    localStorage.setItem('tq_consent', 'granted');
    const premier = appareilId();
    expect(isPlausibleUuid(premier)).toBe(true);
    expect(localStorage.getItem('tq_appareil')).toBe(premier);
    expect(appareilId()).toBe(premier);
    const body = buildQuestionnairePostBody('contact', { ville: 'Fès' }, null, appareilId());
    expect(body.appareil_id).toBe(premier);
  });
});
