// CAL75 — écart rangée/colonne RÉGLABLE en pose optimisée (jusqu'ici réglable SEULEMENT en
// placement libre). `optimizer.ts` ne fait que transmettre `ctx.colGapM`/`ctx.rowGapExtraM` au
// pavage (packConfig, estimatorBrainV2.ts) et re-pave à chaud — la physique testée ici EST le
// changement : options absentes → calepinage identique au millimètre ; écart agrandi → moins de
// panneaux tiennent (le compte baisse), jamais l'inverse.
import { describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom'; // ACAL574
import { type Ctx } from './context'; // ACAL574
import { carteDeLaPoseTenue, direEcartALaPose, direEcartPoseRelue, motifPanExistant, noteEcartPoseRelue, remettreSurLePlan } from './panExistant'; // ACAL574, ACAL1900
import { createLayoutState } from '../../lib/layoutVariability'; // ACAL1900
import { serializeLayout } from './prefill'; // ACAL1900
import { annualSavingsMad, packConfig, defaultEastWestGeometry, type PackOptions } from '../../lib/estimatorBrainV2';
import { PANEL2_SHORT_M, PERIMETER_SETBACK_M } from '../../lib/roofPro2';
import {
  cibleOptimisationSaisie,
  choixOptimisationCourant,
  createOptimizer, // ACAL574
  departagerRemplissage,
  economieAffichee, // ACAL994
  libelleGainBifacial,
  poserCibleOptimisation,
  poserChoixOptimisation,
  PRIORITES_REMPLISSAGE,
  type EntreeDepartage,
} from './optimizer';
import { rectRing } from './harnaisAtelier'; import { MODULE_PAR_DEFAUT_ATELIER } from './moduleSelect'; // T4-X8-012
import { freeGeomFrom } from './freeMode'; // ACAL2032
import { hardViolationsFor, panelCornersFor, toUV } from '../../lib/freeLayout'; // ACAL2032
import type { Obstacle } from '../../lib/obstacles'; // ACAL2032
import type { LayoutPlan } from './types'; // ACAL2032
import { DEG2M as DEG2M_TEST } from './constants'; // ACAL2032
import { fmt, fmtKwc, fmtMad } from './dom'; // ACAL994 + R2-09
import { suiteCouverture } from './tailleConception'; // T4-X5-005
import { phraseSurplus, phraseTiennent, texteSurDevis } from './affichageErp'; // R2-17, T4-X8-012 (une cible)
import { createZones } from './zones'; // ACAL1418
import { factureCarteDe, lireFactureSaisie } from './factureCarte'; // ACAL777
import { createShadingUi, seuilEffectifAccesSolaire } from './shadingUi'; // ACAL548, ACAL1900
import { cibleDepuisCarte, maxDuSolveur, panneauxPourCible, phraseCible } from './cibleProduction'; // ACAL1618, ACAL1903
import { cotesDePavage } from '../../lib/roofPro2';
import {
  causeDuPanVide, ecrireMotifsDansDocument, mesurerPanVide, motifPenteNord, noterMotifPanVide, retraitApplique, // ACAL1970
  semerMotifsDepuisDocument, type MesuresPanVide,
} from './motifPanVide'; // ACAL549

const ring = rectRing(20, 15);
const baseOpts: PackOptions = { family: 'south', tiltDeg: 13 };

describe('CAL75 — packConfig(colGapM, rowGapExtraM)', () => {
  it('options absentes → calepinage IDENTIQUE (même compte, mêmes positions) à avant CAL75', () => {
    const withoutOpts = packConfig(ring, 33.5, baseOpts);
    const withDefaultsExplicit = packConfig(ring, 33.5, { ...baseOpts, colGapM: undefined, rowGapExtraM: 0 });
    expect(withDefaultsExplicit.best.count).toBe(withoutOpts.best.count);
    expect(withDefaultsExplicit.best.rowPitchM).toBeCloseTo(withoutOpts.best.rowPitchM, 9);
    expect(withDefaultsExplicit.best.panels).toEqual(withoutOpts.best.panels);
  });

  it('colGapM agrandi → jamais PLUS de panneaux (les colonnes s’espacent, le compte baisse ou reste égal)', () => {
    const tight = packConfig(ring, 33.5, baseOpts);
    const wide = packConfig(ring, 33.5, { ...baseOpts, colGapM: 0.5 });
    expect(wide.best.count).toBeLessThanOrEqual(tight.best.count);
    expect(wide.best.count).toBeGreaterThan(0); // le toit reste assez grand pour en accueillir
  });

  it('rowGapExtraM agrandi → le pas de rangée grandit d’AUTANT, le compte baisse ou reste égal', () => {
    const tight = packConfig(ring, 33.5, baseOpts);
    const spaced = packConfig(ring, 33.5, { ...baseOpts, rowGapExtraM: 0.3 });
    expect(spaced.best.rowPitchM).toBeCloseTo(tight.best.rowPitchM + 0.3, 9);
    expect(spaced.best.count).toBeLessThanOrEqual(tight.best.count);
  });

  it('un colGapM négatif est ramené à 0 (jamais un recouvrement)', () => {
    const negative = packConfig(ring, 33.5, { ...baseOpts, colGapM: -5 });
    const zero = packConfig(ring, 33.5, { ...baseOpts, colGapM: 0 });
    expect(negative.best.count).toBe(zero.best.count);
  });

  it('même écart appliqué en Est-Ouest (chevron) : rowGapExtraM élargit aussi le pas entre chevrons', () => {
    const ew: PackOptions = { family: 'eastwest', tiltDeg: 13 };
    const tight = packConfig(ring, 33.5, ew);
    const spaced = packConfig(ring, 33.5, { ...ew, rowGapExtraM: 0.3 });
    // Compare la MÊME orientation des deux côtés (`best` peut basculer portrait/paysage selon
    // l'écart, ce qui changerait aussi la géométrie du panneau — pas ce qu'on veut isoler ici).
    expect(spaced.landscape.rowPitchM).toBeCloseTo(tight.landscape.rowPitchM + 0.3, 9);
    expect(spaced.portrait.rowPitchM).toBeCloseTo(tight.portrait.rowPitchM + 0.3, 9);
  });
});

// CAL87 — l'est-ouest dos à dos existait comme variante CALCULÉE, mais son faîtage et son
// écart entre chevrons étaient FIGÉS dans le pavage. Ils sont désormais SAISISSABLES, avec
// pour valeurs par défaut exactement celles appliquées aujourd'hui.
describe('CAL87 — géométrie Est-Ouest paramétrable (faîtage + écart inter-chevrons)', () => {
  const ew: PackOptions = { family: 'eastwest', tiltDeg: 13 };

  it('valeurs par DÉFAUT → variante Est-Ouest IDENTIQUE à aujourd’hui (compte et positions)', () => {
    const avant = packConfig(ring, 33.5, ew);
    const apres = packConfig(ring, 33.5, { ...ew, eastWestGeometry: {} });
    expect(apres.best.count).toBe(avant.best.count);
    expect(apres.best.rowPitchM).toBeCloseTo(avant.best.rowPitchM, 9);
    expect(apres.best.panels).toEqual(avant.best.panels);
  });

  it('les valeurs par défaut EXPOSÉES sont celles que le pavage applique', () => {
    const avant = packConfig(ring, 33.5, ew);
    const d = defaultEastWestGeometry(33.5, 13, PANEL2_SHORT_M);
    expect(d.ridgeGapM).toBe(0);
    // Réinjectées explicitement, elles reproduisent le pavage au millimètre.
    const apres = packConfig(ring, 33.5, { ...ew, eastWestGeometry: d });
    expect(apres.landscape.rowPitchM).toBeCloseTo(avant.landscape.rowPitchM, 9);
  });

  it('un FAÎTAGE saisi élargit le chevron : le pas grandit d’autant, le compte suit', () => {
    const jointif = packConfig(ring, 33.5, ew);
    const ecarte = packConfig(ring, 33.5, { ...ew, eastWestGeometry: { ridgeGapM: 0.4 } });
    expect(ecarte.landscape.rowPitchM).toBeCloseTo(jointif.landscape.rowPitchM + 0.4, 9);
    expect(ecarte.landscape.count).toBeLessThanOrEqual(jointif.landscape.count);
  });

  it('un ÉCART INTER-CHEVRONS saisi remplace la valeur calculée (dans les deux sens)', () => {
    const d = defaultEastWestGeometry(33.5, 13, PANEL2_SHORT_M);
    const base = packConfig(ring, 33.5, ew);
    const large = packConfig(ring, 33.5, { ...ew, eastWestGeometry: { interTentGapM: d.interTentGapM + 0.5 } });
    const serre = packConfig(ring, 33.5, { ...ew, eastWestGeometry: { interTentGapM: 0 } });
    expect(large.landscape.rowPitchM).toBeCloseTo(base.landscape.rowPitchM + 0.5, 9);
    expect(serre.landscape.rowPitchM).toBeCloseTo(base.landscape.rowPitchM - d.interTentGapM, 9);
    expect(large.landscape.count).toBeLessThanOrEqual(base.landscape.count);
  });

  it('une valeur négative est ramenée à 0 (un écart négatif n’existe pas)', () => {
    const neg = packConfig(ring, 33.5, { ...ew, eastWestGeometry: { ridgeGapM: -3, interTentGapM: -1 } });
    const zero = packConfig(ring, 33.5, { ...ew, eastWestGeometry: { ridgeGapM: 0, interTentGapM: 0 } });
    expect(neg.landscape.rowPitchM).toBeCloseTo(zero.landscape.rowPitchM, 9);
  });

  it('la famille SUD n’est pas touchée par la géométrie est-ouest', () => {
    const avant = packConfig(ring, 33.5, baseOpts);
    const apres = packConfig(ring, 33.5, { ...baseOpts, eastWestGeometry: { ridgeGapM: 2, interTentGapM: 2 } });
    expect(apres.best.count).toBe(avant.best.count);
    expect(apres.best.rowPitchM).toBeCloseTo(avant.best.rowPitchM, 9);
  });
});

// CAL83 — la PRIORITÉ DE REMPLISSAGE d'une zone ne fait que DÉPARTAGER.
// Le cas d'essai est à optima multiples : un tracé plus profond que ce que les rangées
// occupent réellement, donc un MÊME compte de panneaux tient à plusieurs positions.
// Ce que ces tests interdisent : qu'une priorité fasse perdre un module, et qu'elle
// prétende départager ce qu'elle ne sait pas (ensoleillement sans ombre déclarée) —
// la règle « zéro chiffre inventé » appliquée à un classement.
describe('CAL83 — priorité de remplissage : un DÉPARTAGE, jamais un arbitrage du compte', () => {
  const grandToit = rectRing(30, 26);

  /** Le pavage RÉEL d'un toit large et profond : le cas à optima multiples. */
  function entreeReelle(): EntreeDepartage {
    const pack = packConfig(grandToit, 33.5, baseOpts);
    return {
      ringENU: pack.ringENU,
      panels: pack.best.panels,
      azimuthDeg: pack.azimuthDeg,
      rowWidthM: pack.best.rowWidthM,
      footprintPerPanelM2: pack.best.footprintPerPanelM2,
      setbackM: PERIMETER_SETBACK_M,
    };
  }

  /** Moyenne du pavage sur l'axe de progression des rangées (v), en mètres. */
  function moyenneV(panels: { cx: number; cy: number }[], azimuthDeg: number): number {
    const az = (azimuthDeg * Math.PI) / 180;
    const f = [Math.sin(az), Math.cos(az)];
    return panels.reduce((acc, p) => acc + p.cx * f[0] + p.cy * f[1], 0) / (panels.length || 1);
  }

  /** Moyenne du pavage sur l'axe long des rangées (u), en mètres. */
  function moyenneU(panels: { cx: number; cy: number }[], azimuthDeg: number): number {
    const az = (azimuthDeg * Math.PI) / 180;
    const u = [-Math.cos(az), Math.sin(az)];
    return panels.reduce((acc, p) => acc + p.cx * u[0] + p.cy * u[1], 0) / (panels.length || 1);
  }

  it('le cas d’essai a bien du MOU : plusieurs positions pour le même compte', () => {
    const e = entreeReelle();
    expect(e.panels.length).toBeGreaterThan(10); // un vrai champ, pas deux panneaux
    const colle = departagerRemplissage(e, 'egout');
    expect(colle.departage).toBe(true);
    expect(colle.decalageV_m).toBeGreaterThan(0);
  });

  it('CHAQUE priorité garde le compte EXACT du pavage de départ', () => {
    const e = entreeReelle();
    for (const { id } of PRIORITES_REMPLISSAGE) {
      const r = departagerRemplissage(e, id);
      expect(r.count, `priorité ${id}`).toBe(e.panels.length);
      expect(r.panels.length, `priorité ${id}`).toBe(e.panels.length);
    }
  });

  it('changer la priorité REDISTRIBUE les panneaux (faîtage ≠ égout) sans changer le compte', () => {
    const e = entreeReelle();
    const faitage = departagerRemplissage(e, 'faitage');
    const egout = departagerRemplissage(e, 'egout');
    expect(faitage.count).toBe(e.panels.length);
    expect(egout.count).toBe(e.panels.length);
    // v croît du faîtage vers l'égout : coller à l'égout pousse le pavage vers les v hauts.
    expect(moyenneV(egout.panels, e.azimuthDeg)).toBeGreaterThan(moyenneV(faitage.panels, e.azimuthDeg));
    expect(egout.panels).not.toEqual(faitage.panels);
  });

  it('les deux rives départagent sur l’axe des rangées, toujours à compte égal', () => {
    const e = entreeReelle();
    const debut = departagerRemplissage(e, 'rive-debut');
    const fin = departagerRemplissage(e, 'rive-fin');
    expect(debut.count).toBe(e.panels.length);
    expect(fin.count).toBe(e.panels.length);
    expect(moyenneU(fin.panels, e.azimuthDeg)).toBeGreaterThan(moyenneU(debut.panels, e.azimuthDeg));
  });

  it('le décalage reste borné par le tracé (jamais une translation folle)', () => {
    const e = entreeReelle();
    for (const id of ['faitage', 'egout', 'rive-debut', 'rive-fin'] as const) {
      const r = departagerRemplissage(e, id);
      expect(Math.abs(r.decalageU_m) + Math.abs(r.decalageV_m)).toBeLessThan(30);
      expect(r.count).toBe(e.panels.length);
    }
  });

  it('« aucune » ne touche à rien : c’est le pavage d’aujourd’hui, à l’identique', () => {
    const e = entreeReelle();
    const r = departagerRemplissage(e, 'aucune');
    expect(r.departage).toBe(false);
    expect(r.decalageU_m).toBe(0);
    expect(r.decalageV_m).toBe(0);
    expect(r.panels).toEqual(e.panels);
  });

  it('« meilleur ensoleillement » sans source d’ombre déclarée : il le DIT, il n’invente pas', () => {
    const e = entreeReelle();
    const r = departagerRemplissage(e, 'ensoleillement');
    expect(r.departage).toBe(false);
    expect(r.count).toBe(e.panels.length);
    expect(r.motif).toMatch(/ombre/i);
  });

  it('« meilleur ensoleillement » avec une ombre relevée s’en éloigne, à compte égal', () => {
    const e = entreeReelle();
    const az = (e.azimuthDeg * Math.PI) / 180;
    const f = [Math.sin(az), Math.cos(az)];
    // Une ombre posée juste avant la première rangée (côté v petit) : le départage
    // doit pousser le pavage dans l'autre sens — sans perdre un seul panneau.
    const vMin = Math.min(...e.panels.map((p) => p.cx * f[0] + p.cy * f[1]));
    const proche = e.panels.find((p) => p.cx * f[0] + p.cy * f[1] <= vMin + 1e-6) ?? e.panels[0];
    const source: [number, number] = [proche.cx - f[0] * 3, proche.cy - f[1] * 3];
    const avec = departagerRemplissage({ ...e, sourcesOmbreENU: [source] }, 'ensoleillement');
    expect(avec.count).toBe(e.panels.length);
    if (avec.departage) {
      expect(moyenneV(avec.panels, e.azimuthDeg)).toBeGreaterThan(moyenneV(e.panels, e.azimuthDeg));
    } else {
      expect(avec.motif).toBeTruthy(); // aucun mou disponible → il le dit
    }
  });

  it('un pavage vide ou un tracé incomplet ne bougent pas, et disent pourquoi', () => {
    const e = entreeReelle();
    const vide = departagerRemplissage({ ...e, panels: [] }, 'egout');
    expect(vide.count).toBe(0);
    expect(vide.motif).toBeTruthy();
    const sansTrace = departagerRemplissage({ ...e, ringENU: [] }, 'egout');
    expect(sansTrace.count).toBe(e.panels.length);
    expect(sansTrace.motif).toBeTruthy();
  });
});

// CALX49 — LE DÉPARTAGE, MAINTENANT BRANCHÉ SUR UN SÉLECTEUR « Priorité de pose ».
// Le constructeur applique `departagerRemplissage` au pavage courant et repose le
// résultat. Ce que ces tests tiennent, c'est ce que cette commande PROMET à l'écran :
//   * les six choix du sélecteur sont ceux du module, libellés compris ;
//   * appliquer une priorité ne change JAMAIS le compte — c'est une translation, pas
//     un ré-arbitrage : les modules gardent leurs écarts deux à deux ;
//   * « Meilleur ensoleillement » sans accès solaire est INACTIF et le DIT en français ;
//   * le pavage de départ reste intact, donc il y a toujours de quoi revenir en arrière.
describe('CALX49 — priorité de pose : la commande du départage', () => {
  const grandToit = rectRing(30, 26);

  function entreeDuPavage(): EntreeDepartage {
    const pack = packConfig(grandToit, 33.5, baseOpts);
    return {
      ringENU: pack.ringENU,
      panels: pack.best.panels,
      azimuthDeg: pack.azimuthDeg,
      rowWidthM: pack.best.rowWidthM,
      footprintPerPanelM2: pack.best.footprintPerPanelM2,
      setbackM: PERIMETER_SETBACK_M,
    };
  }

  it('le sélecteur est alimenté par les SIX valeurs du module, libellés compris', () => {
    expect(PRIORITES_REMPLISSAGE).toHaveLength(6);
    expect(PRIORITES_REMPLISSAGE.map((p) => p.id)).toEqual([
      'aucune',
      'faitage',
      'egout',
      'rive-debut',
      'rive-fin',
      'ensoleillement',
    ]);
    const libelles = PRIORITES_REMPLISSAGE.map((p) => p.label);
    for (const libelle of libelles) expect(libelle.trim().length).toBeGreaterThan(3);
    expect(new Set(libelles).size).toBe(libelles.length);
  });

  it('appliquer une priorité garde le compte ET les écarts entre modules (une translation)', () => {
    const e = entreeDuPavage();
    for (const { id } of PRIORITES_REMPLISSAGE) {
      const r = departagerRemplissage(e, id);
      expect(r.count, `priorité ${id}`).toBe(e.panels.length);
      expect(r.panels.length, `priorité ${id}`).toBe(e.panels.length);
      // Même décalage pour TOUS les modules : aucun n'a été déplacé isolément.
      const dx = r.panels[0].cx - e.panels[0].cx;
      const dy = r.panels[0].cy - e.panels[0].cy;
      r.panels.forEach((p, i) => {
        expect(p.cx - e.panels[i].cx, `priorité ${id}, module ${i}`).toBeCloseTo(dx, 9);
        expect(p.cy - e.panels[i].cy, `priorité ${id}, module ${i}`).toBeCloseTo(dy, 9);
      });
    }
  });

  it('« Meilleur ensoleillement » sans accès solaire est INACTIF, et son motif est lisible', () => {
    const e = entreeDuPavage();
    for (const sansAcces of [undefined, [] as [number, number][]]) {
      const r = departagerRemplissage({ ...e, sourcesOmbreENU: sansAcces }, 'ensoleillement');
      expect(r.departage).toBe(false);
      expect(r.count).toBe(e.panels.length);
      expect(r.decalageU_m).toBe(0);
      expect(r.decalageV_m).toBe(0);
      const motif = r.motif ?? '';
      // Une phrase française entière, qui NOMME ce qui manque — jamais un code.
      expect(motif.length).toBeGreaterThan(30);
      expect(motif).toMatch(/ombre/i);
      expect(motif.trim().endsWith('.')).toBe(true);
    }
  });

  it('le pavage de départ n’est jamais muté : il y a toujours de quoi revenir en arrière', () => {
    const e = entreeDuPavage();
    const avant = e.panels.map((p) => ({ cx: p.cx, cy: p.cy }));
    for (const { id } of PRIORITES_REMPLISSAGE) {
      const r = departagerRemplissage(e, id);
      // Le pavage d'entrée est intact après l'application…
      e.panels.forEach((p, i) => {
        expect(p.cx).toBeCloseTo(avant[i].cx, 12);
        expect(p.cy).toBeCloseTo(avant[i].cy, 12);
      });
      // …et le décalage inverse le repose exactement là où il était.
      const dx = r.panels[0].cx - avant[0].cx;
      const dy = r.panels[0].cy - avant[0].cy;
      r.panels.forEach((p, i) => {
        expect(p.cx - dx, `priorité ${id}`).toBeCloseTo(avant[i].cx, 9);
        expect(p.cy - dy, `priorité ${id}`).toBeCloseTo(avant[i].cy, 9);
      });
    }
  });
});

// ── CALX114 — le point UNIQUE où l'objectif saisi du document est déposé ───────────
// Le balayage est appelé à deux endroits (tableau matrice, affinage PVGIS) : si chacun
// gardait son propre objectif, la ligne badgée et la carte reco classeraient sur deux
// critères différents. Ces tests gardent le dépôt : il n'invente aucun objectif, il
// n'écrase pas les autres clés saisies, et il refuse une valeur hors contrat.
describe('CALX114 — dépôt de `optimisation` (CALX88) pour le balayage', () => {
  it('sans dépôt, aucun objectif n’est saisi et la phrase le NOMME', () => {
    const r = poserChoixOptimisation(null);
    expect(choixOptimisationCourant()).toBeNull();
    expect(cibleOptimisationSaisie()).toBeNull();
    expect(r.appliquee).toBe('energie');
    expect(r.motif).toContain('Aucun objectif saisi');
  });

  it('poser une cible ne touche PAS les autres clés du document', () => {
    poserChoixOptimisation({ priorite: 'faitage', seuilAccesSolaire: 0.7 });
    poserCibleOptimisation('compte');
    expect(choixOptimisationCourant()).toEqual({
      priorite: 'faitage',
      seuilAccesSolaire: 0.7,
      cible: 'compte',
    });
    poserCibleOptimisation(null);
    expect(choixOptimisationCourant()).toEqual({ priorite: 'faitage', seuilAccesSolaire: 0.7 });
    expect(cibleOptimisationSaisie()).toBeNull();
  });

  it('une valeur hors contrat ne presse aucune puce et nomme le champ', () => {
    const r = poserChoixOptimisation({ cible: 'rentabilite' });
    expect(cibleOptimisationSaisie()).toBeNull();
    expect(r.refusee).toBe(true);
    expect(r.champ).toBe('optimisation.cible');
    poserChoixOptimisation(null);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL79 — une seule borne `clampNeeded`, et la cible VENDUE n'est jamais plafonnée.
// ═══════════════════════════════════════════════════════════════════════════════
import { besoinVendu, clampNeeded, lireRendement, RENDEMENT_PVGIS_DEFAUT } from './optimizer';
import { hydrateFromDevis, type DevisPayload } from './prefill';
import { heriterDuPanDecoupe } from './tailleAuto'; // ACAL1448
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

describe('ACAL79 — cible vendue et borne unique', () => {
  it('hydrateFromDevis cible 450 → neededPanels 450', () => {
    const h = hydrateFromDevis({ id: 7, cible: { panneaux: 450 } });
    expect(h.neededPanels).toBe(450);
    expect(besoinVendu(h.neededPanels)).toBe(450);
    // La borne des besoins DÉDUITS reste 400 (choix produit inchangé).
    expect(clampNeeded(450)).toBe(400);
    expect(besoinVendu(null)).toBe(0);
  });

  it('une seule définition de clampNeeded utilisée par consumption', () => {
    // Le constructeur n'en porte plus de copie : il importe celle de l'optimiseur et
    // l'injecte à `createConsumption`.
    const entree = readFileSync(fileURLToPath(new URL('../roof-tool-pro11.ts', import.meta.url)), 'utf8');
    expect(entree).not.toMatch(/const clampNeeded\s*=/);
    expect(entree).toMatch(/clampNeeded, \/\/ ACAL79/);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL80 — point de rendement injectable : null dans l'ERP ⇒ aucune requête.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL80 — lireRendement', () => {
  it('rendementPvgis null → aucun fetch, pitchedSpecificYield rend null', async () => {
    let appels = 0;
    const fetcher = (async () => {
      appels += 1;
      return { ok: true, json: async () => ({ ok: true, annualKwh: 1700 }) };
    }) as unknown as typeof fetch;
    expect(await lireRendement(null, { legs: [] }, fetcher)).toBeNull();
    expect(appels).toBe(0);
    // Avec l'URL par défaut (pages publiques), la requête part et le kWh revient.
    expect(await lireRendement(RENDEMENT_PVGIS_DEFAUT, { legs: [] }, fetcher)).toBe(1700);
    expect(appels).toBe(1);
  });
});

describe('ACAL470 : objectif de production tapé', () => {
  it('plus petit N sans marge ; plafond dit quand l’objectif dépasse le posable', () => {
    // 600 kWh/panneau/an : 12 000 ⇒ exactement 20 ; 12 001 ⇒ 21 (jamais arrondi à l’inférieur)
    expect(panneauxPourCible(12000, 600, 40, clampNeeded)).toEqual({ panneaux: 20, plafonne: false, maxKwhAn: 12000 });
    expect(panneauxPourCible(12001, 600, 40, clampNeeded)?.panneaux).toBe(21);
    // objectif irréaliste : N = ce qui tient, énergie maximale dite
    expect(panneauxPourCible(50000, 600, 30, clampNeeded)).toEqual({ panneaux: 30, plafonne: true, maxKwhAn: 18000 });
    expect(panneauxPourCible(0, 600, 30, clampNeeded)).toBeNull();
    expect(panneauxPourCible(100, 0, 30, clampNeeded)).toBeNull();
  });
});

// ACAL1618 + ACAL1903 (T3-POSE-002) — le maximum annoncé pour une « Production visée » est celui que « + » ATTEINT :
// le gagnant du solveur vivant aux mêmes verrous, besoin non plafonné (portrait ou paysage, inclinaison, marge…),
// jamais les deux sens de la seule pose affichée ; la production annoncée est celle de CE maximum.
describe('ACAL1903 — « Production visée » : le maximum est celui que « + » atteint', () => {
  /** Plat 12 × 8 m, cible 5 (la pose affichée) ; `plus()` pousse « + » jusqu'au bout et rend le compte dessiné. */
  const atelier = (verrou: 'portrait' | null, reglagesAtelier?: unknown, sansChiffrage = false) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><dd id="rp9-reco-prod"></dd><p id="rp9-need-note"></p></body>').window.document;
    const vertices = rectRing(12, 8);
    const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
    const pan = { id: 'area-1', vertices, obstacles: [], roofType: 'flat' };
    const ctx = { opts: sansChiffrage ? { reglagesAtelier } : { chiffrage: null, reglagesAtelier }, centroidLat: cLat, centroid: [cLng, cLat], neededPanels: 5, neededAuto: false, batiments: [], environment: [],
      shadeObstructions: [], obstacles: [], areas: [pan], activeAreaId: 'area-1', activeArea: () => pan, vertices, roofType: 'flat', closed: true,
      pinned: new Set(verrou ? ['orient'] : []), sel: { family: 'south', tilt: 'reco', orient: verrou ?? 'auto', azimuth: 'south', margin: 'keep' },
      v4YieldCache: new Map(), overhangM: 0, documentRelu: null, shadeAnnualFactor: 1, horizonAnnualFactor: 1, dom: {}, useRecommended: true } as unknown as Ctx;
    let dessinee = -1;
    const deps = { renderScene: (_p: unknown, _g: unknown, _t: unknown, _f: unknown, n: number) => { dessinee = n; }, paintComparison: vi.fn(), highlightRow: vi.fn(),
      syncProductionWindow: vi.fn(), prefillLead: vi.fn(), syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 800,
      obstructionRings: vi.fn(() => []), obstructionClearances: () => [], setStatus: vi.fn() };
    const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
    opt.liveResolveFlat(); // la pose affichée : 5 panneaux
    const plus = () => { ctx.neededPanels = clampNeeded(Number.MAX_SAFE_INTEGER); opt.liveResolveFlat(); return dessinee; };
    return { opt, plus, fin: () => { g.document = avant; } };
  };
  it('12 × 8 m, cible 5 : « au plus N » = le compte que « + » pose, avec la production de CETTE pose', () => {
    const a = atelier(null);
    try {
      const r = cibleDepuisCarte(1e6, a.opt.etatCarte(), clampNeeded)!;
      expect(r.plafonne).toBe(true);
      const atteint = a.plus();
      expect(r.panneaux).toBe(atteint);
      expect(r.maxKwhAn).toBe(Math.round(a.opt.etatCarte()!.kwhParPanneau * atteint)); // la carte une fois « + » arrivé
      expect(phraseCible(r).startsWith(`Le toit donne au plus ${r.maxKwhAn.toLocaleString('fr-FR')} kWh/an avec ${atteint} panneaux`)).toBe(true);
    } finally { a.fin(); }
  });
  // Rejeu en direct (T3-VAGUEC) : la société a un seuil d'accès solaire (60 %) ; sans ombre il n'écarte rien, mais sa seule
  // présence renvoyait aux deux sens de la pose AFFICHÉE (30°) : « au plus 16 » alors que « + » en pose 27 (à 0°).
  it('seuil d’accès solaire de la société, sans ombre : « au plus N » = le compte que « + » pose', () => {
    const a = atelier(null, { simulation: { seuil_acces_retrait: { valeur: 0.6 } } });
    try {
      const r = cibleDepuisCarte(1e6, a.opt.etatCarte(), clampNeeded)!;
      const atteint = a.plus();
      expect(atteint).toBeGreaterThan(5);
      expect(r.panneaux).toBe(atteint);
      expect(r.maxKwhAn).toBe(Math.round(a.opt.etatCarte()!.kwhParPanneau * atteint));
    } finally { a.fin(); }
  });
  // ACAL2031 — figé SANS `opts.chiffrage` (site public ; l'aperçu `/preview/toiture-3d-pro-11` est retiré du build, ACAL332) :
  // le maximum de « Production visée » n'est pas réservé à l'ERP — même règle, même compte que « + » atteint.
  it('sans chiffrage : « au plus N » = le compte que « + » pose, avec la production de CETTE pose', () => {
    const a = atelier(null, undefined, true);
    try {
      const r = cibleDepuisCarte(1e6, a.opt.etatCarte(), clampNeeded)!;
      expect(r.plafonne).toBe(true);
      const atteint = a.plus();
      expect(atteint).toBeGreaterThan(5);
      expect(r.panneaux).toBe(atteint);
      expect(r.maxKwhAn).toBe(Math.round(a.opt.etatCarte()!.kwhParPanneau * atteint));
    } finally { a.fin(); }
  });
  it('maxDuSolveur : la capacité laissée par le seuil borne le nombre, la production suit ; rien ne tient ⇒ null', () => {
    const w = { placedCount: 20, layout: 'portrait', annualKwh: 20000 };
    expect(maxDuSolveur(w, (g) => g.annualKwh)).toEqual({ n: 20, sens: 'portrait', kwhAn: 20000 });
    expect(maxDuSolveur(w, (g) => g.annualKwh, 15)).toEqual({ n: 15, sens: 'portrait', kwhAn: 15000 });
    expect(maxDuSolveur({ ...w, layout: 'mixed' }, (g) => g.annualKwh, 30)).toEqual({ n: 20, kwhAn: 20000 });
    expect(maxDuSolveur(w, (g) => g.annualKwh, 0)).toBeNull();
  });
  it('un objectif atteignable donne toujours le plus petit N, sans sens imposé', () => {
    const a = atelier(null);
    try {
      const e = a.opt.etatCarte()!;
      const r = cibleDepuisCarte(Math.round(4.5 * e.kwhParPanneau), e, clampNeeded)!;
      expect(r).toMatchObject({ panneaux: 5, plafonne: false });
      expect(phraseCible(r)).not.toMatch(/portrait|paysage/);
    } finally { a.fin(); }
  });
  it('portrait verrouillé : le maximum est celui que « + » atteint en portrait, jamais plus que sans verrou', () => {
    const libre = atelier(null);
    let maxLibre = 0;
    try { maxLibre = cibleDepuisCarte(1e6, libre.opt.etatCarte(), clampNeeded)!.panneaux; } finally { libre.fin(); }
    const a = atelier('portrait');
    try {
      const r = cibleDepuisCarte(1e6, a.opt.etatCarte(), clampNeeded)!;
      expect(r.panneaux).toBe(a.plus());
      expect(r.panneaux).toBeLessThanOrEqual(maxLibre);
      expect(phraseCible(r)).not.toContain('paysage');
    } finally { a.fin(); }
  });
});

// Demande croisée (ACAL1523) — le gagnant vivant est re-pavé avec le châssis N × M et les cotes du module DU PAN, comme le
// solveur l'a évalué : la pose dessinée = le compte du solveur, multiple de 20, et la note « n châssis de 2 × 10 posés ».
describe('ACAL1523 — renderLiveWinner : châssis et module du pan au re-pavage', () => {
  const m400 = { id: 'produit-7', produitId: 7, libelle: 'Module 400 W', longueurMm: 1700, largeurMm: 1000, epaisseurMm: 33, poidsKg: 20, pmaxWc: 400, source: 'fiche' };
  const catalogue = { calepinage: 1, modules: [{ module: m400, selectionnable: true, champs_manquants: [], motif: null }], champs_requis: [], motif_liste_vide: null };
  const CHASSIS = { rangs: 2, modulesParRang: 10, jeuEntreRangsM: 0.03, source: 'notice du châssis' };
  /** Résout le pan 28 × 12 m (sud verrouillé) ; rend le compte du solveur, le compte DESSINÉ et la note du châssis. */
  const poser = (chassis: typeof CHASSIS | undefined) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><p id="rp9-chassis-note"></p></body>').window.document;
    try {
      const vertices = rectRing(28, 12);
      const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
      const pan = { id: 'z1', label: 'Pan A', vertices, obstacles: [], roofType: 'flat', moduleId: 'produit-7', ...(chassis ? { chassis } : {}) };
      const ctx = {
        closed: true, vertices, roofType: 'flat', areas: [pan], activeAreaId: 'z1', activeArea: () => pan, opts: { chiffrage: null, modulesDisponibles: catalogue }, dom: {},
        centroid: [cLng, cLat], centroidLat: cLat, pinned: new Set<string>(['family']), sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' },
        v4YieldCache: new Map(), overhangM: 0, documentRelu: null, batiments: [], environment: [], shadeObstructions: [], obstacles: [],
        neededAuto: false, neededPanels: 0, layoutPlan: null, useRecommended: true,
      } as unknown as Ctx;
      let dessinee = -1;
      const deps = { renderScene: (_p: unknown, grid: { count: number }) => { dessinee = grid.count; }, paintComparison: vi.fn(), highlightRow: vi.fn(),
        syncProductionWindow: vi.fn(), prefillLead: vi.fn(), syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 0, obstructionRings: () => [], setStatus: vi.fn() };
      createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]).liveResolveFlat();
      const solveur = (ctx.liveResult as unknown as { winner: { fitCount: number } }).winner.fitCount;
      return { solveur, dessinee, note: document.getElementById('rp9-chassis-note')?.textContent ?? '' };
    } finally { g.document = avant; }
  };
  it('28 × 12 m, châssis 2 × 10 à 0,03 m, module 400 W : pose = compte du solveur, multiple de 20, note dite', () => {
    const r = poser(CHASSIS);
    expect(r.solveur % 20).toBe(0);
    expect(r.dessinee).toBe(r.solveur);
    expect(r.note).toBe(`${r.dessinee / 20} châssis de 2 × 10 posés`);
  });
  it('sans châssis, module 400 W (1,70 × 1,00 m) : la pose dessinée est pavée aux cotes du module du pan, comme le solveur', () => {
    const r = poser(undefined);
    expect(r.dessinee).toBe(r.solveur);
  });
});

// T4-V2-021 — toit plat 10 × 8, « Est-Ouest dos à dos » choisie : la carte de la variante disait « 9 panneaux · 6,48 kWc »
// (balayage au module de référence 720 Wc) quand la pose et le total disaient « 10 × 710 W · 7,1 kWc ». La carte de la
// variante POSÉE lit les chiffres de la pose (mêmes panneaux, même module) ; les autres disent qu'elles sont des estimations.
describe('T4-V2-021 — la carte de la variante posée lit la pose, jamais le module de référence', () => {
  const m400 = { id: 'produit-7', produitId: 7, libelle: 'Module 400 W', longueurMm: 1700, largeurMm: 1000, epaisseurMm: 33, poidsKg: 20, pmaxWc: 400, source: 'fiche' };
  const catalogue = { calepinage: 1, modules: [{ module: m400, selectionnable: true, champs_manquants: [], motif: null }], champs_requis: [], motif_liste_vide: null };
  it('Est-Ouest posée : ses chiffres = ceux de la carte de la pose ; une autre carte est dite estimation', () => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div id="rp9-results"></div><span id="rp9-reco-title"></span><dd id="rp9-reco-panels"></dd><dd id="rp9-reco-kwc"></dd><dd id="rp9-reco-prod"></dd></body>').window.document;
    try {
      const vertices = rectRing(10, 8);
      const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
      const pan = { id: 'z1', label: 'Pan A', vertices, obstacles: [], roofType: 'flat', moduleId: 'produit-7' };
      const ctx = {
        closed: true, vertices, roofType: 'flat', areas: [pan], activeAreaId: 'z1', activeArea: () => pan, opts: { modulesDisponibles: catalogue }, dom: {},
        centroid: [cLng, cLat], centroidLat: cLat, pinned: new Set<string>(), sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' },
        v4YieldCache: new Map(), overhangM: 0, documentRelu: null, batiments: [], environment: [], shadeObstructions: [], obstacles: [],
        neededAuto: true, neededPanels: 0, layoutPlan: null, useRecommended: true,
      } as unknown as Ctx;
      const deps = { renderScene: vi.fn(), paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
        syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 800, obstructionRings: () => [], obstructionClearances: () => [], setStatus: vi.fn() };
      createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]).buildMatrix(vertices, 800);
      const carte = (id: string) => document.querySelector<HTMLButtonElement>(`button.rp9-variant[data-variant="${id}"]`);
      carte('eastwest')!.click();
      const posee = carte('eastwest')!;
      expect(posee.getAttribute('aria-pressed')).toBe('true');
      const texte = (id: string) => document.getElementById(id)!.textContent ?? '';
      const n = texte('rp9-reco-panels').match(/^(\d+) × 400 W$/)![1];
      expect(posee.querySelector('.rp9-variant-figures')!.textContent)
        .toBe(`${n} panneaux · ${texte('rp9-reco-kwc')} · ${texte('rp9-reco-prod')}`);
      const autres = Array.from(document.querySelectorAll<HTMLElement>('button.rp9-variant[aria-pressed="false"] .rp9-variant-figures'));
      expect(autres.length).toBeGreaterThan(0);
      for (const a of autres) expect(a.textContent).toMatch(/^Estimation \(module de référence 720 Wc\) : /);
    } finally { g.document = avant; }
  });
});

describe('ACAL574 — re-résolution refusée sur un pan existant', () => {
  it('liveResolveFlat / liveResolvePitched : rien n’est re-pavé ni redessiné, le motif nomme le pan', () => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body></body>').window.document;
    try {
      const pan = { id: 'z1', label: 'Pan A', existant: true, geometrieEnregistree: { count: 4 } };
      // ACAL1404 — pose déjà affichée (`layoutPlan`) : c'est un geste, refusé ; au chargement (plan null) le pan se pave.
      const ctx = { closed: true, vertices: rectRing(10, 8), roofType: 'flat', areas: [pan], activeAreaId: 'z1', opts: {}, layoutPlan: {} } as unknown as Ctx;
      const deps = {
        renderScene: vi.fn(), paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
        syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 800, obstructionRings: vi.fn(() => []), setStatus: vi.fn(),
      };
      const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
      const geometrieAvant = JSON.stringify(pan);
      opt.liveResolveFlat();
      (ctx as unknown as { roofType: string }).roofType = 'pitched';
      opt.liveResolvePitched();
      expect(deps.renderScene).not.toHaveBeenCalled();
      expect(deps.obstructionRings).not.toHaveBeenCalled();
      expect(deps.setStatus).toHaveBeenCalledWith(motifPanExistant(pan));
      expect(JSON.stringify(pan)).toBe(geometrieAvant);
    } finally {
      g.document = avant;
    }
  });
});

