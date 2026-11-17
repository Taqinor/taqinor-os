import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search } from 'lucide-react'

import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { frenchError } from '../../lib/frenchError'
import {
  annulerGeste, listerTaches, listerToutesLesEtiquettes, listerTousLesProjets, rechercher, rouvrirTache, terminerTache,
} from '../../api/tachesApi'
import { proposerAnnuler } from '../../features/taches/lib/gestes'
import { aujourdhuiIso } from '../../features/taches/lib/textes'
import LigneTache from '../../features/taches/ui/LigneTache'
import { useActionsLigne } from '../../features/taches/ui/ActionsLigne'
import { ajouterJours } from '../../features/taches/ui/SelecteurQuand'

/* ============================================================================
   TCH87 — Recherche (`/taches/recherche?q=`) : un champ « Chercher dans mes tâches », deux groupes
   « Ouvertes ({n}) » puis « Faites ({n}) ». Filtres visibles : Faites aussi · Projet ▾ · Priorité haute ;
   repliés : Aujourd'hui · À revoir · 7 jours · Sans date · En attente · En réserve · Avec échéance ·
   Étiquette ▾ et le tri. Vide : « Rien pour « {q} » ». Les vues enregistrées viennent en F4 (TCH166).
   D'OÙ VIENNENT LES LIGNES : sans filtre côté serveur, `recherche/` (projets + tâches par mots) ; dès que
   Faites aussi, Projet, Priorité haute, Étiquette ou En réserve est posé, `taches/` (liste paginée, filtres
   de l'API) ; les puces de jour (Aujourd'hui, 7 jours…) et le tri s'appliquent ensuite sur les lignes lues,
   d'après leurs dates. La dernière liste reste affichée si une lecture échoue (hors ligne).
   Maquettes : recherche.html, recherche-filtres.html, recherche-vide.html.
   ========================================================================== */

const DELAI_MS = 300
const TRIS = [['manuel', 'Manuel'], ['priorite', 'Priorité'], ['echeance', 'Échéance'], ['jour', 'Jour'], ['creation', 'Création']]
const PUCES_JOUR = [
  ['aujourdhui', "Aujourd'hui"], ['a_revoir', 'À revoir'], ['sept_jours', '7 jours'], ['sans_date', 'Sans date'],
  ['en_attente', 'En attente'], ['avec_echeance', 'Avec échéance'],
]

// StatutTache : a_faire · en_attente · fait · annule (« abandonnée » à l'écran)
const ouverte = (t) => t.statut !== 'fait' && t.statut !== 'annule'

/** Puces servies par `GET taches/?periode=` (aujourdhui : jour prévu = J ; semaine : J à J+6) ; ET entre les deux = J. */
function periodeServie(puces) {
  if (puces.includes('aujourdhui')) return 'aujourdhui'
  if (puces.includes('sept_jours')) return 'semaine'
  return null
}

/** Tris servis par `GET taches/?tri=` (rang par défaut) ; « Jour » et « Création » restent triés ici. */
const TRI_SERVI = { priorite: 'priorite', echeance: 'echeance' }

/** Les puces de jour, lues sur la ligne et le jour de l'appareil (ET entre puces). */
function correspond(tache, puce, aujourdhui) {
  const jour = tache.jour_prevu
  switch (puce) {
    case 'aujourdhui': return jour === aujourdhui
    case 'a_revoir': return (Boolean(jour) && jour < aujourdhui) || (tache.reports ?? 0) >= 3
    case 'sept_jours': return Boolean(jour) && jour >= aujourdhui && jour <= ajouterJours(aujourdhui, 6)
    case 'sans_date': return !jour && !tache.quelque_jour
    case 'en_attente': return tache.statut === 'en_attente' || Boolean(tache.bloquee_par) || Boolean(tache.en_attente_de)
    case 'avec_echeance': return Boolean(tache.echeance)
    default: return true
  }
}

const NUL_DERNIER = (a, b) => (a == null) - (b == null)
const TRI = {
  manuel: () => 0,
  priorite: (a, b) => (b.priorite ?? 0) - (a.priorite ?? 0),
  echeance: (a, b) => NUL_DERNIER(a.echeance, b.echeance) || String(a.echeance).localeCompare(String(b.echeance)),
  jour: (a, b) => NUL_DERNIER(a.jour_prevu, b.jour_prevu) || String(a.jour_prevu).localeCompare(String(b.jour_prevu)),
  creation: (a, b) => b.id - a.id,
}

function Groupe({ titre, lignes, ...rappels }) {
  if (lignes.length === 0) return null
  return (
    <section className="section" aria-label={`${titre} (${lignes.length})`}>
      <h2 className="section-titre"><span>{`${titre} (${lignes.length})`}</span></h2>
      <div className="liste" role="list">
        {lignes.map((item) => <LigneTache key={`${item.type}:${item.id}`} item={item} {...rappels} />)}
      </div>
    </section>
  )
}

