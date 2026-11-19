import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import CoquilleTaches, { EVENEMENT_SAISIE_FERMEE, EVENEMENT_SAISIR, SaisieBureau } from '../../features/taches/coquille/CoquilleTaches'
import { lireBrouillon } from '../../features/taches/saisie/FeuilleSaisie'
import { useApresCreation, useOuvrirFiche } from '../../features/taches/lib/fiche'
import Sections, {
  BandeauPasAJour, EtatVide, PHRASE_HORS_LIGNE, Squelette,
} from '../../features/taches/aujourdhui/Sections'
import { FeuilleLier, useLierActivite } from '../../features/taches/aujourdhui/LignesErp'
import Replies, { useARevoir } from '../../features/taches/aujourdhui/Replies'
import FeuilleBilan from '../../features/taches/aujourdhui/FeuilleBilan'
import FeuilleAlleger from '../../features/taches/aujourdhui/FeuilleAlleger'
import { actionsJournee, useModesJournee } from '../../features/taches/aujourdhui/MenuJournee'
import ColonneBureau, { ColonneProjets } from '../../features/taches/aujourdhui/ColonneBureau'
import Propose from '../../features/taches/aujourdhui/Propose'
import Progression from '../../features/taches/aujourdhui/Progression'
import CarteDuMoment from '../../features/taches/ui/CarteDuMoment'
import { useActionsLigne } from '../../features/taches/ui/ActionsLigne'
import { annoncer, annulerToast, fermerToast, proposerAnnuler, useEtatGestes } from '../../features/taches/lib/gestes'
import { useClavierListe } from '../../features/taches/lib/clavierListe'
import { useCompteTaches, useEnLigne } from '../../features/taches/lib/enLigne'
import { ecrireJournee, lireJournee } from '../../features/taches/horsligne/cacheJournee'
import { MESSAGE_EN_FILE as TOAST_EN_FILE, enfilerCoche, enfilerReport } from '../../features/taches/horsligne/captureQueue'
import { accord, aujourdhuiIso, heureDuConflit, jourCourt, jourLong, jourNomme } from '../../features/taches/lib/textes'
import * as client from '../../api/tachesApi'
import { annulerEtRecaler, versionDe } from '../../features/taches/lib/versions'
import recordsApi from '../../api/recordsApi'
import { originFrom } from '../../api/origin'
import { frenchError } from '../../lib/frenchError'
import { EVENEMENT_OUVRIR } from '../../features/ia/copilotMessages'

/* ============================================================================
   TCH76 — Écran « Aujourd'hui » (route /taches/aujourdhui) : l'écran que le fondateur ouvre
   chaque jour sur son iPhone. Il lit `GET aujourdhui/` (contract_samples/aujourdhui.json) et
   rend les sections dans l'ordre vertical de regles.md §4.1 (features/taches/aujourdhui/Sections).
   Règles tenues ici, une fois pour toutes :
     · squelette seulement après 1 s sans réponse, jamais sur une liste déjà affichée ;
     · un rafraîchissement en échec GARDE la liste : bandeau « Pas à jour · HH:MM » [Réessayer] ;
     · relecture au retour du focus ; hors ligne, la lecture reste affichée et les gestes sont
       grisés (« Possible une fois connecté ») ;
     · un geste (cocher, reporter, ★) est optimiste puis réconcilié par la réponse du serveur :
       il ne relit jamais toute la liste ; le toast « … · Annuler » défait par `gestes/{id}/annuler/` ;
     · TCH152 — au bureau (≥ 1024 px) la liste a l'Agenda du jour à sa droite et « Mes projets » à sa
       gauche (`ColonneBureau`) : glisser une ligne sur un créneau lui donne une heure. L'iPhone n'en monte rien.
   Maquettes : ecran-aujourdhui-*.html, etat-chargement.html, etat-pas-a-jour.html.
   ========================================================================== */

const DELAI_SQUELETTE_MS = 1000
const MAX_ESSENTIELLES = 3 // regles.md §4.1 « 3 au plus » (même plafond que `ui/Etoile`)
/** R2-012 — la 4e étoile est refusée À L'ÉCRAN (un toast), pas seulement au lecteur d'écran. */
const refuserEssentielle = () => proposerAnnuler({ message: "3 essentielles au plus — retire une étoile d'abord" })
const MEDIA_BUREAU = '(min-width: 1024px)'
const cleDe = (item) => `${item.type}:${item.id}`
const heureDe = (iso) => String(iso ?? '').slice(11, 16)

/** Les listes d'items du contrat (hors `propose`), dans l'ordre vertical. */
const LISTES_ITEMS = ['essentiel', 'journee', 'ce_soir', 'a_decider', 'en_attente', 'faites']

/** Applique `fn` à chaque item de la journée (toutes sections, Proposé compris) ; `fn` rend l'item, modifié ou non. */
function mapItems(donnees, fn) {
  if (!donnees) return donnees
  const lire = (liste) => (Array.isArray(liste) ? liste.map(fn) : liste)
  const suite = donnees.propose?.suite_par_projet
  const propose = donnees.propose ? {
    ...donnees.propose,
    pour_objectif: lire(donnees.propose.pour_objectif),
    suite_par_projet: Array.isArray(suite) ? suite.map((groupe) => ({ ...groupe, items: lire(groupe.items) })) : suite,
  } : donnees.propose
  return { ...donnees, ...Object.fromEntries(LISTES_ITEMS.map((cle) => [cle, lire(donnees[cle])])), propose }
}

/** Vrai si la journée ne porte AUCUNE ligne (ni tâche, ni activité, ni obligation, ni rendez-vous, ni proposition). */
function journeeVide(donnees) {
  const rien = (liste) => !Array.isArray(liste) || liste.length === 0
  const propose = donnees.propose ?? {}
  return LISTES_ITEMS.every((cle) => rien(donnees[cle]))
    && rien(donnees.obligations) && rien(donnees.rendez_vous)
    && rien(propose.pour_objectif) && rien(propose.suite_par_projet) && !(propose.reste_nb > 0)
}

