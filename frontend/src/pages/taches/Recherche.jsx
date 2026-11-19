import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ChevronDown, CircleX, Search } from 'lucide-react'

import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { frenchError } from '../../lib/frenchError'
import {
  annulerGeste, classerErreur, creerVue, listerToutesLesEtiquettes, listerTousLesProjets, listerVues, rouvrirTache,
  terminerTache, listerTaches, rechercher, listerToutesLesTaches } from '../../api/tachesApi'
import { proposerAnnuler } from '../../features/taches/lib/gestes'
import { useClavierListe } from '../../features/taches/lib/clavierListe'
import { annulerEtRecaler, versionDe } from '../../features/taches/lib/versions'
import { ABR_JOURS, accord, aujourdhuiIso, ecartJours } from '../../features/taches/lib/textes'
import LigneTache from '../../features/taches/ui/LigneTache'
import { useActionsLigne } from '../../features/taches/ui/ActionsLigne'
import { useOuvrirFiche } from '../../features/taches/lib/fiche'
import { ajouterJours } from '../../features/taches/ui/SelecteurQuand'

/* ============================================================================
   TCH87 — Recherche (`/taches/recherche?q=`) : un champ « Chercher dans mes tâches », deux groupes
   « Ouvertes ({n}) » puis « Faites ({n}) ». Filtres visibles : Faites cette semaine (R2-124 : groupes par jour,
   « Aujourd'hui (n) », « Hier (n) », « mar. 17 (n) ») · Faites aussi · Projet ▾ · Priorité haute ;
   repliés : Aujourd'hui · À revoir · 7 prochains jours · Sans date · En attente · En réserve · Avec échéance ·
   Étiquette ▾, le tri, « Enregistrer cette vue » (« Nom de la vue ») et les vues déjà enregistrées (TCH166 : un
   appui les rouvre, mêmes filtres). Vide : « Rien pour « {q} » ».
   D'OÙ VIENNENT LES LIGNES : sans filtre côté serveur, `recherche/` (projets + tâches par mots) ; dès que
   Faites aussi, Projet, Priorité haute, Étiquette ou En réserve est posé, `taches/` (liste paginée, filtres
   de l'API) ; les puces de jour (Aujourd'hui, 7 jours…) et le tri s'appliquent ensuite sur les lignes lues,
   d'après leurs dates. La dernière liste reste affichée si une lecture échoue (hors ligne).
   Maquettes : recherche.html, recherche-filtres.html, recherche-vide.html.
   ========================================================================== */

const DELAI_MS = 300
const REPRISE_FOCUS_MS = 1500
const TRIS = [['manuel', 'Manuel'], ['priorite', 'Priorité'], ['echeance', 'Échéance'], ['jour', 'Jour'], ['creation', 'Création']]
const PUCES_JOUR = [
  ['aujourdhui', "Aujourd'hui"], ['a_revoir', 'À revoir'], ['sept_jours', '7 prochains jours'], ['sans_date', 'Sans date'],
  ['en_attente', 'En attente'], ['avec_echeance', 'Avec échéance'],
]

// StatutTache : a_faire · en_attente · fait · annule (« abandonnée » à l'écran)
const ouverte = (t) => t.statut !== 'fait' && t.statut !== 'annule'

/* R2-124 — « Faites cette semaine » (le Journal de Things) : `GET taches/?periode=faites_semaine` sert les faites depuis
   lundi, la plus récente d'abord ; l'écran les groupe par jour de `fait_le` (heure murale servie : la date est la
   partie avant « T »). Le filtre vit dans l'adresse (`?periode=faites_semaine`) : retour arrière et lien gardent la vue. */
const FAITES_SEMAINE = 'faites_semaine'

