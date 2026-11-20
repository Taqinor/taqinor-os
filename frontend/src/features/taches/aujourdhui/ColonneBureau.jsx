import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { frenchError } from '../../../lib/frenchError'
import { classerErreur, lireAgenda, listerTousLesProjets, planifierTache } from '../../../api/tachesApi'
import { annoncer, proposerAnnuler } from '../lib/gestes'
import { annulerEtRecaler, versionDe } from '../lib/versions'
import { jourNomme } from '../lib/textes'
import GrilleAgenda from '../ui/GrilleAgenda'
import { BandeauPasAJour } from './Sections'

/* ============================================================================
   TCH152 — Aujourd'hui au BUREAU (≥ 1024 px). Deux colonnes autour de la liste (maquette
   ecran-aujourdhui-matin.html, `.col-agenda` et la liste « Mes projets » de la barre latérale) :
     · `ColonneBureau` — à droite : « Agenda » du jour (bande « Toute la journée », la grille horaire
       `GrilleAgenda` : blocs des tâches à heure, rendez-vous externes en lecture seule, ligne « maintenant »).
       Glisser une ligne de la liste sur un créneau lui donne une heure : `POST taches/{id}/planifier/`
       {jour_prevu, heure_debut, lock_version}, optimiste (le bloc apparaît tout de suite), réconcilié par la
       réponse, « Placée à {HH:MM} · Annuler » ; un refus remet l'agenda comme avant et ne relit rien.
       Pendant le glisser seulement, chaque créneau devient « Placer à {HH:MM} » (la grille ne parle jamais au
       serveur, c'est ce module qui écrit) ;
     · `ColonneProjets` — à gauche : « Mes projets », une ligne par projet actif ou en pause avec le nombre de
       tâches ouvertes que le serveur compte (`projets/` → `compteurs.ouvertes`), chacune mène au projet.
   L'iPhone n'a ni l'une ni l'autre : la page ne les monte qu'au bureau, et ne les lit qu'alors.
   Textes : textes.md §2.8 (« Glisse une tâche sur un créneau pour lui donner une heure. »), §2.15
   (« Placée à {HH:MM} · Annuler », « Cette tâche a changé : rien n'a été modifié. »).
   ========================================================================== */

const JOUR_VIDE = (iso) => ({
  jour: iso, ouvre: true, ferie: false, toute_la_journee: [], sans_heure: [], blocs: [], echeances: [], externes: [],
})
const PHRASE_AIDE = 'Glisse une tâche sur un créneau pour lui donner une heure.'
const PHRASE_CHANGEE = "Cette tâche a changé : rien n'a été modifié."
const CHAMPS_ECRITS = ['lock_version', 'jour_prevu', 'heure_debut', 'moment', 'statut', 'estimation_minutes']

const sansTache = (liste, id) => (liste ?? []).filter((t) => !(t.type === 'tache' && t.id === id))

/** La tâche `item` posée à `heure` : elle quitte « sans heure » et rejoint les blocs. */
function avecPose(jour, item, heure) {
  const posee = { ...item, jour_prevu: jour.jour, heure_debut: heure, quelque_jour: false }
  return { ...jour, blocs: [...sansTache(jour.blocs, item.id), posee], sans_heure: sansTache(jour.sans_heure, item.id) }
}

/** Réconcilie le bloc avec la TACHE_ECRITE rendue par le serveur (version, heure…). */
function reconcilie(jour, tache) {
  if (!tache?.id) return jour
  const champs = Object.fromEntries(CHAMPS_ECRITS.filter((c) => c in tache).map((c) => [c, tache[c]]))
  return { ...jour, blocs: (jour.blocs ?? []).map((t) => (t.type === 'tache' && t.id === tache.id ? { ...t, ...champs } : t)) }
}

