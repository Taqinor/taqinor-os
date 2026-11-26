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
//  • quand plus aucun consommateur n'est monté (la fiche est fermée) l'entrée est oubliée : la fiche suivante relit.
const CHARGE = Object.freeze({ statut: 'charge', donnees: null })
const entrees = new Map()

function entree(leadId) {
  let e = entrees.get(leadId)
  if (!e) {
    e = { snap: CHARGE, abonnes: new Set(), enVol: false, rejouer: false, refs: 0 }
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
    .then(({ data }) => poser(e, { statut: 'ok', donnees: data ?? null }))
    .catch((err) => {
      if (err?.response?.status === 404) poser(e, { statut: 'vide', donnees: null })
      else if (e.snap.donnees) poser(e, e.snap) // rien n'est jamais effacé par un échec
      else poser(e, { statut: 'erreur', donnees: null })
    })
    .finally(() => {
      e.enVol = false
      if (e.rejouer) { e.rejouer = false; lire(leadId) }
    })
}

/** Relit la conception d'une fiche OUVERTE (aucun effet si aucune fiche ne la consomme). */
export function relireConceptionLead(leadId) {
  if (leadId && entrees.has(leadId)) lire(leadId)
}

/** `{ statut: 'charge' | 'ok' | 'vide' | 'erreur', donnees }` — `donnees` = la réponse brute du serveur (ou null). */
export default function useConceptionLead(leadId) {
  const abonner = useCallback((rappel) => {
    if (!leadId) return () => {}
    const e = entree(leadId)
    e.abonnes.add(rappel)
    e.refs += 1
    if (e.snap === CHARGE && !e.enVol) lire(leadId)
    return () => {
      e.abonnes.delete(rappel)
      e.refs -= 1
      if (e.refs === 0 && entrees.get(leadId) === e) entrees.delete(leadId)
    }
  }, [leadId])
  return useSyncExternalStore(
    abonner,
    () => (leadId ? entree(leadId).snap : CHARGE),
    () => CHARGE,
  )
}