/** « 15:02 » d'un instant ISO écrit par le cache (heure de l'appareil). */
function heureLocale(iso) {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/**
 * Lit `aujourdhui/` : squelette tardif, liste gardée sur échec, relecture au focus.
 * Raccord F2 (TCH100) — la journée lue est gardée dans le cache du compte (`cacheJournee`) ; sans réseau, l'écran
 * s'ouvre sur ce cache (« Hors ligne · dernière synchro à {HH:MM} ») au lieu d'un écran vide.
 */
function useAujourdhui(tout, userId) {
  const [donnees, setDonnees] = useState(null)
  const [erreur, setErreur] = useState(false)
  const [derniere, setDerniere] = useState('')
  const [squelette, setSquelette] = useState(false)
  const enLigne = useEnLigne()
  const vivant = useRef(true)
  const presentes = useRef(false)
  const vuFait = useRef(false)
  const synchro = useRef(null)

  const charger = useCallback(async () => {
    const minuteur = presentes.current ? null : setTimeout(() => setSquelette(true), DELAI_SQUELETTE_MS)
    try {
      const { data } = await client.lireAujourdhui(tout ? { tout: 1 } : undefined)
      if (!vivant.current) return
      presentes.current = true
      synchro.current = new Date()
      setDonnees(data)
      setErreur(false)
      setDerniere(heureDe(data.maintenant))
    } catch {
      if (!vivant.current) return
      setErreur(true)
      const cache = presentes.current || userId === null ? null : lireJournee(userId, aujourdhuiIso())
      if (cache?.donnees) {
        presentes.current = true
        setDonnees(cache.donnees)
        setDerniere(heureLocale(cache.ecrit_a))
      }
    } finally {
      if (minuteur) clearTimeout(minuteur)
      if (vivant.current) setSquelette(false)
    }
  }, [tout, userId])

  // le cache suit l'écran (gestes optimistes compris), daté de la dernière lecture RÉUSSIE
  useEffect(() => {
    if (donnees?.jour && userId !== null && synchro.current) ecrireJournee(userId, donnees.jour, donnees, synchro.current)
  }, [donnees, userId])

  useEffect(() => {
    vivant.current = true
    // « vu » d'abord : il crée la carte `retour` que la lecture suivante porte (api.md §4 `vu/`) ; un échec ne bloque pas la lecture
    const vu = vuFait.current || navigator.onLine === false ? Promise.resolve() : Promise.resolve(client.marquerVu({ ecran: 'aujourdhui' }))
    vuFait.current = true
    vu.then(charger, charger)
    return () => { vivant.current = false }
  }, [charger])

  useEffect(() => {
    const relire = () => { if (document.visibilityState !== 'hidden' && navigator.onLine !== false) charger() }
    window.addEventListener('focus', relire)
    document.addEventListener('visibilitychange', relire)
    return () => {
      window.removeEventListener('focus', relire)
      document.removeEventListener('visibilitychange', relire)
    }
  }, [charger])

  return { donnees, setDonnees, erreur, derniere, squelette: squelette && !donnees, enLigne, charger }
}

/** L'item de la journée portant cette clé (`tache:20`), dans n'importe quelle section. */
function chercher(donnees, cle) {
  let trouve = null
  mapItems(donnees, (it) => { if (cleDe(it) === cle && !trouve) trouve = it; return it })
  return trouve
}

/**
 * Retire un item de TOUTES ses listes (une essentielle faite est servie dans `essentiel` ET `faites` — regles.md §4.1
 * ligne 3, D-V1) ; rend la journée amputée et ses `origines` (`{ liste, rang, item }`, une par liste) pour la remettre.
 */
function retirer(donnees, cle) {
  const origines = []
  let suite = donnees
  for (const liste of LISTES_ITEMS) {
    const items = donnees[liste] ?? []
    const rang = items.findIndex((it) => cleDe(it) === cle)
    if (rang >= 0) {
      origines.push({ liste, rang, item: items[rang] })
      suite = { ...suite, [liste]: items.filter((it) => cleDe(it) !== cle) }
    }
  }
  if (origines.length === 0) return { suite: mapItems(donnees, (it) => it), origines, item: null }
  return { suite, origines, item: origines[0].item }
}

/** Remet chaque origine rendue par `retirer` dans sa liste, à son rang (Annuler, refus du serveur). */
function remettre(donnees, { origines = [] }) {
  return origines.reduce((d, { liste, rang, item }) => {
    const suite = [...(d[liste] ?? [])]
    suite.splice(Math.min(rang, suite.length), 0, item)
    return { ...d, [liste]: suite }
  }, donnees)
}

/**
 * Pose ou ôte la ★ comme la relecture la rangera (`selectors/journee.py::_ranger`, regles.md §4.1 ligne 3, D-V1) :
 * une ouverte passe d'Essentiel à Prévu (ou l'inverse) ; une FAITE n'est jamais dans Prévu — avec ★ elle est dans
 * Essentiel ET Faites, sans ★ dans Faites seule. Toutes ses occurrences prennent la nouvelle ★. Rend aussi les `origines`.
 */
function rangerEssentielle(donnees, cle, essentielle, lockVersion) {
  const { suite, origines, item } = retirer(donnees, cle)
  if (!item) return { suite: donnees, origines }
  const change = { ...item, essentielle, lock_version: lockVersion ?? item.lock_version }
  if (item.statut !== 'fait') {
    return {
      suite: essentielle
        ? { ...suite, essentiel: [...(suite.essentiel ?? []), change] }
        : { ...suite, journee: [change, ...(suite.journee ?? [])] },
      origines,
    }
  }
  const place = (liste) => ({ liste, rang: origines.find((o) => o.liste === liste)?.rang ?? Infinity, item: change })
  return { suite: remettre(suite, { origines: essentielle ? [place('essentiel'), place('faites')] : [place('faites')] }), origines }
}

/** Vrai au bureau (≥ 1024 px) ; suit le redimensionnement. Sans `matchMedia` (tests), jamais le bureau. */
function useBureau() {
  const lire = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(MEDIA_BUREAU).matches
  const [bureau, setBureau] = useState(lire)
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined
    const requete = window.matchMedia(MEDIA_BUREAU)
    const maj = () => setBureau(requete.matches)
    requete.addEventListener?.('change', maj)
    maj()
    return () => requete.removeEventListener?.('change', maj)
  }, [])
  return bureau
}

