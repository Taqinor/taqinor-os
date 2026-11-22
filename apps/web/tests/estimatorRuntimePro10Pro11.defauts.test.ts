// ACAL983 (garde K-DEFAUT-CHOIX) — côté estimateur, les lignes `porte: "estimateur"` de la liste COMMITTÉE
// `backend/django_core/apps/calepinage/tests/fixtures/defauts_annonces.json` (affirmée aussi par le backend,
// test_acal_generer_devis_portes.py) : une valeur que personne n'a saisie ne fixe jamais seule la recommandation.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { solveLive } from '../src/lib/estimatorBrainV7';
import { EW_TILTS } from '../src/lib/estimatorBrainV6';
import { type LngLat } from '../src/lib/roof';

const ICI = dirname(fileURLToPath(import.meta.url));
const LISTE = JSON.parse(readFileSync(
  join(ICI, '../../../backend/django_core/apps/calepinage/tests/fixtures/defauts_annonces.json'), 'utf8'));
const LIGNES = LISTE.defauts.filter((d: { porte: string }) => d.porte === 'estimateur');

// Toit plat ≈ 163 m² à Marrakech (même cas que estimatorBrainV7.test.ts, ACAL928 : T1-F1-023).
const LAT = 31.63;
const COTE = 12.8;
const dLat = COTE / 111320;
const dLng = COTE / (111320 * Math.cos((LAT * Math.PI) / 180));
const TOIT: LngLat[] = [[-8 - dLng / 2, LAT - dLat / 2], [-8 + dLng / 2, LAT - dLat / 2],
  [-8 + dLng / 2, LAT + dLat / 2], [-8 - dLng / 2, LAT + dLat / 2]];
const FACTURE = 1500;

const REJOUEURS: Record<string, () => void> = {
  inclinaison_est_ouest: () => {
    const permises = EW_TILTS as readonly number[];
    const libre = solveLive(TOIT, LAT, FACTURE, [], {});
    for (const c of [libre.winner, libre.globalWinner, libre.recommended]) {
      if (c.orientation === 'eastwest') expect(permises, `inclinaison est-ouest ${c.tiltDeg}° non saisie`).toContain(c.tiltDeg);
    }
    const tenu = solveLive(TOIT, LAT, FACTURE, [], { orientation: 'eastwest' }).winner;
    expect(permises, `inclinaison est-ouest ${tenu.tiltDeg}° non saisie`).toContain(tenu.tiltDeg);
  },
};

describe('ACAL983 — défauts non saisis : l’estimateur ne les applique jamais seuls', () => {
  it('chaque ligne « estimateur » de la liste committée a son rejeu', () => {
    expect(LIGNES.length).toBeGreaterThan(0);
    expect(LIGNES.map((d: { cle: string }) => d.cle).sort()).toEqual(Object.keys(REJOUEURS).sort());
  });

  for (const ligne of LIGNES as { cle: string; valeur_origine: string }[]) {
    it(`${ligne.cle} : « ${ligne.valeur_origine} » n’est pas recommandée sans saisie`, () => {
      REJOUEURS[ligne.cle]?.();
    });
  }
});
