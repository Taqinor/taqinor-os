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
import { enregistrerAtelier, exempleRoofLayoutV2, ouvrirAtelier } from './harnaisDocument';


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
});
