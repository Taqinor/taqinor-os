/**
 * ENF19 — tableau « facture → puissance / retour / investissement » de /résidentiel,
 * commun aux trois langues (fr/en/ar) : mêmes fourchettes de prix au kWc, même arrondi,
 * seuls les exemples réels (texte) changent d'une langue à l'autre.
 */
import { BILL_RANGES, localEstimateBand } from './billRange';
import { formatMAD } from './format';

export const PRIX_PAR_KWC = { bas: 10000, haut: 12500 };
export const arrondi5k = (v: number) => Math.round(v / 5000) * 5000;

export function buildBrackets(exemples: Record<string, string>) {
  return BILL_RANGES.filter((r) => r.qualifies && r.id !== 'gt10000').map((r) => {
    const band = localEstimateBand(r.id);
    return {
      bill: r.label,
      kwc: band.kwcLabel,
      payback: band.paybackLabel,
      investLow: arrondi5k(band.kwcMin * PRIX_PAR_KWC.bas),
      investHigh: arrondi5k(band.kwcMax * PRIX_PAR_KWC.haut),
      invest: `${formatMAD(arrondi5k(band.kwcMin * PRIX_PAR_KWC.bas))} – ${formatMAD(arrondi5k(band.kwcMax * PRIX_PAR_KWC.haut))}`,
      exemple: exemples[r.id] ?? null,
    };
  });
}
