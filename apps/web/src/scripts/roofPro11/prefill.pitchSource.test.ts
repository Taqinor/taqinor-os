/* ============================================================================
   ACAL252 (C-ACAL-022, D08-T04) — LA PROVENANCE DE LA PENTE DU PAN VOYAGE.
   ----------------------------------------------------------------------------
   L'onglet Pente écrit `zones[i].pitchDeg` ET `zones[i].pitchSource` (mode + ses champs :
   degres | pourcentage | cotes). `deserializeLayout` la relit sur le pan, `serializeLayout` la
   réémet : ouvrir → « Enregistrer le calepinage » sans toucher laisse la provenance
   octet-identique. Une pente retouchée à la main dans l'atelier n'est plus celle que la source
   décrit : la source est alors omise, jamais mentie. Le document vient de l'`exemple` du
   contrat `roof_layout_v2.schema.json` (lu dans le dépôt).
   ========================================================================== */
import { beforeEach, describe, expect, it } from 'vitest';
import { deserializeLayout, type SerializedLayout } from './prefill';
import { reinitialiserNumerotation } from './numerotation';
import { type Ctx } from './context';
import { enregistrerAtelier, exempleRoofLayoutV2, ouvrirAtelier } from './harnaisDocument';

const EXEMPLE = exempleRoofLayoutV2();
const POURCENTAGE = { mode: 'pourcentage', pourcentage: 57.735 };
const COTES = { mode: 'cotes', porteeM: 10, hauteurFaitageM: 5.7735 };
const DEG30 = (Math.atan(0.57735) * 180) / Math.PI;

/** Le document de contrat, avec deux pans qui portent chacun SA pente et SA provenance. */
function documentADeuxPans(): Record<string, unknown> {
  const doc = JSON.parse(JSON.stringify(EXEMPLE)) as { zones: Array<Record<string, unknown>> };
  doc.zones[0].pitchDeg = DEG30;
  doc.zones[0].pitchSource = POURCENTAGE;
  doc.zones[1].pitchDeg = (Math.atan(5.7735 / 10) * 180) / Math.PI;
  doc.zones[1].pitchSource = COTES;
  return doc as unknown as Record<string, unknown>;
}

function ouvrir(document: Record<string, unknown>): Ctx {
  return ouvrirAtelier({
    id: null, geometrie: { roof_layout: JSON.parse(JSON.stringify(document)) }, cibleVendue: false,
  }).c;
}

function enregistrer(c: Ctx): { zones: Array<Record<string, unknown>> } & Record<string, unknown> {
  return enregistrerAtelier(c) as unknown as { zones: Array<Record<string, unknown>> } & Record<string, unknown>;
}

beforeEach(() => reinitialiserNumerotation());

describe('ACAL252 — pitchSource, aller-retour', () => {
  it('aller-retour serialize → deserialize conserve pitchSource', () => {
    const document = documentADeuxPans();
    const pans = deserializeLayout(document as unknown as SerializedLayout);
    expect(pans[0].pitchSource).toEqual(POURCENTAGE);
    expect(pans[1].pitchSource).toEqual(COTES);

    const premiere = enregistrer(ouvrir(document));
    const parId = (doc: { zones: Array<Record<string, unknown>> }, id: string) => doc.zones.find((z) => z.id === id)!;
    const zones = (document as unknown as { zones: Array<Record<string, unknown>> }).zones;
    expect(parId(premiere, zones[0].id as string).pitchSource).toEqual(POURCENTAGE);
    expect(parId(premiere, zones[1].id as string).pitchSource).toEqual(COTES);
    expect(parId(premiere, zones[0].id as string).pitchDeg).toBeCloseTo(30, 3);

    // Rouvrir le document enregistré, enregistrer sans geste : octet-identique.
    const seconde = enregistrer(ouvrir(premiere));
    expect(JSON.stringify(seconde.zones.map((z) => [z.id, z.pitchDeg, z.pitchSource])))
      .toBe(JSON.stringify(premiere.zones.map((z) => [z.id, z.pitchDeg, z.pitchSource])));
  });

  it('un pan sans provenance n’en reçoit aucune (rien d’inventé)', () => {
    const doc = documentADeuxPans() as unknown as { zones: Array<Record<string, unknown>> };
    delete doc.zones[0].pitchSource;
    delete doc.zones[1].pitchSource;
    const sortie = enregistrer(ouvrir(doc as unknown as Record<string, unknown>));
    for (const zone of sortie.zones) expect('pitchSource' in zone).toBe(false);
  });

  it('une pente retouchée à la main dans l’atelier n’emporte pas une provenance périmée', () => {
    const c = ouvrir(documentADeuxPans());
    const actif = c.areas.find((a) => a.id === c.activeAreaId)!;
    expect(actif.pitchSource).toBeTruthy();
    c.pitchDeg = c.pitchDeg + 7; // le curseur de pente de l'atelier
    const sortie = enregistrer(c);
    const zone = sortie.zones.find((z) => z.id === c.activeAreaId)!;
    expect('pitchSource' in zone).toBe(false);
    // L'autre pan, intact, garde la sienne.
    const autre = sortie.zones.find((z) => z.id !== c.activeAreaId)!;
    expect(autre.pitchSource).toBeTruthy();
  });
});