function BandeJournee({ jour }) {
  const elements = [
    ...(jour.toute_la_journee ?? []).map((e) => ({ cle: `erp:${e.famille}:${e.id}`, titre: e.titre, url: e.url })),
    ...(jour.externes ?? []).filter((e) => e.journee_entiere).map((e) => ({ cle: `ext:${e.cle}`, titre: e.titre, agenda: e.agenda })),
  ]
  if (elements.length === 0) return null
  return (
    <div className="agenda-journee" role="group" aria-label="Toute la journée">
      <small>Toute la<br />journée</small>
      <div>
        {elements.map((e) => (
          e.url
            ? <Link key={e.cle} className="bloc erp" to={e.url}><b>{e.titre}</b></Link>
            : <div key={e.cle} className="bloc erp"><b>{e.titre}</b>{e.agenda ? <small className="ag-agenda">{e.agenda}</small> : null}</div>
        ))}
      </div>
    </div>
  )
}

/** R3-024 — les blocs du jour tirés des items de la PAGE (la même source que la liste) : une tâche de ce jour, à heure,
 *  une seule fois (une ★ faite est servie dans `essentiel` ET `faites`), dans l'ordre de l'heure. */
function blocsDuJour(items, jour) {
  const vus = new Set()
  return (items ?? [])
    .filter((t) => t?.type === 'tache' && t.jour_prevu === jour && t.heure_debut && t.statut !== 'annule')
    .filter((t) => (vus.has(t.id) ? false : vus.add(t.id)))
    .sort((a, b) => String(a.heure_debut).localeCompare(String(b.heure_debut)) || a.id - b.id)
}

/**
 * `jour` : le jour affiché (`AAAA-MM-JJ`) ; `maintenant` : l'instant du serveur (ISO) pour la ligne « maintenant » ;
 * `items` (R3-024) : les items de la journée tenue par la page — les blocs en sont tirés, si bien que cocher, reporter,
 * supprimer ou changer l'heure depuis la fiche se voit à l'instant ; l'agenda n'est plus lu que pour les rendez-vous
 * et « Toute la journée ». Sans `items`, les blocs de l'agenda lu. `glisse` : la ligne en train d'être glissée (nulle
 * sinon) ; `onPlacee(item, data)` / `onRetiree(item)` : la page met sa liste à jour (heure sur la ligne ; ligne rendue
 * comme avant après « Annuler »).
 */
