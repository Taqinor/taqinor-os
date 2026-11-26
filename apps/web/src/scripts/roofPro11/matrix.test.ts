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
import { rectRing } from './harnaisAtelier';
import { uniformSetbacks } from '../../lib/roofPro2'; // demande croisée (balayage)

const LAT = 33.59;
const FACTURE = 5000;

/** Toit long et étroit : `compte` et `energie` n'y élisent PAS la même ligne. */
function rect(widthM: number, depthM: number, lng0 = -7.6, lat0 = LAT): LngLat[] {
  return rectRing(widthM, depthM, lng0, lat0);
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

// ACAL1505 — en calepinage le champ `rp9-bill` n'existe pas (`monthlyBill()` = 0) : le balayage prend la facture du
// lead servie (`factureCarteDe`), sinon « % du besoin » vaut 0 sur chaque ligne ; le nombre posé (solveur vivant) ne bouge pas.
describe('ACAL1505 — le balayage vise la facture du lead', () => {
  it('facture du lead servie ⇒ pctOfTarget > 0 sur le balayage (recalcul de la matrice)', () => {
    const ctx = { ...makeCtx(), opts: { factureMensuelleMad: 1200 }, matrixResult: null } as unknown as Ctx;
    createMatrix(ctx, { renderConfig: () => {}, monthlyBill: () => 0, obstructionRings: () => [] }).recomputeMatrix();
    expect(ctx.matrixResult!.targetAnnualKwh).toBeGreaterThan(0);
    expect(ctx.matrixResult!.rows.every((r) => r.pctOfTarget > 0)).toBe(true);
  });

  it('affinage PVGIS (buildMatrix) : même cible, nombre posé inchangé', async () => {
    const { createOptimizer } = await import('./optimizer');
    const lancer = async (factureLead: number) => {
      const pan = { id: 'z1', label: 'Pan A', vertices: rect(10, 7), obstacles: [], roofType: 'flat', neededPanels: 0, neededAuto: true };
      const ctx = {
        ...makeCtx(), vertices: rect(10, 7), matrixResult: null, rec: null, areas: [pan], activeAreaId: 'z1', activeArea: () => pan,
        opts: { rendementPvgis: null }, dom: {}, centroid: rect(10, 7)[0], pinned: new Set(), overhangM: 0, documentRelu: null,
        sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' }, batiments: [], environment: [],
        shadeObstructions: [], obstacles: [], neededAuto: true, neededPanels: 0, layoutPlan: null,
      } as unknown as Ctx;
      let pose = -1;
      const deps = {
        renderScene: (_p: unknown, _g: unknown, _t: unknown, _f: unknown, placed: number) => { pose = placed; },
        paintComparison: () => {}, highlightRow: () => {}, syncProductionWindow: () => {}, prefillLead: () => {}, syncChips: () => {},
        renderMatrixOptimumCard: () => {}, monthlyBill: () => 0, factureCarte: () => factureLead, obstructionRings: () => [], setStatus: () => {},
      };
      await createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]).computeMatrixPvgis();
      return { pose, pcts: ctx.matrixResult!.rows.map((r) => r.pctOfTarget) };
    };
    const sans = await lancer(0);
    const avec = await lancer(1200);
    expect(avec.pcts.every((p) => p > 0)).toBe(true);
    expect(sans.pcts.every((p) => p === 0)).toBe(true);
    expect(avec.pose).toBe(sans.pose);
  });
});

// Demande croisée (lane balayage) — `recomputeMatrix` balayait sans les retraits saisis, les dégagements d'obstacle ni le
// débord : le tableau ne notait pas le toit que `buildMatrix` (affinage PVGIS) et le solveur vivant notent.
describe('Demande croisée — recomputeMatrix passe retraits, dégagements et débord comme buildMatrix', () => {
  it('retraits de 2 m, débord 0,3 m : mêmes lignes que le balayage de buildMatrix, moins de panneaux qu’avec le retrait par défaut', () => {
    const ctx = { ...makeCtx(), matrixResult: null, overhangM: 0.3 } as unknown as Ctx;
    const retraits = uniformSetbacks(2);
    createMatrix(ctx, { renderConfig: () => {}, monthlyBill: () => FACTURE, obstructionRings: () => [], setbacksOf: () => retraits, obstructionClearances: () => [] }).recomputeMatrix();
    const attendu = fineGridMatrixV6(TOIT, LAT, FACTURE, [], { yieldFn: () => null, overhangM: 0.3, obstructionClearancesM: [], setbacksM: retraits, optimisation: null });
    expect(ctx.matrixResult!.rows.map((r) => [r.label, r.placedCount])).toEqual(attendu.rows.map((r) => [r.label, r.placedCount]));
    const parDefaut = fineGridMatrixV6(TOIT, LAT, FACTURE, [], { yieldFn: () => null });
    const max = (rows: { placedCount: number; margin: string }[]) => Math.max(...rows.filter((r) => r.margin === 'keep').map((r) => r.placedCount)); // marge gardée
    expect(max(ctx.matrixResult!.rows)).toBeLessThan(max(parDefaut.rows));
  });
});

