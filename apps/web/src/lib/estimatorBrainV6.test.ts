// CALX114 — LA CIBLE DE L'OPTIMISATION EST SAISIE, ELLE N'EST PLUS FIGÉE SUR L'ÉNERGIE.
//
// CE QUE CES TESTS GARDENT
// ------------------------
// 1. SANS cible saisie, RIEN ne bouge : le gagnant est celui qu'élit la chaîne
//    historique (`betterMatrixV6` à deux arguments), et la matrice renvoyée est
//    identique — un document qui ne porte pas `optimisation` doit continuer à
//    produire le MÊME calepinage, octet pour octet.
// 2. Une cible saisie CHANGE vraiment l'élection : sur une même matrice, `compte`
//    et `energie` n'élisent pas la même ligne (un module de plus contre un peu
//    moins d'énergie), et chaque départage reste déterministe.
// 3. Aucune cible ne classe sur un chiffre fabriqué : `ombrage` et `faitage`
//    exigent une MESURE fournie par l'atelier ; sans elle, la cible est REFUSÉE en
//    nommant `optimisation.cible` (D-CALX 7) — l'absence de mesure d'ombrage ne
//    vaut jamais plein soleil.
import { describe, expect, it } from 'vitest';
import {
  betterMatrixV6,
  CIBLES_OPTIMISATION,
  CIBLE_SANS_CHOIX,
  fineGridMatrixV6,
  libelleCible,
  resoudreCibleOptimisation,
  type MatrixEvalV6,
  type MatrixV6Options,
  type MatrixV6Result,
} from './estimatorBrainV6';
import { type LngLat } from './roof';

/** Contour rectangulaire de `widthM` × `depthM`, tourné de `rotDeg`, près de Casablanca. */
function rect(widthM: number, depthM: number, rotDeg = 0, lng0 = -7.6, lat0 = 33.59): LngLat[] {
  const mPerLat = 111320;
  const mPerLng = 111320 * Math.cos((lat0 * Math.PI) / 180);
  const r = (rotDeg * Math.PI) / 180;
  const coins: [number, number][] = [
    [-widthM / 2, -depthM / 2],
    [widthM / 2, -depthM / 2],
    [widthM / 2, depthM / 2],
    [-widthM / 2, depthM / 2],
  ];
  return coins.map(([x, y]) => {
    const xr = x * Math.cos(r) - y * Math.sin(r);
    const yr = x * Math.sin(r) + y * Math.cos(r);
    return [lng0 + xr / mPerLng, lat0 + yr / mPerLat] as LngLat;
  });
}

const LAT = 33.59;
/** Un toit LONG et ÉTROIT : la ligne la plus dense n'y est PAS la plus énergétique. */
const TOIT = rect(8, 24, 0);
const FACTURE = 5000;

/** Identité d'une ligne de balayage (famille, inclinaison, azimut, pose, marge). */
const id = (r: MatrixEvalV6): string =>
  `${r.family}|${r.tiltDeg}|${Math.round(r.azimuthDeg)}|${r.orientation}|${r.margin}`;

/** Le gagnant qu'élit la chaîne HISTORIQUE (appel à deux arguments) sur ces lignes. */
function gagnantHistorique(rows: readonly MatrixEvalV6[]): MatrixEvalV6 {
  let w: MatrixEvalV6 | null = null;
  for (const r of rows) if (!w || betterMatrixV6(r, w)) w = r;
  return w!;
}

/** Empreinte sérialisée du calepinage renvoyé (lignes + gagnant + optimum). */
function empreinte(res: MatrixV6Result): string {
  return JSON.stringify({ rows: res.rows, winner: res.winner, optimumRow: res.optimumRow });
}

const balayage = (options: MatrixV6Options = {}) => fineGridMatrixV6(TOIT, LAT, FACTURE, [], options);

