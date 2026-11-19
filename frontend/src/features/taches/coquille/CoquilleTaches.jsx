import { useCallback, useContext, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { ReactReduxContext } from 'react-redux'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Bell, ChevronLeft, CloudOff, Ellipsis, Menu, Plus, Search, X } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import Fiche from '../fiche/Fiche'
import FeuilleSaisie from '../saisie/FeuilleSaisie'
import { annulerToast, configurerGestes, fermerToast, pauserToast, proposerAnnuler, reprendreToast, useEtatGestes } from '../lib/gestes'
import BandeauConflit from '../ui/BandeauConflit'
import BarreSelection from '../ui/BarreSelection'
import BoutonCopilote from '../ui/BoutonCopilote'
import FeuilleACrans from '../ui/FeuilleACrans'
import SelecteurProjet from '../ui/SelecteurProjet'
import { useEnLigne } from '../lib/enLigne'
import { definirProprietaire } from '../../../api/tachesApi'
import { derniereSynchro as lireDerniereSynchro, viderCacheALaDeconnexion } from '../horsligne/cacheJournee'
import {
  MESSAGE_AUTRE_COMPTE, brancherRejeu, definirCompteFile, etatFile, garderLaMienne, prendreLAutre, rejouerFile, useVersionFile,
} from '../horsligne/captureQueue'
import { heureDuConflit } from '../lib/textes'
import { MARQUE_FICHE } from '../lib/fiche'

/* ============================================================================
   TCH43 — LA coquille de l'app Tâches : UNE seule, montée par chaque page de
   `pages/taches/*` (jamais recopiée). Elle porte la classe racine `.tch` — la seule
   porte d'entrée des styles de `styles/taches/*` — et, une fois pour toutes :
     · l'en-tête (date, titre de page en Archivo, loupe, ⋯) ;
     · le bouton flottant « Ajouter » (iPhone) / la ligne « Ajouter une tâche · n » (bureau) ;
     · la fiche d'une tâche, ouverte par `?tache=<id>` ;
     · la feuille de saisie, ouverte par ce bouton ou par l'événement
       `taqinor:taches:saisir` (touche `c t`, palette, cockpit) ;
     · le bouton « Copilote » (TCH45) et les composants partagés que chaque écran pilote par
       une prop : `feuille` (FeuilleACrans), `selecteurProjet` (SelecteurProjet dans sa feuille),
       `selection` (BarreSelection des actions en lot) ;
     · l'état « Hors ligne » (`useEnLigne`) et, depuis TCH100, la file d'envoi hors ligne : « Hors ligne · dernière synchro à
       {HH:MM} », « En attente d'envoi ({n}) », le rejeu au retour du réseau, le bandeau de conflit d'une op en file, et le
       grisage de tout geste marqué `data-necessite-reseau` (« Possible une fois connecté », textes.md §2.1).
   L'ERP fournit lui-même barre latérale, barre d'onglets et en-tête global : la coquille
   n'invente aucune navigation (le module reste invisible jusqu'à l'activation, TCH131).
   R2-080 (choix C-6) — sur iPhone (≤ 768 px, le seuil de la coque de l'ERP), l'en-tête de l'ERP est masqué DANS Tâches
   (styles/taches/base.css, sélecteur limité aux pages du module) : la rangée du haut de la coquille porte alors ☰ (le
   tiroir de l'ERP, par son propre bouton) et la cloche de l'ERP (son propre panneau) ; le grand titre se replie en
   titre compact collant au défilement (maquette ecran-aujourdhui-matin-bas.html). Bureau : rien ne change.
   Maquettes : docs/taches/maquettes/composants-5.html, ecran-aujourdhui-matin.html.
   ========================================================================== */

/** Événement DOM qui ouvre la feuille de saisie (`detail` facultatif : texte, projet). */
export const EVENEMENT_SAISIR = 'taqinor:taches:saisir'
/** Émis à la fermeture de la feuille de saisie (Aujourd'hui relit alors son brouillon : carte « Reprendre »). */
export const EVENEMENT_SAISIE_FERMEE = 'taqinor:taches:saisie-fermee'

const DESTINATIONS = [
  ['Revue de la semaine', '/taches/revue'],
  ['Mon rythme', '/taches/rythme'],
  ['Supprimées et derniers gestes', '/taches/supprimees'],
  ['Réglages', '/taches/reglages'],
]

