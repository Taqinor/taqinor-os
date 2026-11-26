import { useCallback, useSyncExternalStore } from 'react'
import ventesApi from '../../../api/ventesApi'

// R5A-N6 — LA conception rangée d'un lead est lue UNE fois par fiche ouverte, partagée par tous ses consommateurs
// (carte « Conception » du rail, avis « brouillon d'avant le dernier calcul » de l'onglet Devis). Avant : chaque consommateur
// lisait de son côté et la carte REJOUAIT 6 fois un 404 (« aucune conception calculée » = la réponse NORMALE du serveur
// tant qu'aucune version n'est rangée) : 9 réponses 404 par ouverture de la fiche du lead 1189.
//  • un 404 est l'état calme « pas encore de conception » (`vide`) : ni toast, ni relecture automatique ;
//  • une autre panne donne `erreur` seulement s'il n'y avait rien à montrer (une valeur déjà lue n'est jamais effacée) ;
//  • une ACTION de l'utilisateur qui peut créer ou changer la conception (enregistrement de la fiche, devis créé/modifié,
//    « Relire ») appelle `relireConceptionLead` : une seule relecture en vol, rejouée une fois derrière si une autre est
//    demandée pendant ce vol ;
//  • EXCEPTION (la première conception d'un lead se calcule EN ARRIÈRE-PLAN, ~5 s de regroupement + calcul : jusqu'à sa
//    première version le serveur répond 404) : un 404 qui SUIT une action (`relireConceptionLead`) ou l'ouverture d'un lead
//    créé à l'instant (option `attendre`) est l'état « en cours de calcul » (`attente`), relu de façon BORNÉE par UNE minuterie
//    par lead (6 × 4 s), partagée par tous les consommateurs, arrêtée à la fermeture de la fiche ; passé le bornage, l'état
//    calme `vide` ;
//  • quand plus aucun consommateur n'est monté (la fiche est fermée) l'entrée est oubliée : la fiche suivante relit.
export const ATTENTE_DELAI_MS = 4000
export const ATTENTE_MAX_RELECTURES = 6
const LEAD_RECENT_MS = 60 * 1000
const CHARGE = Object.freeze({ statut: 'charge', donnees: null })
const entrees = new Map()

function entree(leadId) {
  let e = entrees.get(leadId)
  if (!e) {
    e = { snap: CHARGE, abonnes: new Set(), enVol: false, rejouer: false, refs: 0, attente: false, essais: 0, minuterie: null }
    entrees.set(leadId, e)
  }
  return e
}

function poser(e, snap) {
  e.snap = snap
  e.abonnes.forEach((rappel) => rappel())
}

function lire(leadId) {
  const e = entree(leadId)
  if (e.enVol) { e.rejouer = true; return }
  e.enVol = true
  Promise.resolve().then(() => ventesApi.getConceptionLead(leadId)) // jamais d'exception synchrone dans l'abonnement
    .then(({ data }) => { e.attente = false; e.essais = 0; poser(e, { statut: 'ok', donnees: data ?? null }) })
    .catch((err) => {
      if (err?.response?.status === 404) {
        if (e.attente && e.essais < ATTENTE_MAX_RELECTURES) {
          e.essais += 1
          poser(e, { statut: 'attente', donnees: null })
          clearTimeout(e.minuterie)
          e.minuterie = setTimeout(() => { e.minuterie = null; if (entrees.get(leadId) === e) lire(leadId) }, ATTENTE_DELAI_MS)
        } else {
          e.attente = false
          poser(e, { statut: 'vide', donnees: null })
        }
      }
      else if (e.snap.donnees) poser(e, e.snap) // rien n'est jamais effacé par un échec
      else poser(e, { statut: 'erreur', donnees: null })
    })
    .finally(() => {
      e.enVol = false
      if (e.rejouer) { e.rejouer = false; lire(leadId) }
    })
}

/** Relit la conception d'une fiche OUVERTE (aucun effet si aucune fiche ne la consomme).
 *  `attendre` (défaut : oui) — l'appel suit une ACTION (fiche enregistrée…) : un 404 est alors « en cours de calcul » (relu,
 *  borné) SAUF si l'état de CETTE fiche est déjà l'état calme `vide` (un 404 à l'ouverture ou la fin d'une attente bornée) :
 *  un lead qui n'a légitimement AUCUNE conception (données manquantes) ne doit pas afficher « en cours de calcul » pendant 24 s
 *  après chaque enregistrement. Une lecture, alors, et rien d'autre : si la saisie fait naître la conception, le serveur écrit
 *  « Conception recalculée » à l'historique (crm/receivers.py::_noter_conception_recalculee, première version comprise) et
 *  l'historique relu (30 s, retour de fenêtre, notification) relit la conception (`attendre: false`).
 *  `attendre: false` (l'historique a changé) : une relecture simple, un 404 reste calme. */
export function relireConceptionLead(leadId, { attendre = true } = {}) {
  if (!leadId || !entrees.has(leadId)) return
  const e = entrees.get(leadId)
  e.attente = attendre && e.snap.statut !== 'vide'
  e.essais = 0
  clearTimeout(e.minuterie)
  e.minuterie = null
  lire(leadId)
}

/** `{ statut: 'charge' | 'ok' | 'vide' | 'erreur', donnees }` — `donnees` = la réponse brute du serveur (ou null). */
/** `creeLe` (date_creation du lead) : un lead créé il y a moins d'une minute n'a pas encore sa première conception (calculée en
 *  arrière-plan) — un 404 de la PREMIÈRE lecture est alors « en cours de calcul ». Évalué à l'abonnement, jamais au rendu. */
export default function useConceptionLead(leadId, { creeLe = null } = {}) {
  const abonner = useCallback((rappel) => {
    if (!leadId) return () => {}
    const e = entree(leadId)
    e.abonnes.add(rappel)
    e.refs += 1
    if (e.snap === CHARGE && !e.enVol) { if (creeLe && Date.now() - Date.parse(creeLe) < LEAD_RECENT_MS) e.attente = true; lire(leadId) }
    return () => {
      e.abonnes.delete(rappel)
      e.refs -= 1
      if (e.refs === 0 && entrees.get(leadId) === e) { clearTimeout(e.minuterie); entrees.delete(leadId) }
    }
  }, [leadId, creeLe])
  return useSyncExternalStore(
    abonner,
    () => (leadId ? entree(leadId).snap : CHARGE),
    () => CHARGE,
  )
}