describe('CALX114 — sans cible saisie, le balayage ne bouge PAS', () => {
  it('le gagnant est celui de la chaîne historique', () => {
    const res = balayage();
    expect(id(res.winner)).toBe(id(gagnantHistorique(res.rows)));
  });

  it('un document SANS `optimisation` rend la même matrice qu’un document qui n’en porte que la priorité', () => {
    const sans = balayage();
    const priseEnCompte = balayage({ optimisation: { priorite: 'faitage' } });
    const vide = balayage({ optimisation: {} });
    expect(empreinte(priseEnCompte)).toBe(empreinte(sans));
    expect(empreinte(vide)).toBe(empreinte(sans));
  });

  it('deux balayages identiques rendent la MÊME matrice (aucun hasard)', () => {
    expect(empreinte(balayage())).toBe(empreinte(balayage()));
  });

  it('la cible appliquée est NOMMÉE, jamais un défaut muet', () => {
    const res = balayage();
    expect(res.cible.appliquee).toBe(CIBLE_SANS_CHOIX);
    expect(res.cible.saisie).toBeNull();
    expect(res.cible.refusee).toBe(false);
    expect(res.cible.motif).toContain('optimisation.cible');
    expect(res.cible.motif).toContain('énergie annuelle posée');
  });

  it('sans mesure fournie, aucune ligne ne porte de clé de mesure', () => {
    for (const r of balayage().rows) {
      expect('accesSolaireMoyen' in r).toBe(false);
      expect('degagementFaitageM' in r).toBe(false);
    }
  });
});

describe('CALX114 — une cible saisie change vraiment l’élection', () => {
  it('`compte` et `energie` élisent des lignes DIFFÉRENTES sur la même matrice', () => {
    const parEnergie = balayage({ optimisation: { cible: 'energie' } });
    const parCompte = balayage({ optimisation: { cible: 'compte' } });
    expect(id(parCompte.winner)).not.toBe(id(parEnergie.winner));
    // Le marché est réel et chiffré : un module de plus contre un peu moins d'énergie.
    expect(parCompte.winner.placedCount).toBeGreaterThan(parEnergie.winner.placedCount);
    expect(parEnergie.winner.annualKwh).toBeGreaterThan(parCompte.winner.annualKwh);
  });

  it('`energie` rend EXACTEMENT le gagnant d’un document sans cible', () => {
    expect(id(balayage({ optimisation: { cible: 'energie' } }).winner)).toBe(id(balayage().winner));
  });

  it('chaque cible élit bien le maximum de SON critère', () => {
    const parCompte = balayage({ optimisation: { cible: 'compte' } });
    const parEnergie = balayage({ optimisation: { cible: 'energie' } });
    expect(parCompte.winner.placedCount).toBe(Math.max(...parCompte.rows.map((r) => r.placedCount)));
    expect(parEnergie.winner.annualKwh).toBe(Math.max(...parEnergie.rows.map((r) => r.annualKwh)));
  });

  it('`kwc` suit le compte tant qu’il n’existe qu’une puissance unitaire au catalogue', () => {
    const parKwc = balayage({ optimisation: { cible: 'kwc' } });
    const parCompte = balayage({ optimisation: { cible: 'compte' } });
    expect(id(parKwc.winner)).toBe(id(parCompte.winner));
  });

  it('le départage reste déterministe : deux balayages à `compte` rendent le même gagnant', () => {
    const a = balayage({ optimisation: { cible: 'compte' } });
    const b = balayage({ optimisation: { cible: 'compte' } });
    expect(empreinte(a)).toBe(empreinte(b));
  });

  it('le comparateur ne dit jamais que chacune est meilleure que l’autre', () => {
    const rows = balayage().rows;
    for (const cible of CIBLES_OPTIMISATION.map((c) => c.id)) {
      for (let i = 0; i < 40; i += 1) {
        const a = rows[i];
        const b = rows[rows.length - 1 - i];
        expect(betterMatrixV6(a, b, cible) && betterMatrixV6(b, a, cible)).toBe(false);
      }
    }
  });
});

