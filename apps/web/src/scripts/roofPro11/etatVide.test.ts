// ACAL1808 — les consignes de tracé se lisent par pointeur : au doigt, jamais « clic » ni « double-clic ».
// Nouveau fichier car : `etatVide.ts` n'avait aucun module de test (le tracé libre de `formesToit.ts` y est couvert aussi).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { consigneTrace, creerEtatVide, ETAPE_COINS, ETAPE_LOCALISER } from './etatVide';
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

describe('consigneTrace — la pilule d’état lit le pointeur (ACAL1808 revue)', () => {
  const cas = ['adresse', 'efface', 'nouvelle-zone'] as const;
  it('au doigt : ni clic ni double-clic, et « Terminer le tracé »', () => {
    for (const c of cas) {
      const t = consigneTrace(c, true, 'Pan 2');
      expect(t).not.toMatch(MOT_SOURIS);
      expect(t).toMatch(/touchez/i);
    }
    expect(consigneTrace('efface', true)).toContain('Terminer le tracé');
  });
  it('à la souris : les mots d’aujourd’hui', () => {
    expect(consigneTrace('adresse', false)).toBe('Cherchez votre adresse, puis cliquez les coins de votre toit.');
    expect(consigneTrace('efface', false)).toBe('Cliquez les coins de votre toit. Double-cliquez pour fermer.');
    expect(consigneTrace('nouvelle-zone', false, 'Pan 2')).toContain('(double-cliquez pour fermer)');
  });
  it('l’entrée appelle l’aide aux trois endroits', () => {
    const src = readFileSync(resolve(process.cwd(), 'src/scripts/roof-tool-pro11.ts'), 'utf8');
    expect(src).toContain("consigneTrace('adresse', pointeurTactile(window))");
    expect(src).toContain("consigneTrace('efface', pointeurTactile(window))");
    expect(src).toContain("consigneTrace('nouvelle-zone', pointeurTactile(window), fresh.label)");
    expect(src).not.toMatch(/setStatus\([`'][^)]*liquez/);
  });
});
