/* NTMKT30 — logique pure du wizard « Configurer une séquence de relance ».
 *
 * Un pas vierge ou parti d'un modèle seedé (XMKT20/NTMKT15) : on empile des
 * étapes (délai + canal + contenu) puis on prévisualise le calendrier
 * d'envoi type avant activation. Contrôle bloquant si une étape référence le
 * canal WhatsApp alors que le BSP n'est pas confirmé configuré (XMKT10
 * gated) — message clair plutôt qu'une erreur d'envoi silencieuse plus tard.
 */

export function emptyWizardState() {
  return { nom: '', etapes: [], whatsappConfigure: false }
}

export function nouvelleEtape() {
  return { delai_jours: 0, canal: 'email', modele_message: '' }
}

export function ajouterEtape(state) {
  return { ...state, etapes: [...state.etapes, nouvelleEtape()] }
}

export function retirerEtape(state, index) {
  return { ...state, etapes: state.etapes.filter((_, i) => i !== index) }
}

export function majEtape(state, index, patch) {
  return {
    ...state,
    etapes: state.etapes.map((e, i) => (i === index ? { ...e, ...patch } : e)),
  }
}

/** Calendrier type J+0, J+3, J+7… trié par délai. */
export function calendrierPrevu(etapes) {
  return [...etapes]
    .sort((a, b) => a.delai_jours - b.delai_jours)
    .map(e => ({ jour: `J+${e.delai_jours}`, canal: e.canal }))
}

/** Une étape WhatsApp sans confirmation de configuration bloque l'activation. */
export function blocageWhatsapp(state) {
  const aUneEtapeWhatsapp = state.etapes.some(e => e.canal === 'whatsapp')
  return aUneEtapeWhatsapp && !state.whatsappConfigure
}

export function peutActiver(state) {
  return state.nom.trim().length > 0
    && state.etapes.length > 0
    && !blocageWhatsapp(state)
}
