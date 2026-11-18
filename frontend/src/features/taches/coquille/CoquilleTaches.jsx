import { useCallback, useContext, useEffect, useState } from 'react'
import { ReactReduxContext } from 'react-redux'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { CloudOff, Ellipsis, Plus, Search, X } from 'lucide-react'
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
import { heure as heureDe } from '../lib/textes'
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

export default function CoquilleTaches({
  ecran, titre, sousTitre = null, actionsEcran = [], derniereSynchro = null,
  feuille = null, selecteurProjet = null, selection = null, copilote = {}, conflit = null, contexteSaisie = null, children,
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
    heure: heureDe(String(premierConflit.actuel?.updated_at ?? '').slice(11, 16)),
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
        <header className="entete">
          <div className="entete-haut">
            <div>
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
              <h1 className="entete-titre">{titre}</h1>
            </div>
            <div className="entete-actions">
              <button
                type="button"
                className="bouton-icone"
                aria-label="Chercher dans mes tâches"
                onClick={() => navigate('/taches/recherche')}
              >
                <Search className="i" aria-hidden="true" />
              </button>
              <BoutonCopilote ecran={pathname} {...copilote} />
              <MenuPlus actionsEcran={actionsEcran} navigate={navigate} enLigne={enLigne} />
            </div>
          </div>
        </header>

        <button type="button" className="saisie-bureau bureau-seul" onClick={demanderSaisie}>
          <Plus className="i" aria-hidden="true" />
          Ajouter une tâche
          <kbd aria-hidden="true">n</kbd>
        </button>

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
