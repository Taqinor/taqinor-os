// ACAL480 — parité atelier (navigateur) ↔ serveur sur les trois projets de
// référence d'ACAL382. Lecture seule hors apps/web (même précédent que
// contractSamplesParite.test.ts). D-ACAL-6 : l'écart est INTERNE, le chiffre
// client est celui du devis ; aucun moteur n'est aligné ici.
//
// MESURE du 2026-11-20 (première exécution sur le golden en année pleine,
// jamais choisie), Casablanca (lat 33.5731), productionKwh(lat, famille,
// inclinaison, 1, aspect) en kWh/kWc/an contre `specific_yield_kwh_kwc` du
// golden (série PVGIS-SARAH3 2020 pleine, 8 784 h, pertes de TEST 9,6 %) :
//   residentiel_pan_sud_15          atelier 1484.67 vs serveur 1985.0 → 25.21 %
//   ci_toit_plat_est_ouest_chassis  atelier 1275.53 vs serveur 1794.2 → 28.91 %
//   champ_sol_sud                   atelier 1510.71 vs serveur 2021.4 → 25.26 %
// Ce sont deux moteurs de modèles différents (table de productible vs rejeu
// PVGIS) : l'écart est interne, le chiffre client est celui du devis. Le
// plafond garde la DÉRIVE, il n'aligne rien.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { productionKwh, type ConfigFamily } from '../src/lib/estimatorBrainV2';

const GOLDEN = JSON.parse(readFileSync(new URL(
  '../../../backend/django_core/apps/calepinage/tests/golden_simulation/trois_projets_reference.json',
  import.meta.url), 'utf8'));

const LATITUDE = 33.5731;
// [famille, inclinaison, aspect PVGIS] — mêmes entrées que PROJETS du test backend.
const PROJETS: Record<string, [ConfigFamily, number, number]> = {
  residentiel_pan_sud_15: ['south', 15, 0],
  ci_toit_plat_est_ouest_chassis: ['eastwest', 10, 0],
  champ_sol_sud: ['south', 20, 0],
};
// Mesuré le 2026-11-20 (année pleine), arrondi au point supérieur. Ne baisse que, à la main.
const ECART_MESURE_PCT: Record<string, number> = {
  residentiel_pan_sud_15: 26,
  ci_toit_plat_est_ouest_chassis: 29,
  champ_sol_sud: 26,
};

describe('parité atelier ↔ serveur (ACAL480)', () => {
  for (const [nom, [famille, tilt, aspect]] of Object.entries(PROJETS)) {
    it(`écart atelier ↔ serveur sous le plafond — ${nom}`, () => {
      const serveur: number = GOLDEN.attendu[nom].total.specific_yield_kwh_kwc;
      const atelier = productionKwh(LATITUDE, famille, tilt, 1, aspect);
      const ecart = (Math.abs(atelier - serveur) / serveur) * 100;
      expect(ecart, `${nom} : atelier ${atelier.toFixed(1)} vs serveur ${serveur}`)
        .toBeLessThanOrEqual(ECART_MESURE_PCT[nom]);
    });
  }
});