/** R2-087 — l'aide des touches de Tâches (`?`), mot pour mot textes.md §2.1 « Aide des touches ». Couture r2 — l'aide
 *  dit la VÉRITÉ de l'écran ouvert : une touche n'y figure que sur les écrans dont la liste la traite (3e terme ;
 *  absent : partout). Maj+↓ n'allonge que la tâche qu'on vient de poser dans l'Agenda. */
const LISTES = ['aujourdhui', 'projet']
/* R3-095 — les touches les plus utilisées d'abord : j/k, Entrée, Échap (elles manquaient). « Alt+↑/↓ Réorganiser » est
   retiré tant que le réordonnancement au clavier n'est pas réparé (R3-007, R3-026) : l'aide ne promet que ce qui marche. */
const TOUCHES = [
  ['j / k', 'Ligne suivante / précédente', [...LISTES, 'a-trier', 'recherche']],
  ['Entrée', 'Ouvrir', [...LISTES, 'a-trier', 'recherche']], ['Échap', 'Fermer'],
  ['c t', 'Créer une tâche'], ['g j', "Aujourd'hui"], ['n', 'Ajouter ici'], ['/', 'Chercher'],
  ['Espace', 'Fait', [...LISTES, 'recherche']],
  ['e', 'Renommer', [...LISTES, 'a-trier', 'recherche']], ['d', 'Quand', [...LISTES, 'a-trier']],
  ['m', 'Changer de projet', [...LISTES, 'a-trier']], ['x', 'Sélectionner', ['aujourdhui']],
  ['h', 'Heure', [...LISTES, 'a-trier', 'recherche']], ['*', 'Essentiel', LISTES],
  ['Maj+↓', '+15 min (tâche posée)', ['agenda']],
  ['Ctrl/⌘ Z', 'Annuler (hors champ)', LISTES],
]

function AideTouches({ ecran }) {
  const visibles = TOUCHES.filter(([, , ecrans]) => !ecrans || ecrans.includes(ecran))
  return (
    // focus initial sur la liste : au bureau, la poignée (premier focalisable de la feuille) est masquée et ne prend
    // pas le focus — sans lui, Échap (écouté par la feuille) ne fermait pas l'aide
    <dl className="touches" tabIndex={-1} data-focus-initial>
      {visibles.map(([touche, effet]) => (
        <div key={touche} className="touches-ligne">
          <dt><kbd>{touche}</kbd></dt>
          <dd>{effet}</dd>
        </div>
      ))}
    </dl>
  )
}

/** R2-088 — « Messages sans délai », gardé sur l'appareil par compte (stockage indisponible : rien n'est gardé). */
const cleSansDelai = (compte) => `taqinor:taches:sans-delai:${compte}`
function lireSansDelaiGarde(compte) {
  try {
    const valeur = window.localStorage.getItem(cleSansDelai(compte))
    return valeur === null ? null : valeur === '1'
  } catch {
    return null
  }
}
function garderSansDelai(compte, valeur) {
  try {
    window.localStorage.setItem(cleSansDelai(compte), valeur ? '1' : '0')
    return true
  } catch {
    return false // stockage indisponible (navigation privée) : le réglage vaudra au prochain passage dans Réglages
  }
}

/** Une boîte qui prend la main (dialogue modal, confirmation) : les touches du module se taisent dessous. Le panneau
 *  de la fiche et la saisie en place (`aria-modal="false"`) laissent la liste — et les touches — à la personne. */
const MODALE = '[role="dialog"]:not([aria-modal="false"]), [role="alertdialog"]'

/** R2-084 — les écrans dont la liste reçoit le bouton flottant « Ajouter une tâche ». */
const ECRANS_AVEC_FAB = new Set(['aujourdhui', 'a-trier', 'projets', 'projet', 'agenda'])
/** R3-087 — les écrans qui portent la ligne « Ajouter une tâche · n » du bureau sous l'en-tête : ceux où l'on range des
 *  tâches (Aujourd'hui rend la sienne, sous la progression). Ni Modèles, ni Archive, ni Revue, ni Réglages, ni Mon rythme,
 *  ni Supprimées, ni Recherche (R2-086) : la touche `n` y reste. */
const ECRANS_AVEC_SAISIE = new Set(['a-trier', 'projets', 'projet', 'agenda'])