// ACAL1900 (T3-POSE-004, D-ACAL-75) — une pose enregistrée PLUS GRANDE que la cible se rouvre à l'identique : le
// recalcul de FOND qui suit l'ouverture (balayage PVGIS → `liveResolveFlat(false)`) ne la re-pose plus à la cible.
describe('ACAL1900 — une pose relue n’est pas re-posée par le recalcul de fond', () => {
  /** Boot d'un plat 12 × 8 m, cible 5 : `close()` puis la pose RELUE du document (toutes les cellules, « Remplir »). */
  const ouvrir = async (opts: Record<string, unknown>, pose: 'remplie' | 'optimum' = 'remplie') => {
    const vertices = rectRing(12, 8);
    const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
    const pan = { id: 'z1', label: 'Zone 1', vertices, obstacles: [], roofType: 'flat' };
    const ctx = {
      closed: true, vertices, roofType: 'flat', areas: [pan], activeAreaId: 'z1', activeArea: () => pan, opts, dom: {},
      centroid: [cLng, cLat], centroidLat: cLat, pinned: new Set<string>(), sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' },
      v4YieldCache: new Map(), overhangM: 0, documentRelu: null, batiments: [], environment: [], shadeObstructions: [], obstacles: [],
      neededAuto: false, neededPanels: 5, devisMode: true, cibleVendue: false, layoutPlan: null, layoutState: null, layoutOptimalCount: 0, useRecommended: true,
      freeMode: false, freeState: null,
    } as unknown as Ctx;
    // Même effet que scene3d::renderScene : un rendu de l'optimiseur (sans occupation) remet la disposition à null.
    const renderScene = vi.fn((pack: unknown, grid: { panels: unknown[] }, tiltDeg: number, family: string, maxCount: number, flush: boolean, occ?: Set<number>) => {
      if (occ) return;
      Object.assign(ctx, { layoutPlan: { pack, grid, tiltDeg, family, flush }, layoutOptimalCount: Math.min(grid.panels.length, Math.round(maxCount)), layoutState: null });
    });
    const deps = { renderScene, paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
      syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 0, obstructionRings: () => [], obstructionClearances: () => [], setStatus: vi.fn() };
    const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
    opt.liveResolveFlat(); // close() au boot : l'optimum à la cible (5)
    const cellules = ctx.layoutPlan!.grid.panels;
    ctx.layoutState = createLayoutState(cellules, pose === 'remplie' ? cellules.length : ctx.layoutOptimalCount); // hydrateLayout
    const relue = [...ctx.layoutState.occupied];
    await opt.computeMatrixPvgis(); // le recalcul de fond qui suit l'ouverture
    return { ctx, opt, cellules, relue, pan };
  };
  const enregistrer = (ctx: Ctx) => serializeLayout(ctx, null).zones[0].geometry!;
  const doc = () => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><p id="rp9-need-note"></p><tbody id="rp9-compare"></tbody></body>').window.document;
    return () => { g.document = avant; };
  };

  it('ERP, cible 5, pose de 16 : la pose relue survit au balayage et « Enregistrer » sans geste rend les MÊMES panneaux', async () => {
    const remettre = doc();
    try {
      const { ctx, cellules, relue } = await ouvrir({ chiffrage: null, rendementPvgis: null });
      expect(cellules.length).toBeGreaterThan(5);
      expect(ctx.layoutState).not.toBeNull();
      expect([...ctx.layoutState!.occupied].sort((a, b) => a - b)).toEqual(relue.sort((a, b) => a - b));
      const un = enregistrer(ctx);
      expect(un.count).toBe(cellules.length);
      expect(un.panels.map((p) => [p.cx, p.cy])).toEqual(cellules.map((p) => [p.cx, p.cy])); // mêmes emplacements
      expect(enregistrer(ctx)).toEqual(un); // deux enregistrements sans geste : même nombre, mêmes emplacements
    } finally { remettre(); }
  });

  it('jumeaux : une pose égale à l’optimum reste intacte ; un GESTE sur la cible re-pose toujours', async () => {
    const remettre = doc();
    try {
      const egale = await ouvrir({ chiffrage: null, rendementPvgis: null }, 'optimum');
      expect(enregistrer(egale.ctx).count).toBe(5);
      const { ctx, opt } = await ouvrir({ chiffrage: null, rendementPvgis: null });
      ctx.neededPanels = 6;
      opt.liveResolveFlat(); // « + » sur la cible : un geste
      expect(ctx.layoutState).toBeNull();
      expect(enregistrer(ctx).count).toBe(6);
    } finally { remettre(); }
  });

  // Rejeu en direct (T3-VAGUEC, pile de revue) : après le balayage, l'OMBRAGE relu au boot (`relireEnvironment` →
  // `recomputeShading` → `recalcDisplays` = renderActive) re-posait encore la cible : 16 enregistrés → 5 à l'écran → 5 écrits.
  it('chemin réel de l’ouverture : l’ombrage relu, puis le soleil, REDESSINENT la pose tenue sans la re-poser', async () => {
    const remettre = doc();
    try {
      const { ctx, opt, cellules } = await ouvrir({ chiffrage: null, rendementPvgis: null });
      const rendus: number[] = [];
      let resolus = 0;
      const map = new Proxy({}, { get: () => () => undefined }) as never;
      // Le câblage de roof-tool-pro11 : recalcDisplays = renderActive (plat : renderSelection), renderPoseTenue = renderCustomLayout.
      const ui = createShadingUi(ctx, { map, setStatus: () => {}, applyHeatmap: () => {}, recalcDisplays: () => { resolus += 1; opt.renderSelection(); }, renderPoseTenue: () => rendus.push(ctx.layoutState!.occupied.size) });
      ui.recomputeShading();
      expect(enregistrer(ctx).count).toBe(cellules.length);
      ui.redessiner(); // heure, saison, date du soleil, bande climatique
      expect(enregistrer(ctx).count).toBe(cellules.length);
      expect(rendus).toEqual([cellules.length, cellules.length]);
      expect(resolus).toBe(2); // les chiffres du plan sont recalculés (dérate, horizon, climat), la pose reste
    } finally { remettre(); }
  });

  it('remettreSurLePlan : mêmes cellules ⇒ la pose telle quelle ; plan changé ⇒ re-snap au plus près ; aucun plan ⇒ null', () => {
    const cellules = [0, 1, 2, 3].map((i) => ({ cx: i, cy: 0 }));
    const tenue = createLayoutState(cellules, 0);
    tenue.occupied.add(1).add(3);
    expect(remettreSurLePlan(tenue, cellules)).toBe(tenue);
    const decale = remettreSurLePlan(tenue, cellules.map((c) => ({ cx: c.cx + 0.2, cy: 0 })))!;
    expect([...decale.occupied].sort()).toEqual([1, 3]);
    expect(remettreSurLePlan(tenue, [])).toBeNull();
  });

  it('la carte (indicateurs, bande, Guidé) suit la pose tenue, et la note du nombre garde l’écart après « Enregistrer »', async () => {
    const remettre = doc();
    try {
      const { ctx, opt, cellules } = await ouvrir({ chiffrage: null, rendementPvgis: null });
      const carte = document.createElement('p');
      carte.id = 'rp9-reco-panels';
      document.body.appendChild(carte);
      const n = cellules.length;
      opt.peindreCartePosee(n); // renderCustomLayout → updateProductionWindow → la carte
      expect(carte.textContent).toMatch(new RegExp(`^${n} `));
      expect(opt.etatCarte()?.kwhParPanneau).toBeGreaterThan(0); // même rendement par panneau (ACAL1903 le lit)
      const note = () => document.getElementById('rp9-need-note')!.textContent;
      expect(note()).toBe(noteEcartPoseRelue(n, 5, fmt, false));
      opt.majChiffrage(null); // après « Enregistrer » : le contexte relu repeint carte et note
      expect(carte.textContent).toMatch(new RegExp(`^${n} `));
      expect(note()).toBe(`${n} posés / 5 cible — pose tenue telle quelle (${n - 5} de plus que la cible, rien n’est retiré ni ajouté).`);
      const publique = await ouvrir({ rendementPvgis: null }); // site public : la carte reste celle du gagnant
      publique.opt.peindreCartePosee(n);
      expect(carte.textContent).toMatch(/^5 /);
    } finally { remettre(); }
  });

  // ACAL1951 (T3-VAGUEC2, point 7) — la note nomme le devis et l'option dont vient la cible, et les garde après « Remplir ».
  it('devis lié : la note de la pose tenue garde « N au devis », sa référence et son option (avec batterie)', async () => {
    const remettre = doc();
    try {
      const hydrate = { devis: { referenceDevis: 'DEV-202611-0022', optionCible: 'avec' } };
      const { ctx, opt, cellules } = await ouvrir({ chiffrage: null, rendementPvgis: null, devisLie: true, hydrate });
      Object.assign(ctx, { cibleVendue: true, panneauxDevis: 5 });
      const n = cellules.length;
      opt.peindreCartePosee(n);
      expect(document.getElementById('rp9-need-note')!.textContent).toBe(
        `${n} posés / 5 cible · 5 au devis DEV-202611-0022 (option avec batterie) — pose tenue telle quelle (${n - 5} de plus que la cible, rien n’est retiré ni ajouté).`);
      opt.majChiffrage(null); // le contexte relu après « Enregistrer » : la même phrase
      expect(document.getElementById('rp9-need-note')!.textContent).toContain('· 5 au devis DEV-202611-0022 (option avec batterie) — pose tenue telle quelle');
    } finally { remettre(); }
  });

  it('carteDeLaPoseTenue : même rendement par panneau, économies plafonnées ; rien quand le nombre ne change pas', () => {
    const d = { title: 'Plein sud 30°', isReco: true, count: 5, kwc: 3.55, annualKwh: 5571, pct: 63, savingsLow: 1, savingsHigh: 1, why: '', target: 8843 };
    const c = carteDeLaPoseTenue(d, 16, fmt)!;
    expect(c).toMatchObject({ count: 16, tenue: true, isReco: false });
    expect(c.annualKwh).toBeCloseTo(5571 * 16 / 5, 6);
    expect(c.kwc).toBeCloseTo(11.36, 6);
    expect(c.savingsHigh).toBe(annualSavingsMad(c.annualKwh, 8843).high);
    expect(carteDeLaPoseTenue(d, 5, fmt)).toBeNull();
    expect(carteDeLaPoseTenue({ ...d, count: 0 }, 16, fmt)).toBeNull();
  });

  it('site public (aucun `chiffrage`) : comportement d’avant, le recalcul de fond re-pose l’optimum', async () => {
    const remettre = doc();
    try {
      const { ctx } = await ouvrir({ rendementPvgis: null });
      expect(ctx.layoutState).toBeNull();
    } finally { remettre(); }
  });

  it('l’écart à la cible est DIT, jamais appliqué', () => {
    expect(noteEcartPoseRelue(16, 5, fmt)).toBe('16 posés / 5 cible — pose enregistrée rouverte telle quelle (11 de plus que la cible, rien n’est retiré ni ajouté).');
    expect(noteEcartPoseRelue(3, 5, fmt)).toContain('(2 de moins que la cible');
    expect(noteEcartPoseRelue(5, 5, fmt)).toBeNull();
    expect(noteEcartPoseRelue(16, 0, fmt)).toBeNull();
    const remettre = doc(); // écrit dans la note du nombre (hydrateLayout l'appelle), rien sans écart
    try {
      direEcartPoseRelue(5, 5, fmt);
      expect(document.getElementById('rp9-need-note')!.textContent).toBe('');
      direEcartPoseRelue(16, 5, fmt);
      expect(document.getElementById('rp9-need-note')!.textContent).toBe(noteEcartPoseRelue(16, 5, fmt));
    } finally { remettre(); }
  });
});

