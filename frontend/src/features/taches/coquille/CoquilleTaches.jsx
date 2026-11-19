import { useCallback, useContext, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { ReactReduxContext } from 'react-redux'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Bell, ChevronLeft, CloudOff, Ellipsis, Menu, Plus, Search, X } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import Fiche from '../fiche/Fiche'
import FeuilleSaisie from '../saisie/FeuilleSaisie'
import { annulerToast, fermerToast, pauserToast, proposerAnnuler, reprendreToast, useEtatGestes } from '../lib/gestes'
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
  ['Supprimées récemment', '/taches/supprimees'],
  ['Réglages', '/taches/reglages'],
]

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
  return (
    <button
      type="button"
      className="bouton-icone entete-cloche"
      aria-label={`Notifications (${compte})`}
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
      {compte > 0 ? <span className="entete-cloche-compte chiffres" aria-hidden="true">{compte > 99 ? '99+' : compte}</span> : null}
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
 *  progression, maquette ecran-aujourdhui-matin.html) passe `saisieBureau={false}` à la coquille et la rend lui-même. */
export function SaisieBureau({ onClick }) {
  return (
    <button type="button" className="saisie-bureau bureau-seul" onClick={onClick}>
      <Plus className="i" aria-hidden="true" />
      Ajouter une tâche
      <kbd aria-hidden="true">n</kbd>
    </button>
  )
}

/**
 * `retour` (R2-093, écrans enfants) : `{ libelle, vers }` — `libelle` est le nom de l'écran parent (« Projets »,
 * « Réglages »), `vers` son chemin (`/taches/projets`). Exemple : `retour={{ libelle: 'Projets', vers: '/taches/projets' }}`.
 * Rendu « ‹ {libelle} » au-dessus du titre ; l'écran enfant n'a alors ni loupe ni Copilote (le ⋯ reste).
 */
export default function CoquilleTaches({
  ecran, titre, sousTitre = null, actionsEcran = [], derniereSynchro = null,
  feuille = null, selecteurProjet = null, selection = null, copilote = {}, conflit = null, contexteSaisie = null,
  saisieBureau = true, retour = null, children,
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
  const tacheId = params.get('tache')
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
      suite.delete('tache')
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
  // sous une feuille ouverte ; elle n'écrit rien (aucun raccourci destructif).
  useEffect(() => {
    const surTouche = (e) => {
      if (e.key !== 'n' || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return
      if (e.target?.closest?.('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return
      if (document.querySelector('.tch [role="dialog"]')) return
      e.preventDefault()
      demanderSaisie()
    }
    document.addEventListener('keydown', surTouche)
    return () => document.removeEventListener('keydown', surTouche)
  }, [demanderSaisie])

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
    <div className="tch" data-ecran={ecran} data-hors-ligne={enLigne ? undefined : 'true'} onClickCapture={surClicCapture}>
      <div className="tch-page">
        {/* R2-080 — la rangée du haut (☰, titre compact, actions) colle en haut de l'écran sur iPhone ; au bureau elle
            n'a pas de boîte (`display: contents`) et ses actions se posent à droite du titre, comme avant. */}
        <header className="entete">
          <div className={`entete-barre${replie ? ' replie' : ''}`} ref={barre}>
            {/* R2-093 — un écran ENFANT (projet, sous-page de Réglages) passe `retour` : « ‹ {libelle} » se pose
                AU-DESSUS du titre (iPhone : à la place de ☰ ; bureau : sur la ligne du sur-titre), et l'écran
                enfant ne répète ni la loupe ni le Copilote. */}
            {retour ? (
              <button type="button" className="entete-retour" onClick={() => navigate(retour.vers)}>
                <ChevronLeft className="i" aria-hidden="true" />{retour.libelle}
              </button>
            ) : <BoutonMenuErp />}
            <div className="entete-compact" aria-hidden="true">{titre}</div>
            <div className="entete-actions">
              <ClocheErp />
              {retour ? null : (
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

        {saisieBureau ? <SaisieBureau onClick={demanderSaisie} /> : null}

        {conflit ?? conflitFile ? <BandeauConflit {...(conflit ?? conflitFile)} /> : null}

        {children}
      </div>

      {selection && selection.n > 0 ? (
        <BarreSelection {...selection} />
      ) : (
        <button type="button" className="fab mobile-seul" aria-label="Ajouter une tâche" onClick={demanderSaisie}>
          <Plus className="i" aria-hidden="true" />
        </button>
      )}

      {tacheId ? <Fiche id={tacheId} onFermer={fermerFiche} /> : null}
      <FeuilleSaisie ouverte={saisieOuverte} onFermer={fermerSaisie} />
      {feuille ? <FeuilleACrans {...feuille} /> : null}
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
