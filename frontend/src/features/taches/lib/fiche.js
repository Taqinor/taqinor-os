import { useCallback, useEffect } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'

import { originFrom } from '../../../api/origin'
import { ecrireTexte, lireTexte, viderALaDeconnexion } from './stockage'

/* ============================================================================
   Raccord F2 — les écrans se parlent : une SEULE façon d'ouvrir la fiche d'une tâche (`?tache=<id>`, la coquille
   la monte) et une SEULE façon d'écouter « des tâches viennent d'être créées » (`taqinor:taches:creees`, émis par
   la feuille de saisie). La fiche s'ouvre en AJOUTANT une entrée d'historique marquée : le retour arrière du
   navigateur la ferme sans quitter l'écran, et la coquille la ferme par ce même retour (le focus revient à la
   ligne qui l'a ouverte, FeuilleACrans s'en charge). Ouverte par un lien direct (notification de rappel), sans
   marque, elle se ferme en retirant le paramètre.
   ========================================================================== */

export const EVENEMENT_CREEES = 'taqinor:taches:creees'
/** R2-040 — émis par la fiche après chaque écriture réussie et à sa fermeture : `detail = { tache }` (la tâche
 *  rendue par le serveur, ou `null` quand la fiche n'a rien de plus frais que l'identifiant). */
export const EVENEMENT_ECRITE = 'taqinor:taches:ecrite'
export const MARQUE_FICHE = 'tchFiche'

/** R2-040 — la fiche est montée par la coquille, pas par l'écran : elle prévient l'écran qu'une tâche a changé. */
export function signalerEcrite(tache = null) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(EVENEMENT_ECRITE, { detail: { tache } }))
}

/* R3-061 — l'APERÇU : chaque ligne de tâche (`LigneTache`) dépose ici l'ITEM qu'elle affiche ; la fiche s'ouvre AU MÊME
   INSTANT sur lui (titre, Quand, projet, priorité, ★ et `lock_version` : modifiable tout de suite), la lecture complète
   arrive ensuite et le remplace. Clé = l'identifiant seul (une tâche ; jamais une activité de l'ERP) ; mémoire bornée ;
   vidé à la déconnexion (`taqinor:auth-logout`) : un poste partagé ne montre jamais la tâche d'un autre compte. */
const APERCUS_MAX = 500
const apercus = new Map()

export function retenirApercu(item) {
  if (!item || item.type !== 'tache' || item.id == null) return
  const cle = String(item.id)
  apercus.delete(cle) // la plus récente en dernier : la plus ancienne part la première
  apercus.set(cle, item)
  if (apercus.size > APERCUS_MAX) apercus.delete(apercus.keys().next().value)
}

/** L'item retenu pour la tâche `id`, ou `null`. */
export function apercu(id) {
  return apercus.get(String(id)) ?? null
}

export function oublierApercus() {
  apercus.clear()
}

if (typeof window !== 'undefined') window.addEventListener('taqinor:auth-logout', oublierApercus)

/* R4-23 — ce qu'on tape dans la fiche (titre, notes) ne se perd pas quand la page s'en va (rechargement, retour arrière
   sur une fiche ouverte par son adresse, appli fermée sur l'iPhone) : au `pagehide` / onglet caché, la frappe pas encore
   partie est gardée ICI (brouillon local, par société, compte et tâche ; vidé à la déconnexion) puis envoyée par un
   `fetch` keepalive, que le navigateur termine même après la page. Arrivée, le brouillon s'efface ; sinon la fiche le
   reprend à sa réouverture et le dit. */
export const PREFIXE_BROUILLON_FICHE = 'taches:fiche:'
viderALaDeconnexion(PREFIXE_BROUILLON_FICHE)

export const cleBrouillonFiche = (societe, compte, id) => `${PREFIXE_BROUILLON_FICHE}${societe ?? '0'}:${compte ?? '0'}:${id}`

/** `{ titre?, notes? }` gardés pour cette clé, ou `null` (rien, stockage refusé ou illisible). */
export function lireBrouillonFiche(cle) {
  const brut = lireTexte(cle)
  let lu = null
  try {
    lu = brut ? JSON.parse(brut) : null
  } catch {
    return null // brouillon abîmé : ignoré, la fiche reste celle du serveur
  }
  if (!lu || typeof lu !== 'object') return null
  const champs = Object.fromEntries(['titre', 'notes'].filter((c) => typeof lu[c] === 'string').map((c) => [c, lu[c]]))
  return Object.keys(champs).length > 0 ? champs : null
}

