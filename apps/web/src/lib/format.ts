/**
 * Format monétaire marocain : `12 500 MAD` — séparateur de milliers espace,
 * devise après le nombre. Règle non négociable pour toute chaîne client.
 */
export function formatMAD(amount: number): string {
  const rounded = Math.round(amount);
  const sign = rounded < 0 ? '-' : '';
  const digits = Math.abs(rounded).toString();
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return `${sign}${grouped} MAD`;
}

/** Date longue française (`21 juin 2026`) — partagée par les pages blog/guides. */
export const DATE_LONGUE_FR = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
