import { useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { Calendar, Folder, X } from 'lucide-react'
import { ReactReduxContext } from 'react-redux'

import { frenchError } from '../../../lib/frenchError'
import {
  annulerGeste, classerErreur, definirProprietaire, listerTousLesProjets, nouvelleCle, saisieRapide,
} from '../../../api/tachesApi'
import { MESSAGE_EN_FILE, avecContexte, enfilerAjout, enfilerPhrase } from '../horsligne/captureQueue'
import { estEnLigne, useEnLigne } from '../lib/enLigne'
import { proposerAnnuler } from '../lib/gestes'
import { aujourdhuiIso, jourCourt } from '../lib/textes'
import ChampSaisie, { jetonProjet, jetonProjetExistant } from '../ui/ChampSaisie'
import FeuilleACrans from '../ui/FeuilleACrans'
import SelecteurProjet from '../ui/SelecteurProjet'
import SelecteurQuand from '../ui/SelecteurQuand'
import { ecrireTexte, lireTexte, viderPrefixe } from '../lib/stockage'
import ColleListes, { construireLigne } from './ColleListes'

/* ============================================================================
   TCH82 — Feuille de saisie : « ajouter une tâche en une phrase ». La coquille l'ouvre (bouton
   flottant, « Ajouter une tâche », touche `c t`, événement `taqinor:taches:saisir`).
   Le geste le plus fréquent doit tenir au pouce : le champ a le focus à l'ouverture, Entrée
   envoie, et RIEN de ce qui est tapé n'est refusé ni corrigé — l'analyse du serveur
   (`saisie-rapide/` aperçu) ne fait qu'ajouter des puces, chacune retirable.
   BROUILLON : la phrase est gardée dans le navigateur sous `taches:brouillon:<société>:<compte>`
   (fermer la feuille ne la perd pas ; la carte « Reprendre » d'Aujourd'hui, TCH77, et TCH91 la
   relisent par `lireBrouillon`). Il est vidé à la déconnexion (`taqinor:auth-logout`).
   TCH83 — plus d'une ligne collée (ou « Coller encore ») : la feuille montre l'aperçu de la liste
   (`ColleListes`) au lieu des puces d'une phrase ; l'événement `taqinor:taches:saisir` avec
   `detail.liste` ouvre directement ce mode (« Coller mes listes » de l'état vide d'Aujourd'hui).
   CHAÎNE (spec-2 §1 « Après Entrée, le champ se vide et reste ouvert sur le même projet ; Échap ferme ») : une
   phrase ajoutée vide le champ, la feuille reste ouverte sur le contexte de l'écran ; une LISTE créée la ferme.
   Maquettes : ecran-saisie.html, ecran-saisie-nouveau.html, etat-erreur-champ.html,
   ecran-saisie-liste.html.

   INVARIANT « AUCUNE LETTRE PERDUE » (R2-001, R3-040, R4-22) — toute écriture dans le champ part de sa valeur COURANTE
   au moment où elle s'applique, jamais d'une valeur capturée avant un `await`, un `then`, un minuteur ou un événement de
   file. Les écritures, une à une :
     · frappe : `onChange` → la valeur du DOM (`e.target.value`) ;
     · brouillon repris : au MONTAGE seulement (état initial), jamais après ;
     · Entrée / « Ajouter » (`enchainer`) et « Créer N tâches » (`remettreAZero`) : AU TOUCHER, dans le même geste, avant
       tout envoi — rien de ce qui est tapé ensuite ne peut être effacé ;
     · `#projet` choisi (ChampSaisie), puce Projet, « + Nouveau projet » : mise à jour fonctionnelle / lecture du DOM ;
     · échec rendu au champ (`echouer`) : décidé sur la valeur du DOM À CET INSTANT (`champCourant`) et posé par
       `flushSync` dans la même tâche — aucune frappe ne peut se glisser entre la lecture et l'écriture ; une lettre déjà
       là ⇒ rien n'est écrit, la phrase passe par le toast « Reprendre » ;
     · « Reprendre » : la phrase en cours (lue au DOM) est mise de côté et revient après ;
     · retour de la file (hors ligne) : n'écrit RIEN et ne ferme RIEN — la feuille reste ouverte comme en ligne (une
       fermeture décidée au retour de la file emportait le champ pendant la frappe suivante : « Bravo h » avalé).
   ========================================================================== */

export const PREFIXE_BROUILLON = 'taches:brouillon:'
export const EVENEMENT_DECONNEXION = 'taqinor:auth-logout'
/** Annoncé après une création réussie : les listes ouvertes se rafraîchissent d'elles-mêmes. */
export const EVENEMENT_CREEES = 'taqinor:taches:creees'
/**
 * R3-046 — INTERFACE (figée pour l'écran Aujourd'hui, R3-030) : chaque envoi de la saisie est annoncé sur `window`
 * par `taqinor:taches:envoi`, `detail` =
 *   · `{ etat: 'part', envoi, lignes: [{ client_id, titre, jour }] }` — AU TOUCHER (« Ajouter », Entrée, « Créer N
 *     tâches »), avant tout appel réseau ; `envoi` = la clé d'idempotence de la création (`client_id` = `{envoi}:{n}`),
 *     `jour` = 'AAAA-MM-JJ' ou `null`. Le titre est celui de l'aperçu lu ; sans aperçu encore revenu, la phrase tapée.
 *   · `{ etat: 'creees', envoi, creees: [ITEM…] }` — le serveur a créé (émis juste avant `taqinor:taches:creees`) ;
 *   · `{ etat: 'echec', envoi }` — rien de créé (la phrase est rendue au champ ou par « Reprendre ») ;
 *   · `{ etat: 'en_file', envoi }` — hors ligne : mis en file (les lignes « En attente d'envoi » de la file prennent le
 *     relais). Un envoi finit TOUJOURS par l'un de ces trois.
 */
export const EVENEMENT_ENVOI = 'taqinor:taches:envoi'
const annoncerEnvoi = (detail) => window.dispatchEvent(new CustomEvent(EVENEMENT_ENVOI, { detail }))
const EVENEMENT_SAISIR = 'taqinor:taches:saisir'
const DELAI_APERCU_MS = 300

// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, relu par TCH77/TCH91 et testé directement (D-ENF22)
export const cleBrouillon = (societe, compte) => `${PREFIXE_BROUILLON}${societe ?? '0'}:${compte ?? '0'}`

/** Le brouillon `{ texte, quand, collages?, courant? }` de ce compte, ou `null` (stockage absent, illisible, vide). */
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, relu par TCH77/TCH91 et testé directement (D-ENF22)
export function lireBrouillon(societe, compte) {
  // stockage bloqué (`lib/stockage` rend '') ou JSON abîmé : pas de brouillon, la saisie reste possible
  const brut = lireTexte(cleBrouillon(societe, compte))
  let lu = null
  try {
    lu = brut ? JSON.parse(brut) : null
  } catch {
    return null
  }
  return lu && typeof lu.texte === 'string' && lu.texte.trim() ? lu : null
}

/** Le brouillon est un confort : s'il ne s'écrit pas (`false`), la saisie continue sans lui. */
const ecrireBrouillon = (cle, brouillon) => ecrireTexte(cle, brouillon ? JSON.stringify(brouillon) : '')
const viderBrouillons = () => viderPrefixe(PREFIXE_BROUILLON)

/** Compte connecté, lu sans exiger un Provider (la coquille se monte aussi sans store dans les tests). */
function useCompte() {
  const contexte = useContext(ReactReduxContext)
  const user = contexte?.store?.getState?.()?.auth?.user
  return { societe: user?.active_company_id ?? user?.company_id ?? null, compte: user?.id ?? null }
}

/** Message du champ fautif d'un 400 (`{champ: [..]}` ou `{lignes: {n: {champ: [..]}}}`). */
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, relu par TCH77/TCH91 et testé directement (D-ENF22)
export function messageChamps(champs) {
  if (!champs || typeof champs !== 'object') return ''
  const premier = (liste) => (Array.isArray(liste) && typeof liste[0] === 'string' ? liste[0] : '')
  for (const cle of ['texte', 'titre', 'projet_id', 'lien']) {
    const m = premier(champs[cle])
    if (m) return m
  }
  const lignes = champs.lignes && typeof champs.lignes === 'object' ? Object.values(champs.lignes) : []
  for (const ligne of lignes) {
    for (const liste of Object.values(ligne ?? {})) {
      const m = premier(liste)
      if (m) return m
    }
  }
  for (const [cle, liste] of Object.entries(champs)) {
    if (cle === 'error' || cle === 'code') continue // clé de racine du 400, jamais un champ fautif
    const m = premier(liste)
    if (m) return m
  }
  return ''
}

function libelleQuand(quand) {
  if (!quand) return 'Quand'
  if (quand.quelque_jour) return 'Plus tard'
  if (!quand.jour_prevu) return 'Sans jour'
  const jour = quand.moment === 'soir' ? 'ce soir' : jourCourt(quand.jour_prevu)
  return quand.heure_debut ? `${jour} · ${quand.heure_debut.slice(0, 5)}` : jour
}

/** Corps de l'aperçu : un seul texte, ou plusieurs collages (`textes`) quand on a collé encore. */
function corpsApercu(collages, texte, ignorer) {
  const textes = [...collages, ...(texte.trim() ? [texte] : [])]
  return textes.length > 1 ? { textes, ignorer, apercu: true } : { texte: textes[0] ?? '', ignorer, apercu: true }
}

function phraseErreur(err) {
  const classee = classerErreur(err)
  if (classee.code === 'validation') return messageChamps(classee.champs) || frenchError(err)
  if (classee.code === 'autre_compte') return "Une action d'un autre compte a été retirée de la file."
  return frenchError(err)
}

/** Raccord F2 — textes.md §2.15 (toast) et §2.19 (annonce) d'un ajout mis en file hors ligne. */
const TOAST_EN_FILE = MESSAGE_EN_FILE
const ANNONCE_EN_FILE = 'Hors ligne : gardée, elle partira dès le retour du réseau'

/** Longueur maximale d'un titre (api.md §4, `CHAMPS_LIGNE.titre`). */
const TITRE_MAX = 280
/** Une phrase déjà là (le serveur la décoche : `doublon_de`, `deja_faite`) : dit sous le champ, jamais « Aucune ligne
 *  lisible. » ; « Ajouter quand même » l'envoie (textes.md §2.3). */
const DEJA_DANS_LISTE = 'Déjà dans ta liste'
const DEJA_FAITE = 'Déjà faite'
const raisonDouble = (l) => (l?.doublon_de != null ? DEJA_DANS_LISTE : l?.deja_faite ? DEJA_FAITE : '')

/** R2-007 — un titre trop long coupé au dernier espace avant 280 caractères ; la suite devient la note. */
function couperTitre(titre) {
  const espace = titre.lastIndexOf(' ', TITRE_MAX)
  const coupe = espace > 0 ? espace : TITRE_MAX
  return { titre: titre.slice(0, coupe).trim(), notes: titre.slice(coupe).trim() }
}

/** R2-002 — toast d'une tâche ajoutée depuis Aujourd'hui et posée aujourd'hui. */
const TOAST_AJOUTEE_AUJOURDHUI = "Ajoutée à Aujourd'hui"

/** L'écran Aujourd'hui (`/taches` y mène) : lu à la demande, la feuille se monte aussi hors d'un routeur. */
const surAujourdhui = () => /^\/taches(\/aujourdhui)?\/?$/.test(window.location.pathname)

/** R2-009 — le bureau : la ligne « Ajouter une tâche » n'existe qu'à partir de 768 px (`bureau-seul`). */
const REQUETE_BUREAU = '(min-width: 768px)'

function useBureau() {
  const lire = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(REQUETE_BUREAU).matches
  const [bureau, setBureau] = useState(lire)
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined
    const mq = window.matchMedia(REQUETE_BUREAU)
    const maj = () => setBureau(mq.matches)
    mq.addEventListener?.('change', maj)
    return () => mq.removeEventListener?.('change', maj)
  }, [])
  return bureau
}

