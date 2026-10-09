/**
 * Numéro WhatsApp de la société (YBW55) — fourni par Reda (YBWM4), JAMAIS repris
 * d'un autre site. Tant qu'il est `null`, le bouton WhatsApp n'est pas rendu.
 * Format attendu : indicatif pays + numéro, chiffres seulement (ex. de forme :
 * « 336… » ou « 2126… »).
 *
 * Le lien est une simple navigation au clic (`wa.me`) : aucune requête, aucune
 * donnée transmise avant le clic (registre des sous-traitants, YBW26).
 */
export const WHATSAPP: string | null = null;

/** Lien `wa.me` pour `numero` (chiffres seuls), ou `null` si le numéro est absent ou invalide. */
export function lienWhatsApp(numero: string | null = WHATSAPP): string | null {
  if (!numero) return null;
  const chiffres = numero.replace(/[\s.+-]/g, '');
  if (!/^\d{8,15}$/.test(chiffres)) return null;
  return `https://wa.me/${chiffres}`;
}
