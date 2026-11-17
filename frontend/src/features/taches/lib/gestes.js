import { useMemo, useSyncExternalStore } from 'react'

import { frenchError } from '../../../lib/frenchError'

/* ============================================================================
   TCH46 — Gestes et annonces de l'app Tâches : UN petit magasin (sans dépendance) lu par
   la coquille. Deux sorties, jamais confondues :
     · `annoncer(texte)` : la région `role=status` (lecteur d'écran) — « Fait : Appeler Karim »,
       « Reportée à lun. 23 », « 5 gardées », « Annulé » (textes.md §2.19) ;
     · `proposerAnnuler({ message, annonce, onAnnuler })` : LE toast (un seul à la fois) —
       « Faite · Annuler », 8 secondes, EN PAUSE tant qu'il est survolé ou focalisé (WCAG 2.2.1).
   Le réglage « Messages sans délai » (`configurerGestes({ sansDelai: true })`) le garde
   jusqu'à ce que l'utilisateur le ferme. Tout est ici ; les écrans ne posent jamais de toast à eux.
   Spec : conception/spec-7-ecrans.md §6 « Accessibilité » ; maquettes etat-toast.html.
   ========================================================================== */

export const DUREE_TOAST_MS = 8000
export const LIBELLE_ANNULER = 'Annuler'

let etat = { annonce: '', rang: 0, toast: null, sansDelai: false }
let jetons = 0
const ecouteurs = new Set()
const minuteur = { id: null, restant: 0, debut: 0, raisons: new Set() }

const poser = (suite) => { etat = { ...etat, ...suite }; ecouteurs.forEach((fn) => fn()) }
const abonner = (fn) => { ecouteurs.add(fn); return () => { ecouteurs.delete(fn) } }
const lire = () => etat

function effacerMinuteur() {
  if (minuteur.id !== null) { clearTimeout(minuteur.id); minuteur.id = null }
}

function armer(ms) {
  effacerMinuteur()
  minuteur.restant = ms
  minuteur.debut = Date.now()
  minuteur.id = setTimeout(() => { minuteur.id = null; fermerToast() }, ms)
}

/** Ferme le toast courant (le bouton × du mode « sans délai », l'échéance des 8 s). */
export function fermerToast() {
  effacerMinuteur()
  minuteur.raisons.clear()
  if (etat.toast) poser({ toast: null })
}

/** Pause du compte à rebours (`raison` : « survol » ou « focus ») — tant qu'une raison tient, il ne s'écoule pas. */
export function pauserToast(raison) {
  if (!etat.toast || etat.sansDelai) return
  minuteur.raisons.add(raison)
  if (minuteur.id !== null) {
    minuteur.restant = Math.max(0, minuteur.restant - (Date.now() - minuteur.debut))
    effacerMinuteur()
  }
}

/** Reprend le compte à rebours quand plus aucune raison de pause ne tient. */
export function reprendreToast(raison) {
  if (!etat.toast || etat.sansDelai) return
  minuteur.raisons.delete(raison)
  if (minuteur.raisons.size === 0 && minuteur.id === null) armer(Math.max(minuteur.restant, 1))
}

/** « Messages sans délai » : le toast reste jusqu'à sa fermeture (réglage `messages_sans_delai`). */
export function configurerGestes({ sansDelai = false } = {}) {
  if (sansDelai === etat.sansDelai) return
  poser({ sansDelai })
  if (sansDelai) effacerMinuteur()
  else if (etat.toast) armer(DUREE_TOAST_MS)
}

/** Dit `texte` au lecteur d'écran (région `role=status`, même phrase répétée = relue). */
export function annoncer(texte) {
  poser({ annonce: texte, rang: etat.rang + 1 })
}

/**
 * Pose LE toast (le précédent disparaît). `message` s'écrit « Faite », « Reportée à lun. 23 »…
 * `annonce` (facultatif) est la phrase lue — par défaut le message. Sans `onAnnuler`, un simple
 * message (« Close dans l'ERP ») : aucun bouton Annuler.
 */
export function proposerAnnuler({ message, annonce, onAnnuler, libelle = LIBELLE_ANNULER, duree = DUREE_TOAST_MS } = {}) {
  jetons += 1
  const id = jetons
  minuteur.raisons.clear()
  poser({
    toast: { id, message, libelle, onAnnuler: onAnnuler ?? null },
    annonce: annonce ?? message,
    rang: etat.rang + 1,
  })
  if (etat.sansDelai) effacerMinuteur()
  else armer(duree)
  return id
}

/** Annule le geste du toast : `onAnnuler()` puis « Annulé » lu, le toast part. */
export async function annulerToast() {
  const { toast } = etat
  if (!toast) return
  fermerToast()
  try {
    await toast.onAnnuler?.()
    annoncer('Annulé')
  } catch (err) {
    // l'échec de l'annulation est DIT (message du serveur, en français) — jamais avalé
    proposerAnnuler({ message: frenchError(err, "L'annulation a échoué. Réessayez.") })
  }
}

/** Vide le magasin (tests, déconnexion). */
export function reinitialiserGestes() {
  effacerMinuteur()
  minuteur.raisons.clear()
  etat = { annonce: '', rang: 0, toast: null, sansDelai: false }
  ecouteurs.forEach((fn) => fn())
}

/** L'état lu par la zone d'annonces de la coquille. */
export function useEtatGestes() {
  return useSyncExternalStore(abonner, lire, lire)
}

/** Ce qu'un écran utilise pour confirmer un geste : jamais de toast posé à la main. */
export function useGeste() {
  return useMemo(() => ({ annoncer, proposerAnnuler, fermerToast, annulerToast }), [])
}