/** « Aujourd'hui » · « Hier » · « mar. 17 » : le titre du groupe d'un jour de la semaine. */
function titreDuJourFait(jour, aujourdhui) {
  const ecart = ecartJours(jour, aujourdhui)
  if (ecart === 0) return "Aujourd'hui"
  if (ecart === -1) return 'Hier'
  const [annee, mois, quantieme] = jour.split('-').map(Number)
  return `${ABR_JOURS[new Date(Date.UTC(annee, mois - 1, quantieme)).getUTCDay()]} ${quantieme}`
}

/** Les lignes groupées par jour où elles ont été faites, le plus récent en haut (ordre du serveur gardé dans un jour). */
function parJourFait(lignes, aujourdhui) {
  const groupes = new Map()
  lignes.forEach((t) => {
    const jour = String(t.fait_le ?? '').split('T')[0]
    if (!jour) return
    if (!groupes.has(jour)) groupes.set(jour, [])
    groupes.get(jour).push(t)
  })
  return [...groupes.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([jour, taches]) => ({ jour, titre: titreDuJourFait(jour, aujourdhui), taches }))
}

/** Puces servies par `GET taches/?periode=` (aujourdhui : jour prévu = J ; semaine : J à J+6) ; ET entre les deux = J. */
function periodeServie(puces) {
  if (puces.includes('aujourdhui')) return 'aujourdhui'
  if (puces.includes('sept_jours')) return 'semaine'
  return null
}

/** Tris servis par `GET taches/?tri=` (rang par défaut) ; « Jour » et « Création » restent triés ici. */
const TRI_SERVI = { priorite: 'priorite', echeance: 'echeance' }

/** Ce que l'écran garde d'une vue (clés FERMÉES du serveur, donnees.md §2.16). `null` quand un filtre n'a pas de
 *  clé (En réserve, À revoir, Sans date, tris Jour et Création) : l'enregistrer perdrait ce filtre à la
 *  réouverture, donc on ne l'enregistre pas. */
function filtresDeLEcran({ q, faites, haute, reserve, projetId, etiquetteId, puces, tri, semaine }) {
  if (reserve || puces.includes('a_revoir') || puces.includes('sans_date') || tri === 'jour' || tri === 'creation') return null
  const filtres = { inclure_faites: Boolean(faites) }
  if (q.trim()) filtres.q = q.trim()
  if (projetId != null) filtres.projets = [projetId]
  if (etiquetteId != null) filtres.etiquettes = [etiquetteId]
  if (haute) filtres.priorite_min = 3
  if (puces.includes('en_attente')) filtres.statuts = ['en_attente']
  const periode = semaine ? FAITES_SEMAINE : periodeServie(puces)
  if (periode) filtres.periode = periode
  if (puces.includes('avec_echeance')) filtres.echeance = true
  if (TRI_SERVI[tri]) filtres.tri = TRI_SERVI[tri]
  return filtres
}

/** Les réglages de l'écran qui rendent les `filtres` d'une vue (l'inverse de `filtresDeLEcran`). */
function ecranDeLaVue(filtres) {
  const puces = []
  if (filtres.periode === 'aujourdhui') puces.push('aujourdhui')
  if (filtres.periode === 'semaine') puces.push('sept_jours')
  if (filtres.statuts?.includes('en_attente')) puces.push('en_attente')
  if (filtres.echeance) puces.push('avec_echeance')
  return {
    q: filtres.q ?? '',
    faites: Boolean(filtres.inclure_faites),
    haute: (filtres.priorite_min ?? 0) >= 3,
    projetId: filtres.projets?.[0] ?? null,
    etiquetteId: filtres.etiquettes?.[0] ?? null,
    puces,
    tri: TRI_SERVI[filtres.tri] ? filtres.tri : 'manuel',
    semaine: filtres.periode === FAITES_SEMAINE,
  }
}

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

/* Recherche tolérante (R2-129) : sans accents ni majuscules, et UNE faute de frappe au plus par mot (lettre oubliée,
   en trop, changée ou deux lettres échangées). Elle ne sert que quand la recherche du serveur ne trouve RIEN ; un mot de
   moins de 4 lettres n'est jamais deviné. */
