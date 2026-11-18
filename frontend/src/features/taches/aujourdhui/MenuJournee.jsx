import { useCallback, useState } from 'react'
import api from '../../../api/axios'
import * as client from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { annoncer, proposerAnnuler } from '../lib/gestes'
import { annulerEtRecaler } from '../lib/versions'
import { accord, jourCourt, jourNomme } from '../lib/textes'
import { PHRASE_HORS_LIGNE } from './Sections'

/* ============================================================================
   TCH79 — Le menu ⋯ d'Aujourd'hui (reference/textes.md §2.1) : « Alléger ma journée »,
   « Réorganiser », « Sélectionner », « En faire mon accueil » ; la coquille y ajoute Revue,
   Mon rythme, Supprimées récemment et Réglages (spec-7 §2 « Plus »).
   · Alléger : ouvre la feuille (FeuilleAlleger) — grisé hors ligne ;
   · Réorganiser : bascule le mode ▲▼ des lignes de la journée (Alt+↑/↓ au clavier) ;
   · Sélectionner : bascule la sélection multiple (barre d'actions en lot) ;
   · En faire mon accueil : `POST auth/mobile-home-route/` (route mémorisée côté serveur, accepté
     dès TCH132) — l'icône de l'ERP sur l'iPhone ouvre alors Aujourd'hui.
   Maquette : docs/taches/maquettes/ecran-aujourdhui-15h-menu.html.
   ========================================================================== */

const ROUTE_ACCUEIL = '/taches/aujourdhui'
const LISTES_JOUR = ['essentiel', 'journee', 'ce_soir']
const TOUTES_LES_LISTES = ['essentiel', 'journee', 'ce_soir', 'a_decider', 'en_attente', 'faites']
const cleDe = (item) => `${item.type}:${item.id}`

/** « En faire mon accueil » : le serveur mémorise la route ; un refus est DIT, jamais avalé. */
async function faireMonAccueil() {
  try {
    await api.post('/auth/mobile-home-route/', { route: ROUTE_ACCUEIL })
    proposerAnnuler({ message: "L'icône ouvrira Aujourd'hui" })
  } catch (err) {
    annoncer(frenchError(err, "Impossible d'en faire ton accueil. Réessaie."))
  }
}

/**
 * Les actions de l'écran pour la coquille (`actionsEcran`). Hors ligne : Alléger et l'accueil sont
 * grisés (« Possible une fois connecté »), Réorganiser et Sélectionner restent possibles à vide.
 */
export function actionsJournee({ enLigne, onAlleger, onReorganiser, onSelectionner }) {
  const garde = (action) => () => (enLigne ? action() : annoncer(PHRASE_HORS_LIGNE))
  return [
    { libelle: 'Alléger ma journée', onSelect: garde(onAlleger) },
    { libelle: 'Réorganiser', onSelect: onReorganiser },
    { libelle: 'Sélectionner', onSelect: onSelectionner },
    { libelle: 'En faire mon accueil', onSelect: garde(faireMonAccueil) },
  ]
}

/** Remplace, dans `liste`, les TÂCHES par `taches` (dans cet ordre) en laissant chaque activité ERP à sa place. */
function recomposer(liste, taches) {
  const suite = [...taches]
  return liste.map((item) => (item.type === 'tache' ? suite.shift() : item))
}

function mapStatut(donnees, ids, statut, versions = null) {
  const fn = (item) => (item.type === 'tache' && ids.has(item.id)
    ? { ...item, statut, ...(versions?.[item.id] != null ? { lock_version: versions[item.id] } : {}) }
    : item)
  const propose = donnees.propose
    ? { ...donnees.propose, pour_objectif: (donnees.propose.pour_objectif ?? []).map(fn) }
    : donnees.propose
  return { ...donnees, ...Object.fromEntries(TOUTES_LES_LISTES.map((cle) => [cle, (donnees[cle] ?? []).map(fn)])), propose }
}

