import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CloudOff, Ellipsis, Plus, Search } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import Fiche from '../fiche/Fiche'
import FeuilleSaisie from '../saisie/FeuilleSaisie'
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

export default function CoquilleTaches({
  ecran, titre, sousTitre = null, actionsEcran = [], derniereSynchro = null, enteteExtra = null, children,
}) {
  const navigate = useNavigate()
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
              {enteteExtra}
              <MenuPlus actionsEcran={actionsEcran} navigate={navigate} />
            </div>
          </div>
        </header>

        <button type="button" className="saisie-bureau bureau-seul" onClick={ouvrirSaisie}>
          <Plus className="i" aria-hidden="true" />
          Ajouter une tâche
          <kbd aria-hidden="true">n</kbd>
        </button>

        {children}
      </div>

      <button type="button" className="fab mobile-seul" aria-label="Ajouter une tâche" onClick={ouvrirSaisie}>
        <Plus className="i" aria-hidden="true" />
      </button>

      {tacheId ? <Fiche id={tacheId} onFermer={fermerFiche} /> : null}
      <FeuilleSaisie ouverte={saisieOuverte} onFermer={fermerSaisie} />
    </div>
  )
}