/** Ajoute `champs` (`{ titre?, notes? }`) au brouillon de cette clé. */
export function garderBrouillonFiche(cle, champs) {
  return ecrireTexte(cle, JSON.stringify({ ...(lireBrouillonFiche(cle) ?? {}), ...champs }))
}

/** Retire `champs` (tous si omis) du brouillon de cette clé ; la clé part quand il ne reste rien. */
export function oublierBrouillonFiche(cle, champs = null) {
  const reste = Object.fromEntries(Object.entries(lireBrouillonFiche(cle) ?? {}).filter(([c]) => champs && !champs.includes(c)))
  return ecrireTexte(cle, Object.keys(reste).length > 0 ? JSON.stringify(reste) : '')
}

/** L'adresse d'écriture d'une tâche (`modifierTache`), écrite en entier pour l'envoi qui survit à la page. */
const adresseTache = (id) => `${originFrom(import.meta.env.VITE_API_URL)}/api/django/taches/taches/${id}/`

/** PATCH `corps` (`{ titre?, notes?, lock_version }`) par un `fetch` keepalive (le navigateur le termine même si la page
 *  se ferme) ; rend la `Response` (le serveur a pu refuser : `ok` faux) ou rejette (aucun envoi possible). */
export function envoyerEnPartant(id, corps) {
  if (typeof fetch !== 'function') return Promise.reject(new Error('fetch indisponible'))
  return fetch(adresseTache(id), {
    method: 'PATCH', credentials: 'include', keepalive: true, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corps),
  })
}

/** Ce que la fiche ouvre d'elle-même (R2-021b/025b) : `section` (`decouper` : « Plus » déplié, curseur dans
 *  « Découper en sous-tâches ») et `focus` (`titre` : curseur dans le titre ; `heure` : Quand ouvert sur le champ Heure). */
export const SECTIONS_FICHE = ['decouper']
export const FOCUS_FICHE = ['titre', 'heure']

/** `(id, { section, focus } = {}) => void` : ouvre la fiche de la tâche `id` sur l'écran courant ; `section` et
 *  `focus` (valeurs ci-dessus, toute autre est ignorée) vont dans l'adresse : `?tache=12&section=decouper`. */
export function useOuvrirFiche() {
  const [params, setParams] = useSearchParams()
  const { state } = useLocation()
  const dejaOuverte = params.has('tache')
  const marquee = Boolean(state?.[MARQUE_FICHE])
  return useCallback((id, { section, focus } = {}) => {
    setParams((actuels) => {
      const suite = new URLSearchParams(actuels)
      suite.set('tache', String(id))
      if (SECTIONS_FICHE.includes(section)) suite.set('section', section)
      else suite.delete('section')
      if (FOCUS_FICHE.includes(focus)) suite.set('focus', focus)
      else suite.delete('focus')
      return suite
    // R2-050 — une fiche déjà ouverte (panneau du bureau) CHANGE de tâche en place : l'entrée est remplacée et garde sa
    // marque, sinon la fermeture (retour arrière) rouvrirait la tâche précédente au lieu de rendre la liste
    }, dejaOuverte ? { replace: true, state: { [MARQUE_FICHE]: marquee } } : { state: { [MARQUE_FICHE]: true } })
  }, [setParams, dejaOuverte, marquee])
}

/** Appelle `rappel(detail)` après chaque création (saisie, collage, file rejouée) ET (R2-040) après chaque écriture
 *  de la fiche (Fait, Supprimer, Quand… : `{ tache }`) — l'écran se met à jour seul, sans rechargement. */
export function useApresCreation(rappel) {
  useEffect(() => {
    const surEvenement = (e) => rappel(e?.detail ?? {})
    window.addEventListener(EVENEMENT_CREEES, surEvenement)
    window.addEventListener(EVENEMENT_ECRITE, surEvenement)
    return () => {
      window.removeEventListener(EVENEMENT_CREEES, surEvenement)
      window.removeEventListener(EVENEMENT_ECRITE, surEvenement)
    }
  }, [rappel])
}
