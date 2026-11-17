import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { CloudOff, Ellipsis, Plus, Search, X } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import Fiche from '../fiche/Fiche'
import FeuilleSaisie from '../saisie/FeuilleSaisie'
import { annulerToast, fermerToast, pauserToast, reprendreToast, useEtatGestes } from '../lib/gestes'
import BandeauConflit from '../ui/BandeauConflit'
import BarreSelection from '../ui/BarreSelection'
import BoutonCopilote from '../ui/BoutonCopilote'
import FeuilleACrans from '../ui/FeuilleACrans'
import SelecteurProjet from '../ui/SelecteurProjet'
import { useEnLigne } from '../lib/enLigne'

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
     · l'état « Hors ligne » (`useEnLigne`).
   L'ERP fournit lui-même barre latérale, barre d'onglets et en-tête global : la coquille
   n'invente aucune navigation (le module reste invisible jusqu'à l'activation, TCH131).
   Maquettes : docs/taches/maquettes/composants-5.html, ecran-aujourdhui-matin.html.
   ========================================================================== */

/** Événement DOM qui ouvre la feuille de saisie (`detail` facultatif : texte, projet). */
export const EVENEMENT_SAISIR = 'taqinor:taches:saisir'

const DESTINATIONS = [
  ['Revue de la semaine', '/taches/revue'],
  ['Mon rythme', '/taches/rythme'],
  ['Supprimées récemment', '/taches/supprimees'],
  ['Réglages', '/taches/reglages'],
]

function MenuPlus({ actionsEcran, navigate }) {
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
          <DropdownMenuItem key={vers} onSelect={() => navigate(vers)}>{libelle}</DropdownMenuItem>
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
  feuille = null, selecteurProjet = null, selection = null, copilote = {}, conflit = null, children,
}) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const enLigne = useEnLigne()
  const [params, setParams] = useSearchParams()
  const [saisieOuverte, setSaisieOuverte] = useState(false)
  const tacheId = params.get('tache')

  const ouvrirSaisie = useCallback(() => setSaisieOuverte(true), [])
  const fermerSaisie = useCallback(() => setSaisieOuverte(false), [])
  const fermerFiche = useCallback(() => {
    setParams((actuels) => {
      const suite = new URLSearchParams(actuels)
      suite.delete('tache')
      return suite
    }, { replace: true })
  }, [setParams])

  useEffect(() => {
    window.addEventListener(EVENEMENT_SAISIR, ouvrirSaisie)
    return () => window.removeEventListener(EVENEMENT_SAISIR, ouvrirSaisie)
  }, [ouvrirSaisie])

  return (
    <div className="tch" data-ecran={ecran}>
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
                    {derniereSynchro ? ` Hors ligne · dernière synchro à ${derniereSynchro}` : ' Hors ligne'}
                  </span>
                </div>
              )}
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
              <MenuPlus actionsEcran={actionsEcran} navigate={navigate} />
            </div>
          </div>
        </header>

        <button type="button" className="saisie-bureau bureau-seul" onClick={ouvrirSaisie}>
          <Plus className="i" aria-hidden="true" />
          Ajouter une tâche
          <kbd aria-hidden="true">n</kbd>
        </button>

        {conflit ? <BandeauConflit {...conflit} /> : null}

        {children}
      </div>

      {selection && selection.n > 0 ? (
        <BarreSelection {...selection} />
      ) : (
        <button type="button" className="fab mobile-seul" aria-label="Ajouter une tâche" onClick={ouvrirSaisie}>
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
            onChoisir={selecteurProjet.onChoisir}
            onNouveau={selecteurProjet.onNouveau}
          />
        </FeuilleACrans>
      ) : null}
    </div>
  )
}
