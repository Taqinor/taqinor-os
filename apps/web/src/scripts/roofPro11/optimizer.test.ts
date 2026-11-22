// CAL75 — écart rangée/colonne RÉGLABLE en pose optimisée (jusqu'ici réglable SEULEMENT en
// placement libre). `optimizer.ts` ne fait que transmettre `ctx.colGapM`/`ctx.rowGapExtraM` au
// pavage (packConfig, estimatorBrainV2.ts) et re-pave à chaud — la physique testée ici EST le
// changement : options absentes → calepinage identique au millimètre ; écart agrandi → moins de
// panneaux tiennent (le compte baisse), jamais l'inverse.
import { describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom'; // ACAL574
import { type Ctx } from './context'; // ACAL574
import { motifPanExistant } from './panExistant'; // ACAL574
import { packConfig, defaultEastWestGeometry, type PackOptions } from '../../lib/estimatorBrainV2';
import { PANEL2_SHORT_M, PERIMETER_SETBACK_M } from '../../lib/roofPro2';
import {
  cibleOptimisationSaisie,
  choixOptimisationCourant,
  createOptimizer, // ACAL574
  departagerRemplissage,
  poserCibleOptimisation,
  poserChoixOptimisation,
  PRIORITES_REMPLISSAGE,
  type EntreeDepartage,
} from './optimizer';
import { rectRing } from './harnaisAtelier';
import { factureCarteDe, lireFactureSaisie } from './factureCarte'; // ACAL777
import { seuilEffectifAccesSolaire } from './shadingUi'; // ACAL548
import { panneauxPourCible } from './cibleProduction';
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

// ACAL574 — un pan « existant » ne se re-résout pas : ses modules restent ceux posés.
describe('ACAL574 — re-résolution refusée sur un pan existant', () => {
  it('liveResolveFlat / liveResolvePitched : rien n’est re-pavé ni redessiné, le motif nomme le pan', () => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body></body>').window.document;
    try {
      const pan = { id: 'z1', label: 'Pan A', existant: true, geometrieEnregistree: { count: 4 } };
      const ctx = { closed: true, vertices: rectRing(10, 8), roofType: 'flat', areas: [pan], activeAreaId: 'z1', opts: {} } as unknown as Ctx;
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
  it('lireFactureSaisie : espaces et virgule décimale lus, vide ou illisible = 0', () => {
    expect(lireFactureSaisie({ value: '1 250,5' })).toBe(1250.5);
    expect(lireFactureSaisie({ value: '' })).toBe(0);
    expect(lireFactureSaisie({ value: 'abc' })).toBe(0);
    expect(lireFactureSaisie(null)).toBe(0);
  });
});
