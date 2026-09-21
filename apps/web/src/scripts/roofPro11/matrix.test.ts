// @vitest-environment jsdom
// CALX114 — l'objectif du classement est SAISI dans une puce créée par le module, et la
// ligne « Recommandé » dit selon QUOI elle est recommandée.
//
// Jusqu'ici le tableau comparatif affichait « ✓ Recommandé » sans jamais dire ce que le
// balayage cherchait : le lecteur devait savoir, de mémoire, que l'énergie annuelle posée
// classait tout. Ces tests gardent trois choses : la puce existe même quand la page hôte
// ne la fournit pas, un clic écrit `optimisation.cible` et RE-CLASSE la matrice, et la
// phrase du classement est toujours affichée — y compris quand rien n'a été saisi.
import { beforeEach, describe, expect, it } from 'vitest';
import { createMatrix } from './matrix';
import { poserChoixOptimisation, cibleOptimisationSaisie } from './optimizer';
import { fineGridMatrixV6 } from '../../lib/estimatorBrainV6';
import { type LngLat } from '../../lib/roof';
import { type Ctx } from './context';

const LAT = 33.59;
const FACTURE = 5000;

/** Toit long et étroit : `compte` et `energie` n'y élisent PAS la même ligne. */
function rect(widthM: number, depthM: number, lng0 = -7.6, lat0 = LAT): LngLat[] {
  const dLat = depthM / 2 / 111320;
  const dLng = widthM / 2 / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng, lat0 - dLat],
    [lng0 + dLng, lat0 - dLat],
    [lng0 + dLng, lat0 + dLat],
    [lng0 - dLng, lat0 + dLat],
  ];
}

const TOIT = rect(8, 24);

function makeCtx(): Ctx {
  return {
    roofType: 'flat',
    rec: { targetAnnualKwh: 12000 },
    matrixResult: fineGridMatrixV6(TOIT, LAT, FACTURE, []),
    matrixSort: { key: 'annualKwh', dir: 'desc' },
    matrixFilter: 'all',
    centroidLat: LAT,
    closed: true,
    vertices: TOIT,
    v4YieldCache: new Map<string, number | null>(),
  } as unknown as Ctx;
}

function monterDom() {
  document.body.innerHTML =
    '<div id="rp9-compare-wrap" hidden><table><tbody id="rp9-compare"></tbody></table></div>';
}

function matrice(ctx: Ctx) {
  return createMatrix(ctx, {
    renderConfig: () => {},
    monthlyBill: () => FACTURE,
    obstructionRings: () => [],
  });
}

function puces(): HTMLButtonElement[] {
  return Array.from(document.querySelectorAll<HTMLButtonElement>('#rp9-cible button[data-cible]'));
}

beforeEach(() => {
  monterDom();
  poserChoixOptimisation(null); // état module partagé : aucun objectif saisi
});

describe('CALX114 — la puce d’objectif est créée par le module', () => {
  it('les cinq objectifs du contrat sont proposés, aucun n’est pressé par défaut', () => {
    const ctx = makeCtx();
    matrice(ctx).paintComparison();
    const boutons = puces();
    expect(boutons.map((b) => b.dataset.cible)).toEqual(['compte', 'kwc', 'energie', 'ombrage', 'faitage']);
    expect(boutons.every((b) => b.getAttribute('aria-pressed') === 'false')).toBe(true);
    for (const b of boutons) expect((b.textContent ?? '').length).toBeGreaterThan(0);
  });

  it('sans objectif saisi, la phrase affichée NOMME l’objectif historique', () => {
    const ctx = makeCtx();
    matrice(ctx).paintComparison();
    const note = document.getElementById('rp9-cible-note');
    expect(note?.textContent).toContain('Aucun objectif saisi');
    expect(note?.textContent).toContain('énergie annuelle posée');
  });

  it('la puce existante de la page hôte n’est pas dupliquée', () => {
    const ctx = makeCtx();
    const m = matrice(ctx);
    m.paintComparison();
    m.paintComparison();
    expect(document.querySelectorAll('#rp9-cible').length).toBe(1);
  });
});

describe('CALX114 — un clic écrit l’objectif et re-classe la matrice', () => {
  it('cliquer « le plus de modules posés » change le gagnant affiché', () => {
    const ctx = makeCtx();
    const avant = ctx.matrixResult!.winner;
    matrice(ctx).paintComparison();
    puces().find((b) => b.dataset.cible === 'compte')!.click();
    expect(cibleOptimisationSaisie()).toBe('compte');
    expect(ctx.matrixResult!.cible.appliquee).toBe('compte');
    expect(ctx.matrixResult!.winner.placedCount).toBeGreaterThan(avant.placedCount);
    expect(puces().find((b) => b.dataset.cible === 'compte')!.getAttribute('aria-pressed')).toBe('true');
  });

  it('re-cliquer l’objectif pressé le RETIRE (retour à l’objectif historique)', () => {
    const ctx = makeCtx();
    const avant = ctx.matrixResult!.winner;
    matrice(ctx).paintComparison();
    puces().find((b) => b.dataset.cible === 'compte')!.click();
    puces().find((b) => b.dataset.cible === 'compte')!.click();
    expect(cibleOptimisationSaisie()).toBeNull();
    expect(ctx.matrixResult!.cible.saisie).toBeNull();
    expect(ctx.matrixResult!.winner.placedCount).toBe(avant.placedCount);
    expect(document.getElementById('rp9-cible-note')?.textContent).toContain('Aucun objectif saisi');
  });

  it('un objectif sans mesure est REFUSÉ à l’écran en nommant le champ', () => {
    const ctx = makeCtx();
    matrice(ctx).paintComparison();
    puces().find((b) => b.dataset.cible === 'ombrage')!.click();
    const note = document.getElementById('rp9-cible-note');
    expect(ctx.matrixResult!.cible.refusee).toBe(true);
    expect(note?.textContent).toContain('aucun accès solaire');
    // La puce cliquée reste pressée : le choix est saisi, c'est la MESURE qui manque.
    expect(puces().find((b) => b.dataset.cible === 'ombrage')!.getAttribute('aria-pressed')).toBe('true');
  });
});

describe('CALX114 — la ligne « Recommandé » dit selon quoi', () => {
  it('le badge porte l’objectif réellement appliqué', () => {
    const ctx = makeCtx();
    matrice(ctx).paintComparison();
    const premiere = document.querySelector('#rp9-compare tr');
    expect(premiere?.textContent).toContain('✓ Recommandé');
    expect(premiere?.textContent).toContain('énergie annuelle posée');
  });

  it('l’objectif saisi suit dans le badge', () => {
    const ctx = makeCtx();
    matrice(ctx).paintComparison();
    puces().find((b) => b.dataset.cible === 'compte')!.click();
    expect(document.querySelector('#rp9-compare tr')?.textContent).toContain('le plus de modules posés');
  });
});
