/**
 * ENF19 — tableau « facture → puissance / investissement » de /résidentiel,
 * commun aux trois langues (fr/en/ar) : mêmes fourchettes de prix au kWc, même arrondi,
 * seuls les exemples réels (texte) changent d'une langue à l'autre.
 *
 * WAUD68 — le prix au kWc vient de la constante UNIQUE lib/prixConstants.ts (source + date,
 * D-WAUD-5). Tant qu'elle est vide, `invest` vaut null et la colonne « investissement » est omise.
 */
import { BILL_RANGES, libelleBandeLocale, localEstimateBand } from './billRange';
import { formatMAD } from './format';
import { PRIX_KWC_TTC } from './prixConstants';

export const arrondi5k = (v: number) => Math.round(v / 5000) * 5000;

export function buildBrackets(exemples: Record<string, string>, locale: 'fr' | 'en' | 'ar' = 'fr') {
  const prix = PRIX_KWC_TTC.valeur;
  return BILL_RANGES.filter((r) => r.qualifies && r.id !== 'gt10000').map((r) => {
    const band = localEstimateBand(r.id);
    const investLow = prix ? arrondi5k(band.kwcMin * prix.bas) : null;
    const investHigh = prix ? arrondi5k(band.kwcMax * prix.haut) : null;
    return {
      bill: r.label,
      kwc: libelleBandeLocale(band.kwcLabel, locale),
      payback: libelleBandeLocale(band.paybackLabel, locale),
      investLow,
      investHigh,
      invest: investLow !== null && investHigh !== null ? `${formatMAD(investLow)} – ${formatMAD(investHigh)}` : null,
      exemple: exemples[r.id] ?? null,
    };
  });
}

/** Bornes de l'investissement sur toutes les tranches (null tant que le prix n'est pas sourcé). */
export function bornesInvestissement(brackets: ReturnType<typeof buildBrackets>) {
  const bas = brackets.map((b) => b.investLow).filter((v): v is number => v !== null);
  const haut = brackets.map((b) => b.investHigh).filter((v): v is number => v !== null);
  return bas.length && haut.length ? { bas: formatMAD(Math.min(...bas)), haut: formatMAD(Math.max(...haut)) } : null;
}
