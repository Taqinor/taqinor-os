// NTMOB2 — logique PURE de l'écran de résolution de conflit de synchro.
//
// Le serveur (apps/offlinesync) refuse d'appliquer une opération hors-ligne
// quand l'enregistrement cible a bougé entre la mise en file et le rejeu :
// l'op passe en `conflit` et attend un arbitrage HUMAIN. Ce module ne fait que
// METTRE EN FORME ce que le serveur a déjà décidé — il ne devine aucune
// version, ne compare rien lui-même et n'invente jamais un champ absent.

// Les trois seules décisions possibles, dans l'ordre où l'écran les propose.
// `mienne` en premier (c'est le travail du terrain, celui qu'on risque de
// perdre) ; jamais de choix par défaut : l'arbitrage est explicite.
export const CHOIX = [
  {
    cle: 'mienne',
    libelle: 'Garder ma version',
    aide: 'Votre saisie hors-ligne est appliquée et remplace celle du serveur.',
  },
  {
    cle: 'serveur',
    libelle: 'Garder la version du serveur',
    aide: "Votre opération est abandonnée ; elle reste au journal avec son motif.",
  },
  {
    cle: 'fusion',
    libelle: 'Fusionner manuellement',
    aide: 'Vous recomposez le contenu à appliquer, champ par champ.',
  },
]

export const CLES_CHOIX = CHOIX.map((c) => c.cle)

export function choixValide(choix) {
  return CLES_CHOIX.includes(choix)
}

/** Une fusion n'est envoyable qu'avec un corps recomposé NON VIDE : sans lui,
 *  « fusionner » écraserait en aveugle — le serveur la refuse aussi. */
export function peutEnvoyer(choix, payload) {
  if (!choixValide(choix)) return false
  if (choix !== 'fusion') return true
  return !!payload && typeof payload === 'object' && Object.keys(payload).length > 0
}

/** Corps JSON saisi à la main → objet, ou null si illisible/non-objet.
 *  Jamais d'objet partiellement deviné : illisible ⇒ rien. */
export function lirePayload(texte) {
  try {
    const parsed = JSON.parse(texte)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
    return parsed
  } catch {
    return null
  }
}

/** Les deux versions à montrer côte à côte, telles que le serveur les a
 *  enregistrées. Champ absent ⇒ null, jamais un tiret ni une valeur inventée. */
export function versions(operation) {
  const conflit = (operation && operation.conflit) || {}
  return {
    champ: conflit.champ || null,
    mienne: conflit.base ?? null,
    serveur: conflit.serveur ?? null,
  }
}

/** Une ligne de liste : de quoi reconnaître l'opération sans ouvrir le détail. */
export function resumer(operation) {
  if (!operation) return null
  const { champ, mienne, serveur } = versions(operation)
  return {
    id: operation.id,
    opType: operation.op_type || '',
    module: operation.module_libelle || operation.module || '',
    clientOpId: operation.client_op_id || '',
    champ,
    mienne,
    serveur,
    message: operation.erreur || '',
  }
}