/** Le message dit à qui touche un geste grisé hors ligne (textes.md §2.1). */
export const PHRASE_GESTE_GRISE = 'Possible une fois connecté'

/* R2-080 — sur iPhone, l'en-tête de l'ERP est masqué dans Tâches (base.css) mais reste MONTÉ : ses boutons gardent
   leur effet. ☰ et la cloche de la coquille les actionnent, sans rien dupliquer (un seul tiroir, un seul panneau de
   notifications, un seul sondage du compteur). */
const SELECTEUR_MENU_ERP = '.layout-main > .header .header-menu-btn'
const SELECTEUR_CLOCHE_ERP = '.layout-main > .header .nb-wrap > .nb-btn'
const SELECTEUR_PANNEAU_ERP = '.layout-main > .header .nb-panel'

function BoutonMenuErp() {
  return (
    <button
      type="button"
      className="bouton-icone entete-menu"
      aria-label="Ouvrir le menu"
      onClick={() => document.querySelector(SELECTEUR_MENU_ERP)?.click()}
    >
      <Menu className="i" aria-hidden="true" />
    </button>
  )
}

// L'étiquette de la cloche de l'ERP (« Notifications (3) ») porte son compteur : on la lit, on suit ses changements.
const etiquetteClocheErp = () => document.querySelector(SELECTEUR_CLOCHE_ERP)?.getAttribute('aria-label') ?? null
function suivreClocheErp(rappel) {
  const cloche = document.querySelector(SELECTEUR_CLOCHE_ERP)
  if (!cloche || typeof MutationObserver === 'undefined') return () => {}
  const observateur = new MutationObserver(rappel)
  observateur.observe(cloche, { attributes: true, attributeFilter: ['aria-label'] })
  return () => observateur.disconnect()
}

/** La cloche de l'ERP, atteinte en un toucher depuis Tâches : son compteur est lu sur le bouton de l'ERP, le panneau
 *  ouvert est celui de l'ERP. Rien n'est rendu hors de la coque de l'ERP (tests, pages sans en-tête). */
function ClocheErp() {
  const etiquette = useSyncExternalStore(suivreClocheErp, etiquetteClocheErp, () => null)
  const ouverteAuPointeur = useRef(null)
  if (etiquette === null) return null
  const trouve = etiquette.match(/\((\d+)\)/)
  const compte = trouve ? Number(trouve[1]) : 0
  // le nom lu contient EXACTEMENT ce qui est écrit sur la pastille (« 99+ » au-delà de 99), en mot séparé — « Notifications : 14 »,
  // pas « Notifications (14) » : axe-core 4.14 ne reconnaît pas le texte visible collé à une parenthèse — sinon le nom accessible
  // contredit le texte visible (axe : label-content-name-mismatch)
  const affiche = compte > 99 ? '99+' : String(compte)
  return (
    <button
      type="button"
      className="bouton-icone entete-cloche"
      aria-label={compte > 0 ? `Notifications : ${affiche}` : 'Notifications'}
      // le panneau de l'ERP se ferme de lui-même au premier appui hors de sa cloche : un appui sur CETTE cloche,
      // panneau ouvert, doit le laisser fermé (sinon il se rouvrirait aussitôt)
      onPointerDown={() => { ouverteAuPointeur.current = Boolean(document.querySelector(SELECTEUR_PANNEAU_ERP)) }}
      onClick={() => {
        const etaitOuverte = ouverteAuPointeur.current
        ouverteAuPointeur.current = null
        if (etaitOuverte) return
        document.querySelector(SELECTEUR_CLOCHE_ERP)?.click()
      }}
    >
      <Bell className="i" aria-hidden="true" />
      {compte > 0 ? <span className="entete-cloche-compte chiffres" aria-hidden="true">{affiche}</span> : null}
    </button>
  )
}

/** R2-080 — le grand titre se replie en titre compact (rangée du haut) quand il passe sous elle au défilement. */
function useTitreReplie(barre, titre) {
  const [replie, setReplie] = useState(false)
  useEffect(() => {
    const rangee = barre.current
    const h1 = titre.current
    if (!rangee || !h1 || typeof IntersectionObserver === 'undefined') return undefined
    const bas = Math.round(rangee.getBoundingClientRect().bottom)
    if (bas <= 0) return undefined // bureau : la rangée n'a pas de boîte, pas de titre compact
    const observateur = new IntersectionObserver(
      ([entree]) => setReplie(!entree.isIntersecting && entree.boundingClientRect.top < bas),
      { rootMargin: `-${bas}px 0px 0px 0px` },
    )
    observateur.observe(h1)
    return () => observateur.disconnect()
  }, [barre, titre])
  return replie
}