// ACAL1525 — « Comparer les poses » dans la colonne de 320 px : de vraies puces, jamais un texte collé, et « — » sans cible.
describe('ACAL1525 — puces séparées ; % du besoin « — » sans cible', () => {
  it('chaque puce est un élément espacé ; le texte lu sépare le titre et chaque objectif', () => {
    matrice(makeCtx()).paintComparison();
    const host = document.getElementById('rp9-cible')!;
    expect(host.style.display).toBe('flex');
    expect(host.style.flexWrap).toBe('wrap');
    expect(host.style.gap).not.toBe('');
    expect(host.textContent).toMatch(/Objectif du classement : \S/);
    for (const b of puces()) expect(b.style.borderRadius).not.toBe('');
    const texte = host.textContent ?? '';
    const libelles = puces().map((b) => b.textContent ?? '');
    for (let i = 1; i < libelles.length; i++) expect(texte).toContain(`${libelles[i - 1]} ${libelles[i]}`);
  });

  it('sans cible (aucune facture) la cellule vaut « — », avec une cible un pourcentage', () => {
    const sans = { ...makeCtx(), matrixResult: fineGridMatrixV6(TOIT, LAT, 0, []) } as unknown as Ctx;
    matrice(sans).paintComparison();
    const cellules = () => Array.from(document.querySelectorAll('#rp9-compare tr')).map((tr) => tr.querySelectorAll('td')[4].textContent);
    expect(cellules().every((c) => c === '—')).toBe(true);
    matrice(makeCtx()).paintComparison();
    expect(cellules().every((c) => /^\d+ %$/.test(c ?? ''))).toBe(true);
  });
});

describe('ACAL546 — comparatif sans montant (atelier ERP)', () => {
  it('rp9-compare-wrap avec data-sans-montant : cinq cellules par ligne, aucune ne dit MAD', () => {
    document.body.innerHTML =
      '<div id="rp9-compare-wrap" data-sans-montant="1" hidden><table><tbody id="rp9-compare"></tbody></table></div>';
    const ctx = makeCtx();
    matrice(ctx).paintComparison();
    const lignes = Array.from(document.querySelectorAll('#rp9-compare tr'));
    expect(lignes.length).toBeGreaterThan(0);
    for (const tr of lignes) {
      expect(tr.querySelectorAll('td')).toHaveLength(5);
      expect(tr.textContent).not.toContain('MAD');
    }
  });

  it('sans l’attribut (aperçu public), la sixième cellule en MAD reste', () => {
    const ctx = makeCtx();
    matrice(ctx).paintComparison();
    const tr = document.querySelector('#rp9-compare tr')!;
    expect(tr.querySelectorAll('td')).toHaveLength(6);
    expect(tr.textContent).toContain('MAD');
  });
});

// ACAL1918 — « Comparer les poses » : aucune ligne en double, et le nombre annoncé est celui que la pose affiche au clic.
describe('ACAL1918 — aucune ligne en double ; le nombre annoncé égale le nombre posé au clic', () => {
  const lignesPeintes = () =>
    Array.from(document.querySelectorAll('#rp9-compare tr')).map((tr) =>
      Array.from(tr.querySelectorAll('td')).map((td) => (td.textContent ?? '').replace(/\s*✓.*$/, '')).join('|'),
    );

  it('chaque ligne du tableau est une pose distincte', () => {
    const ctx = { ...makeCtx(), matrixResult: null } as unknown as Ctx;
    matrice(ctx).recomputeMatrix();
    const lignes = lignesPeintes();
    expect(lignes.length).toBeGreaterThan(1);
    expect(new Set(lignes).size).toBe(lignes.length);
  });

  it('cible posée à 5 : la ligne « Recommandé » et toutes les lignes annoncent au plus 5', () => {
    const ctx = { ...makeCtx(), matrixResult: null, neededPanels: 5 } as unknown as Ctx;
    matrice(ctx).recomputeMatrix();
    const premiere = document.querySelector('#rp9-compare tr')!;
    expect(premiere.textContent).toContain('Recommandé');
    expect(premiere.querySelectorAll('td')[1].textContent).toBe('5');
    for (const tr of Array.from(document.querySelectorAll('#rp9-compare tr'))) {
      expect(Number((tr.querySelectorAll('td')[1].textContent ?? '').replace(/\D/g, ''))).toBeLessThanOrEqual(5);
    }
    expect(ctx.matrixResult!.winner.placedCount).toBe(5);
  });
});