/** R2-009 (choix C-3) — l'ancre de la saisie EN PLACE : celle que pose la ligne « Ajouter une tâche » de l'écran
 *  (`SaisieBureau`), si elle est rendue. Aucune (Agenda, Recherche, une autre app de l'ERP) : le dialogue centré. */
function trouverAncre() {
  const ancre = typeof document === 'undefined' ? null : document.querySelector('.tch .saisie-ancre')
  if (!ancre) return null
  return typeof ancre.checkVisibility === 'function' && !ancre.checkVisibility() ? null : ancre
}

/** R3-047 — le projet lu par `#` a sa puce dans le pied de la feuille (« Projet »), pas une seconde sous le champ. */
const TYPES_AU_PIED = ['projet']

/** R3-041 — un bouton qui ne vole pas le focus au champ (le doigt ou la souris le touchent, le clavier reste ouvert). */
const garderLeFocus = (e) => e.preventDefault()

/** Coupure : aucune réponse du serveur (le geste part dans la file, jamais perdu). */
const sansReseau = (err) => classerErreur(err).code === 'reseau'

/**
 * Le contexte de l'écran qui a ouvert la feuille (`taqinor:taches:saisir` → `detail`) : projet courant (Un projet,
 * étape comprise), jour courant (Agenda). Une ligne qui ne nomme pas son projet le reçoit ; le jour devient le
 * « Quand » de départ, visible et retirable.
 */
