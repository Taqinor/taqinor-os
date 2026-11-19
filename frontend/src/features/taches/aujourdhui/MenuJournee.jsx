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
   Mon rythme, Supprimées (avec ses derniers gestes) et Réglages (spec-7 §2 « Plus »).
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
 * R2-026 — « Alléger ma journée » n'est offert que s'il y a de quoi alléger (`peutAlleger` : bilan pas fait, une tâche
 * ouverte au moins que la feuille peut renvoyer).
 */
export function actionsJournee({ enLigne, peutAlleger = true, onAlleger, onReorganiser, onSelectionner }) {
  const garde = (action) => () => (enLigne ? action() : annoncer(PHRASE_HORS_LIGNE))
  return [
    ...(peutAlleger ? [{ libelle: 'Alléger ma journée', onSelect: garde(onAlleger) }] : []),
    { libelle: 'Réorganiser', onSelect: onReorganiser },
    { libelle: 'Sélectionner', onSelect: onSelectionner },
    { libelle: 'En faire mon accueil', onSelect: garde(faireMonAccueil) },
  ]
}

/**
 * R3-020 (M1) — LA progression dans l'instant d'un geste, avant que la réponse du serveur ne la remplace (la
 * `progression` d'une TACHE_ECRITE) ; même règle que le serveur (`selectors/journee.py`) : « essentiel » = les ★ de la
 * section Essentiel servie, ouvertes ou faites aujourd'hui. `fait` (vrai/faux) : cochée / décochée ; `quitte`
 * (vrai/faux) : une ★ OUVERTE quitte la journée (reportée sans échéance aujourd'hui) / y revient (Annuler).
 */
export function progressionApres(progression, item, { fait, quitte } = {}) {
  if (!progression || typeof progression.faites !== 'number' || !item) return progression
  const borne = (n) => Math.max(0, n)
  const suite = { ...progression }
  const etoile = item.type === 'tache' && Boolean(item.essentielle)
  const ajouter = (cle, delta) => { if (typeof suite[cle] === 'number') suite[cle] = borne(suite[cle] + delta) }
  if (fait !== undefined) {
    const delta = fait ? 1 : -1
    suite.faites = borne(suite.faites + delta)
    if (etoile) ajouter('essentiel_faites', delta)
    if (item.prevue_au_plan) ajouter('plan_tenues', delta)
    if (item.type === 'activite') ajouter('activites_closes', delta)
  }
  if (quitte !== undefined && etoile && item.statut !== 'fait') ajouter('essentiel_prevues', quitte ? -1 : 1)
  return suite
}

/** R3-026 — une ligne qui se réordonne : une tâche OUVERTE (une faite, servie aussi dans Essentiel, n'est la voisine de
 *  personne : le serveur ne l'ordonne pas). */
const ordonnable = (item) => item.type === 'tache' && item.statut !== 'fait'
const PHRASE_DEPLACEMENT_REFUSE = 'Impossible de déplacer cette tâche ici.'

/** Remplace, dans `liste`, les tâches ouvertes par `taches` (dans cet ordre) en laissant chaque activité ERP et chaque
 *  tâche faite à sa place. */
function recomposer(liste, taches) {
  const suite = [...taches]
  return liste.map((item) => (ordonnable(item) ? suite.shift() : item))
}

