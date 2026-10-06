/* ============================================================================
   ACAL193 (C-ACAL-003, D-ACAL-13) — PROVENANCE DE L'ÉPINGLE.
   ----------------------------------------------------------------------------
   `pinSource` ('lead' | 'manuel') et `repereAcquitte` (posé par « Garder ce repère »)
   survivent à l'aller-retour ouvrir → enregistrer sans geste, octet-identiques ; un
   déplacement de l'épingle À LA MAIN pose `pinSource: 'manuel'` et cette épingle. Le
   document vient de l'`exemple` du contrat `roof_layout_v2.schema.json` (lu dans le dépôt).
   ========================================================================== */
import { beforeEach, describe, expect, it } from 'vitest';
import { deplacerEpingleALaMain, hydrateFromDevis, oublierEpingleDeplacee } from './prefill';
import { reinitialiserNumerotation } from './numerotation';
import { type Ctx } from './context';
import { enregistrerAtelier, exempleRoofLayoutV2, ouvrirAtelier } from './harnaisDocument';

const EXEMPLE = exempleRoofLayoutV2();

/** Boot (payload de la page) → hydratation : la scène prête, rien n'est encore enregistré. */
function ouvrir(document: Record<string, unknown>): Ctx {
  return ouvrirAtelier({
    id: null, geometrie: { roof_layout: JSON.parse(JSON.stringify(document)) }, cibleVendue: false,
  }).c;
}

/** « Enregistrer » : le sérialiseur câblé du wrapper (harnais ACAL345). */
function enregistrer(c: Ctx): Record<string, unknown> {
  return enregistrerAtelier(c) as unknown as Record<string, unknown>;
}

beforeEach(() => reinitialiserNumerotation());

describe('ACAL193 — pinSource et repereAcquitte', () => {
  it('serializeLayout(deserializeLayout(doc)) conserve pinSource et repereAcquitte', () => {
    expect(EXEMPLE.pinSource).toBe('lead');
    expect(EXEMPLE.repereAcquitte).toBeTruthy();
    const premiere = enregistrer(ouvrir(EXEMPLE));
    expect(premiere.pinSource).toBe(EXEMPLE.pinSource);
    expect(premiere.repereAcquitte).toEqual(EXEMPLE.repereAcquitte);
    expect(premiere.pin).toEqual(EXEMPLE.pin);
    // Rouvrir le document enregistré, enregistrer sans geste : inchangé.
    const seconde = enregistrer(ouvrir(premiere));
    expect(seconde.pinSource).toBe(EXEMPLE.pinSource);
    expect(seconde.repereAcquitte).toEqual(EXEMPLE.repereAcquitte);
    expect(JSON.stringify(seconde)).toBe(JSON.stringify(premiere));
  });

  it('un document sans provenance n’en reçoit aucune (rien d’inventé)', () => {
    const sansProvenance = JSON.parse(JSON.stringify(EXEMPLE)) as Record<string, unknown>;
    delete sansProvenance.pinSource;
    delete sansProvenance.repereAcquitte;
    const sortie = enregistrer(ouvrir(sansProvenance));
    expect('pinSource' in sortie).toBe(false);
    expect('repereAcquitte' in sortie).toBe(false);
  });

  it('déplacer l’épingle pose pinSource manuel', () => {
    const c = ouvrir(EXEMPLE);
    deplacerEpingleALaMain(c, [-7.61, 33.58]);
    const sortie = enregistrer(c);
    expect(sortie.pinSource).toBe('manuel');
    expect(sortie.pin).toEqual({ lat: 33.58, lng: -7.61 });
    // L'acquittement du repère n'est pas touché par le geste.
    expect(sortie.repereAcquitte).toEqual(EXEMPLE.repereAcquitte);
    // Rouvrir le document : la provenance manuelle tient sans nouveau geste.
    const relu = enregistrer(ouvrir(sortie));
    expect(relu.pinSource).toBe('manuel');
    expect(relu.pin).toEqual({ lat: 33.58, lng: -7.61 });
  });

  it('un pin posé depuis le lead reste « lead » sans geste ; « Effacer » oublie le déplacement', () => {
    const c = ouvrir(EXEMPLE);
    expect(enregistrer(c).pinSource).toBe('lead');
    deplacerEpingleALaMain(c, [-7.61, 33.58]);
    oublierEpingleDeplacee(c);
    expect(enregistrer(c).pinSource).toBe('lead');
  });

  it('une coordonnée non finie est ignorée', () => {
    const c = ouvrir(EXEMPLE);
    deplacerEpingleALaMain(c, [Number.NaN, 33.58]);
    const sortie = enregistrer(c);
    expect(sortie.pinSource).toBe('lead');
    expect(sortie.pin).toEqual(EXEMPLE.pin);
  });
});