// ACAL2032 — une pose en PLACEMENT LIBRE face au recalcul d'un toit, d'un module ou d'un obstacle changé (chemin réel :
// roof-tool-pro11::recalc → occupiedCenters → re-pavage → reenterCustomLayout). Pan plat de 12 × 8 m (ENU, azimut 0 :
// u = −x, v = y), 6 panneaux libres de 2 × 1 m sur deux rangées.
describe('ACAL2032 — placement libre : la pose tenue suit un changement de toit, de module, d’obstacle', () => {
  const ORIGINE: [number, number] = [-7.6, 33.5];
  const rangees = [-2, 1].flatMap((v) => [-3.5, 0, 3.5].map((u) => ({ cx: 0 - u, cy: v })));
  /** Les cellules du pavage d'un pan rectangulaire (demi-côtés hu × hv), retrait 0,50 m, jeu 2 cm. */
  const cellules = (hu: number, hv: number, w: number, d: number) => {
    const out: { cx: number; cy: number }[] = [];
    for (let v = -hv + 0.5 + d / 2; v + d / 2 <= hv - 0.5 + 1e-9; v += d + 0.02) {
      for (let u = -hu + 0.5 + w / 2; u + w / 2 <= hu - 0.5 + 1e-9; u += w + 0.02) out.push({ cx: -u, cy: v });
    }
    return out;
  };
  const plan = (hu: number, hv: number, w = 2, d = 1, origin: [number, number] = ORIGINE, dx = 0, azimuthDeg = 0) => ({
    pack: { origin, azimuthDeg, ringENU: [[-hu + dx, -hv], [hu + dx, -hv], [hu + dx, hv], [-hu + dx, hv]] },
    grid: { rowWidthM: w, footprintPerPanelM2: w * d, slopeLenM: d, panels: cellules(hu, hv, w, d).map((c) => ({ ...c, cx: c.cx + dx })) },
    tiltDeg: 0, family: 'S', flush: false,
  }) as unknown as LayoutPlan;
  const ouvrir = async (obstacles: Obstacle[] = []) => {
    const g = globalThis as unknown as { document?: Document; window?: Window };
    const avant = { document: g.document, window: g.window };
    const dom = new JSDOM('<!doctype html><body><p id="rp9-layout-note"></p></body>');
    Object.assign(g, { document: dom.window.document, window: dom.window });
    const { createLayoutEditor } = await import('./layoutEditor');
    const { carteEditeurFactice, depsEditeur } = await import('./harnaisAtelier');
    const conteneur = dom.window.document.createElement('div');
    dom.window.document.body.appendChild(conteneur);
    const ctx = {
      layoutMode: true, closed: true, vertices: [], obstacles, areas: [], roofType: 'flat', pitchDeg: 0, facingAzimuthDeg: 0,
      facingManual: false, neededPanels: 0, layoutPlan: plan(6, 4), layoutState: null, layoutSel: null, layoutOptimalCount: 0,
      freeMode: true, freeState: { panels: rangees.map((p) => ({ ...p })) }, opts: { chiffrage: null },
    } as unknown as Ctx;
    const editeur = createLayoutEditor(ctx, depsEditeur(carteEditeurFactice(conteneur)));
    const remettre = () => Object.assign(g, avant);
    /** Le recalcul de l'entrée : centres capturés, plan re-pavé, pose re-entrée. */
    const recalculer = (neuf: LayoutPlan) => {
      const origineAvant = ctx.layoutPlan!.pack.origin;
      const centres = editeur.occupiedCenters();
      ctx.layoutPlan = neuf;
      editeur.reenterCustomLayout(centres, origineAvant);
    };
    const note = () => dom.window.document.getElementById('rp9-layout-note')!.textContent ?? '';
    return { ctx, editeur, recalculer, note, remettre };
  };
  /** Aucun panneau hors du pan, sur un obstacle ou sur un autre : les contraintes DURES du placement libre. */
  const fautes = (ctx: Ctx) => {
    const g = freeGeomFrom(ctx.layoutPlan, ctx.obstacles ?? [])!;
    const ringUV = g.ringENU.map(([x, y]) => toUV(g, x, y));
    const coins = ctx.freeState!.panels.map((p) => panelCornersFor(g, p));
    return coins.flatMap((c, i) => hardViolationsFor(g, ringUV, c, coins.filter((_, j) => j !== i), []));
  };

  it('toit rétréci (12 → 8 m) : les 2 panneaux qui tiennent restent à leur place, les 4 autres sont DITS déplacés, aucun hors du pan', async () => {
    const { ctx, recalculer, note, remettre } = await ouvrir();
    try {
      recalculer(plan(4, 4));
      expect(fautes(ctx)).toEqual([]);
      const poses = ctx.freeState!.panels;
      expect(poses.filter((p) => p.cx === 0)).toEqual([{ cx: 0, cy: -2 }, { cx: 0, cy: 1 }]); // gardés, au centimètre
      expect(poses).toHaveLength(6);
      expect(note()).toBe('Placement libre après la modification — 2 panneaux gardés à leur place, 4 déplacés sur l’emplacement libre le plus proche.');
    } finally { remettre(); }
  });

  it('module plus large (2 → 3,6 m) : les panneaux qui se chevauchent sont déplacés, et la phrase le dit', async () => {
    const { ctx, recalculer, note, remettre } = await ouvrir();
    try {
      recalculer(plan(6, 4, 3.6));
      expect(fautes(ctx)).toEqual([]);
      expect(ctx.freeState!.panels).toHaveLength(6);
      expect(note()).toBe('Placement libre après la modification — 4 panneaux gardés à leur place, 2 déplacés sur l’emplacement libre le plus proche.');
    } finally { remettre(); }
  });

  it('obstacle posé sur un panneau : celui-là seul est déplacé ; plus de place ⇒ RETIRÉ et dit', async () => {
    const lat = ORIGINE[1] + 1 / DEG2M_TEST;
    const cheminee = { id: 'o1', centerLng: ORIGINE[0], centerLat: lat, lengthM: 0.6, widthM: 0.6, type: 'cheminee' } as Obstacle;
    const { ctx, recalculer, note, remettre } = await ouvrir([cheminee]);
    try {
      recalculer(plan(6, 4));
      expect(fautes(ctx)).toEqual([]);
      expect(ctx.freeState!.panels.filter((p) => p.cy === -2 || (p.cy === 1 && p.cx !== 0))).toHaveLength(5);
      expect(note()).toBe('Placement libre après la modification — 5 panneaux gardés à leur place, 1 déplacé sur l’emplacement libre le plus proche.');
    } finally { remettre(); }
    const plein = await ouvrir([cheminee]);
    try {
      plein.recalculer({ ...plan(6, 4), grid: { ...plan(6, 4).grid, panels: [] } } as LayoutPlan); // aucun emplacement libre
      expect(fautes(plein.ctx)).toEqual([]);
      expect(plein.ctx.freeState!.panels).toHaveLength(5);
      expect(plein.note()).toBe('Placement libre après la modification — 5 panneaux gardés à leur place, 1 retiré (plus de place sur le toit).');
    } finally { plein.remettre(); }
  });

  // Rejeu en direct (calepinage 1928, pan en pente) : le pavage pose sa rangée d'égout BORD CONTRE BORD avec le contour ; un
  // recalcul sans aucun changement disait « 3 retirés » (contrôle au contour sans la tolérance du glissé libre).
  it('panneaux posés bord contre bord avec le contour : gardés tels quels par un recalcul sans changement', async () => {
    const { ctx, recalculer, note, remettre } = await ouvrir();
    try {
      const auBord = [{ cx: 5, cy: -3.5 }, { cx: -5, cy: 3.5 }, { cx: 0, cy: -3.5 }]; // u = −6…−4 / v = −4…−3, etc.
      ctx.freeState = { panels: auBord.map((p) => ({ ...p })) };
      recalculer(plan(6, 4));
      expect(ctx.freeState!.panels).toEqual(auBord);
      expect(note()).toBe('Placement libre conservé — 3 panneaux inchangés.');
      recalculer(plan(6, 4, 2, 1, ORIGINE, 0, 180)); // pan plein sud du rejeu : axes à 1e-16 près
      expect(ctx.freeState!.panels).toEqual(auBord);
      expect(note()).toBe('Placement libre conservé — 3 panneaux inchangés.');
    } finally { remettre(); }
  });

  it('rien ne change de place : la pose telle quelle, même quand le repère du pan se déplace (sommet déplacé ailleurs)', async () => {
    const { ctx, recalculer, note, remettre } = await ouvrir();
    try {
      recalculer(plan(6, 4));
      expect(ctx.freeState!.panels).toEqual(rangees);
      expect(note()).toBe('Placement libre conservé — 6 panneaux inchangés.');
      // L'origine du pavage suit le centre du toit : 1 m plus à l'est, les panneaux restent au MÊME endroit du toit.
      const est: [number, number] = [ORIGINE[0] + 1 / (DEG2M_TEST * Math.cos(ORIGINE[1] * Math.PI / 180)), ORIGINE[1]];
      recalculer(plan(6, 4, 2, 1, est, -1));
      expect(ctx.freeState!.panels.map((p) => [Number(p.cx.toFixed(6)), p.cy])).toEqual(rangees.map((p) => [Number((p.cx - 1).toFixed(6)), p.cy]));
      expect(note()).toBe('Placement libre conservé — 6 panneaux inchangés.');
    } finally { remettre(); }
  });
});