const MOT_TOLERE_MIN = 4
const sansAccents = (texte) => String(texte ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const motsDe = (texte) => sansAccents(texte).split(/[^a-z0-9]+/).filter(Boolean)

/** Vrai si `a` et `b` diffèrent d'une faute au plus. */
function uneFauteAuPlus(a, b) {
  if (a === b) return true
  const [court, long] = a.length <= b.length ? [a, b] : [b, a]
  if (long.length - court.length > 1) return false
  let i = 0
  while (i < court.length && court[i] === long[i]) i += 1
  if (long.length === court.length) {
    return court.slice(i + 1) === long.slice(i + 1)
      || (court[i] === long[i + 1] && court[i + 1] === long[i] && court.slice(i + 2) === long.slice(i + 2))
  }
  return court.slice(i) === long.slice(i + 1)
}

/** La tâche contient-elle chaque mot cherché, à une faute près ? (titre et nom du projet) */
function correspondDePres(tache, mots) {
  const lus = motsDe(`${tache.titre} ${tache.projet?.nom ?? ''}`)
  const plein = sansAccents(`${tache.titre} ${tache.projet?.nom ?? ''}`)
  return motsDe(mots).every((mot) => plein.includes(mot) || (mot.length >= MOT_TOLERE_MIN && lus.some((lu) => (
    uneFauteAuPlus(mot, lu) || uneFauteAuPlus(mot, lu.slice(0, mot.length)) || uneFauteAuPlus(mot, lu.slice(0, mot.length + 1))))))
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
        {lignes.map((item) => <LigneTache key={`${item.type}:${item.id}`} item={item} contexte="recherche" {...rappels} />)}
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
  const [vues, setVues] = useState([])
  const [nomVue, setNomVue] = useState('')
  const [erreurVue, setErreurVue] = useState('')
  const [prochesLues, setProches] = useState(null) // { pour: les mots, lignes: [...] } — [] : rien de proche non plus
  const champ = useRef(null)

  // Le curseur est dans le champ à l'ouverture : on tape directement (R2-129)
  // après le focus que l'ERP pose sur la zone de contenu à chaque navigation (RouteFocus, un effet parent qui passe APRÈS celui-ci)
  const poserChamp = useCallback((el) => { champ.current = el; if (el) { el.focus(); requestAnimationFrame(() => { if (document.activeElement !== el) el.focus() }) } }, [])
  // L'ERP déplace aussi le focus sur la zone de contenu après la navigation, et encore quand ses textes finissent de
  // charger (chargement direct de l'adresse) : dans la seconde et demie qui suit l'ouverture, ce déplacement rend le
  // curseur au champ ; passé ce délai, ou dès que l'utilisateur a mis le focus ailleurs, on ne touche plus à rien.
  useEffect(() => {
    const ouverture = Date.now()
    const reprendre = (e) => { if (e.target?.id === 'contenu' && Date.now() - ouverture < REPRISE_FOCUS_MS) champ.current?.focus() }
    document.addEventListener('focusin', reprendre)
    return () => document.removeEventListener('focusin', reprendre)
  }, [])

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

  const semaine = params.get('periode') === FAITES_SEMAINE
  const poserSemaine = useCallback((actif) => setParams((actuels) => {
    const suite = new URLSearchParams(actuels)
    if (actif) suite.set('periode', FAITES_SEMAINE)
    else suite.delete('periode')
    return suite
  }, { replace: true }), [setParams])
  const periode = semaine ? FAITES_SEMAINE : periodeServie(puces)
  const triServi = TRI_SERVI[tri]
  const serveur = faites || haute || reserve || projetId != null || etiquetteId != null || periode != null
  const mots = q.trim()

  useEffect(() => {
    if (!serveur && !mots) return undefined
    let courant = true
    const filtres = {
      q: mots || undefined,
      projet: projetId ?? undefined,
      etiquette: etiquetteId ?? undefined,
      priorite_min: haute ? 3 : undefined,
      inclure_faites: faites ? true : undefined,
      vue: reserve ? 'quelque_jour' : undefined,
      periode: periode ?? undefined, // Raccord F2 : « Aujourd'hui » / « 7 jours » servis ; R2-124 « Faites cette semaine »
      tri: triServi,
    }
    // Liste paginée (50) : la page 1 suffit tant que `next` est vide, sinon on lit tout (api.md §0).
    const lecture = serveur
      ? listerTaches(filtres).then(async (r) => ({
        projets: [], taches: r.data?.next ? await listerToutesLesTaches(filtres) : (r.data?.results ?? []),
      }))
      : rechercher({ q: mots, limite: 25 }).then((r) => ({ projets: r.data?.projets ?? [], taches: r.data?.taches ?? [] }))
    lecture
      .then((suite) => { if (courant) { setResultat(suite); setLu(true); setErreur('') } })
      .catch((err) => { if (courant) setErreur(frenchError(err)) })
    return () => { courant = false }
  }, [mots, serveur, faites, haute, reserve, projetId, etiquetteId, periode, triServi])

  // Rien trouvé par les mots seuls : une seconde lecture, tolérante aux accents et à une faute de frappe
  const aucunResultat = lu && !serveur && mots.length > 0 && resultat.taches.length === 0 && resultat.projets.length === 0
  const cherchePres = aucunResultat && mots.length >= MOT_TOLERE_MIN
  useEffect(() => {
    if (!cherchePres) return undefined
    let courant = true
    listerToutesLesTaches({ inclure_faites: true })
      .then((toutes) => { if (courant) setProches({ pour: mots, lignes: toutes.filter((t) => correspondDePres(t, mots)) }) })
      .catch(() => { if (courant) setProches({ pour: mots, lignes: [] }) })
    return () => { courant = false }
  }, [cherchePres, mots])
  const proches = cherchePres && prochesLues?.pour === mots ? prochesLues.lignes : null

  const chargerProjets = useCallback(() => {
    if (projets.length === 0) listerTousLesProjets().then(setProjets).catch((err) => setErreur(frenchError(err)))
  }, [projets.length])
  // Sans étiquette au compte, le filtre « Étiquette » n'apparaît pas (textes.md « Recherche »).
  const [etiquettesLues, setEtiquettesLues] = useState(false)
  useEffect(() => {
    if (!replie || etiquettesLues) return
    listerToutesLesEtiquettes()
      .then(setEtiquettes)
      .catch(() => setEtiquettes([]))
      .finally(() => setEtiquettesLues(true))
  }, [replie, etiquettesLues])

  // Les vues enregistrées (`vues/`, ≤ 30, `{"results"}`) : lues une fois, à l'ouverture des filtres repliés.
  const [vuesLues, setVuesLues] = useState(false)
  useEffect(() => {
    if (!replie || vuesLues) return
    listerVues()
      // liste fermée, plafonnée par le serveur (30 vues au plus, non paginée) : jamais de page suivante
      .then((r) => { const { results } = r.data; setVues(results ?? []) })
      .catch((err) => setErreurVue(frenchError(err)))
      .finally(() => setVuesLues(true))
  }, [replie, vuesLues])

  const filtresAEnregistrer = filtresDeLEcran({ q: saisie, faites, haute, reserve, projetId, etiquetteId, puces, tri, semaine })
  const rouvrirVue = (vue) => {
    const suite = ecranDeLaVue(vue.filtres ?? {})
    setSaisie(suite.q); setFaites(suite.faites); setHaute(suite.haute); setReserve(false)
    setProjetId(suite.projetId); setEtiquetteId(suite.etiquetteId); setPuces(suite.puces); setTri(suite.tri)
    poserSemaine(suite.semaine)
    if (suite.projetId != null) chargerProjets()
    setErreurVue('')
  }
  const enregistrerVue = async () => {
    try {
      const { data } = await creerVue({ nom: nomVue.trim(), filtres: filtresAEnregistrer })
      const { geste_id: geste, ...vue } = data
      setVues((liste) => [...liste, vue])
      setNomVue(''); setErreurVue('')
      proposerAnnuler({
        message: 'Vue enregistrée',
        onAnnuler: geste ? async () => { await annulerGeste(geste); setVues((liste) => liste.filter((v) => v.id !== vue.id)) } : undefined,
      })
    } catch (err) {
      setErreurVue(classerErreur(err).champs?.nom?.[0] || classerErreur(err).champs?.filtres?.[0] || frenchError(err))
    }
  }

  const actif = serveur || Boolean(mots)
  const approches = cherchePres && proches !== null && proches.length > 0
  const source = approches ? proches : resultat.taches
  const lignes = useMemo(() => (actif ? source : [])
    .filter((t) => puces.every((p) => correspond(t, p, aujourdhui)))
    .sort(TRI[tri]), [actif, source, puces, tri, aujourdhui])
  const ouvertes = lignes.filter(ouverte)
  const faitesLignes = lignes.filter((t) => !ouverte(t))
  // une tâche rouverte ici reste dans son jour, case vide : on la recoche sans la chercher (geste réversible sur place)
  const joursFaits = semaine ? parJourFait(lignes, aujourdhui) : []
  const projetsTrouves = serveur || !actif ? [] : resultat.projets

  const ouvrirLaFiche = useOuvrirFiche()
  const ouvrirFiche = (item) => ouvrirLaFiche(item.id)
  const majLigne = (id, suite) => setResultat((r) => ({ ...r, taches: r.taches.map((t) => (t.id === id ? { ...t, ...suite } : t)) }))

  const terminer = async (item, suivant) => {
    const { data } = await (suivant ? terminerTache(item.id, {}) : rouvrirTache(item.id))
    majLigne(item.id, { statut: data?.tache?.statut ?? (suivant ? 'fait' : 'a_faire') })
    if (suivant) {
      proposerAnnuler({
        message: 'Faite',
        onAnnuler: data?.geste_id ? async () => {
          const retour = await annulerEtRecaler(data.geste_id, [item.id]) // la version change : la ligne garde celle du serveur
          majLigne(item.id, { statut: 'a_faire', lock_version: versionDe(retour, item.id, item.lock_version) })
        } : undefined,
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

  // Clavier des résultats (R2-036, choix C-10) : j/k de ligne en ligne, Espace coche, e/h ouvre la fiche ; jamais une
  // touche seule qui fait disparaître une ligne. Muet dans le champ de recherche et sous un dialogue.
  const racine = useClavierListe((touche, { cle }) => {
    const item = cle ? lignes.find((t) => `${t.type}:${t.id}` === cle) : null
    if (!item) return
    if (touche === 'terminer') terminer(item, ouverte(item)).catch((err) => setErreur(frenchError(err)))
    else if (touche === 'renommer' || touche === 'heure') ouvrirFiche(item)
  }, { actif: !actions.feuille && !actions.selecteurProjet && !selecteur })

  const basculerPuce = (cle) => setPuces((l) => (l.includes(cle) ? l.filter((c) => c !== cle) : [...l, cle]))
  const projetChoisi = projets.find((p) => p.id === projetId)
  const rien = actif && lu && lignes.length === 0 && projetsTrouves.length === 0 && !(cherchePres && proches === null)

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
      {/* recherche.html : la loupe DANS le champ, le champ aligné sur le contenu (gouttière), les filtres dessous */}
      <div className="es-recherche">
        <label className="es-champ">
          <Search className="i" aria-hidden="true" />
          <input
            ref={poserChamp}
            type="search"
            className="valeur"
            aria-label="Chercher dans mes tâches"
            placeholder="Chercher dans mes tâches"
            autoComplete="off"
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
          />
          {saisie ? (
            <button type="button" className="es-effacer" aria-label="Effacer la recherche" onClick={() => { setSaisie(''); champ.current?.focus() }}>
              <CircleX className="i i-16" aria-hidden="true" />
            </button>
          ) : null}
        </label>
      </div>

      <div className="puces es-filtres" aria-label="Filtres">
        <button type="button" className="puce" role="checkbox" aria-checked={semaine} onClick={() => poserSemaine(!semaine)}>Faites cette semaine</button>
        <button type="button" className="puce" role="checkbox" aria-checked={faites} onClick={() => setFaites((v) => !v)}>Faites aussi</button>
        <button
          type="button"
          className="puce"
          aria-haspopup="dialog"
          aria-pressed={projetId != null}
          onClick={() => { chargerProjets(); if (projetId != null) setProjetId(null); else setSelecteur(true) }}
        >
          {projetId != null ? `Projet : ${projetChoisi?.nom ?? '…'} ×` : <>Projet<ChevronDown className="i i-16" aria-hidden="true" /></>}
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
          {vues.length > 0 ? (
            <div className="puces" role="group" aria-label="Mes vues">
              {vues.map((vue) => <button key={vue.id} type="button" className="puce" onClick={() => rouvrirVue(vue)}>{vue.nom}</button>)}
            </div>
          ) : null}
          <div className="recherche-vue">
            <input
              type="text"
              className="champ"
              aria-label="Nom de la vue"
              placeholder="Nom de la vue"
              maxLength={60}
              value={nomVue}
              onChange={(e) => { setNomVue(e.target.value); setErreurVue('') }}
              onKeyDown={(e) => { if (e.key === 'Enter' && filtresAEnregistrer) { e.preventDefault(); enregistrerVue() } }}
            />
            <button type="button" className="bouton second" disabled={!filtresAEnregistrer} onClick={enregistrerVue}>Enregistrer cette vue</button>
          </div>
          {erreurVue ? <p className="erreur-champ" role="alert">{erreurVue}</p> : null}
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

      {/* passe visuelle n° 46 (recherche.html) : le mot cherché surligné, la méta de statut de chaque résultat */}
      {approches ? <p className="es-sous es-approche" role="status">{`Rien de tel pour « ${mots} » : voici ce qui s'en approche.`}</p> : null}
      {semaine && lignes.length > 0 ? <p className="es-sous" role="status">{`${accord(lignes.length, 'faite')} depuis lundi`}</p> : null}
      <div ref={racine} className="es-resultats">
        {semaine ? joursFaits.map((groupe) => (
          <Groupe key={groupe.jour} titre={groupe.titre} lignes={groupe.taches} aujourdhui={aujourdhui} surligne={mots} onOuvrir={ouvrirFiche} onTerminer={terminer} onAction={action} />
        )) : (
          <>
            <Groupe titre="Ouvertes" lignes={ouvertes} aujourdhui={aujourdhui} surligne={approches ? '' : mots} onOuvrir={ouvrirFiche} onTerminer={terminer} onAction={action} />
            <Groupe titre="Faites" lignes={faitesLignes} aujourdhui={aujourdhui} surligne={approches ? '' : mots} onOuvrir={ouvrirFiche} onTerminer={terminer} onAction={action} />
          </>
        )}
      </div>

      {rien ? (
        <div className="vide-etat">
          <span className="vide-picto"><Search className="i" aria-hidden="true" /></span>
          <p className="vide-phrase">{mots ? `Rien pour « ${mots} »` : (semaine ? 'Rien de fait depuis lundi' : 'Rien pour ces filtres')}</p>
        </div>
      ) : null}
    </CoquilleTaches>
  )
}
