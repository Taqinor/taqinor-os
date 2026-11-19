import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
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
import FeuilleAlleger, { candidatesAlleger } from '../../features/taches/aujourdhui/FeuilleAlleger'
import { actionsJournee, useModesJournee } from '../../features/taches/aujourdhui/MenuJournee'
import ColonneBureau, { ColonneProjets } from '../../features/taches/aujourdhui/ColonneBureau'
import Propose from '../../features/taches/aujourdhui/Propose'
import Progression from '../../features/taches/aujourdhui/Progression'
import CarteDuMoment from '../../features/taches/ui/CarteDuMoment'
import SelecteurQuand, { QUAND_VIDE } from '../../features/taches/ui/SelecteurQuand'
import { useActionsLigne } from '../../features/taches/ui/ActionsLigne'
import { annoncer, annulerToast, fermerToast, proposerAnnuler, useEtatGestes } from '../../features/taches/lib/gestes'
import { useClavierListe } from '../../features/taches/lib/clavierListe'
import { useCompteTaches, useEnLigne } from '../../features/taches/lib/enLigne'
import { ecrireJournee, lireJournee } from '../../features/taches/horsligne/cacheJournee'
import { MESSAGE_EN_FILE as TOAST_EN_FILE, compteFile, enfilerCoche, enfilerReport, fileTaches, TYPES as OPS_FILE, useVersionFile } from '../../features/taches/horsligne/captureQueue'
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
const CONSTAT_REPORTEES = 'C7' // moteur/gabarits.py : « {n} tâches reportées {reports} fois ou plus. » · « Les revoir maintenant ? »
const MAX_ESSENTIELLES = 3 // regles.md §4.1 « 3 au plus » (même plafond que `ui/Etoile`)
/** R2-012 — la 4e étoile est refusée À L'ÉCRAN (un toast), pas seulement au lecteur d'écran. */
const refuserEssentielle = () => proposerAnnuler({ message: "3 essentielles au plus — retire une étoile d'abord" })
const MEDIA_BUREAU = '(min-width: 1024px)'
const cleDe = (item) => `${item.type}:${item.id}`
const heureDe = (iso) => String(iso ?? '').slice(11, 16)

/** R3-024 — les champs d'une TACHE écrite par la fiche qu'une ligne de la journée reprend telle quelle. */
const CHAMPS_FICHE = ['titre', 'jour_prevu', 'moment', 'heure_debut', 'quelque_jour', 'estimation_minutes', 'echeance', 'lock_version']

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
 * R2-022 — « Choisir un jour » : le sélecteur « Quand » de tout le module (`ui/SelecteurQuand`, importé tel quel) —
 * Aujourd'hui · Demain · Ce soir · Reporter à {jour} · Choisir un jour · En réserve · Sans jour : un toucher suffit.
 * Ouverte au clavier (`d`, spec-7 §5 « Quand (Entrée = Reporter au jour nommé) »), la tuile « Reporter à {jour} » a
 * le focus : Entrée reporte. `valeur` : le « Quand » actuel de la ligne (sa tuile est cochée).
 */
function ChoisirJour({ titre, valeur, aujourdhui, reporterA = null, clavier = false, onChoisir }) {
  const racine = useRef(null)
  // posé AVANT que la feuille ne cherche son action par défaut (`data-focus-initial`, effets de mise en page d'abord)
  useLayoutEffect(() => {
    if (!clavier) return
    const tuiles = racine.current?.querySelectorAll('[role="radio"]') ?? []
    const reporter = [...tuiles].find((tuile) => tuile.textContent.startsWith('Reporter à'))
    reporter?.setAttribute('data-focus-initial', '')
  }, [clavier])
  return (
    <div className="choisir-jour" ref={racine}>
      <p className="carte-source">{titre}</p>
      <SelecteurQuand valeur={valeur} aujourdhui={aujourdhui} reporterA={reporterA} onChoisir={onChoisir} />
    </div>
  )
}

