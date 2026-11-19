import { useCallback, useEffect, useRef, useState } from 'react'

import {
  attendreTache, classerErreur, creerProjet, listerTousLesProjets, marquerEssentiel, planifierTache,
  restaurerTache, supprimerTache, traiterLot,
} from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { MESSAGE_EN_FILE, enfilerReport } from '../horsligne/captureQueue'
import { estEnLigne } from '../lib/enLigne'
import { annoncer, proposerAnnuler } from '../lib/gestes'
import { annulerEtRecaler, versionDe } from '../lib/versions'
import { aujourdhuiIso, heureDuConflit, jourCourt, jourNomme } from '../lib/textes'
import SelecteurQuand, { QUAND_VIDE } from './SelecteurQuand'

/* ============================================================================
   Raccord F2 — LE gestionnaire des actions d'une ligne de tâche (menu ⋯ et gestes de `LigneTache`), partagé par
   Aujourd'hui, Un projet, Recherche et l'Agenda : Choisir un jour · Reporter · En réserve · Déplacer vers un
   projet · En attente de… · Priorité · ★ · Supprimer. Chaque geste est OPTIMISTE (la ligne change au toucher),
   réconcilié par la réponse, défait par le toast « Annuler » (`gestes/{id}/annuler/`) — jamais une relecture de
   toute la liste. Un refus remet la ligne comme avant et le DIT.

   L'écran fournit trois rappels sur SON état (et `apresEcriture(data)`, facultatif : la réponse d'une écriture, dont la
   `progression` du jour) :
     · `maj(id, champs)` — pose des champs sur la ligne (optimiste, puis réconciliation, puis retour arrière) ;
     · `retirer(item)` — retire la ligne et rend la fonction qui la remet (facultatif) ;
     · `sortApres(code, item, valeurs)` — vrai si, sur CET écran, la ligne quitte la liste après le geste
       (une tâche déplacée hors du projet affiché, par exemple). Supprimer la retire toujours.
   `actionsPropres` remplace un code par le geste propre de l'écran (Aujourd'hui garde son ★, qui la fait changer
   de section, et son « Lier une tâche » d'activité ERP).
   Hors ligne : reporter et choisir un jour partent dans la file (TCH100) ; le reste dit « Possible une fois
   connecté ». Textes : reference/textes.md §2.4, §2.15, §2.19.
   ========================================================================== */

const PHRASE_HORS_LIGNE = 'Possible une fois connecté'
/** Priorité 3/2/1/0 — lexique « Priorité haute / moyenne / basse / aucune ». */
const PRIORITES = [[3, 'haute'], [2, 'moyenne'], [1, 'basse'], [0, 'aucune']]
const CHAMPS_QUAND = ['jour_prevu', 'moment', 'heure_debut', 'quelque_jour']

const capitale = (texte) => texte.charAt(0).toUpperCase() + texte.slice(1)
const pris = (item, champs) => Object.fromEntries(champs.map((c) => [c, item[c] ?? null]))

export function FeuilleAttente({ item, onValider }) {
  const [texte, setTexte] = useState(item.en_attente_de ?? '')
  return (
    <form className="choisir-jour" noValidate onSubmit={(e) => { e.preventDefault(); if (texte.trim()) onValider(texte.trim()) }}>
      <p className="carte-source">{item.titre}</p>
      <label className="fiche-label" htmlFor="tch-attente-qui">De qui ou de quoi ?</label>
      <input id="tch-attente-qui" type="text" className="champ" maxLength={200} value={texte} onChange={(e) => setTexte(e.target.value)} />
      <button type="submit" className="bouton plein large" disabled={!texte.trim()}>En attente</button>
    </form>
  )
}

export function FeuillePriorite({ item, onChoisir }) {
  return (
    <div className="choisir-jour">
      <p className="carte-source">{item.titre}</p>
      <div className="puces" role="radiogroup" aria-label="Priorité">
        {PRIORITES.map(([valeur, libelle]) => (
          <button key={valeur} type="button" className="puce" role="radio" aria-checked={(item.priorite ?? 0) === valeur}
            onClick={() => onChoisir(valeur, libelle)}>
            {capitale(libelle)}
          </button>
        ))}
      </div>
    </div>
  )
}