/**
 * « Choisir un jour » : un champ date, une seule action (la tâche est prévue ce jour-là). Ouverte au clavier (`d`,
 * spec-7 §5 « Quand (Entrée = Reporter au jour nommé) »), elle arrive sur `initial` — le prochain jour travaillé — et
 * son bouton « Reporter à {jour} » a le focus : Entrée reporte. Entrée dans le champ date valide aussi (formulaire).
 */
function ChoisirJour({ item, minimum, onChoisir, initial = '', reporterA = null }) {
  const [jour, setJour] = useState(initial ?? '')
  const libelle = !jour ? 'Choisis un jour'
    : jour === reporterA ? `Reporter à ${jourNomme(jour, minimum)}` : `Prévue ${jourCourt(jour, minimum)}`
  const valider = (e) => { e.preventDefault(); if (jour) onChoisir(jour) }
  return (
    <form className="choisir-jour" onSubmit={valider}>
      <p className="carte-source">{item.titre}</p>
      <label className="fiche-label" htmlFor="tch-choisir-jour">Jour</label>
      <input id="tch-choisir-jour" type="date" className="champ-date" min={minimum} value={jour} onChange={(e) => setJour(e.target.value)} />
      <button type="submit" className="bouton plein large" disabled={!jour} data-focus-initial={initial ? '' : undefined}>
        {libelle}
      </button>
    </form>
  )
}

/**
 * Le compteur suit un geste (± 1 faite) sans attendre le serveur ; la réponse le recale ensuite quand elle en porte
 * un (`progression` d'une TACHE_ECRITE). Une ligne du plan compte aussi dans « gardées tenues ».
 */
function avancer(progression, item, delta) {
  if (!progression || typeof progression.faites !== 'number') return progression
  const borne = (n) => Math.max(0, n)
  const suite = { ...progression, faites: borne(progression.faites + delta) }
  if (item.prevue_au_plan && typeof progression.plan_tenues === 'number') suite.plan_tenues = borne(progression.plan_tenues + delta)
  if (item.type === 'activite' && typeof progression.activites_closes === 'number') {
    suite.activites_closes = borne(progression.activites_closes + delta)
  }
  return suite
}

/** L'adresse de clôture d'une activité ERP (`recordsApi.markActivityDone`), écrite en entier pour l'envoi qui survit à la page. */
const adresseClore = (id) => `${originFrom(import.meta.env.VITE_API_URL)}/api/django/records/activities/${id}/done/`

/**
 * Clore en PARTANT (onglet fermé, appli passée en arrière-plan) : un `fetch` keepalive, que le navigateur termine
 * même après la page. Refusé (session à rafraîchir…) ou impossible, et la page encore là : l'appel ordinaire
 * (rafraîchissement de session compris) prend le relais.
 */
function cloreEnPartant(id, ordinaire) {
  const envoi = typeof fetch === 'function'
    ? fetch(adresseClore(id), {
      method: 'POST', credentials: 'include', keepalive: true, headers: { 'Content-Type': 'application/json' }, body: '{}',
    })
    : Promise.reject(new Error('fetch indisponible'))
  return envoi.then((reponse) => (reponse.ok ? reponse : ordinaire()), () => ordinaire())
}

/**
 * R2-010 (choix C-9) — Cocher une activité ERP depuis Tâches se DÉFAIT : la ligne passe cochée et le compteur +1 tout
 * de suite, le toast dit « Close dans l'ERP · Annuler », et la clôture (`records/activities/{id}/done/`, sans retour
 * possible côté ERP) ne part qu'au DÉPART du toast — son échéance, sa fermeture, ou un autre toast qui le remplace.
 * « Annuler » (ou décocher pendant le toast) remet la ligne : rien n'est parti. En quittant l'écran, la clôture part
 * aussitôt ; en quittant la PAGE (`pagehide`, onglet caché), par un envoi qui survit à la page : sans cela,
 * l'activité ne serait jamais close. Un refus de l'ERP remet la ligne et s'affiche.
 */