// ACAL1902 (T3-POSE-007, ACAL1504, DC-7) — un retrait SAISI retire des panneaux, dans la pose ET dans le balayage :
// la « marge retirée » ne contourne plus des retraits saisis (elle ne retire que la marge par défaut).
describe('ACAL1902 — un retrait saisi retire des panneaux (pose et balayage)', () => {
  const poser = async (l: number, w: number, retraitM: number | null) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><p id="rp9-need-note"></p><tbody id="rp9-compare"></tbody></body>').window.document;
    try {
      const vertices = rectRing(l, w);
      const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
      const pan = { id: 'z1', label: 'Zone 1', vertices, obstacles: [], roofType: 'flat' };
      const ctx = {
        closed: true, vertices, roofType: 'flat', areas: [pan], activeAreaId: 'z1', activeArea: () => pan, opts: { chiffrage: null, rendementPvgis: null }, dom: {},
        centroid: [cLng, cLat], centroidLat: cLat, pinned: new Set<string>(), sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' },
        v4YieldCache: new Map(), overhangM: 0, documentRelu: null, batiments: [], environment: [], shadeObstructions: [], obstacles: [],
        neededAuto: false, neededPanels: 40, devisMode: true, cibleVendue: false, layoutPlan: null, layoutState: null, useRecommended: true,
      } as unknown as Ctx;
      let dessinee = -1;
      const setbacks = retraitM == null ? undefined : { lateralM: retraitM, extremityM: retraitM, parapetM: retraitM, jointM: 0 };
      const deps = { renderScene: (_p: unknown, _g: unknown, _t: unknown, _f: unknown, n: number) => { dessinee = n; }, paintComparison: vi.fn(), highlightRow: vi.fn(),
        syncProductionWindow: vi.fn(), prefillLead: vi.fn(), syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 0,
        obstructionRings: () => [], obstructionClearances: () => [], setStatus: vi.fn(), setbacksOf: () => setbacks };
      const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
      opt.liveResolveFlat();
      await opt.computeMatrixPvgis();
      const balayage = Math.max(...(ctx.matrixResult as unknown as { rows: { placedCount: number }[] }).rows.map((r) => r.placedCount));
      return { pose: dessinee, balayage };
    } finally { g.document = avant; }
  };

  it('plat 3 × 1,5 m, retraits 0,80 m : 0 panneau posé, 0 dans tout le balayage', async () => {
    expect(await poser(3, 1.5, 0.8)).toEqual({ pose: 0, balayage: 0 });
  });

  it('plat 10 × 7 m, retraits 2 m : moins de panneaux qu’aux retraits par défaut, mêmes comptes pose / balayage', async () => {
    const defaut = await poser(10, 7, null);
    const deux = await poser(10, 7, 2);
    expect(deux.pose).toBeLessThan(defaut.pose);
    expect(deux.balayage).toBeLessThan(defaut.balayage);
    expect(deux.pose).toBe(deux.balayage);
  });

  it('retraits au défaut (0,50 m partout) : balayage d’avant, la marge retirée reste candidate', async () => {
    expect(await poser(10, 7, 0.5)).toEqual(await poser(10, 7, null));
  });
});

// ACAL549 — la cause MESURÉE d'un pan vide, dans l'ordre retrait → obstacles → seuil → module → inconnue.
describe('ACAL549 — causeDuPanVide', () => {
  const MODULE = cotesDePavage(undefined);
  const mesures = (o: Partial<MesuresPanVide> = {}): MesuresPanVide => ({
    largeurPanM: 4, retraitM: 0, coteCourtM: MODULE.courtM, coteLongM: MODULE.longM, aireM2: 12,
    surfacePosableM2: 12, candidats: 3, seuil: null, ecartes: 0, ...o,
  });

  it('pan de 3 × 1,5 m, retrait 0,80 m ⇒ retrait_rive avec 0,80 et 1,50', () => {
    const pack = packConfig(rectRing(3, 1.5), 33.5, { family: 'south', tiltDeg: 13, setbackM: 0.8 });
    expect(pack.best.count).toBe(0);
    const m = causeDuPanVide(mesurerPanVide(pack, pack.best, retraitApplique(undefined, 0.8), MODULE, null));
    expect(m.code).toBe('retrait_rive');
    expect(m.message).toBe('Aucun module : le retrait de rive (0,80 m de chaque côté) ne laisse que 0,00 m sur 1,50 m de large');
    expect(m.mesures).toMatchObject({ retraitM: 0.8, largeurPanM: 1.5, largeurUtileM: 0 });
  });

  it('obstacles couvrant tout ⇒ obstacles (et passe AVANT le seuil) ; seuil ⇒ seuil_acces_solaire ; rien ⇒ module_trop_grand / inconnue', () => {
    expect(causeDuPanVide(mesures({ surfacePosableM2: 0, seuil: 0.8, ecartes: 3 })).code).toBe('obstacles');
    const s = causeDuPanVide(mesures({ seuil: 0.8, ecartes: 3 }));
    expect(s.code).toBe('seuil_acces_solaire');
    expect(s.message).toContain('80 %');
    expect(causeDuPanVide(mesures({ candidats: 0, surfacePosableM2: 1 })).code).toBe('module_trop_grand');
    expect(causeDuPanVide(mesures())).toEqual({ code: 'inconnue', message: "Aucun module posé — la cause n'a pas pu être déterminée", mesures: {} });
  });

  it('le retrait passe AVANT les obstacles (ordre des causes)', () => {
    expect(causeDuPanVide(mesures({ largeurPanM: 1.5, retraitM: 0.8, surfacePosableM2: 0 })).code).toBe('retrait_rive');
  });

  it('écrit `motifsPansVides` pour le pan vide, le relit, et le retire dès que le pan porte un module', () => {
    const motif = causeDuPanVide(mesures({ largeurPanM: 1.5, retraitM: 0.8 }));
    semerMotifsDepuisDocument({});
    noterMotifPanVide('z1', motif);
    const doc: Record<string, unknown> = { zones: [{ id: 'z1', geometry: { count: 0 } }, { id: 'z2', geometry: { count: 4 } }] };
    expect(ecrireMotifsDansDocument(doc)).toBe(true);
    expect(doc.motifsPansVides).toEqual({ z1: motif });
    semerMotifsDepuisDocument({});
    expect(ecrireMotifsDansDocument(doc)).toBe(false);
    expect('motifsPansVides' in doc).toBe(false);
    semerMotifsDepuisDocument({ motifsPansVides: { z1: motif } });
    expect(ecrireMotifsDansDocument(doc)).toBe(true);
    (doc.zones as Array<{ geometry: { count: number } }>)[0].geometry.count = 2;
    expect(ecrireMotifsDansDocument(doc)).toBe(false);
    semerMotifsDepuisDocument({});
  });
});

// ACAL1970 — chemin « toit en pente » : un pan à 22° tourné au nord (azimut 0°), un besoin, aucun module posé ⇒ le
// motif `orientation_nord` (contrat ACAL1969) est noté puis écrit au document ; tourné au sud ⇒ aucun motif.
// Mutant : ne rien noter sur le chemin pente ⇒ pas de `motifsPansVides`.
describe('ACAL1970 — motif orientation_nord du toit en pente', () => {
  const resoudre = (azimut: number) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><p id="rp9-need-note"></p></body>').window.document;
    try {
      const ctx = {
        closed: true, vertices: rectRing(10, 8), roofType: 'pitched', pitchDeg: 22, facingAzimuthDeg: azimut, centroidLat: 33.5,
        areas: [], activeAreaId: 'pan-nord', opts: {}, neededAuto: false, neededPanels: 6, pinned: new Set(),
        pitchedYieldCache: new Map(), pitchedLocks: {}, overhangM: 0, documentRelu: null, batiments: [], environment: [], shadeObstructions: [], obstacles: [],
        activeArea: () => null, dom: {}, centroid: [-7, 33],
      } as unknown as Ctx;
      const deps = { renderScene: vi.fn(), paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
        syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 0, factureCarte: () => 0, obstructionRings: vi.fn(() => []), setStatus: vi.fn() };
      createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]).liveResolvePitched();
      const doc: Record<string, unknown> = { zones: [{ id: 'pan-nord', geometry: { count: 0 } }] };
      ecrireMotifsDansDocument(doc);
      const note = g.document.getElementById('rp9-need-note')?.textContent ?? '';
      return { doc, note, nord: (ctx as unknown as { pitchedLiveResult: { northFacing: boolean } }).pitchedLiveResult.northFacing };
    } finally { g.document = avant; semerMotifsDepuisDocument({}); }
  };
  it('pan nord à 22° ⇒ motif écrit avec azimutDeg et penteDeg ; pan sud ⇒ aucun motif', () => {
    const nord = resoudre(0);
    expect(nord.nord).toBe(true);
    expect(nord.doc.motifsPansVides).toEqual({ 'pan-nord': {
      code: 'orientation_nord', message: 'Aucun module : pan en pente (22°) orienté au nord (azimut 0°)', mesures: { azimutDeg: 0, penteDeg: 22 } } });
    expect('motifsPansVides' in resoudre(180).doc).toBe(false);
    expect(motifPenteNord(true, 0, 0, 0, 22)).toBeNull(); // sans besoin, aucune cause à dire
  });
  // Revue : la note du besoin vue par un visiteur public sur un pan nord dit la pose réelle (0), plus « On pose 6
  // panneaux » ; « au nord » seulement pour un pan vraiment nord, les autres faces de la moitié nord disent la leur.
  it('note du besoin (site public) : « 6 nécessaires — 0 tiennent en pente — Aucun module : … On pose 0. »', () => {
    expect(resoudre(0).note).toBe('6 nécessaires — 0 tiennent en pente — Aucun module : pan en pente (22°) orienté au nord (azimut 0°). On pose 0.');
    const nordEst = resoudre(40);
    expect(nordEst.nord).toBe(true);
    expect(nordEst.note).toContain('orienté nord-est (azimut 40°), trop au nord.');
    expect(nordEst.note).not.toContain('au nord (azimut');
  });
  it('arrondis du schéma : 359,996° ⇒ azimut 0 (jamais 360) ; pente bornée à [0, 90]', () => {
    expect(motifPenteNord(true, 0, 6, 359.996, 22)?.mesures).toEqual({ azimutDeg: 0, penteDeg: 22 });
    expect(motifPenteNord(true, 0, 6, 359.996, 22)?.message).toBe('Aucun module : pan en pente (22°) orienté au nord (azimut 0°)');
    expect(motifPenteNord(true, 0, 6, -10, 95)?.mesures).toEqual({ azimutDeg: 350, penteDeg: 90 });
  });
});