/** Pose `champs` (statut, jour…) sur les tâches `ids` de toutes les listes ; `versions` : leur `lock_version` rendu. */
function mapChamps(donnees, ids, champs, versions = null) {
  const fn = (item) => (item.type === 'tache' && ids.has(item.id)
    ? { ...item, ...(typeof champs === 'function' ? champs(item) : champs), ...(versions?.[item.id] != null ? { lock_version: versions[item.id] } : {}) }
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
    const taches = donnees[liste].filter(ordonnable)
    const i = taches.findIndex((it) => it.id === item.id)
    const j = i + sens
    if (i < 0 || j < 0 || j >= taches.length) return
    const suite = [...taches]
    suite[i] = taches[j]
    suite[j] = taches[i]
    setDonnees((d) => ({ ...d, [liste]: recomposer(d[liste], suite) }))
    try {
      // couture L7 — un refus d'état (409) est dit UNE fois, ici, en mots humains : jamais aussi le toast « Valeur inconnue. »
      await client.reordonnerTache(item.id, { liste: 'jour', avant_id: suite[j - 1]?.id ?? null, apres_id: suite[j + 1]?.id ?? null },
        { erreurSousLeChamp: true })
      annoncer(`${item.titre} : position ${j + 1} sur ${suite.length}`)
    } catch {
      // R3-026 — le refus se VOIT, en mots humains : la ligne revient à sa place (le détail serveur n'aide pas Reda)
      setDonnees((d) => ({ ...d, [liste]: recomposer(d[liste], taches) }))
      proposerAnnuler({ message: PHRASE_DEPLACEMENT_REFUSE })
    }
  }, [donnees, garde, setDonnees])

  const lot = useCallback(async (code, valeurs = null) => {
    try { garde() } catch { return }
    const ids = [...selection.ids].filter((cle) => cle.startsWith('tache:')).map((cle) => Number(cle.slice(6)))
    if (ids.length === 0) return
    try {
      const { data } = await client.traiterLot({ ids, action: code, ...(valeurs ? { valeurs } : {}) })
      const appliquees = new Set(data.appliquees ?? [])
      // R3-020 — `lot/` ne rend pas de progression : chaque tâche appliquée la fait suivre (même règle que le serveur),
      // et la relecture suivante la recale
      const touchees = TOUTES_LES_LISTES.flatMap((cle) => donnees[cle] ?? [])
        .filter((it, i, liste) => it.type === 'tache' && appliquees.has(it.id) && liste.findIndex((x) => x.type === 'tache' && x.id === it.id) === i)
      const ouvertes = touchees.filter((it) => it.statut !== 'fait')
      // une ★ ouverte reportée hors d'aujourd'hui quitte Essentiel, sauf si son échéance l'y garde (C-13)
      const partantes = code === 'planifier' && valeurs?.jour_prevu && valeurs.jour_prevu !== donnees.jour
        ? ouvertes.filter((it) => it.echeance !== donnees.jour) : []
      const suivre = (d, liste, changement) => ({ ...d, progression: liste.reduce((p, it) => progressionApres(p, it, changement), d.progression) })
      let joursAvant = {}
      if (code === 'terminer') {
        setDonnees((d) => suivre(mapChamps(d, appliquees, { statut: 'fait' }), ouvertes, { fait: true }))
      } else if (code === 'planifier' && valeurs?.jour_prevu) {
        const estampille = `→ ${jourNomme(valeurs.jour_prevu, donnees.jour)}`
        setEstampilles((e) => ({ ...e, ...Object.fromEntries([...appliquees].map((id) => [`tache:${id}`, estampille])) }))
        // leur nouveau jour : elles ne comptent plus dans la journée affichée (R2-019)
        joursAvant = Object.fromEntries(TOUTES_LES_LISTES.flatMap((cle) => donnees[cle] ?? [])
          .filter((it) => it.type === 'tache' && appliquees.has(it.id)).map((it) => [it.id, it.jour_prevu ?? null]))
        setDonnees((d) => suivre(mapChamps(d, appliquees, { jour_prevu: valeurs.jour_prevu }), partantes, { quitte: true }))
      }
      quitterSelection()
      proposerAnnuler({
        message: code === 'terminer' ? accord(appliquees.size, 'faite') : `Prévues ${jourCourt(valeurs?.jour_prevu, donnees.jour)}`,
        onAnnuler: async () => {
          // « Annuler » change la version de chaque tâche remise : on garde celle que le serveur rend
          const retour = await annulerEtRecaler(data.geste_id, [...appliquees])
          const versions = Object.fromEntries(Object.entries(retour.taches).map(([id, t]) => [id, t.lock_version]))
          if (code === 'terminer') setDonnees((d) => suivre(mapChamps(d, appliquees, { statut: 'a_faire' }, versions), ouvertes, { fait: false }))
          else {
            setEstampilles((e) => Object.fromEntries(Object.entries(e).filter(([cle]) => !appliquees.has(Number(cle.slice(6))))))
            setDonnees((d) => suivre(mapChamps(d, appliquees, (it) => ({ jour_prevu: joursAvant[it.id] ?? it.jour_prevu }), versions), partantes, { quitte: false }))
          }
        },
      })
      if ((data.refusees ?? []).length > 0) annoncer(accord(data.refusees.length, 'tâche refusée', 'tâches refusées'))
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [donnees, garde, selection, setDonnees, setEstampilles, quitterSelection])

  return { reorganiser, setReorganiser, selection, selectionner, quitterSelection, basculerSelection, deplacer, lot }
}