function useClotureDifferee({ patcher, setDonnees }) {
  const enAttente = useRef(new Map()) // `activite:101` → { item, toast } : cochées, pas encore envoyées
  const toastCourant = useRef(null)
  const vivant = useRef(true)
  const { toast } = useEtatGestes()

  const marquer = useCallback((item, fait) => {
    patcher(cleDe(item), (it) => ({ ...it, statut: fait ? 'fait' : 'a_faire' }))
    setDonnees((d) => (d ? { ...d, progression: avancer(d.progression, item, fait ? 1 : -1) } : d))
  }, [patcher, setDonnees])

  const envoyer = useCallback((cle, enPartant = false) => {
    const attente = enAttente.current.get(cle)
    if (!attente) return
    enAttente.current.delete(cle)
    const { item } = attente
    const ordinaire = () => recordsApi.markActivityDone(item.id)
    const envoi = enPartant ? cloreEnPartant(item.id, ordinaire) : ordinaire()
    envoi.catch((err) => {
      if (vivant.current) marquer(item, false)
      proposerAnnuler({ message: `Pas close dans l'ERP : ${frenchError(err)}` })
    })
  }, [marquer])

  // le toast d'une activité cochée est parti (échéance, ×, remplacé) : sa clôture part maintenant
  useEffect(() => {
    toastCourant.current = toast?.id ?? null
    for (const [cle, attente] of enAttente.current) if (attente.toast !== toastCourant.current) envoyer(cle)
  }, [toast, envoyer])

  const partirRef = useRef(() => {})
  useEffect(() => {
    partirRef.current = (enPartant) => {
      if (enAttente.current.size === 0) return
      const leSien = [...enAttente.current.values()].some((a) => a.toast === toastCourant.current)
      for (const cle of [...enAttente.current.keys()]) envoyer(cle, enPartant)
      if (leSien) fermerToast() // son « Annuler » ne pourrait plus rien défaire
    }
  }, [envoyer])
  // abonné une seule fois : un nouveau rendu ne doit jamais « quitter l'écran » (et tout envoyer) au passage
  useEffect(() => {
    vivant.current = true
    const quitterPage = () => partirRef.current(true)
    const cachee = () => { if (document.visibilityState === 'hidden') partirRef.current(true) }
    window.addEventListener('pagehide', quitterPage)
    document.addEventListener('visibilitychange', cachee)
    return () => {
      window.removeEventListener('pagehide', quitterPage)
      document.removeEventListener('visibilitychange', cachee)
      vivant.current = false
      partirRef.current(false) // on quitte l'écran : la page vit encore, l'appel ordinaire suffit
    }
  }, [])

  const cocher = useCallback((item) => {
    const cle = cleDe(item)
    marquer(item, true)
    const id = proposerAnnuler({
      message: "Close dans l'ERP",
      onAnnuler: () => { if (enAttente.current.delete(cle)) marquer(item, false) },
    })
    enAttente.current.set(cle, { item, toast: id })
  }, [marquer])

  /** Décocher pendant le toast = Annuler (vrai) ; une activité déjà envoyée ne se rouvre pas ici (faux). */
  const decocher = useCallback((item) => {
    const cle = cleDe(item)
    const attente = enAttente.current.get(cle)
    if (!attente) return false
    enAttente.current.delete(cle)
    marquer(item, false)
    if (attente.toast === toastCourant.current) fermerToast()
    return true
  }, [marquer])

  return useMemo(() => ({ cocher, decocher }), [cocher, decocher])
}

/** L'identifiant du toast affiché, lu par les gestes (fermer SON toast, jamais celui d'un autre geste). */
function useToastCourant() {
  const { toast } = useEtatGestes()
  const courant = useRef(null)
  useEffect(() => { courant.current = toast?.id ?? null }, [toast])
  return courant
}

