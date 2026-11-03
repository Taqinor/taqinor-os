/**
 * ENF19 — chiffres dérivés communs aux pages /impact-taqinor et
 * /production-mesuree (FR / EN / AR). Tout est calculé à partir de
 * realisations.ts / proposition.ts (lecture seule) — aucun chiffre saisi à la
 * main ; seul le format numérique (`numberLocale`) change d'une langue à l'autre.
 */
import { FACTS_GENERATED_AT } from './facts';
import { CO2_KG_PER_KWH } from './proposition';
import { MEASURED_FLEET, MEASURED_FLEET_LIFETIME_MWH, REALISATIONS, MEASURED_FLEET_READ_AT } from './realisations';

/** WAUD16 — capacité d'une ligne batterie : « 2 × DYNESS 5 kWh » vaut 10, « 10 kWh Dyness (2 × DL5.0C) » vaut 10. */
export function batterieKwh(batterie: string | null): number {
  const m = /^(?:(\d+)\s*×[^\d]*)?([\d.,]+)\s*kWh/.exec((batterie ?? '').trim());
  return m ? Number(m[1] ?? 1) * parseFloat(m[2].replace(',', '.')) : 0;
}

export function impactFigures(numberLocale: string) {
  const productionTotal = Math.round(MEASURED_FLEET_LIFETIME_MWH * 1000);
  const productionTotalLabel = productionTotal.toLocaleString(numberLocale);

  const co2KgTotal = productionTotal * CO2_KG_PER_KWH;
  const co2TonnesTotal = Math.round((co2KgTotal / 1000) * 10) / 10;
  const co2TonnesLabel = co2TonnesTotal.toLocaleString(numberLocale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  const battersInstalls = REALISATIONS.filter((r) => r.batterie !== null);
  const batteryKwhTotal = battersInstalls.reduce((sum, r) => sum + batterieKwh(r.batterie), 0);

  const generatedDateLabel = new Intl.DateTimeFormat(numberLocale, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(MEASURED_FLEET_READ_AT ?? FACTS_GENERATED_AT));

  const villesUniques = [...new Set(REALISATIONS.map((r) => r.ville))];
  const villesMesurees = [...new Set(MEASURED_FLEET.flatMap((p) => (p.ville ? [p.ville] : [])))];

  return {
    productionTotal,
    productionTotalLabel,
    co2KgTotal,
    co2TonnesTotal,
    co2TonnesLabel,
    battersInstalls,
    batteryKwhTotal,
    villesUniques,
    villesMesurees,
    generatedDateLabel,
  };
}
