// Historique du lead — canal INTERNE « une notification vient d'arriver » : la cloche (NotificationBell) l'émet quand son
// sondage voit le compteur monter ; une fiche ouverte (LeadWorkspace) l'écoute pour relire SON historique tout de suite.
// Aucun réseau ici : la cloche reste la seule à interroger les notifications.
const NOM = 'taqinor:notifications-recues'

/** `liens` : les `link` des notifications NON LUES de la liste (chaînes). */
export function signalerNotificationsRecues(liens) {
  try {
    window.dispatchEvent(new CustomEvent(NOM, { detail: { liens: Array.isArray(liens) ? liens : [] } }))
  } catch { /* sans fenêtre : rien à dire */ }
}

/** Retourne la fonction qui retire l'écoute. */
export function ecouterNotificationsRecues(rappel) {
  const lire = (e) => rappel(e?.detail?.liens ?? [])
  window.addEventListener(NOM, lire)
  return () => window.removeEventListener(NOM, lire)
}

/** Une notification porte-t-elle sur CE lead ? (`/crm/leads?lead=<id>` ou `/crm/leads/<id>`). */
export function lienDuLead(lien, leadId) {
  if (!lien || leadId == null) return false
  const id = String(leadId)
  return new RegExp(`[?&]lead=${id}(?:&|$)`).test(lien) || new RegExp(`/crm/leads/${id}(?:[/?#]|$)`).test(lien)
}