export default function ColonneBureau({ jour, maintenant = '', items = null, glisse = null, onPlacee, onRetiree }) {
  const [agenda, setAgenda] = useState(null)
  const [echec, setEchec] = useState(false)
  const [erreur, setErreur] = useState('')
  // les placements en vol (la page n'a pas encore l'heure) : le bloc est là tout de suite, retiré sur refus
  const [enVol, setEnVol] = useState({})

  const charger = useCallback(() => lireAgenda({ du: jour, au: jour })
    .then((reponse) => {
      const lu = (reponse.data?.jours ?? []).find((j) => j.jour === jour)
      setAgenda(lu ?? JOUR_VIDE(jour))
      setEchec(false)
    })
    .catch(() => setEchec(true)), [jour])

  useEffect(() => { charger() }, [charger])

  const suitLaPage = Array.isArray(items)
  const affiche = useMemo(() => {
    if (!agenda && !suitLaPage) return null
    const base = agenda ?? JOUR_VIDE(jour)
    const blocs = suitLaPage ? blocsDuJour(items, jour) : (base.blocs ?? [])
    const poses = Object.values(enVol)
    return poses.length === 0 ? { ...base, blocs } : poses.reduce((j, { item, heure }) => avecPose(j, item, heure), { ...base, blocs })
  }, [agenda, suitLaPage, items, jour, enVol])

  const finVol = (id) => setEnVol((v) => Object.fromEntries(Object.entries(v).filter(([k]) => Number(k) !== id)))

  /** Pose `item` à `heure` : le bloc apparaît tout de suite ; le serveur confirme, ou l'agenda revient comme avant. */
  const placer = async (item, heure) => {
    const avant = agenda
    setErreur('')
    setEnVol((v) => ({ ...v, [item.id]: { item, heure } }))
    const corps = { jour_prevu: jour, heure_debut: heure, moment: '', quelque_jour: false }
    if (item.lock_version != null) corps.lock_version = item.lock_version
    let reponse
    try {
      reponse = await planifierTache(item.id, corps)
    } catch (err) {
      finVol(item.id)
      if (classerErreur(err).code === 'conflit_version') annoncer(PHRASE_CHANGEE)
      else setErreur(frenchError(err, "La tâche n'a pas pu être placée."))
      return
    }
    const { data } = reponse
    // la page prend l'heure (sa ligne, donc le bloc) ; sans page, l'agenda lu la garde
    if (!suitLaPage) setAgenda((a) => reconcilie(avecPose(a ?? JOUR_VIDE(jour), item, heure), data?.tache))
    finVol(item.id)
    onPlacee?.(item, data, heure)
    proposerAnnuler({
      message: `Placée à ${heure}`,
      onAnnuler: async () => {
        // « Annuler » change la version de la tâche côté serveur : la ligne rendue garde celle que le serveur rend
        const retour = data?.geste_id ? await annulerEtRecaler(data.geste_id, [item.id]) : null
        if (!suitLaPage) setAgenda(avant)
        onRetiree?.({ ...item, lock_version: versionDe(retour, item.id, item.lock_version) })
      },
    })
  }

  const placement = glisse ? { onPoser: (_jour, heure) => placer(glisse, heure) } : null
  const horloge = Number.isNaN(new Date(maintenant).getTime()) ? null : new Date(maintenant)

  return (
    <aside className="tch-bureau-agenda bureau-seul" aria-label="Agenda du jour">
      <div className="agenda-tete"><b>Agenda</b><span className="chiffres">{jourNomme(jour, jour)}</span></div>
      {/* R3-024 — en échec, le dire et offrir de réessayer, jamais l'invite à glisser (un agenda qu'on n'a pas lu) */}
      {echec && !agenda ? (
        <p className="agenda-echec" role="status">
          <span>L&apos;agenda n&apos;a pas pu être lu</span>
          <button type="button" className="bouton lien" onClick={charger}>Réessayer</button>
        </p>
      ) : null}
      {echec && agenda ? <BandeauPasAJour derniere={String(maintenant).slice(11, 16)} onReessayer={charger} /> : null}
      {affiche ? (
        <>
          <BandeJournee jour={affiche} />
          <GrilleAgenda jours={[affiche]} aujourdhui={jour} maintenant={horloge} placement={placement} />
        </>
      ) : null}
      {erreur ? <p className="erreur-champ" role="alert">{erreur}</p> : null}
      {echec && !agenda ? null : <p className="agenda-libre">{PHRASE_AIDE}</p>}
    </aside>
  )
}

/**
 * « Mes projets » : les projets actifs ou en pause, leur nombre de tâches ouvertes (lu du serveur), un lien chacun.
 * R2-029 — `ecarts` ({ projet_id: ±n }) : les gestes de la page depuis cette lecture (« Changer de projet… », et son Annuler)
 * — le compte suit sans relire la liste.
 */
export function ColonneProjets({ ecarts = {} }) {
  const [projets, setProjets] = useState(null)
  const [echec, setEchec] = useState('')

  useEffect(() => {
    let courant = true
    listerTousLesProjets()
      .then((liste) => { if (courant) { setProjets(liste); setEchec('') } })
      .catch((err) => { if (courant) setEchec(frenchError(err)) })
    return () => { courant = false }
  }, [])

  if (!projets?.length && !echec) return null
  return (
    <nav className="tch-bureau-projets bureau-seul" aria-label="Mes projets">
      <p className="nav-titre">Mes projets</p>
      {echec ? <p className="erreur-champ" role="alert">{echec}</p> : null}
      {(projets ?? []).map((projet) => (
        <Link key={projet.id} className="nav-item" data-p={projet.couleur} to={`/taches/projets/${projet.id}`}>
          <i className="point" aria-hidden="true" />
          <span>{projet.nom}</span>
          <span className="compte chiffres">
            {typeof projet.compteurs?.ouvertes === 'number' ? Math.max(0, projet.compteurs.ouvertes + (ecarts[projet.id] ?? 0)) : ''}
          </span>
        </Link>
      ))}
    </nav>
  )
}
