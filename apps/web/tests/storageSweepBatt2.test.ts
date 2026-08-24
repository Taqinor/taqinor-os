// ORDRE FONDATEUR (24/08/2026, soir) — trois demandes sur le graphe client
// « consommation / couverture batterie » de la page publique
// /proposition/<token> :
//   1. le bouton batterie (déjà retrouvé le 21/08, commit d545ede2 — CJ2b
//      (4/4)) n'est pas retouché ici.
//   2. sélection de PLUSIEURS packs de batterie : le curseur « et avec N
//      batteries ? » (WJ120) va désormais jusqu'au plafond RÉEL du mini-
//      balayage de stockage du moteur (`apps.ventes.dimensionnement` DIM2,
//      `balayage_stockage` public — voir `_balayage_stockage_publique`,
//      apps/ventes/public_views.py) au lieu d'un « 3 » arbitraire, et affiche
//      le prix TTC RÉEL de chaque palier quand il existe.
//   3. message de sur-stockage : quand N atteint le premier palier REFUSÉ par
//      le moteur (la batterie ne se rechargerait plus chaque jour), un petit
//      message dérivé du pourcentage RÉEL de remplissage du pire mois
//      s'affiche — jamais un nouveau calcul côté client, jamais un chiffre
//      inventé.
//
// `storageSweepInfo` est le parseur PUR (même discipline « zéro chiffre
// inventé » que `batteryRegimeInfo`/`tarifBracketStory`, propositionLPropCJ2bBis
// .test.ts) : `null` sur une clé absente/malformée. Les tests « Source pin »
// pincent le câblage réel dans [...token].astro (le code, commentaires
// retirés — un commentaire ne doit jamais faire passer un test).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { storageSweepInfo } from '../src/lib/proposition';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const PAGE = read('../src/pages/proposition/[...token].astro').replace(/\r\n/g, '\n');
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

describe('storageSweepInfo — mini-balayage de stockage, client-safe', () => {
  it('null quand `balayage_stockage` est absent', () => {
    expect(storageSweepInfo({})).toBeNull();
    expect(storageSweepInfo({ balayage_stockage: null })).toBeNull();
  });

  it('null quand ni paliers ni refuse ne sont lisibles', () => {
    expect(storageSweepInfo({ balayage_stockage: {} })).toBeNull();
    expect(storageSweepInfo({ balayage_stockage: { paliers: [], refuse: null } })).toBeNull();
  });

  it('lit les paliers retenus (nb_packs, capacité, prix TTC, remplissage moyen)', () => {
    const r = storageSweepInfo({
      balayage_stockage: {
        paliers: [
          { nb_packs: 1, capacite_kwh: 5, cout_ttc: 42000, remplissage_moyen_pct: 98.2 },
          { nb_packs: 2, capacite_kwh: 10, cout_ttc: 78000, remplissage_moyen_pct: 91.5 },
        ],
        refuse: null,
      },
    });
    expect(r).toEqual({
      paliers: [
        { nbPacks: 1, capaciteKwh: 5, coutTtc: 42000, remplissageMoyenPct: 98.2 },
        { nbPacks: 2, capaciteKwh: 10, coutTtc: 78000, remplissageMoyenPct: 91.5 },
      ],
      refuse: null,
    });
  });

  it('un palier sans nb_packs/capacite_kwh lisible est omis (jamais un défaut fabriqué)', () => {
    const r = storageSweepInfo({
      balayage_stockage: {
        paliers: [
          { nb_packs: 1, capacite_kwh: 5, cout_ttc: 42000, remplissage_moyen_pct: 98.2 },
          { nb_packs: null, capacite_kwh: 10 },
          { capacite_kwh: 15, cout_ttc: 1 },
        ],
      },
    });
    expect(r!.paliers).toHaveLength(1);
    expect(r!.paliers[0].nbPacks).toBe(1);
  });

  it('lit le premier palier REFUSÉ (nb_packs, capacité, remplissage du pire mois)', () => {
    const r = storageSweepInfo({
      balayage_stockage: {
        paliers: [],
        refuse: { nb_packs: 3, capacite_kwh: 15, remplissage_pire_mois_pct: 41.7 },
      },
    });
    expect(r).toEqual({
      paliers: [],
      refuse: { nbPacks: 3, capaciteKwh: 15, remplissagePireMoisPct: 41.7 },
    });
  });

  it('refuse sans remplissage_pire_mois_pct reste affichable (le champ passe à null)', () => {
    const r = storageSweepInfo({
      balayage_stockage: { refuse: { nb_packs: 3, capacite_kwh: 15 } },
    });
    expect(r!.refuse).toEqual({ nbPacks: 3, capaciteKwh: 15, remplissagePireMoisPct: null });
  });

  it('un nombre non-fini (NaN, chaîne) devient null plutôt qu’un chiffre inventé', () => {
    const r = storageSweepInfo({
      balayage_stockage: {
        paliers: [{ nb_packs: 1, capacite_kwh: 5, cout_ttc: Number.NaN }],
        refuse: null,
      },
    });
    expect(r!.paliers[0].coutTtc).toBeNull();
  });
});

describe('[...token].astro — le plafond du curseur batterie suit le balayage RÉEL', () => {
  it('BATTERY_SIM_MAX_UNITS retombe sur storageSweep (refusé/dernier palier retenu, sinon 3)', () => {
    expect(CODE).toContain(
      'const storageRealMax = Math.max(storageSweep?.refuse?.nbPacks ?? 0, storageMaxRetenu ?? 0);',
    );
    expect(CODE).toContain('const BATTERY_SIM_MAX_UNITS = Math.max(offeredUnits, storageRealMax || 3);');
  });

  it('la config client relit les paliers réels (prix TTC) et le premier refusé (jamais un nouveau calcul)', () => {
    expect(CODE).toContain('storagePaliers: storagePaliersSorted.map((p) => ({ n: p.nbPacks, ttc: p.coutTtc }))');
    expect(CODE).toContain('{ n: storageSweep.refuse.nbPacks, pireMoisPct: storageSweep.refuse.remplissagePireMoisPct }');
  });

  it('le prix affiché retombe sur le prix RÉEL du palier de stockage à ce N avant « sur étude »', () => {
    expect(CODE).toContain('else if (palierTtc != null) el.textContent = fmtMad(palierTtc);');
  });
});

describe('[...token].astro — message de sur-stockage, dérivé des données réelles', () => {
  it('le bloc ne s’affiche que quand N atteint le premier palier REFUSÉ par le moteur', () => {
    expect(CODE).toContain('id="battery-sim-overstorage"');
    expect(CODE).toContain('const hit = !!refuse && refuse.n === n;');
    expect(CODE).toContain('el.hidden = !hit;');
  });

  it('le pourcentage inséré est le remplissage RÉEL du pire mois (aucun calcul côté JS)', () => {
    expect(CODE).toContain('if (numEl) numEl.textContent = fmtPct(refuse.pireMoisPct);');
  });

  it('la phrase ne parle jamais de "plafond de remplissage" (jargon interne du moteur, non client-safe)', () => {
    expect(CODE).not.toContain('plafond de remplissage');
  });
});
