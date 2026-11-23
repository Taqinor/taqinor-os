// CAL75 — écart rangée/colonne RÉGLABLE en pose optimisée (jusqu'ici réglable SEULEMENT en
// placement libre). `optimizer.ts` ne fait que transmettre `ctx.colGapM`/`ctx.rowGapExtraM` au
// pavage (packConfig, estimatorBrainV2.ts) et re-pave à chaud — la physique testée ici EST le
// changement : options absentes → calepinage identique au millimètre ; écart agrandi → moins de
// panneaux tiennent (le compte baisse), jamais l'inverse.
import { describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom'; // ACAL574
import { type Ctx } from './context'; // ACAL574
import { direEcartPoseRelue, motifPanExistant, noteEcartPoseRelue } from './panExistant'; // ACAL574, ACAL1900
import { createLayoutState } from '../../lib/layoutVariability'; // ACAL1900
import { serializeLayout } from './prefill'; // ACAL1900
import { packConfig, defaultEastWestGeometry, type PackOptions } from '../../lib/estimatorBrainV2';
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
import { rectRing } from './harnaisAtelier';
import { fmt, fmtKwc, fmtMad } from './dom'; // ACAL994 + R2-09
import { phraseSurplus } from './affichageErp'; // R2-17
import { createZones } from './zones'; // ACAL1418
import { factureCarteDe, lireFactureSaisie } from './factureCarte'; // ACAL777
import { seuilEffectifAccesSolaire } from './shadingUi'; // ACAL548
import { cibleDepuisCarte, panneauxPourCible, phraseCible } from './cibleProduction'; // ACAL1618
import { cotesDePavage } from '../../lib/roofPro2';
import {
  causeDuPanVide, ecrireMotifsDansDocument, mesurerPanVide, noterMotifPanVide, retraitApplique,
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
import { hydrateFromDevis } from './prefill';
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
  const atelier = (verrou: 'portrait' | null) => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><dd id="rp9-reco-prod"></dd><p id="rp9-need-note"></p></body>').window.document;
    const vertices = rectRing(12, 8);
    const [cLng, cLat] = [(vertices[0][0] + vertices[2][0]) / 2, (vertices[0][1] + vertices[2][1]) / 2];
    const pan = { id: 'area-1', vertices, obstacles: [], roofType: 'flat' };
    const ctx = { opts: { chiffrage: null }, centroidLat: cLat, centroid: [cLng, cLat], neededPanels: 5, neededAuto: false, batiments: [], environment: [],
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
    const doc = new JSDOM('<!doctype html><body><dd id="rp9-reco-kwc"></dd><dd id="rp9-reco-prod"></dd><dd id="rp9-reco-savings"></dd>'
      + '<dd id="rp9-reco-cover"></dd><p id="rp9-reco-band"></p><p id="rp9-reco-why"></p></body>').window.document;
    g.document = doc;
    const lancer = (factureServie: number | null) => {
      const ctx = {
        closed: true, vertices: rectRing(10, 8), roofType: 'pitched', pitchDeg: 25, facingAzimuthDeg: 200, centroidLat: 33.5,
        areas: [], activeAreaId: null, opts: { chiffrage: null }, neededAuto: true, neededPanels: 0, pinned: new Set(),
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
  const servi = (valeur: number | null, etat: string) => ({ economie_annee1_mad: { valeur, etat, option: 'sans_batterie' } });
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
      expect(economieAffichee(ctx, 'carte', '100 – 200 MAD/an')).toBe(`${fmtMad(7420)}/an`);
      opt.majChiffrage(servi(7420, 'servi') as never);
      expect(economieAffichee(ctx, 'total', '300 – 400 MAD/an')).toBe(`${fmtMad(7420)}/an`);
      expect(ligne(doc)).toBe('au dernier enregistrement · sans batterie');
    } finally { fin(); }
  });

  it('non servi ou hors ligne : l’estimation du navigateur reste et dit « estimation — recalculée à l’enregistrement »', () => {
    for (const chiffrage of [servi(null, 'non_servi'), null]) {
      const { ctx, opt, doc, fin } = monter(chiffrage);
      try {
        expect(economieAffichee(ctx, 'carte', '100 – 200 MAD/an')).toBe('100 – 200 MAD/an');
        opt.majChiffrage(chiffrage as never);
        expect(ligne(doc)).toBe('estimation — recalculée à l’enregistrement');
      } finally { fin(); }
    }
  });

  it('après enregistrement : la valeur servie remplace l’estimation (carte et Total), et revient à l’estimation si retirée', () => {
    const { ctx, opt, doc, fin } = monter(null);
    try {
      const carte = doc.getElementById('rp9-reco-savings') as HTMLElement;
      const total = doc.getElementById('tot') as HTMLElement;
      carte.textContent = economieAffichee(ctx, 'carte', '100 – 200 MAD/an');
      total.textContent = economieAffichee(ctx, 'total', '300 – 400 MAD/an');
      opt.majChiffrage(servi(8123, 'servi') as never);
      expect(carte.textContent).toContain('8');
      expect(carte.textContent).not.toContain('100');
      expect(total.textContent).toBe(carte.textContent);
      expect(ligne(doc)).toBe('au dernier enregistrement · sans batterie');
      opt.majChiffrage(servi(null, 'non_servi') as never);
      expect(carte.textContent).toBe('100 – 200 MAD/an');
      expect(total.textContent).toBe('300 – 400 MAD/an');
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
    const doc = new JSDOM('<!doctype html><body><dd id="rp9-reco-kwc"></dd><dd id="rp9-reco-prod"></dd><dd id="rp9-reco-savings"></dd>'
      + '<div><dd id="rp9-reco-cover"></dd><dt>Couverture<span>?</span></dt></div><p id="rp9-reco-band"></p><p id="rp9-reco-why"></p>'
      + '<p id="rp9-need-note"></p><p data-couverture-max>aucune pose</p></body>').window.document;
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
  const prodEstimee = (): number => { const b = erp(null); const v = b.t('rp9-reco-prod'); b.fin(); return Number(v.replace(/\D/g, '')); };

  it('PRODUCTION : la production SERVIE à kWc égal ; l’estimation sinon (jamais une valeur servie pour un autre kWc)', () => {
    const base = erp(null);
    const estimation = base.t('rp9-reco-prod');
    base.fin();
    expect(estimation).not.toBe(`${fmt(12345)} kWh/an`);
    const egal = erp(servi());
    const autreKwc = erp(servi({ kwc: { valeur: 6, etat: 'servi' } }));
    const nonServi = erp(servi({ production_annuelle_kwh: { valeur: 12345, etat: 'non_servi' } }));
    const sansKwc = erp(servi({ kwc: null }));
    try {
      expect(egal.t('rp9-reco-prod')).toBe(`${fmt(12345)} kWh/an`);
      expect(autreKwc.t('rp9-reco-prod')).toBe(estimation);
      expect(nonServi.t('rp9-reco-prod')).toBe(estimation);
      expect(sansKwc.t('rp9-reco-prod')).toBe(estimation);
    } finally { egal.fin(); autreKwc.fin(); nonServi.fin(); sansKwc.fin(); }
  });

  it('BANDE : l’économie SERVIE à l’année 1 ; non servi : l’estimation prudente ; l’année 25 jamais inventée (ACAL1612)', () => {
    const s = erp(servi());
    const n = erp(servi({ economie_annee1_mad: { valeur: null, etat: 'non_servi' } }));
    try {
      const bande = s.t('rp9-reco-band');
      expect(bande).toContain(`(${fmtMad(7420)}/an).`);
      expect(bande.match(MAD)).toHaveLength(1);
      expect(bande).not.toContain('Année 25'); // ACAL1612 — la fiche ne porte pas sa dégradation : omise avec sa raison
      expect(bande).toContain('la fiche du module ne porte pas sa dégradation');
      expect(n.t('rp9-reco-band').match(MAD)).toHaveLength(1);
      expect(n.t('rp9-reco-band')).not.toMatch(/%\/an/);
    } finally { s.fin(); n.fin(); }
  });

  it('une seule estimation d’économie en ERP (« ≈ X MAD/an »), la fourchette seulement sur le site public', () => {
    const e = erp(null);
    const p = monter({});
    try {
      expect(e.t('rp9-reco-savings')).toMatch(/^≈ [^–]+ MAD\/an$/);
      expect(p.t('rp9-reco-savings')).toMatch(/^[^≈]+ – [^≈]+ MAD\/an$/);
    } finally { e.fin(); p.fin(); }
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

  it('renommage de la tuile : « Production ÷ consommation » en ERP seulement ; « Couverture » reste sur le site public', () => {
    const e = erp(null);
    const p = monter({});
    try {
      expect(e.doc.querySelector('dt')?.firstChild?.nodeValue).toBe('Production ÷ consommation');
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
    const doc = new JSDOM('<!doctype html><body><dd id="rp9-reco-kwc"></dd><dd id="rp9-reco-prod"></dd><dd id="rp9-reco-savings"></dd>'
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

  it('non servi (ERP) : le Total dit « estimation » ; site public : le texte d’avant', () => {
    expect(lire({ chiffrage: null }).total).toBe(`${fmt(4362)} kWh/an · estimation de l’atelier`); // ACAL1612
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
    const doc = new JSDOM('<!doctype html><body><dd id="rp9-reco-kwc"></dd><dd id="rp9-reco-prod"></dd><dd id="rp9-reco-savings"></dd>'
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

// ACAL1526 — la note sous « Panneaux nécessaires » dit la pose DESSINÉE : les emplacements écartés par le seuil
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
