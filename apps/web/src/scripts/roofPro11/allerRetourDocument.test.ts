/* ============================================================================
   ACAL31 — ALLER-RETOUR OCTET-IDENTIQUE DE L'ATELIER (C-ACAL-045, LIVEX-06).
   ----------------------------------------------------------------------------
   L'`exemple` COMPLET du contrat `roof_layout_v2.schema.json` (toutes les clés racine,
   lu dans le dépôt — jamais une copie dans apps/web) est semé, hydraté par la SEULE
   fonction d'application (`appliquerHydratationAuCtx`), puis sérialisé par le sérialiseur
   câblé du wrapper, SANS AUCUN GESTE : le document produit doit être deep-equal à
   l'exemple. Critère A : aucune liste de champs « volatils » tolérés.

   Le même scénario est rejoué au boot RÉEL de l'atelier (devis ET lead) dans
   tests/estimatorRuntimePro10Pro11.test.ts (« runtime ACAL31 »).
   ========================================================================== */
import { beforeEach, describe, expect, it } from 'vitest';
import { hydrateFromDevis } from './prefill';
import { reinitialiserNumerotation } from './numerotation';
import { motifPenteNord, noterMotifPanVide } from './motifPanVide'; // ACAL1970
import { enregistrerAtelier, exempleRoofLayoutV2, ouvrirAtelier } from './harnaisDocument';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import Ajv2020 from 'ajv/dist/2020';
import { racineDepot } from './harnaisAtelier';


const EXEMPLE = exempleRoofLayoutV2();

/** Les CHEMINS qui diffèrent : la garde rougit en NOMMANT la clé. */
function differences(attendu: unknown, obtenu: unknown, chemin = ''): string[] {
  if (JSON.stringify(attendu) === JSON.stringify(obtenu)) return [];
  if (attendu && obtenu && typeof attendu === 'object' && typeof obtenu === 'object'
    && Array.isArray(attendu) === Array.isArray(obtenu)) {
    const a = attendu as Record<string, unknown>;
    const b = obtenu as Record<string, unknown>;
    return [...new Set([...Object.keys(a), ...Object.keys(b)])].flatMap((k) => differences(a[k], b[k], `${chemin}.${k}`));
  }
  return [`${chemin} : attendu ${JSON.stringify(attendu)} — obtenu ${JSON.stringify(obtenu)}`];
}

/** Boot (le payload de la page) → hydratation → « Enregistrer » sans geste (harnais ACAL345). */
function ouvrirPuisEnregistrer(payload: Parameters<typeof hydrateFromDevis>[0]) {
  const { c, h } = ouvrirAtelier(payload);
  return enregistrerAtelier(
    c, h.devisId != null ? { devisId: h.devisId, panelWatt: h.panelWatt, scenario: h.scenario } : null,
  );
}

beforeEach(() => reinitialiserNumerotation());

describe('ACAL31 — aller-retour octet-identique de l’exemple complet', () => {
  it("l'`exemple` de roof_layout_v2.schema.json : boot devis et boot lead → serializeLayout deep-equal", () => {
    // Boot devis d'un calepinage sans devis (cibleVendue false) — c'est aussi le chemin du
    // boot lead quand le lead porte un document (`applyHydration` y délègue).
    const devis = ouvrirPuisEnregistrer({ id: null, geometrie: { roof_layout: JSON.parse(JSON.stringify(EXEMPLE)) }, cibleVendue: false });
    expect(differences(EXEMPLE, devis)).toEqual([]);
    const lead = ouvrirPuisEnregistrer({ geometrie: { roof_layout: JSON.parse(JSON.stringify(EXEMPLE)) }, cibleVendue: false });
    expect(differences(EXEMPLE, lead)).toEqual([]);
  });

  it('aucune valeur inventée : ni source « devis », ni billKwh 0, ni saisi_le réhorodaté', () => {
    const sortie = ouvrirPuisEnregistrer({ id: null, geometrie: { roof_layout: JSON.parse(JSON.stringify(EXEMPLE)) }, cibleVendue: false });
    expect(sortie.source).toBe(EXEMPLE.source);
    expect(sortie.billKwh).toBe(EXEMPLE.billKwh);
    expect(sortie.consumption?.source).toEqual((EXEMPLE.consumption as { source: unknown }).source);
    // Les clés que l'atelier ne possède pas sont transmises telles quelles.
    expect((sortie.zones[0] as unknown as Record<string, unknown>).pitchSuggestion)
      .toEqual(((EXEMPLE.zones as Array<Record<string, unknown>>)[0]).pitchSuggestion);
    expect((sortie as unknown as Record<string, unknown>).parcelle).toEqual(EXEMPLE.parcelle);
  });

  it('test-du-test : un document dont la source est réécrite en « devis » rougit en nommant la clé', () => {
    const sortie = ouvrirPuisEnregistrer({ id: null, geometrie: { roof_layout: JSON.parse(JSON.stringify(EXEMPLE)) }, cibleVendue: false });
    expect(differences(EXEMPLE, { ...sortie, source: 'devis' })).toEqual(['.source : attendu "lead" — obtenu "devis"']);
  });

  // ACAL365 (C-ACAL-VER-014) — PV13 : « si le JSON dit 20 panneaux, le résultat dit 20 ».
  it('l’exemple respecte PV13 : result = somme des zones', () => {
    type Zone = { geometry: { count: number; kwc: number }; result?: { annualKwh?: number } };
    const zones = EXEMPLE.zones as Zone[];
    const result = EXEMPLE.result as { panels: number; kwc: number; annualKwh: number };
    expect(result.panels).toBe(zones.reduce((s, z) => s + z.geometry.count, 0));
    expect(result.kwc).toBeCloseTo(zones.reduce((s, z) => s + z.geometry.kwc, 0), 9);
    // Chaque pan porte SA production (ACAL355) ; le total en est la somme, jamais un prorata.
    for (const z of zones) expect(typeof z.result?.annualKwh).toBe('number');
    expect(result.annualKwh).toBe(zones.reduce((s, z) => s + (z.result?.annualKwh ?? 0), 0));
  });
});

