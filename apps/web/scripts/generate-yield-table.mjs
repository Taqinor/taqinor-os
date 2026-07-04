/**
 * Génère src/lib/yieldTable.ts : table de productible (kWh/kWc/an, pertes 14 %)
 * lue depuis PVGIS pour les 5 latitudes de la zone de service, en grille
 * (inclinaison × azimut). DONNÉE committée, pas une dépendance : l'estimateur
 * reste instantané et résilient quand PVGIS est lent/injoignable.
 *
 * Lancer manuellement quand on veut rafraîchir la table :
 *   node scripts/generate-yield-table.mjs
 * (non exécuté au build — le résultat est committé tel quel.)
 *
 * WJ74 — STAMP & PIN : la fenêtre TMY PVGIS (startyear/endyear) est PINNÉE
 * explicitement ci-dessous (jamais laissée au défaut implicite du serveur, qui
 * peut changer de fenêtre glissante entre deux appels sans prévenir) et la
 * table générée porte un horodatage GENERATED_AT + la fenêtre utilisée, pour
 * que toute dérive future soit visible et que la donnée committée reste
 * reproductible. Rafraîchir une fois par an (voir DONE LOG).
 */
import { writeFile } from 'node:fs/promises';

const ENDPOINT = 'https://re.jrc.ec.europa.eu/api/v5_2/PVcalc';
const LOSS = 14;
// Fenêtre TMY PINNÉE (base PVGIS-SARAH2/SARAH3, dispo 2005–2023 en v5.2 au
// moment de l'écriture) : bornes EXPLICITES envoyées à chaque appel, jamais le
// défaut implicite du serveur — reproductible d'une génération à l'autre.
const PVGIS_TMY_STARTYEAR = 2005;
const PVGIS_TMY_ENDYEAR = 2020;

// Latitude de référence + coordonnées représentatives par ville de service.
const CITIES = [
  { key: 'agadir', lat: 30.42, lon: -9.6 },
  { key: 'marrakech', lat: 31.63, lon: -8.0 },
  { key: 'casablanca', lat: 33.59, lon: -7.62 },
  { key: 'rabat', lat: 34.02, lon: -6.83 },
  { key: 'tanger', lat: 35.77, lon: -5.8 },
];

const TILTS = [0, 5, 10, 15, 20, 25, 29, 30, 35];
// Azimut PVGIS : 0=Sud, -90=Est, 90=Ouest, ±45=SE/SO.
const ASPECTS = [0, -45, 45, -90, 90];

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function fetchYield(lat, lon, angle, aspect) {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    peakpower: '1',
    loss: String(LOSS),
    angle: String(angle),
    aspect: String(aspect),
    pvtechchoice: 'crystSi',
    mountingplace: 'building',
    outputformat: 'json',
    // WJ74 — fenêtre TMY pinnée explicitement (voir constantes ci-dessus) :
    // reproductible, ne dérive pas avec la fenêtre glissante par défaut du serveur.
    startyear: String(PVGIS_TMY_STARTYEAR),
    endyear: String(PVGIS_TMY_ENDYEAR),
  });
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const res = await fetch(`${ENDPOINT}?${params}`, { headers: { accept: 'application/json' } });
      if (!res.ok) throw new Error('status ' + res.status);
      const data = await res.json();
      const eY = data?.outputs?.totals?.fixed?.E_y;
      if (typeof eY === 'number' && eY > 0) return Math.round(eY);
      throw new Error('no E_y');
    } catch (e) {
      if (attempt === 3) throw e;
      await sleep(800 * (attempt + 1));
    }
  }
}

const table = {};
for (const city of CITIES) {
  table[city.key] = { lat: city.lat, grid: {} };
  for (const aspect of ASPECTS) {
    table[city.key].grid[aspect] = {};
    for (const tilt of TILTS) {
      const v = await fetchYield(city.lat, city.lon, tilt, aspect);
      table[city.key].grid[aspect][tilt] = v;
      process.stderr.write(`${city.key} a${aspect} t${tilt} = ${v}\n`);
      await sleep(150);
    }
  }
}

const generatedAt = new Date().toISOString();

const header = `/**
 * Productible solaire (kWh/kWc/an, pertes système 14 %) lu depuis PVGIS pour les
 * 5 latitudes de la zone de service Taqinor, en grille inclinaison × azimut.
 *
 * GÉNÉRÉ par scripts/generate-yield-table.mjs — DONNÉE committée, jamais une
 * dépendance. Sert de repli instantané/résilient à l'estimateur quand l'appel
 * PVGIS live est lent ou injoignable. Azimut : 0=Sud, -90=Est, 90=Ouest,
 * ±45=SE/SO. Pour une latitude intermédiaire, l'estimateur interpole entre
 * les deux villes encadrantes (voir specificYieldFromTable dans estimatorBrain).
 *
 * WJ74 — STAMP & PIN : GENERATED_AT (horodatage de cette génération) et la
 * fenêtre TMY PVGIS PINNÉE (PVGIS_TMY_STARTYEAR/ENDYEAR, mêmes valeurs que
 * scripts/generate-yield-table.mjs) sont exportées ci-dessous comme marqueur
 * de fraîcheur/reproductibilité. Rafraîchir une fois par an ; noter la date
 * dans le DONE LOG du plan à chaque régénération.
 */
export const GENERATED_AT = '${generatedAt}';
export const PVGIS_TMY_STARTYEAR = ${PVGIS_TMY_STARTYEAR};
export const PVGIS_TMY_ENDYEAR = ${PVGIS_TMY_ENDYEAR};

export interface CityYield {
  lat: number;
  /** grid[aspect][tilt] = kWh/kWc/an. */
  grid: Record<string, Record<string, number>>;
}

export const YIELD_TABLE: Record<string, CityYield> = `;

await writeFile(
  new URL('../src/lib/yieldTable.ts', import.meta.url),
  header + JSON.stringify(table, null, 2) + ';\n',
);
process.stderr.write('\nyieldTable.ts écrit.\n');
