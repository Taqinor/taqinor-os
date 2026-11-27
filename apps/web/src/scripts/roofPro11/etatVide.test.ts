// ACAL1808 — les consignes de tracé se lisent par pointeur : au doigt, jamais « clic » ni « double-clic ».
// Nouveau fichier car : `etatVide.ts` n'avait aucun module de test (le tracé libre de `formesToit.ts` y est couvert aussi).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { creerEtatVide, ETAPE_COINS, ETAPE_LOCALISER } from './etatVide';
import { monterFormesToit } from './formesToit';

const MOT_SOURIS = /clic|clique/i;

/** Un vrai document + un `window.matchMedia` qui répond (pointer: coarse) selon le pointeur simulé. */
function monter(tactile: boolean) {
  const dom = new JSDOM('<!doctype html><body><div class="cal-coque"><div id="carte"></div><button id="ancre"></button></div></body>');
  const w = dom.window as unknown as Record<string, unknown>;
  w.matchMedia = (q: string) => ({ matches: tactile && q.includes('coarse') });
  vi.stubGlobal('window', dom.window);
  vi.stubGlobal('document', dom.window.document);
  return dom.window.document;
}

afterEach(() => vi.unstubAllGlobals());

describe('creerEtatVide — la carte d\'aide lit le pointeur (ACAL1808)', () => {
  it('au doigt : aucune consigne ne dit clic ni double-clic', () => {
    const doc = monter(true);
    const ev = creerEtatVide(doc.getElementById('carte'));
    ev.maj(0, false);
    const t0 = doc.getElementById('rp9-etat-vide')!.textContent!;
    ev.maj(2, false);
    const t2 = doc.getElementById('rp9-etat-vide')!.textContent!;
    expect(t0).not.toMatch(MOT_SOURIS);
    expect(t2).not.toMatch(MOT_SOURIS);
    expect(t2).toContain('Touchez');
  });

  it('à la souris : les consignes de clic restent', () => {
    const doc = monter(false);
    const ev = creerEtatVide(doc.getElementById('carte'));
    ev.maj(0, false);
    expect(doc.getElementById('rp9-etat-vide')!.textContent).toBe(ETAPE_LOCALISER);
    ev.maj(2, false);
    expect(doc.getElementById('rp9-etat-vide')!.textContent).toBe(ETAPE_COINS);
  });
});

describe('monterFormesToit — la consigne du tracé libre lit le pointeur (ACAL1808)', () => {
  function cliquerTraceLibre(tactile: boolean): string {
    const doc = monter(tactile);
    const msgs: string[] = [];
    monterFormesToit({
      ancre: doc.getElementById('ancre'),
      contour: () => [],
      pente: () => 20,
      existants: () => [],
      obstacles: () => 0,
      appliquer: () => {},
      setStatus: (m) => msgs.push(m),
    });
    (doc.querySelector('[data-forme="libre"]') as HTMLButtonElement).click();
    return msgs[msgs.length - 1];
  }

  it('au doigt : « Touchez la carte », pas de « cliquez »', () => {
    const m = cliquerTraceLibre(true);
    expect(m).not.toMatch(MOT_SOURIS);
    expect(m).toContain('touchez la carte pour poser chaque coin');
  });

  it('à la souris : « cliquez sur la carte »', () => {
    expect(cliquerTraceLibre(false)).toContain('cliquez sur la carte');
  });
});