// ACAL548 — UNE règle pour le seuil d'accès solaire : le dossier prime, la société sert de départ, sinon aucun filtre.
describe('ACAL548 — seuil effectif (dossier > société > rien)', () => {
  const societe = { simulation: { seuil_acces_retrait: { valeur: 0.6, source: 'societe' } } };
  it('sans valeur au document, le réglage société s’applique', () => {
    expect(seuilEffectifAccesSolaire(undefined, societe)).toEqual({ valeur: 0.6, origine: 'societe' });
  });
  it('avec une valeur au document, elle prime sur la société', () => {
    expect(seuilEffectifAccesSolaire(0.8, societe)).toEqual({ valeur: 0.8, origine: 'dossier' });
  });
  it('sans rien, aucun filtre ; une valeur de société hors [0, 1] n’est pas utilisée', () => {
    expect(seuilEffectifAccesSolaire(undefined, null)).toBeNull();
    expect(seuilEffectifAccesSolaire(undefined, { simulation: { seuil_acces_retrait: { valeur: 1.2 } } })).toBeNull();
  });
  it('le dépôt d’une valeur de dossier garde les autres clés et la société n’est jamais écrite', () => {
    poserChoixOptimisation({ priorite: 'faitage' });
    poserChoixOptimisation({ ...choixOptimisationCourant(), seuilAccesSolaire: 0.8 });
    expect(choixOptimisationCourant()).toEqual({ priorite: 'faitage', seuilAccesSolaire: 0.8 });
    poserChoixOptimisation(null);
    expect(choixOptimisationCourant()).toBeNull();
  });
});

// ACAL777 — la facture lue par les cartes : la saisie PRIME, le lead sert de repli, jamais d'invention.
describe('ACAL777 — factureCarteDe / lireFactureSaisie', () => {
  it('saisie > 0 prime ; sinon la facture du lead ; sinon 0 (rien inventé)', () => {
    expect(factureCarteDe(1200, 900)).toBe(1200);
    expect(factureCarteDe(0, 900)).toBe(900);
    expect(factureCarteDe(0, null)).toBe(0);
    expect(factureCarteDe(0, undefined)).toBe(0);
    expect(factureCarteDe(0, -5)).toBe(0);
  });
  // V1-02 — lead à factures été ≠ hiver (moyenne servie 1 350) : en TOIT EN PENTE le solveur lisait le champ
  // `rp9-bill` (absent en ERP ⇒ 0) et la tuile restait « — / Facture inconnue » ; la facture servie est le repli d'AFFICHAGE.
  it('V1-02 : toit en pente sans champ facture — la tuile a sa valeur depuis la facture servie, plus « Facture inconnue »', () => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    const doc = new JSDOM('<!doctype html><body><dd id="rp9-reco-kwc"></dd><dd id="rp9-reco-prod"></dd><dl><dd id="rp9-reco-savings"></dd></dl>'
      + '<dd id="rp9-reco-cover"></dd><p id="rp9-reco-band"></p><p id="rp9-reco-why"></p></body>').window.document;
    g.document = doc;
    const lancer = (factureServie: number | null, erp = false) => {
      const ctx = {
        closed: true, vertices: rectRing(10, 8), roofType: 'pitched', pitchDeg: 25, facingAzimuthDeg: 200, centroidLat: 33.5,
        areas: [], activeAreaId: null, opts: erp ? { chiffrage: null } : {}, neededAuto: true, neededPanels: 0, pinned: new Set(),
        pitchedYieldCache: new Map(), pitchedLocks: {}, overhangM: 0, documentRelu: null, batiments: [], environment: [], shadeObstructions: [], obstacles: [],
        activeArea: () => null, dom: {}, centroid: [-7, 33],
      } as unknown as Ctx;
      const deps = {
        renderScene: vi.fn(), paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
        syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 0, factureCarte: () => factureServie ?? 0,
        obstructionRings: vi.fn(() => []), setStatus: vi.fn(),
      };
      createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]).liveResolvePitched();
      return (id: string) => doc.getElementById(id)?.textContent ?? '';
    };
    try {
      const avecFacture = lancer(1350);
      expect(avecFacture('rp9-reco-cover')).toMatch(/\d+ %/);
      expect(avecFacture('rp9-reco-why')).not.toContain('Facture inconnue');
      const sansFacture = lancer(null);
      expect(sansFacture('rp9-reco-cover')).toBe('—'); // rien inventé sans facture
      expect(sansFacture('rp9-reco-why')).toContain('Facture inconnue');
      // ACAL2022 — en ERP la part « production ÷ consommation » est celle de la conception SERVIE (rien de servi : « — »), la facture reste lue.
      const erpAvec = lancer(1350, true);
      expect(erpAvec('rp9-reco-cover')).toBe('—');
      expect(erpAvec('rp9-reco-why')).not.toContain('Facture inconnue');
    } finally { g.document = avant; }
  });
  it('lireFactureSaisie : espaces et virgule décimale lus, vide ou illisible = 0', () => {
    expect(lireFactureSaisie({ value: '1 250,5' })).toBe(1250.5);
    expect(lireFactureSaisie({ value: '' })).toBe(0);
    expect(lireFactureSaisie({ value: 'abc' })).toBe(0);
    expect(lireFactureSaisie(null)).toBe(0);
  });
});

describe('ACAL975 — le gain bifacial n’existe pas en pose affleurante', () => {
  const base = { annualKwh: 8000 };
  it('affleurant ⇒ chaîne vide ; sud incliné ⇒ ~+5 % ; est-ouest ⇒ ~+3 % ; sans production ⇒ vide', () => {
    expect(libelleGainBifacial({ ...base, family: 'south', tiltDeg: 22, flush: true })).toBe('');
    expect(libelleGainBifacial({ ...base, family: 'south', tiltDeg: 22 })).toContain('~+5 %');
    expect(libelleGainBifacial({ ...base, family: 'eastwest', tiltDeg: 10 })).toContain('~+3 %');
    expect(libelleGainBifacial({ annualKwh: 0, family: 'south', tiltDeg: 22 })).toBe('');
  });
});

// ACAL994 — l'économie SERVIE remplace l'estimation (carte + Total) avec son libellé ; site public inchangé.
describe('ACAL994 — économie servie, étiquette, majChiffrage', () => {
  // T4-X9-003 — la conception a une TAILLE (`kwc`) : son économie ne se lit qu'à côté d'une pose de cette taille.
  const servi = (valeur: number | null, etat: string) => ({ kwc: { valeur: 5, etat: 'servi' }, economie_annee1_mad: { valeur, etat, option: 'sans_batterie' } });
  const monter = (chiffrage?: unknown) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    const doc = new JSDOM('<!doctype html><body><div><dd id="rp9-reco-savings"></dd></div><dd id="tot"></dd></body>').window.document;
    g.document = doc;
    const ctx = { opts: chiffrage === undefined ? {} : { chiffrage }, dom: { areasTotalSavingsEl: doc.getElementById('tot') } } as unknown as Ctx;
    const deps = { renderScene: vi.fn(), paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
      syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 800, obstructionRings: vi.fn(() => []), setStatus: vi.fn() };
    const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
    return { ctx, opt, doc, fin: () => { g.document = avant; } };
  };
  const ligne = (doc: Document) => doc.querySelector('[data-economie-etat]')?.textContent ?? null;

  it('servi : la valeur du serveur est affichée (carte et Total), « au dernier enregistrement »', () => {
    const { ctx, opt, doc, fin } = monter(servi(7420, 'servi'));
    try {
      expect(economieAffichee(ctx, 'carte', '100 – 200 MAD/an', 5)).toBe(`${fmtMad(7420)}/an`);
      opt.majChiffrage(servi(7420, 'servi') as never);
      expect(economieAffichee(ctx, 'total', '300 – 400 MAD/an', 5)).toBe(`${fmtMad(7420)}/an`);
      expect(ligne(doc)).toBe('au dernier enregistrement · sans batterie');
    } finally { fin(); }
  });

  it('non servi (ACAL2022) : plus d’estimation en ERP — « économie au prochain enregistrement » ; site public : l’estimation', () => {
    for (const chiffrage of [servi(null, 'non_servi'), null]) {
      const { ctx, opt, doc, fin } = monter(chiffrage);
      try {
        expect(economieAffichee(ctx, 'carte', '100 – 200 MAD/an')).toBe('économie au prochain enregistrement');
        expect(economieAffichee(ctx, 'carte', '— facture inconnue')).toBe('— facture inconnue');
        opt.majChiffrage(chiffrage as never);
        expect(ligne(doc)).toBe('économie au prochain enregistrement');
      } finally { fin(); }
    }
  });

  it('après enregistrement : la valeur servie remplace « au prochain enregistrement » ; hors ligne ensuite : les valeurs du dernier calcul, dites (ACAL2022)', () => {
    const { ctx, opt, doc, fin } = monter(null);
    try {
      const carte = doc.getElementById('rp9-reco-savings') as HTMLElement;
      const total = doc.getElementById('tot') as HTMLElement;
      carte.textContent = economieAffichee(ctx, 'carte', '100 – 200 MAD/an', 5);
      total.textContent = economieAffichee(ctx, 'total', '300 – 400 MAD/an', 5);
      opt.majChiffrage(servi(8123, 'servi') as never);
      expect(carte.textContent).toContain('8');
      expect(carte.textContent).not.toContain('100');
      expect(total.textContent).toBe(carte.textContent);
      expect(ligne(doc)).toBe('au dernier enregistrement · sans batterie');
      opt.majChiffrage(null); // la relecture échoue (hors ligne) : les valeurs du dernier calcul restent, et c'est dit
      expect(carte.textContent).toBe(`${fmtMad(8123)}/an`);
      expect(total.textContent).toBe(`${fmtMad(8123)}/an`);
      expect(ligne(doc)).toBe('valeurs du dernier calcul, hors ligne');
      opt.majChiffrage(servi(null, 'non_servi') as never); // le serveur retire la valeur : plus d'estimation du navigateur
      expect(carte.textContent).toBe('économie au prochain enregistrement');
      expect(total.textContent).toBe('économie au prochain enregistrement');
      expect(ligne(doc)).toBe('économie au prochain enregistrement');
    } finally { fin(); }
  });

  // T4-X9-003 — la carte TOTAL alignait « 8 × 710 W · 5,68 kWc » et « 8 886 MAD/an » : l'économie de la conception
  // (4,40 kWc). Tailles différentes : aucun montant au Total, ni au premier rendu ni après « Enregistrer » (majChiffrage).
  it('T4-X9-003 — Total : pose d’une autre taille que la conception ⇒ aucun montant ; même taille ⇒ le montant servi', () => {
    const conception = { kwc: { valeur: 4.4, etat: 'servi' }, economie_annee1_mad: { valeur: 8886, etat: 'servi', option: 'avec_batterie' } };
    const { ctx, opt, doc, fin } = monter(conception);
    try {
      const total = doc.getElementById('tot') as HTMLElement;
      total.textContent = economieAffichee(ctx, 'total', '300 – 400 MAD/an', 5.68);
      expect(total.textContent).toBe('—');
      opt.majChiffrage(conception as never);
      expect(total.textContent).toBe('—');
      expect(total.textContent).not.toMatch(/MAD/);
      expect(economieAffichee(ctx, 'total', '300 – 400 MAD/an', 4.4)).toBe(`${fmtMad(8886)}/an`);
    } finally { fin(); }
  });

  it('site public (aucun chiffrage) : estimation seule, aucune ligne d’étiquette', () => {
    const { ctx, opt, doc, fin } = monter(undefined);
    try {
      expect(economieAffichee(ctx, 'carte', '100 – 200 MAD/an')).toBe('100 – 200 MAD/an');
      expect(opt).toBeDefined();
      expect(ligne(doc)).toBeNull();
    } finally { fin(); }
  });
});

// R2-09 — UN formateur de puissance : virgule française, 2 décimales.
describe('R2-09 — fmtKwc', () => {
  it('2,13 kWc, 8,00 kWc, jamais « 2.13 » ni une seule décimale', () => {
    expect(fmtKwc(2.13)).toBe('2,13');
    expect(fmtKwc(8)).toBe('8,00');
    expect(fmtKwc(2.1)).toBe('2,10');
  });
});