export default function Aujourdhui() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const tout = params.get('tout') === '1'
  const { userId, societe } = useCompteTaches()
  // la carte « Ta saisie de tout à l'heure t'attend. » [Reprendre] lit le brouillon de la feuille de saisie
  const [brouillon, setBrouillon] = useState(() => lireBrouillon(societe, userId))
  useEffect(() => {
    const relire = () => setBrouillon(lireBrouillon(societe, userId))
    window.addEventListener(EVENEMENT_SAISIE_FERMEE, relire)
    return () => window.removeEventListener(EVENEMENT_SAISIE_FERMEE, relire)
  }, [societe, userId])
  const { donnees, setDonnees, erreur, derniere, squelette, enLigne, charger } = useAujourdhui(tout, userId)
  const [estampilles, setEstampilles] = useState({})
  const [feuille, setFeuille] = useState(null)
  const [conflit, setConflit] = useState(null)
  const [invite, setInvite] = useState(false)
  const [focusPrevu, setFocusPrevu] = useState(0)
  const bureau = useBureau()
  const [glisse, setGlisse] = useState(null) // la ligne qu'on glisse vers une heure de l'Agenda (bureau seulement)

  const garde = useCallback(() => {
    if (enLigne) return
    annoncer(PHRASE_HORS_LIGNE)
    throw new Error(PHRASE_HORS_LIGNE)
  }, [enLigne])

  const patcher = useCallback((cle, fn) => {
    setDonnees((d) => (d ? mapItems(d, (it) => (cleDe(it) === cle ? fn(it) : it)) : d))
  }, [setDonnees])

  const poserProgression = useCallback((progression) => {
    if (progression && typeof progression.faites === 'number') setDonnees((d) => (d ? { ...d, progression } : d))
  }, [setDonnees])
  const closeErp = useClotureDifferee({ patcher, setDonnees })
  const toastCourant = useToastCourant()
  const rangGeste = useRef(0) // dernier geste optimiste : seule SA réponse recale le statut et le compteur
  const dernierFaite = useRef(null) // { cle, toast } du dernier « Faite » : décocher la même ligne le ferme
  const ecritures = useRef(new Map()) // `tache:42` → dernière écriture en vol : une tâche, une écriture à la fois
  const enchainer = useCallback((cle, ecrire) => {
    const avant = ecritures.current.get(cle) ?? Promise.resolve()
    const envoi = avant.then(ecrire)
    ecritures.current.set(cle, envoi.then(() => null, () => null))
    return envoi
  }, [])

  const terminer = useCallback(async (item, suivant) => {
    const cle = cleDe(item)
    // hors ligne (TCH100) : cocher une tâche part dans la file ; décocher et clore une activité ERP attendent le réseau
    if (!enLigne && item.type === 'tache' && suivant) {
      try {
        await enfilerCoche(item.id)
      } catch (err) {
        annoncer(frenchError(err)) // sans compte connecté, la file refuse : la case revient en arrière
        throw err
      }
      patcher(cle, (it) => ({ ...it, statut: 'fait' }))
      proposerAnnuler({ message: TOAST_EN_FILE, annonce: `Fait : ${item.titre}` })
      return
    }
    garde()
    if (item.type === 'activite') {
      if (suivant) closeErp.cocher(item)
      else if (!closeErp.decocher(item)) throw new Error('Une activité de l’ERP close ne se rouvre pas ici.')
      return
    }
    // R2-011 — OPTIMISTE : barré, compteur et toast AU TOUCHER ; la réponse recale (version, statut, progression) ;
    // un refus remet tout et s'affiche. Les écritures d'une même tâche partent dans l'ordre des gestes.
    const geste = { annule: false, rang: (rangGeste.current += 1) }
    const marquer = (fait) => {
      patcher(cle, (it) => ({ ...it, statut: fait ? 'fait' : 'a_faire' }))
      setDonnees((d) => (d ? { ...d, progression: avancer(d.progression, item, fait ? 1 : -1) } : d))
    }
    marquer(suivant)
    const envoi = enchainer(cle, () => (suivant ? client.terminerTache(item.id) : client.rouvrirTache(item.id)))
    const annuler = async () => {
      geste.annule = true
      rangGeste.current += 1 // une réponse en retard ne recale plus l'écran
      marquer(false)
      const reponse = await envoi.then((r) => r, () => null)
      if (!reponse) return // l'écriture a échoué : rien n'est à défaire côté serveur
      try {
        const retour = await annulerEtRecaler(reponse.data.geste_id, [item.id]) // la version change : on garde celle du serveur
        patcher(cle, (it) => ({ ...it, lock_version: versionDe(retour, item.id, it.lock_version) }))
      } catch (err) {
        marquer(true) // l'annulation est refusée : la tâche reste faite, et le toast le dit
        throw err
      }
    }
    let toastFaite = null
    if (suivant) toastFaite = proposerAnnuler({ message: 'Faite', annonce: `Fait : ${item.titre}`, onAnnuler: annuler })
    else if (dernierFaite.current?.cle === cle && dernierFaite.current.toast === toastCourant.current) fermerToast()
    dernierFaite.current = toastFaite ? { cle, toast: toastFaite } : null
    envoi.then(({ data }) => {
      const aJour = !geste.annule && geste.rang === rangGeste.current
      patcher(cle, (it) => ({
        ...it,
        lock_version: data.tache?.lock_version ?? it.lock_version,
        ...(aJour && data.tache?.statut ? { statut: data.tache.statut } : {}),
      }))
      if (aJour) poserProgression(data.progression)
      const prochaine = data.suivante?.jour_prevu
      if (suivant && prochaine && !geste.annule && toastCourant.current === toastFaite) {
        const message = `Faite · prochaine ${jourNomme(prochaine, donnees?.jour)}`
        toastFaite = proposerAnnuler({ message, onAnnuler: annuler })
        dernierFaite.current = { cle, toast: toastFaite }
      }
    }, (err) => {
      if (geste.annule) return
      marquer(!suivant)
      proposerAnnuler({ message: frenchError(err) })
    })
  }, [garde, enLigne, donnees, patcher, poserProgression, closeErp, setDonnees, enchainer, toastCourant])

  const poserJour = useCallback(async (item, jour, message, lockVersion = item.lock_version) => {
    const cle = cleDe(item)
    if (!enLigne) {
      // hors ligne (TCH100) : reporter / choisir un jour part dans la file, avec le `lock_version` du cache
      try {
        await enfilerReport(item.id, { jour_prevu: jour, moment: '', heure_debut: null, quelque_jour: false, lock_version: lockVersion })
      } catch (err) {
        annoncer(frenchError(err))
        return
      }
      setEstampilles((e) => ({ ...e, [cle]: `→ ${jourNomme(jour, donnees?.jour)}` }))
      proposerAnnuler({ message: TOAST_EN_FILE, annonce: message })
      return
    }
    // R2-011 — OPTIMISTE : « → ven. 20 » et le toast AU RELÂCHER ; la réponse recale la version et la progression ;
    // un refus retire l'estampille et le dit (409 : le bandeau de conflit, « Garder la mienne » réécrit).
    const estampille = `→ ${jourNomme(jour, donnees?.jour)}`
    const poser = () => setEstampilles((e) => ({ ...e, [cle]: estampille }))
    const oter = () => setEstampilles((e) => Object.fromEntries(Object.entries(e).filter(([k]) => k !== cle)))
    const ecrire = (version) => {
      const geste = { annule: false }
      poser()
      const envoi = enchainer(cle, () => client.planifierTache(item.id, { jour_prevu: jour, lock_version: version }))
      const toast = proposerAnnuler({
        message,
        onAnnuler: async () => {
          geste.annule = true
          oter()
          const reponse = await envoi.then((r) => r, () => null)
          if (!reponse) return // le report a échoué : rien n'est à défaire côté serveur
          try {
            const retour = await annulerEtRecaler(reponse.data.geste_id, [item.id]) // la version change : on garde celle du serveur
            patcher(cle, (it) => ({ ...it, lock_version: versionDe(retour, item.id, it.lock_version) }))
          } catch (err) {
            poser() // l'annulation est refusée : la tâche reste reportée, et le toast le dit
            throw err
          }
        },
      })
      envoi.then(({ data }) => {
        setConflit(null)
        patcher(cle, (it) => ({ ...it, lock_version: data.tache?.lock_version ?? it.lock_version }))
        if (!geste.annule) poserProgression(data.progression) // `tache_ecrite.progression` : la progression suit sans relire la journée
      }, (err) => {
        if (geste.annule) return
        oter()
        if (err?.response?.status === 409 && err.response.data?.code === 'conflit_version') {
          if (toastCourant.current === toast) fermerToast()
          const actuel = err.response.data.actuel ?? {}
          setConflit({
            heure: heureDuConflit(actuel),
            onGarder: () => ecrire(err.response.data.lock_version ?? actuel.lock_version),
            onPrendre: () => { patcher(cle, (it) => ({ ...it, ...actuel })); setConflit(null) },
          })
          return
        }
        proposerAnnuler({ message: frenchError(err) })
      })
    }
    ecrire(lockVersion)
  }, [enLigne, donnees, patcher, poserProgression, enchainer, toastCourant])

  const reporter = useCallback((item) => {
    const jour = donnees?.prochain_jour_ouvre
    if (jour) poserJour(item, jour, `Reportée à ${jourNomme(jour, donnees.jour)}`)
  }, [donnees, poserJour])

  const basculerEssentiel = useCallback(async (item, suivant) => {
    try { garde() } catch { return }
    // R2-012 — le plafond se teste AVANT l'appel, depuis l'étoile comme depuis le menu ⋯ : la 4e ne part jamais
    if (suivant && !item.essentielle && (donnees?.essentiel?.length ?? 0) >= MAX_ESSENTIELLES) { refuserEssentielle(); return }
    try {
      const { data } = await client.marquerEssentiel({ tache_id: item.id, essentielle: suivant })
      poserProgression(data.progression)
      const avant = { origines: [] }
      setDonnees((d) => {
        const r = rangerEssentielle(d, cleDe(item), suivant, data.tache?.lock_version)
        avant.origines = r.origines
        return r.suite
      })
      proposerAnnuler({
        message: suivant ? 'Essentielle' : 'Plus essentielle',
        onAnnuler: async () => {
          const rendu = await annulerEtRecaler(data.geste_id, [item.id]) // la version change : on garde celle du serveur
          // l'état d'avant : la ★ d'avant, à chacune de ses places d'avant (une essentielle faite retrouve ses deux lignes)
          setDonnees((d) => {
            const { suite, item: trouve } = retirer(d, cleDe(item))
            if (!trouve || avant.origines.length === 0) return d
            const retour = { ...trouve, essentielle: !suivant, lock_version: versionDe(rendu, item.id, trouve.lock_version) }
            return remettre(suite, { origines: avant.origines.map((o) => ({ ...o, item: retour })) })
          })
        },
      })
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [garde, donnees, setDonnees, poserProgression])

  /** Sort une ligne de sa section ; rend la fonction qui la remet à sa place (Annuler, refus du serveur). */
  const sortirLigne = useCallback((item) => {
    const origine = {}
    setDonnees((d) => {
      const r = retirer(d, cleDe(item))
      Object.assign(origine, r)
      return r.suite
    })
    return () => setDonnees((d) => remettre(d, origine))
  }, [setDonnees])

  const garder = useCallback(async (items) => {
    try { garde() } catch { return }
    try {
      const lignes = items.map((it) => ({ type: it.type, id: it.id }))
      const { data } = await client.garderJournee({ jour: donnees.jour, mode: 'express', lignes, essentielles: [], triage: [] })
      setDonnees(data.aujourdhui)
      setInvite(true)
      setFocusPrevu((v) => v + 1)
      proposerAnnuler({
        message: `${accord(items.length, 'gardée')}`,
        onAnnuler: async () => { await client.annulerGeste(data.geste_id); await charger() },
      })
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [garde, donnees, setDonnees, charger])

  const repondre = useCallback(async (proposition, reponse) => {
    try { garde() } catch { return }
    try {
      const { data } = await client.repondreProposition(proposition.id, { reponse })
      setDonnees((d) => ({ ...d, carte_du_moment: null, objectif: data.rythme?.objectif ?? d.objectif }))
      if (proposition.type === 'retour' && reponse === 'remettre_dans_propose') {
        const n = proposition.donnees?.taches ?? 0
        proposerAnnuler({
          message: `${n} ${n >= 2 ? 'remises' : 'remise'} dans Proposé`,
          onAnnuler: async () => { await client.annulerGeste(data.geste_id); await charger() },
        })
        await charger()
      }
    } catch (err) {
      if (err?.response?.status === 409 && err.response.data?.code === 'proposition_expiree') {
        setDonnees((d) => ({ ...d, carte_du_moment: null }))
        // la carte part : le refus se VOIT (textes.md §2.16 « Cette proposition a expiré. »), pas seulement lu
        proposerAnnuler({ message: frenchError(err) })
        return
      }
      annoncer(frenchError(err))
    }
  }, [garde, setDonnees, charger])

  const alleger = useCallback(async (ids) => {
    try { garde() } catch { return }
    try {
      const { data } = await client.alleger({ jour: donnees.jour, garder: ids })
      setDonnees(data.aujourdhui)
      setFeuille(null)
      const n = data.renvoyees?.length ?? 0
      proposerAnnuler({
        message: `${n} ${n >= 2 ? 'retournées' : 'retournée'} aux projets`,
        onAnnuler: async () => { await client.annulerGeste(data.geste_id); await charger() },
      })
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [garde, donnees, setDonnees, charger])

  const modes = useModesJournee({ donnees, setDonnees, garde, setEstampilles })
  const revoir = useARevoir({ donnees, setDonnees, garde, charger })
  const lier = useLierActivite({ donnees, setDonnees, garde, charger })

  const ouvrirFiche = useOuvrirFiche()
  // une création (saisie, collage, file rejouée) : la journée se relit une fois, sans recharger la page
  useApresCreation(useCallback(() => { charger(); setBrouillon(lireBrouillon(societe, userId)) }, [charger, societe, userId]))

  // Raccord F2 — le gestionnaire commun des actions de ligne ; Aujourd'hui garde son ★ (la ligne change de section),
  // son Reporter / Choisir un jour (estampille « → jeu. 19 ») et « Lier une tâche » des activités ERP.
  const actionsPropres = useMemo(() => ({
    essentiel: (item) => basculerEssentiel(item, !item.essentielle),
    choisir_jour: (item) => setFeuille({ type: 'jour', item }),
    reporter,
    lier: (item) => setFeuille({ type: 'lier', item }),
  }), [basculerEssentiel, reporter])
  const actions = useActionsLigne({
    aujourdhui: donnees?.jour,
    prochainJourOuvre: donnees?.prochain_jour_ouvre,
    maj: (id, champs) => patcher(`tache:${id}`, (it) => ({ ...it, ...champs })),
    retirer: sortirLigne,
    apresEcriture: (data) => poserProgression(data?.progression),
    // en réserve ou en attente, la tâche quitte la journée (elle revient au relu, dans « En attente »)
    sortApres: (code, item, valeurs) => (code === 'planifier' && Boolean(valeurs.quelque_jour)) || code === 'attente',
    actionsPropres,
  })

  const geste = useMemo(() => ({
    terminer,
    reporter,
    choisirJour: (item) => setFeuille({ type: 'jour', item }),
    ouvrir: (item) => (item.type === 'activite' ? (item.lien?.url ? navigate(item.lien.url) : null) : ouvrirFiche(item.id)),
    action: actions.surAction,
    essentiel: (item, suivant) => { setInvite(false); return basculerEssentiel(item, suivant) },
    deplacer: modes.deplacer,
    selectionner: modes.selectionner,
    garder,
    voirTout: (ouvert) => setParams((actuels) => {
      const suite = new URLSearchParams(actuels)
      if (ouvert) suite.set('tout', '1')
      else suite.delete('tout')
      return suite
    }, { replace: true }),
    copilote: (question) => {
      if (enLigne) window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, { detail: { ecran: '/taches/aujourdhui', question, envoyer: true } }))
    },
    refusEssentiel: refuserEssentielle,
    annoncer,
    naviguer: (url) => navigate(url),
  }), [terminer, reporter, basculerEssentiel, garder, enLigne, navigate, ouvrirFiche, setParams, modes.deplacer, modes.selectionner, actions.surAction])

  const glissable = useMemo(() => (bureau ? { onDebut: setGlisse, onFin: () => setGlisse(null) } : null), [bureau])
  // La ligne glissée peut quitter le DOM en cours de route (elle prend son heure et change de place) : `dragend` ne
  // lui parvient alors plus. Le dépôt, ou la fin du glisser vu par la fenêtre, ferme donc aussi les créneaux.
  useEffect(() => {
    if (!glisse) return undefined
    const fin = () => setGlisse(null)
    window.addEventListener('drop', fin)
    window.addEventListener('dragend', fin)
    return () => { window.removeEventListener('drop', fin); window.removeEventListener('dragend', fin) }
  }, [glisse])
  // « Placée à {HH:MM} » : la ligne prend son heure sans relire la journée ; « Annuler » lui rend celle d'avant
  const placee = useCallback((item, data, heureChoisie) => {
    patcher(cleDe(item), (it) => ({
      ...it,
      heure_debut: data?.tache?.heure_debut ?? heureChoisie,
      lock_version: data?.tache?.lock_version ?? it.lock_version,
    }))
    poserProgression(data?.progression)
  }, [patcher, poserProgression])
  const replacee = useCallback((item) => patcher(cleDe(item), () => item), [patcher])

  const contexte = useMemo(() => ({
    donnees,
    estampilles,
    nbEssentielles: donnees?.essentiel?.length ?? 0,
    gardee: Boolean(donnees?.plan?.planifie_le),
    invite,
    focusPrevu,
    reorganiser: modes.reorganiser,
    selection: modes.selection,
    glissable,
  }), [donnees, estampilles, invite, focusPrevu, modes.reorganiser, modes.selection, glissable])

  // Clavier (spec-7 §5) : j/k, Espace, * … ; jamais une touche seule qui fait disparaître une ligne
  const racine = useClavierListe((action, { cle }) => {
    const item = cle ? chercher(donnees, cle) : null
    actions.prechargerProjets() // au clavier, `m` puis Entrée doit trouver la liste des projets déjà lue
    if (action === 'annuler') annulerToast()
    else if (!item) return
    else if (action === 'terminer') terminer(item, item.statut !== 'fait').catch((err) => { if (err?.response) annoncer(frenchError(err)) })
    else if (action === 'essentiel' && item.type === 'tache') basculerEssentiel(item, !item.essentielle)
    else if (action === 'quand' && item.type === 'tache') setFeuille({ type: 'jour', item, initial: donnees?.prochain_jour_ouvre ?? '' })
    else if (action === 'selectionner' && item.type === 'tache') modes.selectionner(item)
    else if (action === 'monter') modes.deplacer(item, -1)
    else if (action === 'descendre') modes.deplacer(item, 1)
    else if (action === 'deplacer' && item.type === 'tache') actions.surAction('deplacer', item, { clavier: true })
    else if (item.type === 'tache' && ['renommer', 'heure'].includes(action)) ouvrirFiche(item.id)
  }, { actif: !feuille && !actions.feuille && !actions.selecteurProjet })

  const ouvrirSaisie = useCallback((detail) => {
    window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail }))
  }, [])

  const jourFeuille = donnees?.jour ?? aujourdhuiIso()

  // Bilan du soir : ouvert par la carte du moment, ou par `?ouvrir=bilan` (notification du soir)
  const bilanDemande = feuille?.type === 'bilan' || params.get('ouvrir') === 'bilan'
  const fermerBilan = () => {
    setFeuille(null)
    setParams((actuels) => { const suite = new URLSearchParams(actuels); suite.delete('ouvrir'); return suite }, { replace: true })
  }
  const bilanEnregistre = (data) => {
    fermerBilan()
    setDonnees((d) => ({ ...d, carte_du_moment: null, plan: { ...d.plan, cloture_le: data.plan?.cloture_le ?? d.plan?.cloture_le } }))
    proposerAnnuler({
      message: 'Bilan enregistré',
      onAnnuler: async () => { await client.annulerGeste(data.geste_id); await charger() },
    })
    charger()
  }

  let laFeuille = null
  if (bilanDemande && donnees) {
    laFeuille = {
      ouverte: true,
      titre: feuille?.jour && feuille.jour !== donnees.jour ? "Bilan d'hier" : 'Bilan du soir',
      cranInitial: '85',
      onFermer: fermerBilan,
      children: (
        <FeuilleBilan
          jour={feuille?.type === 'bilan' ? feuille.jour : null}
          aujourdhui={donnees.jour}
          maintenant={donnees.maintenant}
          enLigne={enLigne}
          onValide={bilanEnregistre}
          onPasser={fermerBilan}
        />
      ),
    }
  } else if (feuille?.type === 'jour') {
    laFeuille = {
      ouverte: true,
      titre: 'Choisir un jour',
      onFermer: () => setFeuille(null),
      children: (
        <ChoisirJour
          item={feuille.item}
          minimum={jourFeuille}
          initial={feuille.initial}
          reporterA={donnees?.prochain_jour_ouvre ?? null}
          onChoisir={(jour) => {
            setFeuille(null)
            const message = jour === donnees?.prochain_jour_ouvre
              ? `Reportée à ${jourNomme(jour, jourFeuille)}` : `Prévue ${jourCourt(jour, jourFeuille)}`
            poserJour(feuille.item, jour, message)
          }}
        />
      ),
    }
  } else if (feuille?.type === 'alleger' && donnees) {
    laFeuille = {
      ouverte: true,
      titre: 'Alléger ma journée',
      cranInitial: '85',
      onFermer: () => setFeuille(null),
      children: <FeuilleAlleger donnees={donnees} enLigne={enLigne} onGarder={alleger} />,
    }
  } else if (feuille?.type === 'lier') {
    laFeuille = {
      ouverte: true,
      titre: 'Lier une tâche',
      onFermer: () => setFeuille(null),
      children: (
        <FeuilleLier item={feuille.item} onLier={async (titre) => {
          const refus = await lier(feuille.item, titre)
          if (!refus) setFeuille(null)
          return refus
        }} />
      ),
    }
  } else if (feuille?.type === 'jour_lot') {
    laFeuille = {
      ouverte: true,
      titre: 'Quand',
      onFermer: () => setFeuille(null),
      children: (
        <ChoisirJour
          item={{ titre: accord(modes.selection.ids.size, 'tâche sélectionnée', 'tâches sélectionnées') }}
          minimum={jourFeuille}
          onChoisir={(jour) => { setFeuille(null); modes.lot('planifier', { jour_prevu: jour }) }}
        />
      ),
    }
  }

  const sousTitre = donnees && donnees.jour_ouvre === false ? 'Jour non travaillé' : jourLong(donnees?.jour)
  const ouvrirFeuille = (type, parametres = {}) => setFeuille({ type, ...parametres })
  const actionsEcran = actionsJournee({
    enLigne,
    onAlleger: () => ouvrirFeuille('alleger'),
    onReorganiser: () => modes.setReorganiser((v) => !v),
    onSelectionner: modes.basculerSelection,
  })
  const barreSelection = modes.selection.actif ? {
    n: modes.selection.ids.size,
    actions: [{ code: 'planifier', libelle: 'Quand' }, { code: 'terminer', libelle: 'Terminer' }],
    onAction: (code) => (code === 'planifier' ? setFeuille({ type: 'jour_lot' }) : modes.lot(code)),
    onFermer: modes.quitterSelection,
  } : null
  const bandeau = erreur ? <BandeauPasAJour derniere={derniere} onReessayer={charger} /> : null

  const contenu = (
    <>
      {modes.reorganiser || modes.selection.actif ? (
        <div className="mode-ecran" role="status">
          <span>{modes.reorganiser ? 'Réorganiser' : 'Sélectionner'}</span>
          <button type="button" className="bouton lien" onClick={() => { modes.setReorganiser(false); modes.quitterSelection() }}>OK</button>
        </div>
      ) : null}
      {squelette ? <Squelette /> : null}
      {donnees && !journeeVide(donnees) ? <Progression donnees={donnees} onRythme={() => navigate('/taches/rythme')} /> : null}
      {/* passe visuelle n° 15 — bureau : « Ajouter une tâche » sous la progression (maquette ecran-aujourdhui-matin.html).
          Elle reste là quand la journée est vide ou encore en chargement : c'est le « + » du bureau (l'iPhone garde son
          bouton flottant dans ces états-là aussi) — on ne retire jamais le moyen d'ajouter une tâche. */}
      <SaisieBureau onClick={() => ouvrirSaisie({})} />
      {bandeau}
      {donnees && !journeeVide(donnees) ? (
        <CarteDuMoment
          carte={donnees.carte_du_moment}
          jour={donnees.jour}
          maintenant={donnees.maintenant}
          objectif={donnees.objectif?.nb}
          enLigne={enLigne}
          onRepondre={repondre}
          onGarder={() => garder(donnees.propose?.pour_objectif ?? [])}
          onAlleger={() => ouvrirFeuille('alleger')}
          onBilan={(jourBilan) => ouvrirFeuille('bilan', { jour: jourBilan })}
          onNaviguer={navigate}
          onCopilote={geste.copilote}
          brouillon={brouillon ? (
            <div className="carte" role="region" aria-label="Brouillon">
              <p className="carte-texte">Ta saisie de tout à l&apos;heure t&apos;attend.</p>
              <div className="carte-actions">
                <button type="button" className="bouton second" onClick={() => ouvrirSaisie({})}>Reprendre</button>
              </div>
            </div>
          ) : null}
        />
      ) : null}
      {donnees && journeeVide(donnees) ? (
        <EtatVide
          donnees={donnees}
          onColler={() => ouvrirSaisie({ coller: true })}
          onDicter={() => ouvrirSaisie({ dicter: true })}
          onTrier={() => navigate('/taches/a-trier')}
        />
      ) : null}
      {donnees && !journeeVide(donnees) ? (
        <div ref={racine}>
        <Sections
          donnees={donnees}
          contexte={contexte}
          geste={geste}
          repliees={<Replies donnees={donnees} contexte={contexte} geste={geste} revoir={revoir} enLigne={enLigne} />}
          propose={(
            <Propose
              donnees={donnees}
              contexte={contexte}
              geste={geste}
              enLigne={enLigne}
              tout={tout}
              carteGarder={donnees.carte_du_moment?.type === 'garder'}
            />
          )}
        />
        </div>
      ) : null}
    </>
  )

  return (
    <CoquilleTaches
      ecran="aujourdhui"
      titre="Aujourd'hui"
      sousTitre={sousTitre}
      derniereSynchro={derniere}
      conflit={conflit ?? actions.conflit}
      feuille={laFeuille ?? actions.feuille}
      selecteurProjet={actions.selecteurProjet}
      actionsEcran={actionsEcran}
      selection={barreSelection}
      saisieBureau={false}
    >
      {bureau ? (
        <div className="tch-bureau">
          <ColonneProjets />
          <div className="tch-bureau-liste">{contenu}</div>
          {donnees ? <ColonneBureau jour={donnees.jour} maintenant={donnees.maintenant} glisse={glisse} onPlacee={placee} onRetiree={replacee} /> : null}
        </div>
      ) : contenu}
    </CoquilleTaches>
  )
}