export function FeuilleSupprimer({ item, onConfirmer }) {
  return (
    <div className="choisir-jour">
      <p className="carte-texte">{`Supprimer « ${item.titre} » ?`}</p>
      <button type="button" className="bouton danger large" onClick={onConfirmer}>Supprimer</button>
    </div>
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- hook du gestionnaire, co-localisé avec ses feuilles (D-ENF22)
export function useActionsLigne({
  aujourdhui = aujourdhuiIso(), prochainJourOuvre = null, maj, retirer = null, sortApres = () => false, actionsPropres = {},
  apresEcriture = null,
}) {
  const [feuille, setFeuille] = useState(null)
  const [projets, setProjets] = useState(null)
  const [conflit, setConflit] = useState(null)
  const fermer = useCallback(() => setFeuille(null), [])
  const rappels = useRef({ maj, retirer, sortApres, apresEcriture })
  const relancer = useRef(null)
  useEffect(() => { rappels.current = { maj, retirer, sortApres, apresEcriture } })

  /** Pose le changement sur la ligne (ou la sort) ; rend la fonction qui le défait. */
  const poser = useCallback((code, item, champs, valeurs = champs) => {
    const { maj: poserChamps, retirer: sortir, sortApres: sort } = rappels.current
    if (sortir && sort(code, item, valeurs)) return sortir(item) ?? (() => {})
    const avant = pris(item, Object.keys(champs))
    poserChamps(item.id, champs)
    return () => poserChamps(item.id, avant)
  }, [])

  /** « Annuler » : le serveur change la version de la tâche ; la ligne remise garde celle qu'il rend (F4 revue #7). */
  const annuler = useCallback(async (gesteId, item, defaire) => {
    const retour = await annulerEtRecaler(gesteId, [item.id])
    defaire()
    const version = versionDe(retour, item.id, null)
    if (version != null) rappels.current.maj(item.id, { lock_version: version })
  }, [])

  const echec = useCallback((err, defaire) => {
    defaire()
    annoncer(frenchError(err))
  }, [])

  const planifier = useCallback(async (item, quand, message, lockVersion = item.lock_version) => {
    const corps = { ...QUAND_VIDE, ...quand, lock_version: lockVersion }
    if (!estEnLigne()) {
      try {
        await enfilerReport(item.id, corps)
      } catch (err) {
        annoncer(frenchError(err))
        return
      }
      poser('planifier', item, pris(corps, CHAMPS_QUAND))
      proposerAnnuler({ message: MESSAGE_EN_FILE, annonce: message })
      return
    }
    const defaire = poser('planifier', item, pris(corps, CHAMPS_QUAND))
    try {
      const { data } = await planifierTache(item.id, corps)
      setConflit(null)
      if (data?.tache?.lock_version != null) rappels.current.maj(item.id, { lock_version: data.tache.lock_version })
      rappels.current.apresEcriture?.(data)
      proposerAnnuler({
        message,
        onAnnuler: data?.geste_id ? () => annuler(data.geste_id, item, defaire) : undefined,
      })
    } catch (err) {
      const classee = classerErreur(err)
      defaire()
      if (classee.code === 'conflit_version') {
        setConflit({
          heure: heureDuConflit(classee.actuel),
          onGarder: () => { setConflit(null); relancer.current?.(item, quand, message, classee.lockVersion ?? classee.actuel?.lock_version) },
          onPrendre: () => { if (classee.actuel) rappels.current.maj(item.id, classee.actuel); setConflit(null) },
        })
        return
      }
      annoncer(frenchError(err))
    }
  }, [poser, annuler])
  useEffect(() => { relancer.current = planifier }, [planifier])

  const reporter = useCallback((item) => {
    if (!prochainJourOuvre) return
    planifier(item, { jour_prevu: prochainJourOuvre }, `Reportée à ${jourNomme(prochainJourOuvre, aujourdhui)}`)
  }, [planifier, prochainJourOuvre, aujourdhui])

  const parLot = useCallback(async (item, action, valeurs, champs, message) => {
    const defaire = poser(action, item, champs, valeurs)
    try {
      const { data } = await traiterLot({ ids: [item.id], action, valeurs })
      const refus = (data?.refusees ?? []).find((r) => r.id === item.id)
      if (refus) { defaire(); annoncer('Cette tâche a changé : rien n\'a été modifié.'); return }
      proposerAnnuler({
        message,
        onAnnuler: data?.geste_id ? () => annuler(data.geste_id, item, defaire) : undefined,
      })
    } catch (err) {
      echec(err, defaire)
    }
  }, [poser, echec, annuler])

  const deplacer = useCallback((item, projet) => {
    setFeuille(null)
    parLot(item, 'deplacer', { projet_id: projet.id }, { projet: { id: projet.id, nom: projet.nom, couleur: projet.couleur, priorite: projet.priorite } },
      `Déplacée dans « ${projet.nom} »`)
  }, [parLot])

  const nouveauProjet = useCallback(async (item, nom) => {
    setFeuille(null)
    try {
      const { data } = await creerProjet({ nom }, { erreurSousLeChamp: true })
      const cree = data?.projet ?? data
      setProjets((liste) => (liste ? [...liste, cree] : liste))
      deplacer(item, cree)
    } catch (err) {
      // la feuille est déjà fermée : le refus (409 `nom_pris`, `nom` déjà pris…) se VOIT dans le toast, et il est lu
      proposerAnnuler({ message: classerErreur(err).champs?.nom?.[0] ?? frenchError(err) })
    }
  }, [deplacer])

  const attendre = useCallback(async (item, texte) => {
    setFeuille(null)
    const defaire = poser('attente', item, { statut: 'en_attente', en_attente_de: texte })
    try {
      const { data } = await attendreTache(item.id, { en_attente_de: texte })
      rappels.current.apresEcriture?.(data)
      proposerAnnuler({
        message: `En attente de : ${texte}`,
        onAnnuler: data?.geste_id ? () => annuler(data.geste_id, item, defaire) : undefined,
      })
    } catch (err) {
      echec(err, defaire)
    }
  }, [poser, echec, annuler])

  const essentiel = useCallback(async (item, suivant = !item.essentielle) => {
    const defaire = poser('essentiel', item, { essentielle: suivant })
    try {
      const { data } = await marquerEssentiel({ tache_id: item.id, essentielle: suivant })
      rappels.current.apresEcriture?.(data)
      proposerAnnuler({
        message: suivant ? 'Essentielle' : 'Plus essentielle',
        annonce: `${suivant ? 'Essentielle' : 'Plus essentielle'} : ${item.titre}`,
        onAnnuler: data?.geste_id ? () => annuler(data.geste_id, item, defaire) : undefined,
      })
    } catch (err) {
      echec(err, defaire)
    }
  }, [poser, echec, annuler])

  const supprimer = useCallback(async (item) => {
    setFeuille(null)
    const { retirer: sortir, maj: poserChamps } = rappels.current
    const remettre = sortir ? (sortir(item) ?? (() => {})) : (() => {})
    try {
      const { data: supprimee } = await supprimerTache(item.id)
      proposerAnnuler({
        message: 'Supprimée',
        onAnnuler: async () => {
          if (supprimee?.geste_id) {
            // « Annuler » côté serveur (A7) : rappels annulés remis, geste consommé. Une tâche modifiée depuis reste supprimée.
            const { data, taches } = await annulerEtRecaler(supprimee.geste_id, [item.id])
            const conflits = data?.conflits?.length ?? 0
            if (conflits > 0) { annoncer(`Annulé, sauf ${conflits} modifiée${conflits > 1 ? 's' : ''} depuis.`); return }
            remettre()
            if (taches[item.id]) poserChamps(item.id, { lock_version: taches[item.id].lock_version }) // la version rendue par le serveur
            return
          }
          const { data } = await restaurerTache(item.id)
          remettre()
          if (data?.tache) poserChamps(item.id, { lock_version: data.tache.lock_version })
        },
      })
    } catch (err) {
      echec(err, remettre)
    }
  }, [echec])

  // la liste des projets n'est lue qu'une fois ; `prechargerProjets` la lit d'avance (clavier : `m` puis Entrée
  // tout de suite doit trouver la liste — F2 acceptation, P144.3)
  const lectureProjets = useRef(null)
  const lireProjets = useCallback(() => {
    if (!lectureProjets.current) {
      lectureProjets.current = listerTousLesProjets()
        .then((liste) => { setProjets(liste); return liste })
        .catch((err) => { lectureProjets.current = null; throw err })
    }
    return lectureProjets.current
  }, [])
  const prechargerProjets = useCallback(() => {
    if (projets) return
    lireProjets().catch((err) => { annoncer(frenchError(err)) })
  }, [projets, lireProjets])

  const ouvrirProjets = useCallback((item, { clavier = false } = {}) => {
    setFeuille({ type: 'projet', item, clavier })
    if (!projets) lireProjets().catch((err) => { setFeuille(null); annoncer(frenchError(err)) })
  }, [projets, lireProjets])

  /** Le rappel `onAction(code, item)` de `LigneTache` ; `{ clavier: true }` quand une touche l'a demandé. */
  const surAction = useCallback((code, item, options = {}) => {
    if (actionsPropres[code]) { actionsPropres[code](item); return }
    const reseau = code !== 'choisir_jour' && code !== 'reporter' && code !== 'reserve'
    if (reseau && !estEnLigne()) { annoncer(PHRASE_HORS_LIGNE); return }
    if (code === 'choisir_jour') setFeuille({ type: 'quand', item })
    else if (code === 'reporter') reporter(item)
    else if (code === 'reserve') planifier(item, { quelque_jour: true }, 'En réserve')
    else if (code === 'deplacer') ouvrirProjets(item, options)
    else if (code === 'attente') setFeuille({ type: 'attente', item })
    else if (code === 'priorite') setFeuille({ type: 'priorite', item })
    else if (code === 'essentiel') essentiel(item)
    else if (code === 'supprimer') setFeuille({ type: 'supprimer', item })
  }, [actionsPropres, reporter, planifier, ouvrirProjets, essentiel])

  const item = feuille?.item
  let feuilleProps = null
  if (feuille?.type === 'quand') {
    feuilleProps = {
      ouverte: true, onFermer: fermer, titre: 'Choisir un jour',
      children: (
        <SelecteurQuand
          valeur={pris(item, CHAMPS_QUAND)} aujourdhui={aujourdhui} reporterA={prochainJourOuvre}
          onChoisir={(quand) => {
            setFeuille(null)
            const message = quand.quelque_jour ? 'En réserve'
              : quand.jour_prevu ? `Prévue ${jourCourt(quand.jour_prevu, aujourdhui)}` : 'Sans jour'
            planifier(item, quand, message)
          }}
        />
      ),
    }
  } else if (feuille?.type === 'attente') {
    feuilleProps = { ouverte: true, onFermer: fermer, titre: 'En attente de…', children: <FeuilleAttente item={item} onValider={(t) => attendre(item, t)} /> }
  } else if (feuille?.type === 'priorite') {
    feuilleProps = {
      ouverte: true, onFermer: fermer, titre: 'Priorité',
      children: (
        <FeuillePriorite item={item} onChoisir={(valeur, libelle) => {
          setFeuille(null)
          if (valeur !== (item.priorite ?? 0)) parLot(item, 'prioriser', { priorite: valeur }, { priorite: valeur }, `Priorité ${libelle}`)
        }} />
      ),
    }
  } else if (feuille?.type === 'supprimer') {
    feuilleProps = { ouverte: true, onFermer: fermer, titre: 'Supprimer', children: <FeuilleSupprimer item={item} onConfirmer={() => supprimer(item)} /> }
  }

  const selecteurProjet = feuille?.type === 'projet' ? {
    ouverte: true,
    onFermer: fermer,
    titre: 'Déplacer vers…',
    projets: projets ?? [],
    chargement: projets === null,
    focusChamp: Boolean(feuille.clavier),
    valeur: item.projet?.id ?? null,
    sansProjet: false,
    onChoisir: (projetId) => { const projet = (projets ?? []).find((p) => p.id === projetId); if (projet) deplacer(item, projet) },
    onNouveau: (nom) => nouveauProjet(item, nom),
  } : null

  return { surAction, reporter, essentiel, prechargerProjets, feuille: feuilleProps, selecteurProjet, conflit }
}