export default function Recherche({ aujourdhui = aujourdhuiIso() }) {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const [saisie, setSaisie] = useState(q)
  const [faites, setFaites] = useState(false)
  const [haute, setHaute] = useState(false)
  const [reserve, setReserve] = useState(false)
  const [projetId, setProjetId] = useState(null)
  const [etiquetteId, setEtiquetteId] = useState(null)
  const [puces, setPuces] = useState([])
  const [tri, setTri] = useState('manuel')
  const [replie, setReplie] = useState(false)
  const [projets, setProjets] = useState([])
  const [etiquettes, setEtiquettes] = useState([])
  const [selecteur, setSelecteur] = useState(false)
  const [resultat, setResultat] = useState({ projets: [], taches: [] })
  const [lu, setLu] = useState(false)
  const [erreur, setErreur] = useState('')

  // la saisie reste TELLE QUE TAPÉE ; l'adresse (`?q=`) la suit après une courte pause
  useEffect(() => {
    const minuteur = setTimeout(() => {
      if (saisie === q) return
      setParams((actuels) => {
        const suite = new URLSearchParams(actuels)
        if (saisie) suite.set('q', saisie)
        else suite.delete('q')
        return suite
      }, { replace: true })
    }, DELAI_MS)
    return () => clearTimeout(minuteur)
  }, [saisie, q, setParams])

  const periode = periodeServie(puces)
  const triServi = TRI_SERVI[tri]
  const serveur = faites || haute || reserve || projetId != null || etiquetteId != null || periode != null
  const mots = q.trim()

  useEffect(() => {
    if (!serveur && !mots) return undefined
    let courant = true
    const lecture = serveur
      ? listerTaches({
        q: mots || undefined,
        projet: projetId ?? undefined,
        etiquette: etiquetteId ?? undefined,
        priorite_min: haute ? 3 : undefined,
        inclure_faites: faites ? true : undefined,
        vue: reserve ? 'quelque_jour' : undefined,
        periode: periode ?? undefined,
        tri: triServi,
      }).then((r) => ({ projets: [], taches: r.data?.results ?? [] }))
      : rechercher({ q: mots, limite: 25 }).then((r) => ({ projets: r.data?.projets ?? [], taches: r.data?.taches ?? [] }))
    lecture
      .then((suite) => { if (courant) { setResultat(suite); setLu(true); setErreur('') } })
      .catch((err) => { if (courant) setErreur(frenchError(err)) })
    return () => { courant = false }
  }, [mots, serveur, faites, haute, reserve, projetId, etiquetteId, periode, triServi])

  const chargerProjets = useCallback(() => {
    if (projets.length === 0) listerTousLesProjets().then(setProjets).catch((err) => setErreur(frenchError(err)))
  }, [projets.length])
  // Les étiquettes (`etiquettes/`) ne sont servies qu'en F4 (TCH166, 501 d'ici là) : sans liste lue, le filtre
  // « Étiquette » n'apparaît pas — ce n'est pas une erreur de l'écran, rien n'est affiché.
  const [etiquettesLues, setEtiquettesLues] = useState(false)
  useEffect(() => {
    if (!replie || etiquettesLues) return
    listerToutesLesEtiquettes()
      .then(setEtiquettes)
      .catch(() => setEtiquettes([]))
      .finally(() => setEtiquettesLues(true))
  }, [replie, etiquettesLues])

  const actif = serveur || Boolean(mots)
  const lignes = useMemo(() => (actif ? resultat.taches : [])
    .filter((t) => puces.every((p) => correspond(t, p, aujourdhui)))
    .sort(TRI[tri]), [actif, resultat.taches, puces, tri, aujourdhui])
  const ouvertes = lignes.filter(ouverte)
  const faitesLignes = lignes.filter((t) => !ouverte(t))
  const projetsTrouves = serveur || !actif ? [] : resultat.projets

  const ouvrirFiche = (item) => setParams((actuels) => {
    const suite = new URLSearchParams(actuels)
    suite.set('tache', String(item.id))
    return suite
  })
  const majLigne = (id, suite) => setResultat((r) => ({ ...r, taches: r.taches.map((t) => (t.id === id ? { ...t, ...suite } : t)) }))

  const terminer = async (item, suivant) => {
    const { data } = await (suivant ? terminerTache(item.id, {}) : rouvrirTache(item.id))
    majLigne(item.id, { statut: data?.tache?.statut ?? (suivant ? 'fait' : 'a_faire') })
    if (suivant) {
      proposerAnnuler({
        message: 'Faite',
        onAnnuler: data?.geste_id ? async () => { await annulerGeste(data.geste_id); majLigne(item.id, { statut: 'a_faire' }) } : undefined,
      })
    }
  }
  // Raccord F2 — le gestionnaire commun des actions de ligne : chaque geste change la ligne sur place, sans relire.
  const actions = useActionsLigne({
    aujourdhui,
    maj: majLigne,
    retirer: (item) => {
      let rang = -1
      setResultat((r) => { rang = r.taches.findIndex((t) => t.id === item.id); return { ...r, taches: r.taches.filter((t) => t.id !== item.id) } })
      return () => setResultat((r) => {
        const taches = [...r.taches]
        taches.splice(rang < 0 ? 0 : Math.min(rang, taches.length), 0, item)
        return { ...r, taches }
      })
    },
  })
  const action = actions.surAction

  const basculerPuce = (cle) => setPuces((l) => (l.includes(cle) ? l.filter((c) => c !== cle) : [...l, cle]))
  const projetChoisi = projets.find((p) => p.id === projetId)
  const rien = actif && lu && lignes.length === 0 && projetsTrouves.length === 0

  return (
    <CoquilleTaches
      ecran="recherche"
      titre="Recherche"
      feuille={actions.feuille}
      conflit={actions.conflit}
      selecteurProjet={actions.selecteurProjet ?? {
        ouverte: selecteur, onFermer: () => setSelecteur(false), projets, sansProjet: false,
        onChoisir: (id) => { setProjetId(id); setSelecteur(false) },
        onNouveau: () => setSelecteur(false),
      }}
    >
      <div className="recherche-champ">
        <Search className="i i-16" aria-hidden="true" />
        <input
          type="search"
          className="champ"
          aria-label="Chercher dans mes tâches"
          placeholder="Chercher dans mes tâches"
          autoComplete="off"
          value={saisie}
          onChange={(e) => setSaisie(e.target.value)}
        />
      </div>

      <div className="puces" aria-label="Filtres">
        <button type="button" className="puce" role="checkbox" aria-checked={faites} onClick={() => setFaites((v) => !v)}>Faites aussi</button>
        <button
          type="button"
          className="puce"
          aria-haspopup="dialog"
          aria-pressed={projetId != null}
          onClick={() => { chargerProjets(); if (projetId != null) setProjetId(null); else setSelecteur(true) }}
        >
          {projetId != null ? `Projet : ${projetChoisi?.nom ?? '…'} ×` : 'Projet ▾'}
        </button>
        <button type="button" className="puce" role="checkbox" aria-checked={haute} onClick={() => setHaute((v) => !v)}>Priorité haute</button>
        <button type="button" className="puce vide" aria-expanded={replie} onClick={() => setReplie((v) => !v)}>Plus de filtres</button>
      </div>

      {replie ? (
        <div className="recherche-replies">
          <div className="puces" aria-label="Plus de filtres">
            {PUCES_JOUR.map(([cle, libelle]) => (
              <button key={cle} type="button" className="puce" role="checkbox" aria-checked={puces.includes(cle)} onClick={() => basculerPuce(cle)}>{libelle}</button>
            ))}
            <button type="button" className="puce" role="checkbox" aria-checked={reserve} onClick={() => setReserve((v) => !v)}>En réserve</button>
          </div>
          {etiquettes.length > 0 ? (
            <label className="champ-etiquette">
              <span>Étiquette</span>
              <select className="champ" value={etiquetteId ?? ''} onChange={(e) => setEtiquetteId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Toutes</option>
                {etiquettes.map((e) => <option key={e.id} value={e.id}>{e.nom}</option>)}
              </select>
            </label>
          ) : null}
          <label className="champ-etiquette">
            <span>Tri</span>
            <select className="champ" value={tri} onChange={(e) => setTri(e.target.value)}>
              {TRIS.map(([cle, libelle]) => <option key={cle} value={cle}>{libelle}</option>)}
            </select>
          </label>
        </div>
      ) : null}

      {erreur ? <p className="erreur-champ" role="alert">{erreur}</p> : null}

      {projetsTrouves.length > 0 ? (
        <div className="liste" role="list" aria-label="Projets trouvés">
          {projetsTrouves.map((p) => (
            <button key={p.id} type="button" role="listitem" className="fiche-ligne" data-p={p.couleur} onClick={() => navigate(`/taches/projets/${p.id}`)}>
              <span><i className="point" aria-hidden="true" /> {p.nom}</span>
            </button>
          ))}
        </div>
      ) : null}

      <Groupe titre="Ouvertes" lignes={ouvertes} onOuvrir={ouvrirFiche} onTerminer={terminer} onAction={action} />
      <Groupe titre="Faites" lignes={faitesLignes} onOuvrir={ouvrirFiche} onTerminer={terminer} onAction={action} />

      {rien ? (
        <div className="vide-etat">
          <p className="vide-phrase">{mots ? `Rien pour « ${mots} »` : 'Rien pour ces filtres'}</p>
        </div>
      ) : null}
    </CoquilleTaches>
  )
}
