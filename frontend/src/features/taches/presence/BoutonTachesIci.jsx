import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Check, Plus } from 'lucide-react'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { frenchError } from '../../../lib/frenchError'
import { ROUTE } from '../../../lib/search/entityRoutes'
import { IconButton } from '../../../ui/IconButton'
import { Popover, PopoverContent, PopoverTrigger } from '../../../ui/Popover'
import { annulerGeste, listerTaches, listerToutesLesTaches, terminerTache } from '../../../api/tachesApi'
import { annoncer, proposerAnnuler } from '../lib/gestes'
import CaseRonde from '../ui/CaseRonde'
import { cibleDepuisEcran, EVENEMENT_SAISIR, libelleDeCible } from './cibleEcran'

/* ============================================================================
   TCH102 — `BoutonTachesIci` : la pastille ✓+ de l'en-tête de l'ERP (spec-6a-erp.md « Écrans »).
   Sur la fiche d'un lead, d'un client ou d'un devis (`cibleDepuisEcran`), elle montre le NOMBRE de
   tâches ouvertes liées à cet objet — `GET taches/taches/?cible=&cible_id=&ouvertes=1`, UNE requête
   par objet affiché, relue quand une tâche est créée (`taqinor:taches:creees`) ou à l'ouverture de la
   liste. Au clic : la liste (cocher = terminer, comme partout : optimiste, « Annuler »), et
   « Nouvelle tâche liée » qui ouvre la feuille de saisie par l'événement unique `taqinor:taches:saisir`
   avec le lien de la fiche. Ailleurs, ou sans le droit `taches_voir` : le bouton n'existe pas.
   Une relecture en échec ne vide jamais la liste déjà affichée. Monté dans l'en-tête par TCH123.
   ========================================================================== */

const EVENEMENT_CREEES = 'taqinor:taches:creees'

/** Les tâches ouvertes liées à `cible` : `{ taches, nb, retirer, relire }` — la liste gardée si une relecture échoue. */
function useTachesLiees(nomCible, idCible) {
  const [lu, setLu] = useState({ cle: '', taches: [], nb: 0 })
  const cle = `${nomCible}:${idCible}`
  const courante = useRef(cle)
  useEffect(() => { courante.current = cle })
  const relire = useCallback(async () => {
    try {
      const filtres = { cible: nomCible, cible_id: idCible, ouvertes: 1 }
      const { data } = await listerTaches(filtres)
      // liste paginée : la page 1 suffit tant que `next` est vide, sinon on lit tout (api.md §0)
      const taches = data?.next ? await listerToutesLesTaches(filtres) : (Array.isArray(data?.results) ? data.results : [])
      if (courante.current === cle) {
        setLu({ cle, taches, nb: taches.length })
      }
    } catch {
      // relecture en échec : la dernière liste reste affichée (jamais vidée), le bouton ne dit rien de faux
    }
  }, [nomCible, idCible, cle])
  useEffect(() => {
    const premiere = setTimeout(relire, 0)
    window.addEventListener(EVENEMENT_CREEES, relire)
    return () => { clearTimeout(premiere); window.removeEventListener(EVENEMENT_CREEES, relire) }
  }, [relire])
  const propre = lu.cle === cle
  const retirer = (id) => setLu((l) => ({ ...l, taches: l.taches.filter((t) => t.id !== id), nb: Math.max(0, l.nb - 1) }))
  return { taches: propre ? lu.taches : [], nb: propre ? lu.nb : 0, lu: propre, retirer, relire }
}

function LigneLiee({ tache, onTerminer, onOuvrir }) {
  return (
    <div className="ligne" role="listitem">
      <CaseRonde coche={false} titre={tache.titre} onBasculer={() => onTerminer(tache)} />
      <div className="ligne-corps">
        <button type="button" className="ligne-corps-bouton" onClick={() => onOuvrir(tache)}>
          <span className="titre">{tache.titre}</span>
        </button>
      </div>
    </div>
  )
}

function Actif({ cible }) {
  const navigate = useNavigate()
  const [ouvert, setOuvert] = useState(false)
  const { taches, nb, lu, retirer, relire } = useTachesLiees(cible.cible, cible.id)
  const libelle = libelleDeCible(cible.cible)

  const terminer = async (tache) => {
    try {
      const { data } = await terminerTache(tache.id)
      retirer(tache.id)
      proposerAnnuler({
        message: 'Faite',
        annonce: `Fait : ${tache.titre}`,
        onAnnuler: async () => { await annulerGeste(data?.geste_id); await relire() },
      })
    } catch (err) {
      annoncer(frenchError(err))
      throw err // la case revient en arrière
    }
  }
  const ouvrirTache = (tache) => { setOuvert(false); navigate(ROUTE.tache(tache.id)) }
  const nouvelle = () => {
    setOuvert(false)
    window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail: { lien: { cible: cible.cible, id: cible.id, libelle } } }))
  }
  const changer = (suivant) => { setOuvert(suivant); if (suivant) relire() }

  return (
    <Popover open={ouvert} onOpenChange={changer}>
      <PopoverTrigger asChild>
        <IconButton label={nb > 0 ? `Tâches liées à cette fiche (${nb} ouvertes)` : 'Tâches liées à cette fiche'} className="tch-ici">
          <span className="tch tch-ici-icone">
            <Check className="i i-16" aria-hidden="true" /><Plus className="i i-14" aria-hidden="true" />
            {nb > 0 ? <span className="tch-ici-nb chiffres" data-testid="tch-ici-nb">{nb}</span> : null}
          </span>
        </IconButton>
      </PopoverTrigger>
      <PopoverContent align="end" className="tch tch-ici-liste">
        <div role="list" aria-label="Tâches liées à cette fiche">
          {taches.map((t) => <LigneLiee key={t.id} tache={t} onTerminer={terminer} onOuvrir={ouvrirTache} />)}
        </div>
        {lu && taches.length === 0 ? <p className="aide-champ">Aucune tâche ouverte liée.</p> : null}
        <button type="button" className="bouton plein tch-ici-nouvelle" onClick={nouvelle}>
          <Plus className="i i-16" aria-hidden="true" />Nouvelle tâche liée
        </button>
      </PopoverContent>
    </Popover>
  )
}

export default function BoutonTachesIci() {
  const peutVoir = useHasPermission('taches_voir')
  const lieu = useLocation()
  const cible = peutVoir ? cibleDepuisEcran(lieu) : null
  return cible ? <Actif key={`${cible.cible}:${cible.id}`} cible={cible} /> : null
}