/** Le toast d'un « Quand » choisi (mêmes phrases que le menu ⋯ : « Reportée à ven. 20 », « Prévue lun. 23 »…). */
function messageQuand(quand, aujourdhui, reporterA) {
  if (quand.quelque_jour) return 'En réserve'
  if (!quand.jour_prevu) return 'Sans jour'
  if (quand.jour_prevu === aujourdhui && quand.moment === 'soir') return 'Ce soir'
  if (quand.jour_prevu === reporterA) return `Reportée à ${jourNomme(quand.jour_prevu, aujourdhui)}`
  return `Prévue ${jourCourt(quand.jour_prevu, aujourdhui)}`
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

/** Les titres d'un ajout en file : la phrase tapée (R2-008a, analysée au rejeu) ou, forme d'avant, ses lignes lues. */
function titresEnFile(op) {
  const corps = op.payload?.corps ?? {}
  const textes = corps.phrase?.textes
  if (Array.isArray(textes) && textes.length > 0) return textes.map((t) => String(t).trim()).filter(Boolean)
  if (typeof corps.texte === 'string' && corps.texte.trim()) return [corps.texte.trim()]
  return (corps.lignes ?? []).map((ligne) => ligne?.titre).filter(Boolean)
}

/**
 * R2-008b — les tâches ajoutées HORS LIGNE (file `captureQueue`, op « ajouter » de CE compte) : l'écran les montre tout
 * de suite, grisées « En attente d'envoi », jusqu'au rejeu (la journée se relit alors et elles y prennent leur place).
 */
function useAjoutsEnFile() {
  const version = useVersionFile()
  const [ajouts, setAjouts] = useState([])
  useEffect(() => {
    let courant = true
    const moi = compteFile()?.userId
    fileTaches().pending().then((ops) => {
      if (!courant) return
      const miens = (ops ?? []).filter((op) => op.op_type === OPS_FILE.AJOUTER && !op.serverError && op.payload?.userId === moi)
      setAjouts(miens.flatMap((op) => titresEnFile(op).map((titre, rang) => ({ cle: `${op.client_op_id}:${rang}`, titre }))))
    }, (err) => { if (courant) annoncer(frenchError(err)) })
    return () => { courant = false }
  }, [version])
  return ajouts
}

/** « En attente d'envoi » : les ajouts hors ligne, grisés, sans case ni geste (ils n'existent pas encore). */
function AjoutsEnFile({ ajouts }) {
  if (ajouts.length === 0) return null
  return (
    <section className="section en-file" role="region" aria-label="En attente d’envoi">
      <h2 className="section-titre"><span>En attente d&apos;envoi</span></h2>
      <div className="liste" role="list">
        {ajouts.map((ajout) => (
          <div key={ajout.cle} className="ligne lecture-seule en-file" role="listitem" data-en-file="">
            <span className="case vide" aria-hidden="true" />
            <div className="ligne-corps">
              <div className="titre">{ajout.titre}</div>
              <div className="meta"><span>{TOAST_EN_FILE}</span></div>
            </div>
            <div className="ligne-fin" />
          </div>
        ))}
      </div>
    </section>
  )
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
  const [deplierARevoir, setDeplierARevoir] = useState(0)
  const bureau = useBureau()
  const ajoutsEnFile = useAjoutsEnFile()
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
    // R2-008b — décocher hors ligne : le refus se VOIT (un toast), pas seulement au lecteur d'écran ; la case revient
    if (!enLigne && item.type === 'tache' && !suivant) {
      proposerAnnuler({ message: 'Décocher attend le réseau' })
      throw new Error('Décocher attend le réseau')
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

  /**
   * Prévoit la ligne un autre jour (Reporter, « Choisir un jour »). `quand` : le jour (`AAAA-MM-JJ`, seul champ envoyé)
   * ou la valeur complète de `SelecteurQuand` (jour, moment, heure). La ligne reste à l'écran avec son estampille
   * (« → ven. 20 », « → Sans jour ») et porte ses nouveaux champs : un autre jour ne compte plus dans la journée
   * affichée (« essentiel f/p », gardées — R2-019).
   */
  const poserJour = useCallback(async (item, quand, message, lockVersion = item.lock_version) => {
    const cle = cleDe(item)
    const champs = typeof quand === 'string' ? { jour_prevu: quand } : { ...QUAND_VIDE, ...quand }
    const jour = champs.jour_prevu ?? null
    const estampille = !jour ? '→ Sans jour' : jour !== donnees?.jour ? `→ ${jourNomme(jour, donnees?.jour)}` : ''
    const avant = Object.fromEntries(Object.keys(champs).map((k) => [k, item[k] ?? QUAND_VIDE[k] ?? null]))
    const poser = () => {
      if (estampille) setEstampilles((e) => ({ ...e, [cle]: estampille }))
      patcher(cle, (it) => ({ ...it, ...champs }))
    }
    const oter = () => {
      setEstampilles((e) => Object.fromEntries(Object.entries(e).filter(([k]) => k !== cle)))
      patcher(cle, (it) => ({ ...it, ...avant }))
    }
    if (!enLigne) {
      // hors ligne (TCH100) : reporter / choisir un jour part dans la file, avec le `lock_version` du cache
      try {
        await enfilerReport(item.id, { ...QUAND_VIDE, ...champs, lock_version: lockVersion })
      } catch (err) {
        annoncer(frenchError(err))
        return
      }
      poser()
      proposerAnnuler({ message: TOAST_EN_FILE, annonce: message })
      return
    }
    // R2-011 — OPTIMISTE : « → ven. 20 » et le toast AU RELÂCHER ; la réponse recale la version et la progression ;
    // un refus retire l'estampille et le dit (409 : le bandeau de conflit, « Garder la mienne » réécrit).
    const ecrire = (version) => {
      const geste = { annule: false }
      poser()
      const envoi = enchainer(cle, () => client.planifierTache(item.id, { ...champs, lock_version: version }))
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
      setDonnees((d) => rangerEssentielle(d, cleDe(item), suivant, data.tache?.lock_version).suite)
      // R2-027 — l'étoile pleine suffit : plus de toast « Essentielle · Annuler » (retoucher l'étoile la retire) ;
      // le lecteur d'écran l'entend toujours
      annoncer(`${suivant ? 'Essentielle' : 'Plus essentielle'} : ${item.titre}`)
    } catch (err) {
      proposerAnnuler({ message: frenchError(err) }) // un refus se VOIT
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

  /**
   * Les champs posés par une action de ligne (`ActionsLigne`). R2-013 — « En attente de… » ne fait pas disparaître la
   * ligne : elle passe dans « En attente » (en tête, le compteur suit) ; son « Annuler » (statut rendu) la remet à sa
   * place d'avant. Tout autre champ se pose sur la ligne, où qu'elle soit.
   */
  const placesAvantAttente = useRef(new Map())
  const [ecartsProjets, setEcartsProjets] = useState({})
  // la journée À JOUR (un « Annuler » rappelle le `maj` d'avant le geste : sa journée à lui serait périmée)
  const donneesCourantes = useRef(donnees)
  useEffect(() => { donneesCourantes.current = donnees }, [donnees])
  const majLigne = useCallback((id, champs) => {
    const cle = `tache:${id}`
    // R2-029 — une tâche ouverte change de projet (« Changer de projet… », ou son Annuler) : « Mes projets » (bureau) suit
    if (Object.prototype.hasOwnProperty.call(champs, 'projet')) {
      const actuel = chercher(donneesCourantes.current, cle)
      const avant = actuel?.projet?.id ?? null
      const apres = champs.projet?.id ?? null
      if (actuel && actuel.statut !== 'fait' && avant !== apres) {
        setEcartsProjets((e) => {
          const suite = { ...e }
          if (avant !== null) suite[avant] = (suite[avant] ?? 0) - 1
          if (apres !== null) suite[apres] = (suite[apres] ?? 0) + 1
          return suite
        })
      }
    }
    if (champs.statut === 'en_attente') {
      setDonnees((d) => {
        const { suite, origines, item } = retirer(d, cle)
        if (!item) return d
        placesAvantAttente.current.set(cle, origines)
        return { ...suite, en_attente: [{ ...item, ...champs }, ...(suite.en_attente ?? [])] }
      })
      return
    }
    const origines = champs.statut ? placesAvantAttente.current.get(cle) : null
    if (origines) {
      placesAvantAttente.current.delete(cle)
      setDonnees((d) => {
        const { suite, item } = retirer(d, cle)
        if (!item) return d
        return remettre(suite, { origines: origines.map((o) => ({ ...o, item: { ...item, ...champs } })) })
      })
      return
    }
    patcher(cle, (it) => ({ ...it, ...champs }))
  }, [setDonnees, patcher])

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
      // R2-014b — « Les revoir maintenant ? » Oui : la section « À revoir » se déplie et vient à l'écran
      if (proposition.cle === CONSTAT_REPORTEES && reponse === 'oui') setDeplierARevoir((v) => v + 1)
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
  useApresCreation(useCallback((detail) => {
    // couture r2 (R2-040) — « Fait » touché dans la fiche : la ligne se barre SUR PLACE et le compte avance, exactement
    // comme une case cochée ; une relecture l'aurait rangée dans « Faites » replié (elle disparaissait sous la fiche)
    const ecrite = detail?.tache
    const cle = ecrite?.id != null ? `tache:${ecrite.id}` : null
    const avant = cle && donnees ? chercher(donnees, cle) : null
    if (avant && ecrite.statut === 'fait' && avant.statut !== 'fait') {
      patcher(cle, (it) => ({ ...it, statut: 'fait', lock_version: ecrite.lock_version ?? it.lock_version }))
      setDonnees((d) => (d ? { ...d, progression: avancer(d.progression, avant, 1) } : d))
      return
    }
    // R3-024 — une écriture de la fiche (Quand, heure, titre…) se pose SUR PLACE, à l'instant (la ligne et le bloc de
    // l'Agenda suivent sans attendre) ; la relecture qui suit range la ligne là où le serveur la met
    if (avant) patcher(cle, (it) => ({ ...it, ...Object.fromEntries(CHAMPS_FICHE.filter((c) => c in ecrite).map((c) => [c, ecrite[c]])) }))
    charger()
    setBrouillon(lireBrouillon(societe, userId))
  }, [charger, societe, userId, donnees, patcher, setDonnees]))

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
    maj: majLigne,
    retirer: sortirLigne,
    apresEcriture: (data) => poserProgression(data?.progression),
    // en réserve, la tâche quitte la journée ; en attente, elle PASSE dans « En attente » (`majLigne`, R2-013)
    sortApres: (code, item, valeurs) => code === 'planifier' && Boolean(valeurs.quelque_jour),
    actionsPropres,
  })

  const geste = useMemo(() => ({
    terminer,
    reporter,
    choisirJour: (item) => setFeuille({ type: 'jour', item }),
    ouvrir: (item) => (item.type === 'activite' ? (item.lien?.url ? navigate(item.lien.url) : null) : ouvrirFiche(item.id)),
    decouper: (item) => ouvrirFiche(item.id, { section: 'decouper' }), // R2-021 : la fiche s'ouvre SUR « Découper »
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
  // R3-024 — la colonne Agenda tire ses blocs des MÊMES items que la liste : un geste ici se voit là-bas à l'instant
  const itemsDuJour = useMemo(() => (donnees ? LISTES_ITEMS.flatMap((cle) => donnees[cle] ?? []) : []), [donnees])

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
    else if (action === 'essentiel' && item.type === 'tache') {
      // couture r2 — la ligne change de section (Prévu ↔ Essentiel) : son bouton est remonté ailleurs, le focus le suit
      basculerEssentiel(item, !item.essentielle).then(() => requestAnimationFrame(() => {
        if (document.activeElement && document.activeElement !== document.body) return
        document.querySelector(`[data-ligne="${cle}"] .ligne-corps-bouton`)?.focus()
      }))
    }
    else if (action === 'quand' && item.type === 'tache') setFeuille({ type: 'jour', item, clavier: true })
    else if (action === 'selectionner' && item.type === 'tache') modes.selectionner(item)
    else if (action === 'monter') modes.deplacer(item, -1)
    else if (action === 'descendre') modes.deplacer(item, 1)
    else if (action === 'deplacer' && item.type === 'tache') actions.surAction('deplacer', item, { clavier: true })
    // R2-025 — `e` met le curseur dans le titre, `h` ouvre le champ heure (la fiche s'ouvre sur sa cible)
    else if (item.type === 'tache' && action === 'renommer') ouvrirFiche(item.id, { focus: 'titre' })
    else if (item.type === 'tache' && action === 'heure') ouvrirFiche(item.id, { focus: 'heure' })
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
      variante: 'panneau', // ≥ 1024 px : panneau fixe à droite, non modal ; en dessous, la feuille (R2-050)
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
          titre={feuille.item.titre}
          valeur={Object.fromEntries(Object.keys(QUAND_VIDE).map((k) => [k, feuille.item[k] ?? QUAND_VIDE[k]]))}
          aujourdhui={jourFeuille}
          reporterA={donnees?.prochain_jour_ouvre ?? null}
          clavier={Boolean(feuille.clavier)}
          onChoisir={(quand) => {
            setFeuille(null)
            // en réserve, la ligne quitte la journée : le geste commun du menu ⋯ (optimiste, Annuler)
            if (quand.quelque_jour) actions.surAction('reserve', feuille.item)
            else poserJour(feuille.item, quand, messageQuand(quand, jourFeuille, donnees?.prochain_jour_ouvre))
          }}
        />
      ),
    }
  } else if (feuille?.type === 'alleger' && donnees) {
    laFeuille = {
      ouverte: true,
      titre: 'Alléger ma journée',
      cranInitial: '85',
      variante: 'panneau', // ≥ 1024 px : panneau fixe à droite, non modal ; en dessous, la feuille (R2-050)
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
          titre={accord(modes.selection.ids.size, 'tâche sélectionnée', 'tâches sélectionnées')}
          valeur={QUAND_VIDE}
          aujourdhui={jourFeuille}
          reporterA={donnees?.prochain_jour_ouvre ?? null}
          onChoisir={(quand) => {
            setFeuille(null)
            modes.lot('planifier', quand.quelque_jour ? { quelque_jour: true } : { jour_prevu: quand.jour_prevu })
          }}
        />
      ),
    }
  }

  const sousTitre = donnees && donnees.jour_ouvre === false ? 'Jour non travaillé' : jourLong(donnees?.jour)
  const ouvrirFeuille = (type, parametres = {}) => setFeuille({ type, ...parametres })
  const actionsEcran = actionsJournee({
    enLigne,
    peutAlleger: Boolean(donnees) && !donnees.plan?.cloture_le && candidatesAlleger(donnees).length > 0,
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
      <AjoutsEnFile ajouts={ajoutsEnFile} />
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
          bilanFait={Boolean(donnees.plan?.cloture_le)}
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
          onColler={(lu) => ouvrirSaisie({ coller: true, ...lu })}
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
          repliees={<Replies donnees={donnees} contexte={contexte} geste={geste} revoir={revoir} enLigne={enLigne} deplierARevoir={deplierARevoir} />}
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
          <ColonneProjets ecarts={ecartsProjets} />
          <div className="tch-bureau-liste">{contenu}</div>
          {donnees ? <ColonneBureau jour={donnees.jour} maintenant={donnees.maintenant} items={itemsDuJour} glisse={glisse} onPlacee={placee} onRetiree={replacee} /> : null}
        </div>
      ) : contenu}
    </CoquilleTaches>
  )
}