// R2-05/08/13/16/17 + R3-04/25 — le rendu de la carte de résultat : lit le chiffrage SERVI (atelier ERP, `opts.chiffrage` défini),
// jamais une valeur servie pour un autre kWc ; le site public (aucun `chiffrage`) garde ses textes d'avant.
describe('R2-16/17 — carte de résultat : production, bande, estimation, pose au-dessus de la consommation', () => {
  const GRILLE = { count: 10, kwc: 5.5, panels: [], rowWidthM: 2, footprintPerPanelM2: 2, slopeLenM: 1 };
  const servi = (over: Record<string, unknown> = {}) => ({
    kwc: { valeur: 5.5, etat: 'servi' }, production_annuelle_kwh: { valeur: 12345, etat: 'servi' },
    economie_annee1_mad: { valeur: 7420, etat: 'servi', option: 'sans_batterie' }, ...over,
  });
  const monter = (opts: Record<string, unknown>, ctxOver: Record<string, unknown> = {}, cible = 4000) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    const doc = new JSDOM('<!doctype html><body><dd id="rp9-reco-kwc"></dd><dd id="rp9-reco-prod"></dd><dl><dd id="rp9-reco-savings"></dd></dl>'
      + '<div><dd id="rp9-reco-cover"></dd><dt>Couverture<span>?</span></dt></div><p id="rp9-reco-band"></p><p id="rp9-reco-why"></p>'
      + '<input id="rp9-need-input"><p id="rp9-need-note"></p><p data-couverture-max>aucune pose</p></body>').window.document;
    g.document = doc;
    const ctx = { opts, dom: {}, centroidLat: 33.5, rec: { targetAnnualKwh: cible }, neededPanels: 0, activeArea: () => null, batiments: [], centroid: [-7, 33],
      environment: [], shadeObstructions: [], obstacles: [], areas: [], pinned: new Set(), ...ctxOver } as unknown as Ctx;
    const deps = { renderScene: vi.fn(), paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
      syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 800, obstructionRings: vi.fn(() => []), setStatus: vi.fn() };
    const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
    opt.renderConfig({ pack: { origin: [-7, 33], ringENU: [], azimuthDeg: 0, portrait: GRILLE, landscape: GRILLE } as never, grid: GRILLE as never,
      family: 'south', tiltDeg: 20, azimuthDeg: 0, isReco: true, title: 't', why: 'w', rowId: null });
    const t = (id: string) => doc.getElementById(id)?.textContent ?? '';
    return { ctx, opt, doc, t, fin: () => { g.document = avant; } };
  };
  const erp = (chiffrage: unknown, ctxOver: Record<string, unknown> = {}, cible = 4000) => monter({ chiffrage }, ctxOver, cible);
  const MAD = /MAD\/an/g;
  const prodEstimee = (): number => { const b = monter({}); const v = b.t('rp9-reco-prod'); b.fin(); return Number(v.replace(/\D/g, '')); }; // ACAL2022 — l'estimation locale ne se lit plus qu'en mode public

  // ACAL1914 (revue) — des panneaux posés que AUCUNE chaîne ne raccorde ne gonflent plus l'estimation du navigateur : quand la table
  // d'affectation servie existe, l'estimation est celle des modules raccordés du pan (part = raccordés ÷ modules servis du pan) ;
  // sans chaîne formée, l'estimation d'aujourd'hui reste telle quelle.
  it('ACAL1914 — l’estimation ne compte que les panneaux raccordés quand des chaînes existent ; sans chaîne, inchangée', () => {
    const modules = (n: number, raccordes: number) => {
      const colorByModule = new Map<string, unknown>(); const labelByModule = new Map<string, string>();
      for (let i = 1; i <= n; i++) { colorByModule.set(`z1#${i}`, [0, 0, 0]); if (i <= raccordes) labelByModule.set(`z1#${i}`, 'chaîne 1'); }
      return { colorByModule, labelByModule, legend: [] };
    };
    const tous = prodEstimee(); // 10 panneaux posés, aucune table : l'estimation d'aujourd'hui
    const lire = (coloration: unknown) => { const b = monter({}, { activeAreaId: 'z1', affectationColoration: coloration }); const v = Number(b.t('rp9-reco-prod').replace(/\D/g, '')); b.fin(); return v; };
    expect(tous).toBeGreaterThan(0);
    expect(lire(modules(10, 10))).toBe(tous); // tous raccordés : rien ne change
    expect(lire(modules(10, 0))).toBe(tous); // aucune chaîne encore : l'estimation reste (un design sans chaîne)
    const huit = lire(modules(10, 8)); // 2 panneaux non raccordés
    expect(Math.abs(huit - (tous * 8) / 10)).toBeLessThanOrEqual(1); // = la production des 8 raccordés (production par panneau × 8)
    expect(huit).toBeLessThan(tous);
  });

  it('PRODUCTION : la production SERVIE à kWc égal ; l’estimation sinon (jamais une valeur servie pour un autre kWc)', () => {
    const base = erp(null);
    const estimation = base.t('rp9-reco-prod');
    base.fin();
    expect(estimation).toBe('production au prochain enregistrement'); // ACAL2022 — jamais l'estimation locale en ERP
    const egal = erp(servi());
    const autreKwc = erp(servi({ kwc: { valeur: 6, etat: 'servi' } }));
    const nonServi = erp(servi({ production_annuelle_kwh: { valeur: 12345, etat: 'non_servi' } }));
    const sansKwc = erp(servi({ kwc: null }));
    try {
      expect(egal.t('rp9-reco-prod')).toBe(`${fmt(12345)} kWh/an`);
      // T4-X9-007 — la case du chiffre clé dit « — » ; la phrase (deux décimales) se lit UNE fois, en texte courant, sous les cartes.
      expect(autreKwc.t('rp9-reco-prod')).toBe('—');
      expect(autreKwc.t('rp9-reco-tailles')).toBe('Production et économie calculées pour la conception du lead : 6,00 kWc — votre pose en compte 5,50 kWc.');
      expect(autreKwc.doc.querySelectorAll('[data-phrase-tailles]')).toHaveLength(1);
      expect(egal.doc.getElementById('rp9-reco-tailles')).toBeNull();
      expect(nonServi.t('rp9-reco-prod')).toBe('—'); // T4-X2-006 — « non servi » : aucune conception ne viendra à l'enregistrement
      expect(sansKwc.t('rp9-reco-prod')).toBe(estimation);
    } finally { egal.fin(); autreKwc.fin(); nonServi.fin(); sansKwc.fin(); }
  });

  it('BANDE : l’économie SERVIE à l’année 1 ; non servie : aucun montant ; l’année 25 jamais inventée (ACAL1612, ACAL2022)', () => {
    const s = erp(servi());
    const n = erp(servi({ economie_annee1_mad: { valeur: null, etat: 'non_servi' } }));
    try {
      const bande = s.t('rp9-reco-band');
      expect(bande).toContain(`(${fmtMad(7420)}/an).`);
      expect(bande.match(MAD)).toHaveLength(1);
      expect(bande).not.toContain('Année 25'); // ACAL1612 — la fiche ne porte pas sa dégradation : omise avec sa raison
      expect(bande).toContain('la fiche du module ne porte pas sa dégradation');
      expect(n.t('rp9-reco-band')).toContain(`Année 1 ~${fmt(12345)} kWh/an.`); // ACAL2022 — économie non servie : aucun montant estimé
      expect(n.t('rp9-reco-band')).not.toMatch(MAD);
      expect(n.t('rp9-reco-band')).not.toMatch(/%\/an/);
    } finally { s.fin(); n.fin(); }
  });

  it('ACAL2022 — en ERP l’économie est la servie au kWc posé ou « économie au prochain enregistrement » ; la fourchette seulement sur le site public', () => {
    const e = erp(null);
    const s = erp(servi());
    const autreKwc = erp(servi({ kwc: { valeur: 6, etat: 'servi' } })); // pendant le dessin : kWc posé ≠ kWc servi
    const p = monter({});
    try {
      expect(e.t('rp9-reco-savings')).toBe('économie au prochain enregistrement');
      expect(s.t('rp9-reco-savings')).toBe(`${fmtMad(7420)}/an`);
      expect(autreKwc.t('rp9-reco-savings')).toBe('—'); // T4-X9-007 — la phrase est sous les cartes, pas dans la case
      expect(autreKwc.t('rp9-reco-cover')).toBe('—'); // la part production ÷ consommation n'est pas calculée par le navigateur
      expect(s.t('rp9-reco-cover')).toBe('—'); // servi sans part (clé `couverture_pct` absente) : rien d'inventé
      expect(e.t('rp9-reco-kwc')).toBe('5,50 kWc'); // pendant le dessin : panneaux et kWc posés, seuls

      expect(p.t('rp9-reco-savings')).toMatch(/^[^≈]+ – [^≈]+ MAD\/an$/);
      const avecPart = erp(servi({ couverture_pct: { valeur: 43, etat: 'servi' } }));
      expect(avecPart.t('rp9-reco-cover')).toBe('43 %'); // la part SERVIE de la conception (ACAL2023 : la même que la vue client)
      avecPart.fin();
    } finally { e.fin(); s.fin(); autreKwc.fin(); p.fin(); }
  });

  it('T4-X5-005 — après un enregistrement, la production et la part production ÷ consommation changent ENSEMBLE (la part n’est jamais celle d’une estimation d’avant)', () => {
    const e = erp(servi({ production_annuelle_kwh: { valeur: 8619, etat: 'servi' }, couverture_pct: { valeur: 123, etat: 'servi' } }));
    try {
      expect(e.t('rp9-reco-prod')).toBe(`${fmt(8619)} kWh/an`);
      expect(e.t('rp9-reco-cover')).toBe('123 %');
      e.opt.majChiffrage(servi({ production_annuelle_kwh: { valeur: 9105, etat: 'servi' }, couverture_pct: { valeur: 130, etat: 'servi' } }) as never);
      expect(e.t('rp9-reco-prod')).toBe(`${fmt(9105)} kWh/an`);
      expect(e.t('rp9-reco-cover')).toBe('130 %'); // 9 105 ÷ 7 028 : le quotient du bloc servi, pas les 123 % de l'estimation d'avant
      e.opt.majChiffrage(servi({ production_annuelle_kwh: { valeur: 9105, etat: 'servi' }, couverture_pct: { valeur: null, etat: 'omis' } }) as never);
      expect(e.t('rp9-reco-cover')).toBe('—'); // production sans part servie : aucun pourcentage gardé d'avant
    } finally { e.fin(); }
  });

  // T4-X2-006 (rejeu X9) — « Est-Ouest dos à dos — 24 panneaux · 17,04 kWc · 21 735 kWh/an » : la carte de la variante
  // posée gardait l'estimation de l'atelier sans le dire, après la simulation (27 197 kWh). ERP : elle est DITE estimation.
  // Rejeu R5B (26/11) — « Estimation pour comparer les poses : … 21 735 kWh/an » restait à côté du Total « 27 305 kWh/an ·
  // simulation » : deux productions pour la même pose. ERP : la variante posée ne dit plus de production estimée.
  it('T4-X2-006 — variante posée (ERP) : aucune production estimée, renvoi au Total ; servie : son chiffre ; autre pose : « Estimation »', async () => {
    const { chiffresDeLaPose, texteChiffresVariante } = await import('./chiffresVariante');
    const carte = { count: 24, kwc: 17.04, annualKwh: 21735 };
    const estimee = chiffresDeLaPose(carte, null, () => null);
    expect(texteChiffresVariante(carte, estimee, null, fmt, fmtKwc, true)).toBe('24 panneaux · 17,04 kWc · production : voir le Total');
    expect(texteChiffresVariante(carte, estimee, null, fmt, fmtKwc, true)).not.toContain(fmt(21735));
    expect(texteChiffresVariante(carte, null, null, fmt, fmtKwc, true)).toBe(`Estimation : 24 panneaux · 17,04 kWc · ${fmt(21735)} kWh/an`);
    expect(texteChiffresVariante(carte, estimee, null, fmt, fmtKwc)).toBe(`24 panneaux · 17,04 kWc · ${fmt(21735)} kWh/an`); // site public : inchangé
    const servie = chiffresDeLaPose(carte, null, () => 22000);
    expect(texteChiffresVariante(carte, servie, null, fmt, fmtKwc, true)).toBe(`24 panneaux · 17,04 kWc · ${fmt(22000)} kWh/an`);
  });

  // ACAL1268 (D-ACAL-66) — atelier ERP d'un lead de POMPAGE : la pose (panneaux, kWc) reste, aucun kWh de réseau ; résidentiel et
  // site public : le texte d'avant, à l'octet.
  it('ACAL1268 — cartes de variante : pompage sans kWh ; résidentiel (ERP) et site public inchangés', async () => {
    const { chiffresDeLaPose, texteChiffresVariante } = await import('./chiffresVariante');
    const carte = { count: 24, kwc: 17.04, annualKwh: 21735 };
    const estimee = chiffresDeLaPose(carte, null, () => null);
    expect(texteChiffresVariante(carte, estimee, null, fmt, fmtKwc, 'pompage')).toBe('24 panneaux · 17,04 kWc');
    expect(texteChiffresVariante(carte, null, null, fmt, fmtKwc, 'pompage')).toBe('Estimation : 24 panneaux · 17,04 kWc');
    expect(texteChiffresVariante(carte, estimee, null, fmt, fmtKwc, true)).toBe('24 panneaux · 17,04 kWc · production : voir le Total');
    expect(texteChiffresVariante(carte, null, null, fmt, fmtKwc, true)).toBe(`Estimation : 24 panneaux · 17,04 kWc · ${fmt(21735)} kWh/an`);
    expect(texteChiffresVariante(carte, estimee, null, fmt, fmtKwc, false)).toBe(`24 panneaux · 17,04 kWc · ${fmt(21735)} kWh/an`);
  });

  // T4-X5-005 (rejeu X9) — la phrase de la carte disait « 8 panneaux — production ÷ consommation : 123 % », un rapport tiré
  // d'une production montrée nulle part (l'estimation du navigateur). En ERP la phrase ne porte plus aucun pourcentage : la
  // part ne se lit que dans sa case, servie avec la production qu'elle divise (et « — » quand cette production n'est pas montrée).
  it('T4-X5-005 — ERP : la phrase de la carte ne porte aucun « production ÷ consommation : N % » ; le site public garde « ≈ N % de la facture »', () => {
    // La suite de la phrase, telle que la carte la compose (toit plat et toit en pente : `optimizer.ts::couverture`).
    expect(suiteCouverture(6547, 123, true)).toBe('');
    expect(suiteCouverture(6547, 123, false)).toBe(' ≈ 123 % de la facture');
    expect(suiteCouverture(0, 0, true)).toBe('. Facture inconnue — saisissez-la pour voir la couverture');
    // La part, elle, reste dans sa case : servie à même taille, « — » sinon.
    const memeTailleServie = erp(servi({ couverture_pct: { valeur: 43, etat: 'servi' } }));
    const autreTaille = erp(servi({ kwc: { valeur: 4.4, etat: 'servi' } }));
    try {
      expect(memeTailleServie.t('rp9-reco-cover')).toBe('43 %');
      expect(autreTaille.t('rp9-reco-cover')).toBe('—');
    } finally { memeTailleServie.fin(); autreTaille.fin(); }
  });

  it('« Pose très au-dessus de la consommation » : au-dessus de 2 × la consommation (deux nombres), pas en dessous, jamais sur le site public', () => {
    const prod = prodEstimee();
    const dessus = erp(null, {}, prod / 2.1);
    const dessous = erp(null, {}, prod / 1.9);
    const publique = monter({}, {}, prod / 2.1);
    try {
      expect(dessus.t('rp9-reco-why')).toContain(`Pose très au-dessus de la consommation : ${fmt(prod)} kWh/an produits pour ${fmt(Math.round(prod / 2.1))} kWh/an consommés.`);
      expect(dessous.t('rp9-reco-why')).not.toContain('Pose très au-dessus');
      expect(publique.t('rp9-reco-why')).not.toContain('Pose très au-dessus');
    } finally { dessus.fin(); dessous.fin(); publique.fin(); }
    expect(phraseSurplus(200, 100)).toBe(''); // strictement au-dessus de deux fois
    expect(phraseSurplus(201, 100)).toContain('201 kWh/an produits pour 100 kWh/an consommés');
    expect(phraseSurplus(500, 0)).toBe('');
    expect(phraseSurplus(500, null)).toBe('');
  });

  it('libellé « N posés / M cible » ; « · K au devis » seulement avec un devis lié, vendu, au compte positif', () => {
    const lie = { devisMode: true, cibleVendue: true, neededPanels: 12, panneauxDevis: 14 };
    const a = monter({ chiffrage: null, devisLie: true }, lie);
    const sansDevis = monter({ chiffrage: null }, lie);
    const nonVendu = monter({ chiffrage: null, devisLie: true }, { ...lie, cibleVendue: false });
    const sansCompte = monter({ chiffrage: null, devisLie: true }, { ...lie, panneauxDevis: null });
    const publique = monter({}, { devisMode: true, cibleVendue: true, neededPanels: 12 });
    try {
      expect(a.t('rp9-need-note')).toContain('10 posés / 12 cible · 14 au devis — seuls 10 tiennent');
      for (const x of [sansDevis, nonVendu, sansCompte]) {
        expect(x.t('rp9-need-note')).toContain('10 posés / 12 cible — seuls');
        expect(x.t('rp9-need-note')).not.toContain('au devis');
      }
      expect(publique.t('rp9-need-note')).toContain('10 posés / 12 au devis — seuls 10 tiennent'); // site public : texte d’avant
      // R2-13 — le compte relu avec le contexte repeint la note (même rafraîchissement que l’économie)
      (a.ctx as unknown as { panneauxDevis: number }).panneauxDevis = 16;
      a.opt.majChiffrage(null);
      expect(a.t('rp9-need-note')).toContain('· 16 au devis');
    } finally { for (const x of [a, sansDevis, nonVendu, sansCompte, publique]) x.fin(); }
  });

  // T4-X8-012 (une cible) — « 16 posés / 16 cible » à côté de la carte « Cible — panneaux : 7 » : le nombre à poser (« Panneaux à
  // poser », choisi ou enregistré) était écrit « cible ». « cible » = la cible SERVIE (la conception du lead), avec sa source dans
  // les mots de la carte ; le nombre à poser garde son nom.
  describe('T4-X8-012 (une cible) — la note dit LA cible servie, jamais le nombre à poser', () => {
    const watt = MODULE_PAR_DEFAUT_ATELIER.pmaxWc as number;
    const hydrate = (cible: Record<string, unknown> | null, extra: Record<string, unknown> = {}) => ({ devis: { origineCible: 'factures', libelleOrigineCible: 'Factures du lead', cible, ...extra } });
    const note = (opts: Record<string, unknown>, neededPanels: number) => { const x = monter(opts, { devisMode: true, cibleVendue: false, neededPanels }); const t = x.t('rp9-need-note'); x.fin(); return t; };
    const SERVIE = (n: number) => hydrate({ panneaux: n, panel_watt: watt });

    it('cibles tapée (12), du devis (14) et des factures (7) toutes différentes : une seule cible dite, avec sa source', () => {
      // la pose en tient 10 : 3 de plus que la cible des factures ; le champ « à poser » (12) n’apparaît plus comme « cible »
      expect(note({ chiffrage: null, hydrate: SERVIE(7) }, 12))
        .toBe('10 posés / 7 cible (Factures du lead) · 3 de plus que la cible — le toit n’en tient pas davantage en plein sud (toit ou obstacles).');
      // même cible par la table servie du module posé (la carte « Couvrir la facture »), prioritaire sur le compte de la conception
      expect(note({ chiffrage: null, hydrate: hydrate({ panneaux: 99, panel_watt: 550 }, { panneauxSelonWatt: { [String(watt)]: 7 } }) }, 12))
        .toContain('10 posés / 7 cible (Factures du lead) · 3 de plus que la cible');
      // un devis lié vendu de 14 : la note garde « · 14 au devis » mais la cible reste la servie
      const lie = monter({ chiffrage: null, devisLie: true, hydrate: SERVIE(7) }, { devisMode: true, cibleVendue: true, neededPanels: 12, panneauxDevis: 14 });
      try { expect(lie.t('rp9-need-note')).toContain('10 posés / 7 cible (Factures du lead) · 3 de plus que la cible · 14 au devis — le toit n’en tient pas'); } finally { lie.fin(); }
    });

    it('sous la cible : « k de moins » et « seuls N tiennent » reste vrai ; à la cible : aucun écart ; place libre : phrase d’avant', () => {
      expect(note({ chiffrage: null, hydrate: SERVIE(14) }, 12))
        .toBe('10 posés / 14 cible (Factures du lead) · 4 de moins que la cible — seuls 10 tiennent en plein sud (toit ou obstacles).');
      expect(note({ chiffrage: null, hydrate: SERVIE(10) }, 12))
        .toBe('10 posés / 10 cible (Factures du lead) — le toit n’en tient pas davantage en plein sud (toit ou obstacles).');
      // 8 à poser (choisis), le toit en tient 10 : posés 8 / cible 7, la place restante est dite comme avant
      expect(note({ chiffrage: null, hydrate: SERVIE(7) }, 8)).toBe('8 posés / 7 cible (Factures du lead) · 1 de plus que la cible — il reste de la place sur le toit, laissée libre.');
    });

    it('sans cible servie, ou sans compte servi pour le module posé : le texte d’avant, jamais « 0 cible »', () => {
      const avant = '10 posés / 12 cible — seuls 10 tiennent en plein sud (toit ou obstacles).';
      expect(note({ chiffrage: null }, 12)).toBe(avant);
      expect(note({ chiffrage: null, hydrate: { devis: { panneauxSelonWatt: { [String(watt)]: 7 } } } }, 12)).toBe(avant); // une table seule n'est pas une origine
      expect(note({ chiffrage: null, hydrate: hydrate({ panneaux: null, panel_watt: null }) }, 12)).toBe(avant); // refus du moteur : aucune cible
      expect(note({ chiffrage: null, hydrate: hydrate({ panneaux: 7, panel_watt: watt + 100 }) }, 12)).toBe(avant); // autre module, aucun compte servi
      // rien à poser : aucune phrase « N posés / T cible » ; la note ne dit « aucune cible » que s'il n'y en a aucune de servie
      expect(note({ chiffrage: null, hydrate: SERVIE(7) }, 0)).toBe('La cible est de 7 panneaux (Factures du lead) — on pose ce qui tient (10). Saisissez un nombre pour le plafonner.');
      expect(note({ chiffrage: null }, 0)).toBe('Aucune cible de puissance sur ce calepinage — on pose ce qui tient (10). Saisissez un nombre pour le plafonner.');
      expect(note({ chiffrage: null, hydrate: SERVIE(7) }, 0)).not.toContain('0 cible');
    });

    it('SITE PUBLIC : mêmes textes à l’octet près, même quand le payload porte une cible servie', () => {
      const sans = note({}, 12);
      expect(sans).toBe('10 posés / 12 au devis — seuls 10 tiennent en plein sud (toit ou obstacles).');
      expect(note({ hydrate: SERVIE(7) }, 12)).toBe(sans);
      expect(texteSurDevis(10, 12, false, true, 14, ' X', { panneaux: 7, origine: 'Factures du lead' })).toBe('10 posés / 12 au devis');
      expect(phraseTiennent(10, null)).toBe('seuls 10 tiennent'); // sans cible : la phrase d'avant
    });

    it('les notes de pose tenue disent la même cible et la même source ; sans cible servie, le nombre à poser comme avant', () => {
      document.body.innerHTML = '<p id="rp9-need-note"></p>';
      const ctx = { neededPanels: 12, opts: { chiffrage: null, hydrate: SERVIE(7) } };
      direEcartALaPose(16, ctx as never, watt, fmt, false, '');
      expect(document.getElementById('rp9-need-note')!.textContent)
        .toBe('16 posés / 7 cible (Factures du lead) — pose tenue telle quelle (9 de plus que la cible, rien n’est retiré ni ajouté).');
      direEcartALaPose(16, { neededPanels: 12, opts: { chiffrage: null } } as never, watt, fmt, true, '');
      expect(document.getElementById('rp9-need-note')!.textContent).toBe(noteEcartPoseRelue(16, 12, fmt, true));
      document.body.innerHTML = '<p id="rp9-need-note">intact</p>';
      direEcartALaPose(7, ctx as never, watt, fmt, true, ''); // pose = cible : rien à dire
      expect(document.getElementById('rp9-need-note')!.textContent).toBe('intact');
    });
  });

  // T4-X8-012 — après « Le plus de panneaux » (le plafond 400 de `clampNeeded`, « tout ce qui tient ») puis Enregistrer, l'Expert
  // disait « PANNEAUX NÉCESSAIRES 400 » et « 9 posés / 400 cible » : le plafond lu comme le besoin de la facture.
  it('T4-X8-012 — ERP, « le plus de panneaux » : le champ dit le besoin de la FACTURE (servi), la note dit le choix en mots, jamais « 400 cible »', () => {
    const watt = String(MODULE_PAR_DEFAUT_ATELIER.pmaxWc); // aucun module choisi sur le pan : le module par défaut est posé
    const lePlus = monter({ chiffrage: null, hydrate: { devis: { panneauxSelonWatt: { [watt]: 7 } } } }, { devisMode: true, cibleVendue: false, neededPanels: 400 });
    const sansTable = monter({ chiffrage: null }, { devisMode: true, cibleVendue: false, neededPanels: 400 });
    const ordinaire = monter({ chiffrage: null, hydrate: { devis: { panneauxSelonWatt: { [watt]: 7 } } } }, { devisMode: true, cibleVendue: false, neededPanels: 12 });
    const publique = monter({}, { devisMode: true, cibleVendue: true, neededPanels: 400 });
    const champ = (x: { doc: Document }) => x.doc.getElementById('rp9-need-input') as HTMLInputElement;
    try {
      expect(lePlus.t('rp9-need-note')).toBe('Vous avez choisi le plus de panneaux possible : 10 posés. Le besoin de la facture : 7.');
      expect(champ(lePlus).value).toBe('7');
      expect(champ(lePlus).dataset.lePlus).toBe('1');
      expect(sansTable.t('rp9-need-note')).toBe('Vous avez choisi le plus de panneaux possible : 10 posés.');
      expect(champ(sansTable).value).toBe('—');
      for (const x of [lePlus, sansTable]) expect(`${x.t('rp9-need-note')} ${champ(x).value}`).not.toContain('400');
      // un besoin ordinaire : le champ et la note d'avant
      expect(champ(ordinaire).value).toBe('12');
      expect(champ(ordinaire).dataset.lePlus ?? '').toBe('');
      expect(ordinaire.t('rp9-need-note')).toContain('10 posés / 12 cible — seuls 10 tiennent');
      expect(publique.t('rp9-need-note')).toContain('10 posés / 400 au devis'); // site public : texte d’avant
    } finally { for (const x of [lePlus, sansTable, ordinaire, publique]) x.fin(); }
    // la pose rouverte ne se compare jamais au plafond (« 9 posés / 400 cible … 391 de moins que la cible »)
    expect(noteEcartPoseRelue(9, 400, fmt)).toBeNull();
    expect(noteEcartPoseRelue(9, 12, fmt)).toContain('9 posés / 12 cible');
  });

  it('ACAL1951 — « au devis » nomme le devis et l’option (sans / avec batterie) ; une cible estimée ne nomme aucune option', () => {
    const lie = { devisMode: true, cibleVendue: true, neededPanels: 12, panneauxDevis: 14 };
    const avec = monter({ chiffrage: null, devisLie: true, hydrate: { devis: { referenceDevis: 'DEV-202611-0022', optionCible: 'avec' } } }, lie);
    const sans = monter({ chiffrage: null, devisLie: true, hydrate: { devis: { referenceDevis: 'DEV-202611-0022', optionCible: 'sans' } } }, lie);
    const estimee = monter({ chiffrage: null, devisLie: true, hydrate: { devis: { referenceDevis: 'DEV-202611-0022', optionCible: null } } }, lie);
    try {
      expect(avec.t('rp9-need-note')).toContain('10 posés / 12 cible · 14 au devis DEV-202611-0022 (option avec batterie) — seuls 10 tiennent');
      expect(sans.t('rp9-need-note')).toContain('· 14 au devis DEV-202611-0022 (option sans batterie) — seuls');
      expect(estimee.t('rp9-need-note')).toContain('· 14 au devis DEV-202611-0022 — seuls');
      expect(estimee.t('rp9-need-note')).not.toContain('option');
    } finally { for (const x of [avec, sans, estimee]) x.fin(); }
  });

  it('renommage de la tuile : « De la consommation » en ERP seulement (T4-X7-002) ; « Couverture » reste sur le site public', () => {
    const e = erp(null);
    const p = monter({});
    try {
      expect(e.doc.querySelector('dt')?.firstChild?.nodeValue).toBe('De la consommation');
      expect(e.doc.querySelector('dt span')?.textContent).toBe('?'); // l’infobulle voisine reste
      expect(p.doc.querySelector('dt')?.firstChild?.nodeValue).toBe('Couverture');
    } finally { e.fin(); p.fin(); }
  });

  it('SITE PUBLIC figé : mêmes textes et mêmes nombres qu’avant la recette (valeurs relevées sur le code d’avant : ni servi, ni renommage, ni phrase)', () => {
    const p = monter({}, { devisMode: true, cibleVendue: true, neededPanels: 12 }, 20000);
    try {
      expect(p.t('rp9-reco-kwc')).toBe('5,50 kWc');
      expect(p.t('rp9-reco-prod')).toBe(`${fmt(7150)} kWh/an`);
      expect(p.t('rp9-reco-savings')).toBe(`${fmtMad(8702)} – ${fmtMad(11603)}/an`);
      expect(p.t('rp9-reco-cover')).toBe('36 %');
      expect(p.t('rp9-reco-band')).toBe(`Dans la durée (dégradation ~0,5 %/an) : Année 1 ~${fmt(7150)} kWh/an (${fmtMad(11603)}/an) → Année 25 ~${fmt(6339)} kWh/an (${fmtMad(10288)}/an). Économies toujours plafonnées à votre facture.`);
      expect(p.t('rp9-reco-why')).toBe('w');
      expect(p.t('rp9-need-note')).toBe(`10 posés / 12 au devis — seuls 10 tiennent en plein sud (toit ou obstacles).`);
    } finally { p.fin(); }
  });

  it('R3-04 : la phrase « aucune pose ne couvre » se masque quand la tuile affichée couvre le besoin (ERP seulement)', () => {
    const prod = prodEstimee();
    const couvre = erp(null, {}, prod / 2); // tuile à 200 %
    const manque = erp(null, {}, prod * 2); // tuile à 50 %
    const publique = monter({}, {}, prod / 2);
    try {
      const masquee = (x: { doc: Document }) => x.doc.querySelector<HTMLElement>('[data-couverture-max]')!.hidden;
      expect(masquee(couvre)).toBe(true);
      expect(masquee(manque)).toBe(false);
      expect(masquee(publique)).toBe(false);
    } finally { couvre.fin(); manque.fin(); publique.fin(); }
  });
});