function lireContexte(detail) {
  const projetId = Number.isInteger(detail?.projet_id) ? detail.projet_id : null
  return {
    projetId,
    projetNom: projetId != null && typeof detail.projet_nom === 'string' ? detail.projet_nom : '',
    sectionId: projetId != null && Number.isInteger(detail.section_id) ? detail.section_id : null,
    // TCH102 — « Nouvelle tâche liée » : l'objet de l'écran d'où part la saisie (`{cible, id, libelle?}`), retirable
    lien: typeof detail?.lien?.cible === 'string' && Number.isInteger(detail.lien.id)
      ? { cible: detail.lien.cible, id: detail.lien.id, libelle: typeof detail.lien.libelle === 'string' ? detail.lien.libelle : '' }
      : null,
  }
}


export default function FeuilleSaisie({ ouverte, onFermer, lienParDefaut = null, demandes = null }) {
  const { societe, compte } = useCompte()
  const cle = cleBrouillon(societe, compte)
  const [initial] = useState(() => lireBrouillon(societe, compte))
  const [texte, setTexte] = useState(() => (Array.isArray(initial?.collages) ? initial.courant ?? '' : initial?.texte ?? ''))
  const [collages, setCollages] = useState(() => (Array.isArray(initial?.collages) ? initial.collages : []))
  const [quand, setQuand] = useState(() => initial?.quand ?? null)
  const [quandOuvert, setQuandOuvert] = useState(false)
  // replié par un VRAI collage d'une liste (aperçu seul) ; une liste reprise du brouillon montre l'aperçu seul, comme avant
  const [champReplie, setChampReplie] = useState(() => (initial?.collages?.length ?? 0) > 0 || String(initial?.texte ?? '').includes('\n'))
  const [ignorer, setIgnorer] = useState([])
  const [priorites, setPriorites] = useState({})
  const [apercu, setApercu] = useState(null)
  const [erreur, setErreur] = useState('')
  const [cid, setCid] = useState(() => nouvelleCle())
  const [contexte, setContexte] = useState(() => lireContexte(null))
  const [quandDepart, setQuandDepart] = useState(null)
  /** Vrai quand le « Quand » affiché est celui que l'écran a posé d'office (jamais choisi à la main) : gardé avec le
   *  brouillon, il ne suit pas la saisie rouverte depuis un écran qui n'en pose pas. */
  const quandAuto = useRef(Boolean(initial?.quandAuto))
  const choisirQuand = (valeur) => { quandAuto.current = false; setQuand(valeur) }
  const enLigne = useEnLigne()
  // R2-009 — au bureau, la saisie s'ouvre à la place de la ligne « Ajouter une tâche » de l'écran (ancre lue à
  // l'ouverture). R3-044 — une liste collée et « Coller mes listes » y restent aussi (plus de bascule en boîte centrée
  // sur voile) ; sans ligne à l'écran (Agenda, autre app), le dialogue centré
  const bureau = useBureau()
  // (la coquille ouvre toujours la feuille APRÈS le montage de l'écran : la ligne est déjà là)
  const ancre = useMemo(() => (ouverte && bureau ? trouverAncre() : null), [ouverte, bureau])
  // R2-003 — les projets du compte, lus une fois à l'ouverture : la liste à `#` et le sélecteur de la puce « Projet »
  const [projets, setProjets] = useState(null)
  const [projetOuvert, setProjetOuvert] = useState(false)
  useEffect(() => {
    if (!ouverte || !enLigne || projets) return undefined
    let vivant = true
    listerTousLesProjets()
      .then((liste) => { if (vivant) setProjets(Array.isArray(liste) ? liste : []) })
      // la liste n'est qu'une aide : sans elle, `#nom` tapé en entier reste lu par le serveur
      .catch(() => { if (vivant) setProjets([]) })
    return () => { vivant = false }
  }, [ouverte, enLigne, projets])
  const projetsOuverts = useMemo(() => (projets ?? []).filter((p) => !p.statut || p.statut !== 'archive'), [projets])
  // couture r2 — le projet de l'écran nommé même quand la demande ne portait que son id (vue pas encore lue)
  const nomProjet = contexte.projetId == null ? ''
    : contexte.projetNom || (projets ?? []).find((p) => p.id === contexte.projetId)?.nom || ''
  // R2-001 — l'envoi part en ARRIÈRE-PLAN : ce qui est à l'écran au retour du serveur est lu ici, jamais une copie figée
  const actuel = useRef({ texte, collages, ouverte })
  useLayoutEffect(() => { actuel.current = { texte, collages, ouverte } })
  const montee = useRef(true)
  useEffect(() => { montee.current = true; return () => { montee.current = false } }, [])
  /** Les envois en vol, enchaînés : les tâches arrivent dans l'ordre tapé. */
  const envois = useRef(Promise.resolve())
  /** R3-046 — la rafale en cours : envois pas encore revenus, et ce qui a été créé (un seul toast à la fin). */
  const rafale = useRef({ enVol: 0, envois: 0, n: 0, gestes: [], message: '' })
  /** Phrases mises de côté par « Reprendre » : chacune revient dans le champ quand la précédente est partie. */
  const suivantes = useRef([])
  const corps = useRef(null)
  /** R4-22 — la phrase dans le champ À CET INSTANT : la valeur du DOM (le navigateur l'a déjà écrite, même si React ne
   *  l'a pas encore rendue), sinon la dernière rendue (feuille fermée). */
  const champCourant = () => corps.current?.querySelector('.saisie-champ')?.value ?? actuel.current.texte

  useEffect(() => { if (compte != null) definirProprietaire(compte) }, [compte])

  // le brouillon suit la frappe ; une phrase vide l'efface
  useEffect(() => {
    const tout = [...collages, texte].filter((t) => t.trim()).join('\n\n')
    ecrireBrouillon(cle, tout ? { texte: tout, quand, quandAuto: Boolean(quand) && quandAuto.current, collages, courant: texte } : null)
  }, [cle, texte, collages, quand])

  const remettreAZero = useCallback(() => {
    setTexte(''); setCollages([]); setQuand(null); setQuandOuvert(false); setChampReplie(false); setIgnorer([])
    setPriorites({}); setApercu(null); setErreur(''); setCid(nouvelleCle()); setContexte(lireContexte(null)); setQuandDepart(null)
  }, [])

  /** Chaîne : la phrase est partie, le champ se vide ; projet et jour de l'écran restent (spec-2 §1). Appelée AU
   *  TOUCHER, avant tout envoi (R2-001) : rien de ce qui est tapé ensuite ne peut être effacé par le retour du serveur. */
  const enchainer = useCallback(() => {
    setTexte(suivantes.current.shift() ?? ''); setIgnorer([]); setApercu(null); setErreur(''); setCid(nouvelleCle())
    setQuand(quandDepart); setQuandOuvert(false)
    // R3-041 — le champ reprend le focus TOUT DE SUITE (« Ajouter » au clavier, Tab puis Entrée) : la phrase suivante
    // se tape aussitôt. Au doigt et à la souris, le bouton ne l'a jamais pris (voir `garderLeFocus`).
    corps.current?.querySelector('.saisie-champ')?.focus()
  }, [quandDepart])

  // déconnexion : plus aucune trace de la phrase (écran, stockage)
  useEffect(() => {
    const surDeconnexion = () => { viderBrouillons(); remettreAZero() }
    window.addEventListener(EVENEMENT_DECONNEXION, surDeconnexion)
    return () => window.removeEventListener(EVENEMENT_DECONNEXION, surDeconnexion)
  }, [remettreAZero])

  // « Coller mes listes » (état vide d'Aujourd'hui) : l'événement de la coquille peut porter `liste` ou `texte` ;
  // Raccord F2 : il porte aussi le contexte de l'écran (`projet_id`, `projet_nom`, `section_id`, `jour_prevu`, `heure_debut`)
  const lienDefaut = useRef(lienParDefaut)
  useEffect(() => { lienDefaut.current = lienParDefaut })
  /** Ce qu'une demande de saisie porte (le `detail` de `taqinor:taches:saisir`) arrive dans la feuille. */
  const recevoir = useCallback((detail) => {
    if (typeof detail.texte === 'string') setTexte(detail.texte)
    if (detail.liste || detail.coller) setChampReplie(false)
    // déjà ouverte (en place au bureau, le focus parti dans la liste) : `n` ou « Ajouter une tâche » ramène au champ
    if (actuel.current.ouverte) requestAnimationFrame(() => corps.current?.querySelector('.saisie-champ')?.focus())
    // TCH102 — `c t` / palette : sans lien dans l'événement, la saisie se lie à l'objet de l'écran (puce retirable)
    setContexte(lireContexte({ ...detail, lien: detail.lien ?? lienDefaut.current }))
    // R2-002 (choix C-1) — ouverte depuis Aujourd'hui sans jour dans la demande : elle part sur aujourd'hui, comme
    // l'Agenda part sur sa case (puce visible et retirable ; une date lue dans la phrase l'emporte)
    const jour = typeof detail.jour_prevu === 'string' && detail.jour_prevu ? detail.jour_prevu
      : surAujourdhui() ? aujourdhuiIso() : null
    if (jour) {
      const depart = { jour_prevu: jour, moment: '', heure_debut: detail.heure_debut ?? null, quelque_jour: false }
      quandAuto.current = true
      setQuand(depart)
      setQuandDepart(depart)
    } else if (quandAuto.current) {
      // couture r2 — le jour posé d'office par un AUTRE écran (brouillon d'Aujourd'hui) ne suit pas : rien de choisi
      quandAuto.current = false
      setQuand(null)
      setQuandDepart(null)
    }
  }, [])
  // Dans /taches la feuille est montée avec la coquille : elle écoute l'événement elle-même. Hors de /taches elle est
  // chargée À PART par l'hôte `TachesPresence`, qui écoute pour elle : elle s'abonne à lui (`demandes.abonner`) et
  // reçoit aussitôt la demande arrivée pendant son chargement — un événement émis avant son montage perdait sinon la
  // phrase tapée et le lien de l'écran. Un seul chemin à la fois, jamais deux lectures de la même demande.
  useEffect(() => {
    if (demandes) return demandes.abonner(recevoir)
    const surSaisir = (e) => recevoir(e?.detail ?? {})
    window.addEventListener(EVENEMENT_SAISIR, surSaisir)
    return () => window.removeEventListener(EVENEMENT_SAISIR, surSaisir)
  }, [demandes, recevoir])

  // Échap ferme, même quand le focus n'est pas dans la feuille (le brouillon, lui, reste) — sauf l'Échap qu'un menu
  // ouvert (puce de priorité de l'aperçu) a pris pour se fermer, lui (`preventDefault` de Radix)
  useEffect(() => {
    if (!ouverte) return undefined
    const surTouche = (e) => { if (e.key === 'Escape' && !e.defaultPrevented) onFermer?.() }
    document.addEventListener('keydown', surTouche)
    return () => document.removeEventListener('keydown', surTouche)
  }, [ouverte, onFermer])

  // l'analyse : une puce par jeton lu. Jamais bloquante : sans réseau, la phrase part quand même.
  useEffect(() => {
    if (!ouverte || !enLigne || ![...collages, texte].some((t) => t.trim())) return undefined
    let vivant = true
    const minuteur = setTimeout(() => {
      saisieRapide(corpsApercu(collages, texte, ignorer), { cle: null, erreurSousLeChamp: true })
        .then((r) => { if (vivant) setApercu({ texte, collages, ignorer, donnees: r.data }) })
        .catch((err) => {
          if (!vivant) return
          setApercu(null)
          if (classerErreur(err).code === 'validation') setErreur(phraseErreur(err))
        })
    }, DELAI_APERCU_MS)
    return () => { vivant = false; clearTimeout(minuteur) }
  }, [ouverte, enLigne, texte, collages, ignorer])

  const frais = apercu && apercu.texte === texte && apercu.collages === collages && apercu.ignorer === ignorer
    ? apercu.donnees : null
  const donneesListe = frais ?? apercu?.donnees ?? null
  const modeListe =collages.length > 0 || texte.includes('\n') || (frais?.lignes?.length ?? 0) > 1
  const ligne = frais?.lignes?.[0] ?? null
  // R2-007 — l'erreur de la ligne lue (« Le titre est trop long : 280 caractères au plus. ») se dit sous le champ
  // (seul le « trop long » se dit pendant la frappe : un titre encore vide, « demain… », n'est pas une faute)
  const titreTropLong = !modeListe && (ligne?.titre?.length ?? 0) > TITRE_MAX && Boolean(ligne?.erreurs?.titre)
  // couture r2 (R2-002) — une date lue dans la phrase l'emporte sur le jour posé d'office par l'écran : la puce « Quand »
  // ne montre plus ce jour-là (le jour lu est la puce de la phrase) ; un Quand choisi à la main reste affiché
  const dateLue = !modeListe && Boolean(ligne?.champs?.jour_prevu || ligne?.champs?.quelque_jour)
  const quandVu = quand && quand === quandDepart && dateLue ? null : quand
  // la phrase lue est déjà là (tâche ouverte identique, ou déjà faite) : Entrée le dit, « Ajouter quand même » l'envoie
  const doubleLu = !modeListe && ligne?.cochee === false ? raisonDouble(ligne) : ''
  const erreurLue = titreTropLong ? messageChamps(ligne.erreurs) : ''
  const nouveauxProjets = useMemo(
    () => (frais?.projets_nouveaux ?? []).map((p) => ({ nom: p.nom, priorite: priorites[p.nom] ?? p.priorite })),
    [frais, priorites],
  )

  const surTexte = (valeur) => { setTexte(valeur); setErreur('') }
  // une LISTE COLLÉE (le texte collé porte un saut de ligne) : le champ se replie dès que l'aperçu est là, la feuille
  // montre l'aperçu seul (premier-usage-1-apercu.html) ; « Coller encore » le rouvre. Relecture adverse F4 n° 3 : seul
  // un vrai collage replie — une suggestion du clavier, une dictée ou un mot collé grandissent aussi le texte d'un coup
  const surColle = (colle) => { if (colle.includes('\n')) setChampReplie(true) }
  /** R2-003 — la puce « Projet » : le projet choisi devient celui de l'écran (puce « ● Nom », retirable). */
  /** R3-047 — un `#projet` déjà lu dans la phrase : le choix du pied le REMPLACE dans le texte (jamais deux `#`, jamais
   *  un « #Ventes » laissé dans le titre), écrit sur la valeur COURANTE du champ. */
  const remplacerProjetLu = (jeton) => setTexte((t) => (
    t.slice(projetLu.debut, projetLu.fin) === projetLu.source
      ? `${t.slice(0, projetLu.debut)}#${jeton}${t.slice(projetLu.fin)}` : t))
  const choisirProjet = (projetId) => {
    const projet = projetsOuverts.find((p) => p.id === projetId)
    if (projetLu && projet) remplacerProjetLu(jetonProjetExistant(projet.nom))
    else setContexte((c) => ({ ...c, projetId: projet ? projet.id : null, projetNom: projet?.nom ?? '', sectionId: null }))
    setProjetOuvert(false)
  }
  /** « + Nouveau projet » / « Créer « nom » » : `#Nom` s'ajoute à la phrase, le serveur le lit « Nouveau projet ». */
  const nouveauProjet = (nom) => {
    const jeton = jetonProjet(nom)
    if (projetLu && jeton) remplacerProjetLu(jeton)
    else setTexte((t) => `${t.trimEnd()}${t.trim() ? ' ' : ''}#${jeton}${jeton ? ' ' : ''}`)
    setProjetOuvert(false)
    requestAnimationFrame(() => corps.current?.querySelector('.saisie-champ')?.focus())
  }
  const basculerQuand = () => { setQuandOuvert((v) => !v); setProjetOuvert(false) }
  const basculerProjet = () => { setProjetOuvert((v) => !v); setQuandOuvert(false) }
  /** R3-045 — le `#projet` lu dans la phrase (il l'emporte sur le projet de l'écran) et la couleur de ce dernier. */
  const projetLu = modeListe ? null : (ligne?.jetons ?? []).find((j) => j.type === 'projet') ?? null
  const couleurDe = (id) => (id == null ? null : (projets ?? []).find((p) => p.id === id)?.couleur ?? null)
  const couleurContexte = couleurDe(contexte.projetId)
  /** R3-047 — ce que la puce « Projet » du pied montre du projet lu : son nom (existant), sinon le libellé servi
   *  (« Nouveau projet : X », « Projet archivé : X ») ; la couleur d'un projet existant seulement. */
  const valeurLue = projetLu?.valeur ?? {}
  const existantLu = Boolean(projetLu) && !valeurLue.nouveau && !valeurLue.archive
  const nomLu = existantLu ? valeurLue.nom ?? String(projetLu.libelle ?? '').replace(/^●\s*/u, '') : projetLu?.libelle ?? ''
  const couleurLu = existantLu ? valeurLue.couleur ?? couleurDe(valeurLue.id) : null
  const surIgnorer = (jeton) => setIgnorer((liste) => [...liste, jeton])
  const surPriorite = (nom, niveau) => setPriorites((p) => ({ ...p, [nom]: niveau }))
  const collerEncore = () => {
    if (texte.trim()) setCollages((liste) => [...liste, texte])
    setTexte(''); setChampReplie(false); setErreur('')
  }

  /* ── R2-001 — l'envoi EN ARRIÈRE-PLAN. Au toucher « Ajouter » / Entrée, la phrase et tout ce qui la décide (Quand,
     contexte, priorités, clé) sont FIGÉS dans un `gel`, le champ se vide aussitôt et l'envoi part ; au retour, seul ce
     gel est lu. Un échec rend la phrase au champ s'il est resté vide, sinon un toast « Pas ajoutée : … · Reprendre ».
     Jamais un `setTexte('')` après un `await`. */

  const restaurer = (gel) => {
    setTexte(gel.texte); setCollages(gel.collages); setIgnorer(gel.ignorer); setQuand(gel.quand)
    quandAuto.current = gel.quand != null && gel.quand === gel.quandDepart
    setPriorites(gel.priorites); setContexte(gel.contexte); setCid(gel.cid); setChampReplie(false); setApercu(null)
  }
  /** Rouvre la feuille fermée entre-temps (l'hôte et la coquille écoutent la même demande). */
  const rouvrir = () => window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail: {} }))
  const reprendre = (gel) => {
    if (!montee.current) { rouvrir(); return } // la phrase a été remise dans le brouillon : la feuille la relit
    if (!actuel.current.ouverte) rouvrir()
    const enCours = champCourant()
    if (enCours.trim()) suivantes.current.push(enCours)
    restaurer(gel)
    // le toast parti, le focus revient au champ : Entrée renvoie la phrase reprise
    requestAnimationFrame(() => corps.current?.querySelector('.saisie-champ')?.focus())
  }
  const echouer = (gel, message) => {
    annoncerEnvoi({ etat: 'echec', envoi: gel.cid })
    // R4-22 — lu et écrit dans la même tâche : une lettre tapée entre les deux est impossible
    const libre = !champCourant().trim() && actuel.current.collages.length === 0
    if (!montee.current) ecrireBrouillon(cle, { texte: [...gel.collages, gel.texte].filter((t) => t.trim()).join('\n\n'), quand: gel.quand })
    else if (libre) flushSync(() => { restaurer(gel); setErreur(message) })
    // feuille ouverte et phrase rendue au champ : l'erreur SOUS le champ suffit ; sinon le toast le dit
    if (montee.current && libre && actuel.current.ouverte) return
    // R3-046 — ce toast-là (« Reprendre ») n'est jamais recouvert par celui de la fin de la rafale
    rafale.current.echecDit = true
    proposerAnnuler({
      message: `Pas ajoutée : ${message}`,
      libelle: 'Reprendre',
      // la phrase est déjà dans le champ (feuille fermée entre-temps) : il suffit de la rouvrir
      onAnnuler: () => (montee.current && libre ? rouvrir() : reprendre(gel)),
    })
  }

  /** Hors ligne (TCH100) : les lignes lues partent dans la file — ou, si personne n'a encore lu la phrase, la PHRASE
   *  elle-même, que le serveur lira au rejeu (R2-008a : « ce soir » devient un jour, plus un mot du titre). R4-22 — la
   *  feuille RESTE ouverte, comme en ligne (chaîne, spec-2 §1) : le retour de la file ne touche ni au champ ni à la
   *  feuille ; Échap ou la croix la ferment. */
  const mettreEnFile = async (gel, lignes) => {
    const depart = gel.quand != null && gel.quand === gel.quandDepart
    try {
      if (lignes) await enfilerAjout(lignes)
      else {
        await enfilerPhrase({
          textes: [...gel.collages, gel.texte], ignorer: gel.ignorer, cid: gel.cid, priorites: gel.priorites,
          quand: depart ? null : gel.quand, quandDefaut: depart ? gel.quand : null, contexte: gel.contexte,
        })
      }
    } catch (err) {
      // sans compte connecté la file refuse : la phrase revient (champ ou brouillon), jamais perdue
      echouer(gel, frenchError(err))
      return
    }
    annoncerEnvoi({ etat: 'en_file', envoi: gel.cid })
    proposerAnnuler({ message: TOAST_EN_FILE, annonce: ANNONCE_EN_FILE })
  }

  /** Les lignes à créer que l'aperçu `donnees` donne pour ce gel (cochées, ou forcées par « Ajouter quand même » /
   *  « Mettre le reste en note »). */
  const lignesLues = (gel, donnees) => {
    // R2-002 — le Quand de DÉPART (jour de l'écran) cède à une date lue dans la phrase ; un Quand choisi à la main, non
    const depart = gel.quand != null && gel.quand === gel.quandDepart
    // R2-007 — « Mettre le reste en note » : la ligne au titre trop long part quand même, coupée
    const coupee = (l) => gel.resteEnNote && (l.titre?.length ?? 0) > TITRE_MAX && Object.keys(l.erreurs ?? {}).every((c) => c === 'titre')
    const forcee = (l) => gel.memeSiDouble && Boolean(raisonDouble(l))
    return (donnees?.lignes ?? []).filter((l) => l.cochee !== false || coupee(l) || forcee(l)).map((l) => {
      const base = construireLigne(l, {
        cid: gel.cid, quand: depart ? null : gel.quand, quandDefaut: depart ? gel.quand : null, priorites: gel.priorites,
      })
      return coupee(l) ? { ...base, ...couperTitre(l.titre) } : base
    })
  }
  /** R3-046 — les lignes annoncées au toucher : les lignes prêtes (liste), celles de l'aperçu frais, sinon la phrase
   *  tapée (une ligne provisoire, que le retour du serveur remplace). */
  const lignesAnnoncees = (gel) => {
    const lignes = gel.lignes ?? (gel.frais ? lignesLues(gel, gel.frais) : [])
    if (lignes.length > 0) return lignes.map((l) => ({ client_id: l.client_id, titre: l.titre, jour: l.jour_prevu ?? null }))
    const titre = [...gel.collages, gel.texte].map((t) => t.trim()).filter(Boolean).join(' ')
    return [{ client_id: `${gel.cid}:0`, titre, jour: gel.quand?.quelque_jour ? null : gel.quand?.jour_prevu ?? null }]
  }

  /** Les lignes du gel : déjà prêtes (liste), lues dans l'aperçu frais, ou demandées au serveur maintenant. */
  const lignesDuGel = async (gel) => {
    if (gel.lignes) return { lignes: gel.lignes }
    let donnees = gel.frais
    if (!donnees) {
      if (!estEnLigne()) return { horsLigne: true }
      try {
        donnees = (await saisieRapide(corpsApercu(gel.collages, gel.texte, gel.ignorer), { cle: null, erreurSousLeChamp: true })).data
      } catch (err) {
        return sansReseau(err) ? { horsLigne: true } : { erreur: phraseErreur(err) }
      }
    }
    const lignes = lignesLues(gel, donnees)
    if (lignes.length > 0) return { lignes }
    // rien à créer : le message du serveur pour la ligne (« trop long », « titre vide »), « Déjà dans ta liste » pour
    // une phrase déjà là, sinon le générique
    const message = (donnees.lignes ?? []).map((l) => messageChamps(l.erreurs) || raisonDouble(l)).find(Boolean)
    return { erreur: message || 'Aucune ligne lisible.' }
  }

  const envoyerEnFond = async (gel) => {
    const lu = await lignesDuGel(gel)
    if (lu.erreur) { echouer(gel, lu.erreur); return }
    if (lu.horsLigne) { await mettreEnFile(gel, null); return }
    const lignes = lu.lignes.map((l) => avecContexte(l, gel.contexte))
    if (!estEnLigne()) { await mettreEnFile(gel, lignes); return }
    let data
    try {
      ({ data } = await saisieRapide({ lignes, apercu: false }, { cle: gel.cid, erreurSousLeChamp: true }))
    } catch (err) {
      if (sansReseau(err)) await mettreEnFile(gel, lignes)
      else echouer(gel, phraseErreur(err))
      return
    }
    const n = data?.creees?.length ?? lignes.length
    const geste = data?.geste_id
    annoncerEnvoi({ etat: 'creees', envoi: gel.cid, creees: data?.creees ?? [] })
    window.dispatchEvent(new CustomEvent(EVENEMENT_CREEES, { detail: { creees: data?.creees ?? [] } }))
    const aujourdhui = gel.depuisAujourdhui && n === 1 && lignes[0]?.jour_prevu === aujourdhuiIso()
    // R3-046 — le toast attend la fin de la rafale (`terminerEnvoi`) : un seul pour cinq phrases, pas cinq « Ajoutée »
    const r = rafale.current
    r.envois += 1
    r.n += n
    if (geste) r.gestes.push(geste)
    r.message = n > 1 ? `${n} tâches créées` : aujourdhui ? TOAST_AJOUTEE_AUJOURDHUI : 'Ajoutée'
  }

  /** R3-046 — un envoi est revenu ; le dernier de la rafale dit ce qui a été créé, en UN toast (« 5 tâches ajoutées »),
   *  dont « Annuler » défait tous les gestes de la rafale. */
  const terminerEnvoi = () => {
    const r = rafale.current
    r.enVol -= 1
    if (r.enVol > 0) return
    if (r.envois === 0 || r.echecDit) {
      rafale.current = { enVol: 0, envois: 0, n: 0, gestes: [], message: '' }
      return
    }
    const gestes = [...r.gestes]
    const message = r.envois > 1 ? `${r.n} tâches ajoutées` : r.message
    rafale.current = { enVol: 0, envois: 0, n: 0, gestes: [], message: '' }
    proposerAnnuler({
      message,
      onAnnuler: gestes.length > 0 ? () => Promise.all(gestes.map((g) => annulerGeste(g))) : undefined,
    })
  }

  /** Fige, vide l'écran TOUT DE SUITE (une phrase : la chaîne reste ouverte ; une liste : la feuille se ferme), envoie. */
  const lancer = (gel, liste) => {
    // R3-046 — annoncé AVANT tout : l'écran montre la ligne « envoi… » à l'instant du toucher
    annoncerEnvoi({ etat: 'part', envoi: gel.cid, lignes: lignesAnnoncees(gel) })
    rafale.current.enVol += 1
    if (liste) { remettreAZero(); onFermer?.() } else enchainer()
    // le brouillon part avec la phrase : l'écran qui le relit (carte « Ta saisie t'attend ») ne doit pas la revoir
    ecrireBrouillon(cle, null)
    // un envoi qui casse ne bloque jamais les suivants : son échec est DIT, la phrase rendue
    envois.current = envois.current.then(() => envoyerEnFond(gel)).catch((err) => echouer(gel, frenchError(err)))
      .finally(terminerEnvoi)
  }
  const geler = (extra = {}) => ({
    texte, collages, ignorer, quand, quandDepart, priorites, contexte, cid, frais, depuisAujourdhui: surAujourdhui(), ...extra,
  })

  /** « Créer N tâches » de l'aperçu d'une liste : les lignes sont prêtes. */
  const creer = (lignes) => lancer(geler({ lignes }), true)

  const envoyer = () => {
    if (!texte.trim()) return
    // R2-007 — un titre trop long ne part pas : le message du serveur reste sous le champ, rien n'est effacé
    if (titreTropLong) { setErreur(erreurLue); return }
    if (doubleLu) { setErreur(doubleLu); return }
    lancer(geler(), modeListe)
  }
  const envoyerQuandMeme = () => { if (texte.trim()) lancer(geler({ memeSiDouble: true }), false) }
  const double = !modeListe && (erreur === DEJA_DANS_LISTE || erreur === DEJA_FAITE)
  const envoyerResteEnNote = () => { if (texte.trim()) lancer(geler({ resteEnNote: true }), false) }

  return (
    <FeuilleACrans
      ouverte={Boolean(ouverte)}
      onFermer={onFermer}
      titre="Ajouter une tâche"
      cranInitial={modeListe ? '85' : '50'}
      variante="popover"
      ancre={ancre}
    >
      <div className="feuille-saisie" ref={corps}>
        {!(modeListe && donneesListe) || !champReplie ? (
          <ChampSaisie
            valeur={texte}
            onChange={surTexte}
            onColle={surColle}
            jetons={modeListe ? [] : ligne?.jetons ?? []}
            alertes={modeListe ? [] : ligne?.alertes ?? []}
            nouveauxProjets={modeListe ? [] : nouveauxProjets}
            onPrioriteProjet={surPriorite}
            onIgnorer={surIgnorer}
            onSoumettre={envoyer}
            erreur={modeListe ? '' : erreur || erreurLue}
            projets={modeListe ? null : projetsOuverts}
            typesAuPied={TYPES_AU_PIED}
          />
        ) : null}
        {titreTropLong ? (
          <p className="aide-champ">
            <span className="chiffres">{`${ligne.titre.length} / ${TITRE_MAX}`}</span>
            {' · '}
            <button type="button" className="bouton discret" onClick={envoyerResteEnNote}>Mettre le reste en note</button>
          </p>
        ) : null}
        {double ? (
          <p className="aide-champ">
            <button type="button" className="bouton discret" onClick={envoyerQuandMeme}>Ajouter quand même</button>
          </p>
        ) : null}
        {modeListe && donneesListe ? (
          <ColleListes
            apercu={donneesListe}
            cid={cid}
            priorites={priorites}
            projets={projetsOuverts}
            onPriorite={surPriorite}
            onCreer={creer}
            onCollerEncore={collerEncore}
            erreur={erreur}
          />
        ) : null}
        {modeListe ? null : (
          <>
            {quandOuvert ? <SelecteurQuand valeur={quand ?? undefined} onChoisir={choisirQuand} /> : null}
            {projetOuvert ? (
              <SelecteurProjet
                projets={projetsOuverts}
                valeur={contexte.projetId}
                chargement={projets === null}
                onChoisir={choisirProjet}
                onNouveau={nouveauProjet}
              />
            ) : null}
            <div className="saisie-pied">
              <span className="puces">
                {/* R3-045 — le × du jour est DANS sa puce (comme les puces lues), plus une bulle qui ne contient qu'une
                    croix ; la puce ouvre « Quand », son × le retire */}
                {quandVu ? (
                  <span className="puce lue" data-jeton="quand">
                    <Calendar className="i i-16" aria-hidden="true" />
                    <button type="button" className="cible" aria-expanded={quandOuvert} onClick={basculerQuand}>
                      <span className="chiffres">{libelleQuand(quandVu)}</span>
                    </button>
                    <button type="button" className="retirer" aria-label="Retirer le jour choisi" onClick={() => { choisirQuand(null); setQuandOuvert(false) }}>
                      <X aria-hidden="true" />
                    </button>
                  </span>
                ) : (
                  <button type="button" className="puce vide" aria-expanded={quandOuvert} onClick={basculerQuand}>
                    <Calendar className="i i-16" aria-hidden="true" />
                    <span className="chiffres">{libelleQuand(quandVu)}</span>
                  </button>
                )}
                {/* R3-047 — la puce « Projet » du pied MONTRE le projet lu par `#` (une seule puce : celle de dessous le
                    champ ne se répète pas) ; la toucher ouvre le sélecteur, qui remplace le `#projet` dans la phrase.
                    R3-045 — le projet de l'écran : un point de SA couleur (`data-p`), jamais un « ● » de texte noir ; un
                    `#projet` lu dans la phrase l'emporte (`avecContexte`) : il prend sa place */}
                {projetLu ? (
                  <span
                    className={valeurLue.nouveau ? 'puce nouveau' : couleurLu ? 'puce projet-lu' : 'puce lue'}
                    data-jeton="projet"
                    data-p={couleurLu || undefined}
                  >
                    {couleurLu ? <i className="point" aria-hidden="true" /> : null}
                    <button type="button" className="cible" aria-expanded={projetOuvert} onClick={basculerProjet}>
                      <span className="projet-nom">{nomLu}</span>
                    </button>
                    <button type="button" className="retirer" aria-label={`Retirer ${nomLu}`}
                      onClick={() => surIgnorer({ type: projetLu.type, source: projetLu.source })}>
                      <X aria-hidden="true" />
                    </button>
                  </span>
                ) : contexte.projetId != null && nomProjet ? (
                  <button type="button" className={couleurContexte ? 'puce projet-lu' : 'puce lue'} data-p={couleurContexte || undefined}
                    aria-label={`Retirer « ${nomProjet} »`}
                    onClick={() => setContexte((c) => ({ ...c, projetId: null, projetNom: '', sectionId: null }))}>
                    {couleurContexte ? <i className="point" aria-hidden="true" /> : null}
                    <span className="projet-nom">{nomProjet}</span>
                    <X className="i i-14" aria-hidden="true" />
                  </button>
                ) : (
                  <button type="button" className="puce vide" aria-expanded={projetOuvert} onClick={basculerProjet}>
                    <Folder className="i i-16" aria-hidden="true" />
                    <span>Projet</span>
                  </button>
                )}
                {contexte.lien ? (
                  <button type="button" className="puce lue" aria-label={`Retirer le lien « ${contexte.lien.libelle || 'cette fiche'} »`}
                    onClick={() => setContexte((c) => ({ ...c, lien: null }))}>
                    <span>{`Lié à : ${contexte.lien.libelle || 'cette fiche'}`}</span>
                    <X className="i i-14" aria-hidden="true" />
                  </button>
                ) : null}
              </span>
              <button
                type="button"
                className="bouton plein"
                aria-disabled={!texte.trim() || titreTropLong || undefined}
                // R3-041 — toucher « Ajouter » ne prend pas le focus au champ : le clavier de l'iPhone reste ouvert et
                // la frappe suivante va dans le champ (même geste que la liste des projets `#`)
                onMouseDown={garderLeFocus}
                onClick={envoyer}
              >
                Ajouter
              </button>
            </div>
          </>
        )}
        {enLigne ? null : <p className="aide-champ" role="status">Hors ligne : elle partira dès le retour du réseau.</p>}
      </div>
    </FeuilleACrans>
  )
}