// ACAL1601 — la place des factures mensuelles saisies au contrat, validée par un VRAI validateur
// JSON Schema sur le schéma lu dans le dépôt (jamais une copie).
describe('ACAL1601 — consumption.factures_mois au contrat roof_layout_v2', () => {
  const schema = JSON.parse(readFileSync(join(
    racineDepot(), 'backend', 'django_core', 'apps', 'calepinage', 'contract_samples', 'roof_layout_v2.schema.json',
  ), 'utf8')) as Record<string, unknown>;
  const valider = new Ajv2020({ strict: false, allErrors: true }).compile(schema);
  const avec = (factures: unknown) => {
    const doc = JSON.parse(JSON.stringify(EXEMPLE)) as Record<string, Record<string, unknown>>;
    doc.consumption = { ...doc.consumption, factures_mois: factures };
    return doc;
  };
  const trois = [{ mois: 1, valeur: 520, unite: 'kwh' }, { mois: 2, valeur: 480, unite: 'kwh' }, { mois: 3, valeur: 450, unite: 'kwh' }];

  it('trois factures mensuelles conformes, mois 13 refusé', () => {
    expect(valider(avec(trois))).toBe(true);
    expect(valider(avec([{ mois: 13, valeur: 520, unite: 'kwh' }]))).toBe(false);
    expect(valider(avec([{ mois: 1, valeur: 520, unite: 'w' }]))).toBe(false);
    expect(valider(avec([{ mois: 1, valeur: -1, unite: 'kwh' }]))).toBe(false);
    expect(valider(avec([{ mois: 1, valeur: 300, unite: 'mad' }]))).toBe(true);
  });

  it('un document sans la clé reste conforme', () => {
    expect((EXEMPLE.consumption as Record<string, unknown>).factures_mois).toBeUndefined();
    expect(valider(JSON.parse(JSON.stringify(EXEMPLE)))).toBe(true);
  });
});
// ACAL1970 (revue) — un pan EN PENTE tourné au nord, sans module, avec un besoin : la résolution de fond de la
// réouverture (`close()` → `recalc()` → chemin pente) peut noter (ou retirer) son motif à l'écran, mais « Enregistrer »
// SANS GESTE réécrit le document tel qu'il a été LU : ni motif gagné, ni motif perdu. Un geste sur ce pan l'écrit.
describe('ACAL1970 — motif d’un pan en pente nord vide : aller-retour octet-identique', () => {
  /** L'exemple, avec un pan NON actif passé en pente nord vide à besoin 6 ; enregistré une fois (le document « tel que stocké »). */
  function stocke(motif: boolean) {
    const doc = JSON.parse(JSON.stringify(EXEMPLE)) as { activeAreaId: string; zones: Array<Record<string, unknown>> } & Record<string, unknown>;
    const z = doc.zones.find((p) => p.id !== doc.activeAreaId)!;
    Object.assign(z, { roofType: 'pitched', pitchDeg: 22, facingAzimuthDeg: 0, neededPanels: 6, neededAuto: false });
    delete z.pitchSource;
    z.geometry = { ...(z.geometry as Record<string, unknown>), count: 0, kwc: 0, panels: [] };
    if (motif) doc.motifsPansVides = { [z.id as string]: motifPenteNord(true, 0, 6, 0, 22) };
    reinitialiserNumerotation();
    const premier = ouvrirPuisEnregistrer({ id: null, geometrie: { roof_layout: doc }, cibleVendue: false });
    return { premier, panId: z.id as string };
  }
  const rouvrir = (document: unknown, apres: (c: ReturnType<typeof ouvrirAtelier>['c']) => void) => {
    reinitialiserNumerotation();
    const { c } = ouvrirAtelier({ id: null, geometrie: { roof_layout: JSON.parse(JSON.stringify(document)) }, cibleVendue: false });
    apres(c);
    return enregistrerAtelier(c, null);
  };

  it('sans motif stocké : la résolution de l’ouverture note le motif, le document enregistré sans geste est identique', () => {
    const { premier, panId } = stocke(false);
    expect('motifsPansVides' in premier).toBe(false);
    const sortie = rouvrir(premier, () => noterMotifPanVide(panId, motifPenteNord(true, 0, 6, 0, 22)));
    expect(differences(premier, sortie)).toEqual([]);
  });

  it('motif stocké : la résolution de l’ouverture le retire de la mémoire, il reste au document, identique', () => {
    const { premier, panId } = stocke(true);
    expect((premier as Record<string, unknown>).motifsPansVides).toEqual({ [panId]: motifPenteNord(true, 0, 6, 0, 22) });
    const sortie = rouvrir(premier, () => noterMotifPanVide(panId, null));
    expect(differences(premier, sortie)).toEqual([]);
  });

  it('un GESTE sur ce pan (besoin changé) : le motif de la session est écrit', () => {
    const { premier, panId } = stocke(false);
    const sortie = rouvrir(premier, (c) => {
      const pan = c.areas.find((a) => a.id === panId)!;
      pan.neededPanels = 7;
      noterMotifPanVide(panId, motifPenteNord(true, 0, 7, 0, 22));
    }) as unknown as Record<string, unknown>;
    expect(sortie.motifsPansVides).toEqual({ [panId]: motifPenteNord(true, 0, 7, 0, 22) });
  });
});