function MenuPlus({ actionsEcran, navigate, enLigne }) {
  const aller = (vers) => (e) => {
    if (enLigne) { navigate(vers); return }
    e.preventDefault()
    proposerAnnuler({ message: PHRASE_GESTE_GRISE })
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className="bouton-icone" aria-label="Plus d'actions">
          <Ellipsis className="i" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {actionsEcran.map(({ libelle, onSelect }) => (
          <DropdownMenuItem key={libelle} onSelect={onSelect}>{libelle}</DropdownMenuItem>
        ))}
        {actionsEcran.length > 0 ? <DropdownMenuSeparator /> : null}
        {DESTINATIONS.map(([libelle, vers]) => (
          <DropdownMenuItem key={vers} aria-disabled={enLigne ? undefined : 'true'} style={enLigne ? undefined : { opacity: 0.5 }} onSelect={aller(vers)}>
            {libelle}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/**
 * TCH46 — annonces et toast : la région `role=status` (lue par le lecteur d'écran) et LE toast
 * « … · Annuler » (8 s, en pause au survol et au focus ; « Messages sans délai » : jusqu'à
 * fermeture). Lus dans `lib/gestes.js`, jamais posés ailleurs.
 */
export function ZoneAnnonces() {
  const { annonce, rang, toast, sansDelai } = useEtatGestes()
  return (
    <>
      <div className="annonce" role="status" aria-live="polite" aria-atomic="true">
        {annonce ? `${annonce}${rang % 2 ? '' : ' '}` : ''}
      </div>
      {toast ? (
        <div className="toast-place">
          <div
            className="toast"
            role="group"
            aria-label="Geste effectué"
            onMouseEnter={() => pauserToast('survol')}
            onMouseLeave={() => reprendreToast('survol')}
            onFocus={() => pauserToast('focus')}
            onBlur={() => reprendreToast('focus')}
          >
            <span>{toast.message}</span>
            {toast.onAnnuler ? <button type="button" onClick={annulerToast}>{toast.libelle}</button> : null}
            {sansDelai ? (
              <button type="button" aria-label="Fermer" onClick={fermerToast}><X className="i" aria-hidden="true" /></button>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  )
}

/** La ligne « Ajouter une tâche · n » du bureau. Un écran qui la veut AILLEURS que sous l'en-tête (Aujourd'hui : sous la
 *  progression, maquette ecran-aujourdhui-matin.html) passe `saisieBureau={false}` à la coquille et la rend lui-même.
 *  R2-009 (choix C-3) — `.saisie-ancre`, juste après la ligne, reçoit la saisie EN PLACE au bureau (FeuilleSaisie la
 *  trouve et y rend sa feuille, sans voile : la liste reste lisible et vivante dessous, comme Things et Todoist) ; vide,
 *  elle n'a pas de boîte. */
export function SaisieBureau({ onClick }) {
  return (
    <>
      <button type="button" className="saisie-bureau bureau-seul" onClick={onClick}>
        <Plus className="i" aria-hidden="true" />
        Ajouter une tâche
        <kbd aria-hidden="true">n</kbd>
      </button>
      <div className="saisie-ancre bureau-seul" />
    </>
  )
}

/**
 * `retour` (R2-093, écrans enfants) : `{ libelle, vers }` — `libelle` est le nom de l'écran parent (« Projets »,
 * « Réglages »), `vers` son chemin (`/taches/projets`). Exemple : `retour={{ libelle: 'Projets', vers: '/taches/projets' }}`.
 * Rendu « ‹ {libelle} » au-dessus du titre ; l'écran enfant n'a alors ni loupe ni Copilote (le ⋯ reste).
 * `saisieBureau` (R3-087) : la ligne « Ajouter une tâche » du bureau ; sans valeur, les écrans de ECRANS_AVEC_SAISIE.
 * `largeur` (R3-082, M3) : `"pleine"` pose `data-largeur="pleine"` — le contenu prend toute la largeur utile au bureau
 * (agenda, tableau, chronologie, Planifier) ; l'en-tête reste sur sa bande de 1 320 px (base.css).
 */
export default function CoquilleTaches({
  ecran, titre, sousTitre = null, actionsEcran = [], derniereSynchro = null,
  feuille = null, selecteurProjet = null, selection = null, copilote = {}, conflit = null, contexteSaisie = null,
  saisieBureau = null, retour = null, largeur = null, children,
}) {
  const navigate = useNavigate()
  const { pathname, state: etatLieu } = useLocation()
  const enLigne = useEnLigne()
  const [params, setParams] = useSearchParams()
  const redux = useContext(ReactReduxContext)
  const utilisateur = redux?.store?.getState?.().auth?.user ?? null
  const userId = Number.isInteger(utilisateur?.id) ? utilisateur.id : null
  const companyId = utilisateur?.active_company_id ?? null
  const versionFile = useVersionFile()
  const [file, setFile] = useState({ enAttente: 0, conflits: [] })
  const [saisieOuverte, setSaisieOuverte] = useState(false)
  const [aideTouches, setAideTouches] = useState(false)
  const tacheId = params.get('tache')
  // R2-084 — le + n'apparaît que là où l'on ajoute des tâches à une liste ; jamais dans un parcours (Planifier le
  // projet, Planifier ma semaine, Revue) ni dans Réglages, Recherche, Mon rythme, Supprimées (journée vide : base.css)
  const avecFab = ECRANS_AVEC_FAB.has(ecran)
    && !(ecran === 'agenda' && params.get('placer') === '1')
    && !(ecran === 'projet' && params.get('planifier') === '1')
  // R2-086 — sur la Recherche, son champ EST l'en-tête : ni loupe (qui ouvrait… la recherche) ni « Ajouter une tâche »
  const surRecherche = ecran === 'recherche'
  const avecSaisieBureau = !surRecherche && (saisieBureau ?? ECRANS_AVEC_SAISIE.has(ecran))
  const barre = useRef(null)
  const titreH1 = useRef(null)
  const replie = useTitreReplie(barre, titreH1)

  const ouvrirSaisie = useCallback(() => setSaisieOuverte(true), [])
  const fermerSaisie = useCallback(() => {
    setSaisieOuverte(false)
    window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIE_FERMEE))
  }, [])
  // « + » et « Ajouter une tâche » passent par l'événement : la feuille reçoit le contexte de l'écran (projet, jour)
  const demanderSaisie = useCallback(() => {
    window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail: contexteSaisie ?? {} }))
  }, [contexteSaisie])
  // Raccord F2 — ouverte par `useOuvrirFiche` (entrée d'historique marquée), la fiche se ferme par le retour : le
  // bouton « retour » du navigateur et la croix font la même chose, on ne quitte jamais l'écran.
  const fermerFiche = useCallback(() => {
    if (etatLieu?.[MARQUE_FICHE]) { navigate(-1); return }
    setParams((actuels) => {
      const suite = new URLSearchParams(actuels)
      // la fiche et ce qu'elle a ouvert (`section=decouper`, `focus=titre|heure` — useOuvrirFiche) partent ensemble
      ;['tache', 'section', 'focus'].forEach((cle) => suite.delete(cle))
      return suite
    }, { replace: true })
  }, [setParams, navigate, etatLieu])

  // Hors ligne (TCH100) : le compte qui écrit, le rejeu au retour du réseau, le vidage à la déconnexion.
  useEffect(() => {
    definirProprietaire(userId)
    definirCompteFile(userId, companyId)
    if (userId === null) return undefined
    const retirer = brancherRejeu({ surJetees: () => proposerAnnuler({ message: MESSAGE_AUTRE_COMPTE }) })
    const retirerCache = viderCacheALaDeconnexion()
    rejouerFile()
    return () => { retirer(); retirerCache() }
  }, [userId, companyId])

  // R2-088 — « Messages sans délai » vaut dès l'ouverture de Tâches (et après un rechargement), pas seulement après un
  // passage dans Réglages : la dernière valeur connue (celle que Réglages a lue au serveur ou posée) est gardée sur
  // l'appareil et rendue aux gestes au montage — sans requête de plus (aucun écran ne paie un GET pour elle, hors ligne
  // compris). Un réglage changé sur un AUTRE appareil vaut ici au premier passage dans Réglages.
  const { sansDelai } = useEtatGestes()
  const compteGestes = userId ?? 'anonyme'
  useEffect(() => {
    const garde = lireSansDelaiGarde(compteGestes)
    if (garde !== null) configurerGestes({ sansDelai: garde })
  }, [compteGestes])
  useEffect(() => { garderSansDelai(compteGestes, sansDelai) }, [compteGestes, sansDelai])

  // L'état de la file (en attente, conflits) se relit quand elle bouge.
  useEffect(() => {
    let vivant = true
    etatFile().then((etat) => { if (vivant) setFile(etat) })
    return () => { vivant = false }
  }, [versionFile])

  useEffect(() => {
    window.addEventListener(EVENEMENT_SAISIR, ouvrirSaisie)
    return () => window.removeEventListener(EVENEMENT_SAISIR, ouvrirSaisie)
  }, [ouvrirSaisie])

  // Touche `n` « Ajouter ici » (textes.md §2.1) : la saisie, avec le contexte de l'écran. Jamais dans un champ ni
  // sous une feuille MODALE ; le panneau de la fiche et la saisie en place (non modaux, la liste reste à la main) ne
  // la bloquent pas. Elle n'écrit rien (aucun raccourci destructif).
  useEffect(() => {
    const surTouche = (e) => {
      if (e.key !== 'n' || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return
      if (e.target?.closest?.(`input, textarea, select, [contenteditable="true"], ${MODALE}`)) return
      if (document.querySelector(MODALE)) return
      e.preventDefault()
      demanderSaisie()
    }
    document.addEventListener('keydown', surTouche)
    return () => document.removeEventListener('keydown', surTouche)
  }, [demanderSaisie])

  // R2-087 — dans Tâches, `?` montre les touches DU MODULE (pas l'aide générale de l'ERP) et `/` va à la Recherche
  // (sur la Recherche : dans son champ). Écouté sur `document`, donc AVANT l'écouteur de l'ERP (posé sur `window`),
  // qui ne reçoit plus la touche. Jamais dans un champ ni sous une boîte ouverte ; aucune des deux n'écrit rien.
  useEffect(() => {
    const surTouche = (e) => {
      if ((e.key !== '?' && e.key !== '/') || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return
      if (e.target?.closest?.(`input, textarea, select, [contenteditable="true"], ${MODALE}`)) return
      if (document.querySelector(MODALE)) return
      e.preventDefault()
      e.stopPropagation()
      if (e.key === '?') { setAideTouches(true); return }
      const champ = document.querySelector('.tch input[type="search"]')
      if (champ) champ.focus()
      else navigate('/taches/recherche')
    }
    document.addEventListener('keydown', surTouche)
    return () => document.removeEventListener('keydown', surTouche)
  }, [navigate])

  const synchro = derniereSynchro ?? (userId === null ? null : lireDerniereSynchro(userId))
  const premierConflit = file.conflits[0]
  const conflitFile = premierConflit ? {
    heure: heureDuConflit(premierConflit.actuel),
    onGarder: async () => { await garderLaMienne(premierConflit.opId); await rejouerFile() },
    onPrendre: () => prendreLAutre(premierConflit.opId),
  } : null
  const surClicCapture = (e) => {
    if (enLigne || !e.target.closest?.('[data-necessite-reseau]')) return
    e.preventDefault()
    e.stopPropagation()
    proposerAnnuler({ message: PHRASE_GESTE_GRISE })
  }

  return (
    <div
      className="tch"
      data-ecran={ecran}
      data-largeur={largeur === 'pleine' ? 'pleine' : undefined}
      data-hors-ligne={enLigne ? undefined : 'true'}
      onClickCapture={surClicCapture}
    >
      <div className="tch-page">
        {/* R2-080 — la rangée du haut (☰, titre compact, actions) colle en haut de l'écran sur iPhone ; au bureau elle
            n'a pas de boîte (`display: contents`) et ses actions se posent à droite du titre, comme avant. */}
        <header className="entete">
          {/* R3-083 — l'état replié s'appelle `entete-repliee` : la classe `replie` est celle des sections repliées
              d'Aujourd'hui (`.tch .replie` : marge, rembourrage de 16, espacement de 8, texte doux) et la rangée en
              héritait au défilement — ses icônes glissaient de 10 pt et le titre compact passait en gris. */}
          <div className={`entete-barre${replie ? ' entete-repliee' : ''}`} ref={barre}>
            {/* R2-093 — un écran ENFANT (projet, sous-page de Réglages) passe `retour` : « ‹ {libelle} » se pose
                AU-DESSUS du titre (iPhone : à la place de ☰ ; bureau : sur la ligne du sur-titre), et l'écran
                enfant ne répète ni la loupe ni le Copilote. */}
            {retour ? (
              <button type="button" className="entete-retour" onClick={() => navigate(retour.vers)}>
                <ChevronLeft className="i" aria-hidden="true" />{retour.libelle}
              </button>
            ) : <BoutonMenuErp />}
            {/* R3-083 — sur iPhone la cloche se range à GAUCHE, à côté de ☰ : deux icônes à gauche, trois à droite (loupe ·
                Copilote · ⋯), le titre compact centré sur l'écran entre les deux groupes. Bureau : elle n'est pas rendue. */}
            <ClocheErp />
            <div className="entete-compact" aria-hidden="true" inert>{titre}</div>
            <div className="entete-actions">
              {retour || surRecherche ? null : (
                <button
                  type="button"
                  className="bouton-icone"
                  aria-label="Chercher dans mes tâches"
                  onClick={() => navigate('/taches/recherche')}
                >
                  <Search className="i" aria-hidden="true" />
                </button>
              )}
              {retour ? null : <BoutonCopilote ecran={pathname} {...copilote} />}
              <MenuPlus actionsEcran={actionsEcran} navigate={navigate} enLigne={enLigne} />
            </div>
          </div>
          <div className="entete-titres">
            {/* le sur-titre garde sa ligne même vide : le grand titre est au même endroit sur tous les écrans */}
            <div className="entete-surtitre">
              {enLigne ? (
                sousTitre ? <div className="entete-date">{sousTitre}</div> : null
              ) : (
                <div className="entete-date" role="status">
                  <CloudOff className="i i-14" aria-hidden="true" />
                  <span className="chiffres">
                    {synchro ? ` Hors ligne · dernière synchro à ${synchro}` : ' Hors ligne'}
                  </span>
                </div>
              )}
              {file.enAttente > 0 ? (
                <div className="entete-date" role="status"><span className="chiffres">{`En attente d'envoi (${file.enAttente})`}</span></div>
              ) : null}
            </div>
            <h1 className="entete-titre" ref={titreH1}>{titre}</h1>
          </div>
        </header>

        {avecSaisieBureau ? <SaisieBureau onClick={demanderSaisie} /> : null}

        {conflit ?? conflitFile ? <BandeauConflit {...(conflit ?? conflitFile)} /> : null}

        {children}
      </div>

      {selection && selection.n > 0 ? (
        <BarreSelection {...selection} />
      ) : avecFab ? (
        <button type="button" className="fab mobile-seul" aria-label="Ajouter une tâche" onClick={demanderSaisie}>
          <Plus className="i" aria-hidden="true" />
        </button>
      ) : null}

      {tacheId ? <Fiche id={tacheId} onFermer={fermerFiche} /> : null}
      <FeuilleSaisie ouverte={saisieOuverte} onFermer={fermerSaisie} />
      {feuille ? <FeuilleACrans {...feuille} /> : null}
      <FeuilleACrans ouverte={aideTouches} onFermer={() => setAideTouches(false)} titre="Touches de Tâches" cranInitial="85">
        <AideTouches ecran={ecran} />
      </FeuilleACrans>
      <ZoneAnnonces />
      {selecteurProjet ? (
        <FeuilleACrans
          ouverte={Boolean(selecteurProjet.ouverte)}
          onFermer={selecteurProjet.onFermer}
          titre={selecteurProjet.titre ?? 'Projet'}
          cranInitial="85"
        >
          <SelecteurProjet
            projets={selecteurProjet.projets}
            valeur={selecteurProjet.valeur}
            sansProjet={selecteurProjet.sansProjet}
            chargement={selecteurProjet.chargement}
            focusChamp={selecteurProjet.focusChamp}
            onChoisir={selecteurProjet.onChoisir}
            onNouveau={selecteurProjet.onNouveau}
          />
        </FeuilleACrans>
      ) : null}
    </div>
  )
}
