/**
 * ACAL891 — la LIMITE de modules au-delà de laquelle l'atelier n'est plus fluide, et le refus
 * nommé d'un remplissage qui la dépasserait.
 *
 * La limite est une MESURE (ACAL890 : `frontend/e2e/calepinage-perf.limite.json`, écrit par
 * `CAL_PERF_ECRIRE=1`, jamais tapé à la main), lue ICI à la construction. Fichier absent ou
 * `limite_modules` nul ⇒ AUCUNE limite, donc aucun refus : on n'invente pas de plafond.
 */
const MESURE = import.meta.glob('../../../../../frontend/e2e/calepinage-perf.limite.json', {
  eager: true, import: 'default',
}) as Record<string, { limite_modules?: number | null }>;

/** La limite mesurée de modules, ou `null` quand elle n'a pas été relevée. */
export function limiteModules(): number | null {
  const limite = Object.values(MESURE)[0]?.limite_modules;
  return typeof limite === 'number' && Number.isFinite(limite) && limite > 0 ? limite : null;
}

/** Le refus à afficher si `total` modules dépasseraient `limite` ; `null` = rien à refuser. */
export function refusLimiteModules(total: number, limite: number | null): string | null {
  if (limite === null || !(total > limite)) return null;
  return `Au-delà de ${limite.toLocaleString('fr-FR')} modules, l’atelier n’est plus fluide : réduisez le toit ou posez par parties.`;
}

/** La note « Toit rempli automatiquement » : surplus dit quand le remplissage dépasse le besoin. */
export function noteToitRempli(count: number, besoin: number, fmt: (n: number) => string): string {
  return besoin > 0 && count > besoin
    ? `Toit rempli automatiquement — ${fmt(count)} panneaux (le maximum qui tient). C’est plus que votre besoin (${fmt(besoin)}) : le surplus produit n’est pas rémunéré. Retirez-en avec « − » pour coller au besoin.`
    : `Toit rempli automatiquement — ${fmt(count)} panneaux (le maximum qui tient sur ce toit).`;
}