// ACAL1418 — UNE production à l'écran quand le chiffrage est servi : la carte, le Total « Production estimée » et la ligne
// « Année 1 » de la bande lisent la production servie (à kWc égal) ; non servi : le Total dit « estimation ».
describe('ACAL1418 — chiffrage servi : Total et bande = production servie ; non servi : estimation étiquetée', () => {
  const chiffrage = { kwc: { valeur: 5.5, etat: 'servi' }, production_annuelle_kwh: { valeur: 4636, etat: 'servi' }, economie_annee1_mad: { valeur: 7420, etat: 'servi' } };
  const GRILLE = { count: 10, kwc: 5.5, panels: [], rowWidthM: 2, footprintPerPanelM2: 2, slopeLenM: 1 };
  /** Rend la bande (via la carte) et le Total (via le panneau des pans) sous un DOM le temps du cas. */
  const lire = (opts: Record<string, unknown>) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    const doc = new JSDOM('<!doctype html><body><dd id="rp9-reco-kwc"></dd><dd id="rp9-reco-prod"></dd><dl><dd id="rp9-reco-savings"></dd></dl>'
      + '<p id="rp9-reco-band"></p><p id="rp9-reco-why"></p><p id="rp9-need-note"></p><div id="rp9-areas"></div><dd id="tot-prod"></dd></body>').window.document;
    g.document = doc;
    try {
      const pan = { id: 'area-1', label: '', vertices: rectRing(10, 7), obstacles: [], roofType: 'flat', pitchDeg: 22, facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true, result: null, renderPlan: null };
      const ctx = { opts, centroidLat: 33.5, rec: { targetAnnualKwh: 4000 }, neededPanels: 0, batiments: [], centroid: [-7, 33], environment: [], shadeObstructions: [],
        obstacles: [], areas: [pan], activeAreaId: 'area-1', activeArea: () => pan, vertices: pan.vertices, roofType: 'flat', closed: true, pinned: new Set(),
        liveResult: { winner: { placedCount: 10, kwc: 5.5, annualKwh: 4362, savingsLow: 1, savingsHigh: 2 }, target: 4000 }, shadeAnnualFactor: 1, horizonAnnualFactor: 1,
        dom: { areasWindowEl: doc.getElementById('rp9-areas'), areasTotalProdEl: doc.getElementById('tot-prod') } } as unknown as Ctx;
      const deps = { renderScene: vi.fn(), paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
        syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 800, obstructionRings: vi.fn(() => []), setStatus: vi.fn() };
      createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]).renderConfig({ pack: { origin: [-7, 33], ringENU: [], azimuthDeg: 0, portrait: GRILLE, landscape: GRILLE } as never,
        grid: GRILLE as never, family: 'south', tiltDeg: 20, azimuthDeg: 0, isReco: true, title: 't', why: 'w', rowId: null });
      createZones(ctx, { setStatus: vi.fn() }).renderAreasPanel();
      const t = (id: string) => doc.getElementById(id)?.textContent ?? '';
      return { carte: t('rp9-reco-prod'), bande: t('rp9-reco-band'), total: t('tot-prod') };
    } finally { g.document = avant; }
  };

  it('servi : carte, Total et « Année 1 » disent les 4 636 kWh/an servis', () => {
    const r = lire({ chiffrage });
    expect(r.carte).toBe(`${fmt(4636)} kWh/an`);
    expect(r.total).toBe(`${fmt(4636)} kWh/an`);
    expect(r.bande).toContain(`Année 1 ~${fmt(4636)} kWh/an`);
  });

  it('non servi (ERP) : le Total dit « production au prochain enregistrement » ; site public : le texte d’avant', () => {
    expect(lire({ chiffrage: null }).total).toBe('production au prochain enregistrement'); // ACAL2022 (ex-ACAL1612 : « estimation de l’atelier »)
    expect(lire({}).total).toBe(`${fmt(4362)} kWh/an`);
  });
});

// Demande croisée (lane zones) — la bande lit la production servie au kWc DE LA CARTE (module du pan : 10 × 710 W = 7,1),
// et « Enregistrer » (majChiffrage) repeint aussi la production de la carte et le Total, pas seulement l'économie.
describe('Demande croisée — bande au kWc de la carte ; majChiffrage repeint production et Total', () => {
  const m710 = { id: 'produit-7', produitId: 7, libelle: 'Module 710 W', longueurMm: 2384, largeurMm: 1303, epaisseurMm: 33, poidsKg: 38, pmaxWc: 710, source: 'fiche' };
  const catalogue = { calepinage: 1, modules: [{ module: m710, selectionnable: true, champs_manquants: [], motif: null }], champs_requis: [], motif_liste_vide: null };
  const servi = { kwc: { valeur: 7.1, etat: 'servi' }, production_annuelle_kwh: { valeur: 4636, etat: 'servi' }, economie_annee1_mad: { valeur: 7420, etat: 'servi' } };
  const GRILLE = { count: 10, kwc: 5.5, panels: [], rowWidthM: 2, footprintPerPanelM2: 2, slopeLenM: 1 };
  const monter = (chiffrage: unknown) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    const doc = new JSDOM('<!doctype html><body><dd id="rp9-reco-kwc"></dd><dd id="rp9-reco-prod"></dd><dl><dd id="rp9-reco-savings"></dd></dl>'
      + '<p id="rp9-reco-band"></p><p id="rp9-reco-why"></p><p id="rp9-need-note"></p><div id="rp9-areas"></div><dd id="tot-prod"></dd></body>').window.document;
    g.document = doc;
    const pan = { id: 'area-1', label: '', vertices: rectRing(10, 7), obstacles: [], roofType: 'flat', pitchDeg: 22, facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true, result: null, renderPlan: null, moduleId: 'produit-7' };
    const ctx = { opts: { chiffrage, modulesDisponibles: catalogue }, centroidLat: 33.5, rec: { targetAnnualKwh: 4000 }, neededPanels: 0, batiments: [], centroid: [-7, 33], environment: [], shadeObstructions: [],
      obstacles: [], areas: [pan], activeAreaId: 'area-1', activeArea: () => pan, vertices: pan.vertices, roofType: 'flat', closed: true, pinned: new Set(),
      liveResult: { winner: { placedCount: 10, kwc: 5.5, annualKwh: 4362, savingsLow: 1, savingsHigh: 2 }, target: 4000 }, shadeAnnualFactor: 1, horizonAnnualFactor: 1,
      dom: { areasWindowEl: doc.getElementById('rp9-areas'), areasTotalProdEl: doc.getElementById('tot-prod') } } as unknown as Ctx;
    const deps = { renderScene: vi.fn(), paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
      syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 800, obstructionRings: vi.fn(() => []), setStatus: vi.fn() };
    const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
    opt.renderConfig({ pack: { origin: [-7, 33], ringENU: [], azimuthDeg: 0, portrait: GRILLE, landscape: GRILLE } as never,
      grid: GRILLE as never, family: 'south', tiltDeg: 20, azimuthDeg: 0, isReco: true, title: 't', why: 'w', rowId: null });
    const zones = createZones(ctx, { setStatus: vi.fn() });
    zones.renderAreasPanel();
    const t = (id: string) => doc.getElementById(id)?.textContent ?? '';
    return { opt, zones, t, fin: () => { g.document = avant; } };
  };

  it('servi à 7,1 kWc (module du pan) : la carte ET la bande « Année 1 » disent 4 636 kWh/an', () => {
    const m = monter(servi);
    try {
      expect(m.t('rp9-reco-kwc')).toBe('7,10 kWc');
      expect(m.t('rp9-reco-prod')).toBe(`${fmt(4636)} kWh/an`);
      expect(m.t('rp9-reco-band')).toContain(`Année 1 ~${fmt(4636)} kWh/an`);
    } finally { m.fin(); }
  });

  it('« Enregistrer » : le bloc relu repeint la production de la carte et le Total (avant : seule l’économie)', () => {
    const m = monter(null);
    try {
      expect(m.t('rp9-reco-prod')).not.toBe(`${fmt(4636)} kWh/an`);
      m.opt.majChiffrage(servi as never);
      m.zones.renderAreasPanel(); // ce que fait l'enveloppe `majChiffrage` de roof-tool-pro11.ts après l'optimiseur
      expect(m.t('rp9-reco-prod')).toBe(`${fmt(4636)} kWh/an`);
      expect(m.t('tot-prod')).toBe(`${fmt(4636)} kWh/an`);
    } finally { m.fin(); }
  });
});

// ACAL1526 — la note sous « Panneaux à poser » (ERP) dit la pose DESSINÉE : les emplacements écartés par le seuil
// d'accès solaire (`poseSousSeuil`) sont retirés, jamais « il reste de la place » quand la pose a été rognée.
describe('ACAL1526 — seuil d’accès : la note dit la pose dessinée', () => {
  /** Un pan plat 10 × 7 avec une cheminée de 1,1 m au milieu ; `seuil` = accès solaire minimal (0..1) ou null. */
  const poser = (seuil: number | null, besoin: number) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    const doc = new JSDOM('<!doctype html><body><p id="rp9-need-note"></p></body>').window.document;
    g.document = doc;
    poserChoixOptimisation(seuil == null ? null : { seuilAccesSolaire: seuil });
    try {
      const vertices = rectRing(10, 7);
      const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
      const cheminee = { id: 'o1', type: 'cheminee', centerLng: cLng, centerLat: cLat, lengthM: 0.6, widthM: 0.6, heightM: 1.1 };
      const ctx = { opts: { chiffrage: null }, dom: {}, centroidLat: cLat, centroid: [cLng, cLat], rec: { targetAnnualKwh: 4000 }, neededPanels: besoin,
        devisMode: true, cibleVendue: true, activeArea: () => null, activeAreaId: null, batiments: [], environment: [], shadeObstructions: [],
        obstacles: [cheminee], areas: [], pinned: new Set() } as unknown as Ctx;
      let dessines = -1;
      const deps = { renderScene: (_p: unknown, _g: unknown, _t: unknown, _f: unknown, placed: number) => { dessines = placed; }, paintComparison: vi.fn(),
        highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(), syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(),
        monthlyBill: () => 0, obstructionRings: vi.fn(() => []), setStatus: vi.fn() };
      const pack = packConfig(vertices, cLat, { family: 'south', tiltDeg: 13 });
      createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]).renderConfig({
        pack, grid: pack.best, family: 'south', tiltDeg: 13, azimuthDeg: 180, isReco: true, title: 't', why: 'w', rowId: null,
      });
      return { note: doc.getElementById('rp9-need-note')?.textContent ?? '', dessines, capacite: pack.best.count };
    } finally {
      poserChoixOptimisation(null);
      g.document = avant;
    }
  };

  it('seuil qui rogne la pose sous la cible : « X posés / N cible — K emplacements écartés par le seuil »', () => {
    const sansSeuil = poser(null, 6);
    expect(sansSeuil.note).toContain('il reste de la place'); // la cible tient sans seuil
    const r = poser(0.99, sansSeuil.capacite); // cible = tout ce qui tient : le seuil en écarte forcément
    expect(r.dessines).toBeLessThan(sansSeuil.capacite);
    const ecartes = sansSeuil.capacite - r.dessines;
    expect(r.note).toBe(`${fmt(r.dessines)} posés / ${fmt(sansSeuil.capacite)} cible — ${fmt(ecartes)} emplacement${ecartes > 1 ? 's' : ''} écarté${ecartes > 1 ? 's' : ''} par le seuil d’accès solaire.`);
    expect(r.note).not.toContain('il reste de la place');
  });
});