/**
 * Les deux modes de l'écran et leurs gestes : Réorganiser (▲▼, Alt+↑/↓ → `reordonner/`, liste « jour »)
 * et Sélectionner (barre d'actions en lot → `lot/`). Optimistes : la ligne bouge AU TOUCHER, un refus
 * la remet et le dit ; jamais de relecture de toute la liste.
 */
export function useModesJournee({ donnees, setDonnees, garde, setEstampilles }) {
  const [reorganiser, setReorganiser] = useState(false)
  const [selection, setSelection] = useState({ actif: false, ids: new Set() })

  const selectionner = useCallback((item) => {
    setSelection((avant) => {
      const ids = new Set(avant.ids)
      if (ids.has(cleDe(item))) ids.delete(cleDe(item))
      else ids.add(cleDe(item))
      return { actif: true, ids }
    })
  }, [])
  const quitterSelection = useCallback(() => setSelection({ actif: false, ids: new Set() }), [])
  const basculerSelection = useCallback(() => setSelection((s) => ({ actif: !s.actif, ids: new Set() })), [])

  const deplacer = useCallback(async (item, sens) => {
    try { garde() } catch { return }
    const liste = LISTES_JOUR.find((cle) => donnees[cle]?.some((it) => cleDe(it) === cleDe(item)))
    if (!liste) return
    const taches = donnees[liste].filter((it) => it.type === 'tache')
    const i = taches.findIndex((it) => it.id === item.id)
    const j = i + sens
    if (i < 0 || j < 0 || j >= taches.length) return
    const suite = [...taches]
    suite[i] = taches[j]
    suite[j] = taches[i]
    setDonnees((d) => ({ ...d, [liste]: recomposer(d[liste], suite) }))
    try {
      await client.reordonnerTache(item.id, { liste: 'jour', avant_id: suite[j - 1]?.id ?? null, apres_id: suite[j + 1]?.id ?? null })
      annoncer(`${item.titre} : position ${j + 1} sur ${suite.length}`)
    } catch (err) {
      setDonnees((d) => ({ ...d, [liste]: recomposer(d[liste], taches) }))
      annoncer(frenchError(err))
    }
  }, [donnees, garde, setDonnees])

  const lot = useCallback(async (code, valeurs = null) => {
    try { garde() } catch { return }
    const ids = [...selection.ids].filter((cle) => cle.startsWith('tache:')).map((cle) => Number(cle.slice(6)))
    if (ids.length === 0) return
    try {
      const { data } = await client.traiterLot({ ids, action: code, ...(valeurs ? { valeurs } : {}) })
      const appliquees = new Set(data.appliquees ?? [])
      if (code === 'terminer') {
        setDonnees((d) => mapStatut(d, appliquees, 'fait'))
      } else if (code === 'planifier' && valeurs?.jour_prevu) {
        const estampille = `→ ${jourNomme(valeurs.jour_prevu, donnees.jour)}`
        setEstampilles((e) => ({ ...e, ...Object.fromEntries([...appliquees].map((id) => [`tache:${id}`, estampille])) }))
      }
      quitterSelection()
      proposerAnnuler({
        message: code === 'terminer' ? accord(appliquees.size, 'faite') : `Prévues ${jourCourt(valeurs?.jour_prevu, donnees.jour)}`,
        onAnnuler: async () => {
          // « Annuler » change la version de chaque tâche remise : on garde celle que le serveur rend
          const retour = await annulerEtRecaler(data.geste_id, [...appliquees])
          const versions = Object.fromEntries(Object.entries(retour.taches).map(([id, t]) => [id, t.lock_version]))
          if (code === 'terminer') setDonnees((d) => mapStatut(d, appliquees, 'a_faire', versions))
          else setEstampilles((e) => Object.fromEntries(Object.entries(e).filter(([cle]) => !appliquees.has(Number(cle.slice(6))))))
        },
      })
      if ((data.refusees ?? []).length > 0) annoncer(accord(data.refusees.length, 'tâche refusée', 'tâches refusées'))
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [donnees, garde, selection, setDonnees, setEstampilles, quitterSelection])

  return { reorganiser, setReorganiser, selection, selectionner, quitterSelection, basculerSelection, deplacer, lot }
}