describe('CALX114 — une cible sans mesure est REFUSÉE, jamais devinée', () => {
  it('`ombrage` sans accès solaire mesuré est écartée en nommant le champ', () => {
    const res = balayage({ optimisation: { cible: 'ombrage' } });
    expect(res.cible.saisie).toBe('ombrage');
    expect(res.cible.refusee).toBe(true);
    expect(res.cible.champ).toBe('optimisation.cible');
    expect(res.cible.motif).toContain('aucun accès solaire');
    expect(res.cible.motif).toContain('ne vaut pas plein soleil');
    // Et le classement retombe sur l'objectif historique, pas sur un accès inventé.
    expect(res.cible.appliquee).toBe(CIBLE_SANS_CHOIX);
    expect(id(res.winner)).toBe(id(balayage().winner));
  });

  it('`ombrage` AVEC l’accès solaire mesuré par l’atelier élit le mieux exposé', () => {
    const mesure = (tiltDeg: number) => (tiltDeg === 0 ? 0.95 : 0.5);
    const res = balayage({
      optimisation: { cible: 'ombrage' },
      mesuresCible: ({ row }) => ({ accesSolaireMoyen: mesure(row.tiltDeg) }),
    });
    expect(res.cible.refusee).toBe(false);
    expect(res.cible.appliquee).toBe('ombrage');
    expect(res.winner.accesSolaireMoyen).toBe(0.95);
    expect(res.winner.tiltDeg).toBe(0);
    // À accès solaire égal, c'est la chaîne historique qui départage — donc le
    // gagnant est le meilleur des mieux exposés, pas le premier venu.
    const mieuxExposees = res.rows.filter((r) => r.accesSolaireMoyen === 0.95);
    expect(id(res.winner)).toBe(id(gagnantHistorique(mieuxExposees)));
  });

  it('`faitage` sans dégagement mesuré est écartée en nommant le champ', () => {
    const res = balayage({ optimisation: { cible: 'faitage' } });
    expect(res.cible.refusee).toBe(true);
    expect(res.cible.champ).toBe('optimisation.cible');
    expect(res.cible.motif).toContain('faîtage');
    expect(res.cible.appliquee).toBe(CIBLE_SANS_CHOIX);
  });

  it('`faitage` AVEC un dégagement mesuré préfère la configuration qui le laisse libre', () => {
    const res = balayage({
      optimisation: { cible: 'faitage' },
      mesuresCible: ({ row }) => ({ degagementFaitageM: row.margin === 'keep' ? 1.2 : 0 }),
    });
    expect(res.cible.appliquee).toBe('faitage');
    expect(res.winner.degagementFaitageM).toBe(1.2);
    expect(res.winner.margin).toBe('keep');
  });

  it('une mesure illisible n’est pas retenue (la ligne reste non mesurée)', () => {
    const res = balayage({
      mesuresCible: () => ({ accesSolaireMoyen: Number.NaN, degagementFaitageM: undefined }),
    });
    for (const r of res.rows) expect('accesSolaireMoyen' in r).toBe(false);
  });
});

describe('CALX114 — `resoudreCibleOptimisation` : le vocabulaire est celui du contrat', () => {
  it('les cinq cibles sont celles de `optimisation.cible` (CALX88), dans son ordre', () => {
    expect(CIBLES_OPTIMISATION.map((c) => c.id)).toEqual(['compte', 'kwc', 'energie', 'ombrage', 'faitage']);
    for (const c of CIBLES_OPTIMISATION) expect(libelleCible(c.id)).toBe(c.label);
  });

  it('une cible hors contrat est refusée en citant la valeur ET le champ', () => {
    const r = resoudreCibleOptimisation({ cible: 'rentabilite' });
    expect(r.refusee).toBe(true);
    expect(r.champ).toBe('optimisation.cible');
    expect(r.motif).toContain('rentabilite');
    expect(r.appliquee).toBe(CIBLE_SANS_CHOIX);
    expect(r.saisie).toBeNull();
  });

  it('un document absent, vide ou sans cible nomme l’objectif historique', () => {
    for (const choix of [undefined, null, {}, { cible: null }, { cible: '' }]) {
      const r = resoudreCibleOptimisation(choix);
      expect(r.appliquee).toBe(CIBLE_SANS_CHOIX);
      expect(r.refusee).toBe(false);
      expect(r.motif.length).toBeGreaterThan(0);
    }
  });

  it('`ombrage` et `faitage` passent dès que leur mesure existe', () => {
    expect(resoudreCibleOptimisation({ cible: 'ombrage' }, { accesSolaire: true }).appliquee).toBe('ombrage');
    expect(resoudreCibleOptimisation({ cible: 'faitage' }, { faitage: true }).appliquee).toBe('faitage');
    expect(resoudreCibleOptimisation({ cible: 'ombrage' }, { faitage: true }).refusee).toBe(true);
  });

  it('`compte` et `kwc` n’exigent aucune mesure supplémentaire', () => {
    for (const cible of ['compte', 'kwc', 'energie'] as const) {
      const r = resoudreCibleOptimisation({ cible });
      expect(r.appliquee).toBe(cible);
      expect(r.refusee).toBe(false);
      expect(r.motif).toContain(libelleCible(cible).toLowerCase());
    }
  });
});