// ACAL1533 — le chiffre annoncé par « Portrait / Paysage » (sous les puces de pose, Expert, toit ombré) est celui
// qu'on obtient au clic : même seuil d'accès (`poseSousSeuil`), même marge, et la ligne marquée suit la pose affichée.
describe('ACAL1533 — le chiffre annoncé par Portrait est le nombre posé après le clic', () => {
  /** Pan plat avec cheminée, atelier en mode Expert ; les puces imitent celles de l'entrée (un clic verrouille l'axe). */
  const monter = (seuil: number | null, besoin: number, largeurM = 10, profondeurM = 7) => {
    const g = globalThis as unknown as { document?: Document; window?: unknown };
    const avant = { d: g.document, w: g.window };
    const fen = new JSDOM('<!doctype html><body data-mode-expert="1"><div><button data-orient="auto"></button><button data-orient="portrait"></button>'
      + '<button data-orient="landscape"></button></div><div><button data-margin="keep"></button><button data-margin="remove"></button></div></body>').window;
    g.document = fen.document;
    g.window = fen;
    poserChoixOptimisation(seuil == null ? null : { seuilAccesSolaire: seuil });
    const vertices = rectRing(largeurM, profondeurM);
    const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
    const cheminee = { id: 'o1', type: 'cheminee', centerLng: cLng, centerLat: cLat, lengthM: 0.6, widthM: 0.6, heightM: 1.1 };
    const pan = { id: 'z1', label: 'Pan A', vertices, obstacles: [cheminee], roofType: 'flat', neededPanels: besoin, neededAuto: false };
    const ctx = {
      closed: true, vertices, roofType: 'flat', areas: [pan], activeAreaId: 'z1', activeArea: () => pan, opts: { chiffrage: null }, dom: {},
      centroid: [cLng, cLat], centroidLat: cLat, pinned: new Set<string>(), sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' },
      v4YieldCache: new Map(), overhangM: 0, documentRelu: null, batiments: [], environment: [], shadeObstructions: [], obstacles: [cheminee],
      neededAuto: false, neededPanels: besoin, layoutPlan: null, useRecommended: true,
    } as unknown as Ctx & { pinned: Set<string>; sel: Record<string, unknown> };
    let pose = -1;
    const sync = () => {
      for (const b of Array.from(fen.document.querySelectorAll<HTMLElement>('[data-orient]'))) b.setAttribute('aria-pressed', String(b.dataset.orient === (ctx.useRecommended ? 'auto' : ctx.sel.orient)));
      for (const b of Array.from(fen.document.querySelectorAll<HTMLElement>('[data-margin]'))) b.setAttribute('aria-pressed', String(b.dataset.margin === ctx.sel.margin));
    };
    const deps = {
      renderScene: (_p: unknown, _g: unknown, _t: unknown, _f: unknown, placed: number) => { pose = placed; }, paintComparison: vi.fn(), highlightRow: vi.fn(),
      syncProductionWindow: vi.fn(), prefillLead: vi.fn(), syncChips: sync, renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 0,
      obstructionRings: () => [], setStatus: vi.fn(),
    };
    const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
    for (const axe of ['orient', 'margin'] as const) {
      for (const b of Array.from(fen.document.querySelectorAll<HTMLElement>(`[data-${axe}]`))) {
        b.addEventListener('click', () => {
          const v = b.dataset[axe]!;
          if (v === 'auto' || (ctx.pinned.has(axe) && ctx.sel[axe] === v)) ctx.pinned.delete(axe);
          else { ctx.pinned.add(axe); ctx.sel = { ...ctx.sel, [axe]: v }; }
          opt.liveResolveFlat();
        });
      }
    }
    opt.liveResolveFlat();
    const lignes = () => Array.from(fen.document.querySelectorAll<HTMLElement>('[data-orient-ombre]'));
    const annonce = (sens: string) => Number((lignes().find((l) => l.dataset.orientOmbre === sens)?.textContent ?? '').match(/: (\d+) panneaux/)?.[1] ?? NaN);
    return {
      ctx, lignes, annonce, pose: () => pose,
      cliquer: (sens: string) => lignes().find((l) => l.dataset.orientOmbre === sens)!.click(),
      fin: () => { poserChoixOptimisation(null); g.document = avant.d; g.window = avant.w; },
    };
  };

  const marquee = (m: ReturnType<typeof monter>) => m.lignes().find((l) => l.getAttribute('aria-pressed') === 'true')?.dataset.orientOmbre ?? null;

  // Cas relevés sur la tête : seuil 0,99 / cible 4 ⇒ « Portrait : 4 » puis 3 posés ; cible 10 sans seuil ⇒ « Portrait : 7 »
  // puis 10 posés et la marge passée de Pleine rive à Garder ; aucune ligne marquée en « auto ».
  it('annoncé = posé après le clic, marge inchangée, ligne marquée = pose affichée (avec et sans seuil)', () => {
    for (const seuil of [null, 0.99]) {
      for (const besoin of [4, 10, 16]) {
        for (const sens of ['portrait', 'landscape'] as const) {
          const m = monter(seuil, besoin);
          try {
            expect(marquee(m)).toBe(m.ctx.sel.orient); // la pose dessinée est marquée, même en « auto »
            const margeAvant = m.ctx.sel.margin;
            const annonce = m.annonce(sens);
            m.cliquer(sens);
            expect({ seuil, besoin, sens, pose: m.pose(), marge: m.ctx.sel.margin }).toEqual({ seuil, besoin, sens, pose: annonce, marge: margeAvant });
            expect(marquee(m)).toBe(sens);
          } finally { m.fin(); }
        }
      }
    }
  });
});

describe('R3-25 (b) / R3-04 — cartes de variante espacées, phrase « aucune pose ne couvre »', () => {
  const anneau = (w: number, h: number, lng0 = -7.62, lat0 = 33.59): Array<[number, number]> => {
    const k = 111320 * Math.cos((lat0 * Math.PI) / 180);
    return [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]].map(([x, y]) => [lng0 + x / k, lat0 + y / 111320] as [number, number]);
  };
  const balayer = (facture: number, opts: Record<string, unknown> = {}) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    const doc = new JSDOM('<!doctype html><body><div id="rp9-results"></div></body>').window.document;
    g.document = doc;
    const ctx = { opts, dom: {}, centroidLat: 33.59, roofType: 'flat', closed: false, vertices: [], areas: [], pinned: new Set(), v4YieldCache: new Map(),
      activeArea: () => null, batiments: [], centroid: [-7.62, 33.59], environment: [], shadeObstructions: [], obstacles: [], overhangM: 0 } as unknown as Ctx;
    const deps = { renderScene: vi.fn(), paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
      syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => facture, obstructionRings: vi.fn(() => []), setStatus: vi.fn() };
    createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]).buildMatrix(anneau(22, 15), facture);
    return { doc, host: doc.getElementById('rp9-variants') as HTMLElement, fin: () => { g.document = avant; } };
  };

  it('R3-25 : le conteneur est une grille à écart, chaque carte une colonne (titre, chiffres, raison chacun sa ligne)', () => {
    const { host, fin } = balayer(2500);
    try {
      const cartes = Array.from(host.querySelectorAll<HTMLElement>('button.rp9-variant'));
      expect(cartes.length).toBeGreaterThan(0);
      expect(host.style.display).toBe('grid');
      expect(host.style.gap).toBe('0.5rem');
      for (const c of cartes) {
        expect(c.style.display).toBe('flex');
        expect(c.style.flexDirection).toBe('column');
      }
    } finally { fin(); }
  });

  it('R3-04 : une facture énorme (aucune pose ne couvre) porte la phrase du maximum mesuré, repérable pour le masquer', () => {
    const { host, fin } = balayer(2_000_000);
    try {
      const phrase = host.querySelector<HTMLElement>('p[data-couverture-max]');
      expect(phrase?.textContent).toMatch(/^Aucune pose ne couvre le besoin \(estimation\) : le toit donne au plus \d+ % \(\d+ panneaux\)\.$/);
    } finally { fin(); }
  });
});

// ACAL1331 + ACAL1448 (D-ACAL-76 « dimensionner », 23/11/2026) — un calepinage VIERGE de l'atelier ERP se pose, dès que son
// toit est fermé, à la taille de la cible servie (celle du devis lié, sinon celle tirée de la facture du lead), et l'écran
// le DIT ; le commercial ajuste ; une pose tenue n'est jamais re-posée (ACAL1900) ; le site public ne change pas.
describe('ACAL1331 — la taille de la cible posée d’elle-même sur un calepinage vierge, et dite', () => {
  // les mots que l'ERP pose dans le payload (contexteAtelier.js : LIBELLES_SOURCE_CIBLE et sa forme « d'après »)
  const motsDeLaCarte: Record<string, { libelleOrigineCible: string; libelleApresOrigineCible: string }> = {
    factures: { libelleOrigineCible: 'Factures du lead', libelleApresOrigineCible: 'les factures du lead' },
    devis: { libelleOrigineCible: 'Devis lié', libelleApresOrigineCible: 'le devis lié' },
    lead: { libelleOrigineCible: 'Taille souhaitée sur la fiche du lead', libelleApresOrigineCible: 'la taille souhaitée sur la fiche du lead' },
  };
  const payload = (origineCible: string | null, roofLayout: unknown = null) => ({
    id: null, geometrie: { roof_layout: roofLayout, roof_point: null, roof_outline: null },
    cible: { panneaux: 8, panel_watt: 710, scenario: null }, cibleVendue: origineCible === 'devis', origineCible,
    ...(motsDeLaCarte[origineCible ?? ''] ?? {}),
  });
  /** Boot d'un plat `l × p` m depuis le payload de l'atelier (`hydrateFromDevis`, cible imposée au pan unique comme
   *  `imposeTarget`), puis `close()` : le premier rendu de l'optimiseur. */
  const fermer = (l: number, p: number, opts: Record<string, unknown>) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><p id="rp9-need-note"></p><dd id="rp9-reco-kwc"></dd><tbody id="rp9-compare"></tbody></body>').window.document;
    const h = hydrateFromDevis((opts.hydrate as { devis?: DevisPayload } | undefined)?.devis ?? null);
    const vertices = rectRing(l, p);
    const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
    const pan = { id: 'z1', label: 'Zone 1', vertices, obstacles: [], roofType: 'flat' };
    const ctx = {
      closed: true, vertices, roofType: 'flat', areas: [pan], activeAreaId: 'z1', activeArea: () => pan, opts, dom: {},
      centroid: [cLng, cLat], centroidLat: cLat, pinned: new Set<string>(), sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' },
      v4YieldCache: new Map(), overhangM: 0, documentRelu: h.documentRelu, batiments: [], environment: [], shadeObstructions: [], obstacles: [],
      neededAuto: h.neededAuto, neededPanels: h.neededPanels ?? 0, devisMode: true, cibleVendue: h.cibleVendue, panneauxDevis: h.neededPanels,
      layoutPlan: null, layoutState: null, layoutOptimalCount: 0, useRecommended: true, freeMode: false, freeState: null,
    } as unknown as Ctx;
    let dessinee = -1;
    const renderScene = vi.fn((pack: unknown, grid: { panels: unknown[] }, tiltDeg: number, family: string, maxCount: number, flush: boolean, occ?: Set<number>) => {
      dessinee = maxCount;
      if (!occ) Object.assign(ctx, { layoutPlan: { pack, grid, tiltDeg, family, flush }, layoutOptimalCount: Math.min(grid.panels.length, Math.round(maxCount)), layoutState: null });
    });
    const deps = { renderScene, paintComparison: vi.fn(), highlightRow: vi.fn(), syncProductionWindow: vi.fn(), prefillLead: vi.fn(),
      syncChips: vi.fn(), renderMatrixOptimumCard: vi.fn(), monthlyBill: () => 0, obstructionRings: () => [], obstructionClearances: () => [], setStatus: vi.fn() };
    const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
    opt.liveResolveFlat(); // close() : le toit vient d'être fermé
    const note = () => document.getElementById('rp9-need-note')!.textContent ?? '';
    const kwc = () => (document.getElementById('rp9-reco-kwc')!.textContent ?? '').replace(/\s*kWc$/, '');
    return { ctx, opt, dessinee: () => dessinee, note, kwc, fin: () => { g.document = avant; } };
  };
  const ERP = (origine: string | null, roofLayout: unknown = null) => ({ chiffrage: null, rendementPvgis: null, hydrate: { devis: payload(origine, roofLayout) } });

  it('cible 8 tirée de la facture, toit qui en tient plus : 8 posés et DITS ; « + » ⇒ 9 et la phrase ne prétend plus la facture', () => {
    const a = fermer(12, 8, ERP('factures'));
    try {
      expect(a.dessinee()).toBe(8);
      expect(a.note()).toBe(`Posé d’après les factures du lead : 8 panneaux · ${a.kwc()} kWc — ajustez si besoin.`);
      a.ctx.neededPanels = 9; // « + »
      a.opt.liveResolveFlat();
      expect(a.dessinee()).toBe(9);
      expect(a.note()).not.toContain('d’après');
      expect(serializeLayout(a.ctx, null).zones[0].geometry!.count).toBe(9);
    } finally { a.fin(); }
  });

  it('pose tenue (le commercial a déplacé ou enregistré) : le recalcul de fond ne re-pose rien', async () => {
    const a = fermer(12, 8, ERP('factures'));
    try {
      const cellules = a.ctx.layoutPlan!.grid.panels;
      a.ctx.layoutState = createLayoutState(cellules, 7); // un panneau retiré à la main : 7
      await a.opt.computeMatrixPvgis();
      a.opt.liveResolveFlat(false);
      expect(serializeLayout(a.ctx, null).zones[0].geometry!.count).toBe(7);
    } finally { a.fin(); }
  });

  it('toit trop petit pour la cible : ce qui tient est posé, et l’écart est dit', () => {
    const a = fermer(5, 4, ERP('factures'));
    try {
      const n = a.dessinee();
      expect(n).toBeGreaterThan(0);
      expect(n).toBeLessThan(8);
      expect(a.note()).toMatch(new RegExp(`^Posé d’après les factures du lead : ${n} panneaux · ${a.kwc()} kWc sur 8 — seuls ${n} tiennent .+ ; ajustez si besoin\\.$`));
    } finally { a.fin(); }
  });

  it('devis lié : « Posé d’après le devis lié » ; taille souhaitée du lead : dite telle', () => {
    for (const [origine, mot] of [['devis', 'le devis lié'], ['lead', 'la taille souhaitée sur la fiche du lead']]) {
      const a = fermer(12, 8, ERP(origine));
      try {
        expect(a.dessinee()).toBe(8);
        expect(a.note().startsWith(`Posé d’après ${mot} : 8 panneaux`)).toBe(true);
      } finally { a.fin(); }
    }
  });

  it('T4-X8-012 (une cible) — la note nomme la MÊME source que la carte (même table) ; un payload sans ces mots garde le repli d’avant ; site public octet pour octet', () => {
    // la tête de la note dit la source de la carte « Cible — panneaux » (« Factures du lead ») après « d’après » : « les factures du lead »
    const a = fermer(5, 4, ERP('factures'));
    try { expect(a.note().startsWith('Posé d’après les factures du lead : ')).toBe(true); } finally { a.fin(); }
    // payload sans les mots de la table (jamais produit par l'ERP d'aujourd'hui) : le repli, texte d'avant
    const sansMots = fermer(12, 8, { chiffrage: null, rendementPvgis: null, hydrate: { devis: { ...payload('factures'), libelleOrigineCible: undefined, libelleApresOrigineCible: undefined } } });
    try { expect(sansMots.note()).toBe(`Posé d’après la facture : 8 panneaux · ${sansMots.kwc()} kWc — ajustez si besoin.`); } finally { sansMots.fin(); }
    // site public : le texte est le même avec ou sans les mots de l'ERP dans le payload (aucune note « d'après », aucun « cible »)
    const sans = fermer(12, 8, { rendementPvgis: null, hydrate: { devis: { ...payload('factures'), libelleOrigineCible: undefined, libelleApresOrigineCible: undefined } } });
    const avec = fermer(12, 8, { rendementPvgis: null, hydrate: { devis: payload('factures') } });
    try {
      expect(avec.note()).toBe(sans.note());
      expect(avec.note()).not.toMatch(/d’après|cible/);
    } finally { sans.fin(); avec.fin(); }
  });

  it('jumeaux inchangés : pose déjà enregistrée, aucune origine servie, site public', () => {
    const posee = { schema_version: 2, zones: [{ id: 'z1', vertices: rectRing(12, 8), geometry: { count: 8, panels: [{ cx: 0, cy: 0 }] } }] };
    for (const opts of [ERP('factures', posee), ERP(null), { rendementPvgis: null, hydrate: { devis: payload('factures') } }]) {
      const a = fermer(12, 8, opts);
      try { expect(a.note()).not.toContain('d’après'); } finally { a.fin(); }
    }
  });

  it('ACAL1448 — « 2 pans » sur un toit posé : le premier pan (le mieux exposé) garde la taille, tous gardent le module', () => {
    const pans = [{ id: 'area-2', neededPanels: 0, neededAuto: true }, { id: 'area-3', neededPanels: 0, neededAuto: true, existant: false }];
    heriterDuPanDecoupe({ moduleId: 'produit-710' }, { neededPanels: 5, neededAuto: false }, pans as never, true);
    expect(pans).toEqual([
      { id: 'area-2', neededPanels: 5, neededAuto: false, moduleId: 'produit-710' },
      { id: 'area-3', neededPanels: 0, neededAuto: true, existant: false, moduleId: 'produit-710' },
    ]);
    const publics = [{ id: 'area-2', neededPanels: 0, neededAuto: true }];
    heriterDuPanDecoupe({ moduleId: 'produit-710' }, { neededPanels: 5, neededAuto: false }, publics as never, false); // site public : rien
    expect(publics).toEqual([{ id: 'area-2', neededPanels: 0, neededAuto: true }]);
  });
});
