/* Aides communes des listes ordonnées de Paramètres (Consignes de sécurité,
   Shot list) : clé technique stable et permutation de deux lignes voisines. */

/** Clé technique (ASCII, sans accents) dérivée d'un libellé, tronquée à 40. */
export const slugifyCle = (s) => s.trim().toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40)

/** Échange l'ordre de la ligne `idx` avec sa voisine (`dir` = -1 / +1). */
export async function permuterOrdre({ slots, idx, dir, sauver, recharger, erreur }) {
  const j = idx + dir
  if (j < 0 || j >= slots.length) return
  const a = slots[idx]; const b = slots[j]
  try {
    await Promise.all([
      sauver(a.id, { ordre: b.ordre }),
      sauver(b.id, { ordre: a.ordre }),
    ])
    recharger()
  } catch (e) { erreur(e) }
}
