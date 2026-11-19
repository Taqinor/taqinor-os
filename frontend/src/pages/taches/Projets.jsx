import { Navigate, useLocation } from 'react-router-dom'
import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { CorpsListeProjets, useListeProjets, useMaitreDetail } from '../../features/taches/projets/ListeProjets'

/* ============================================================================
   TCH88 — Écran Projets (`/taches/projets`). Maquette : docs/taches/maquettes/projets-liste.html.
   Textes : reference/textes.md §2.6. Contrat : `projets_liste.json` (liste paginée + `constat`).
   La liste, ses gestes et son cache sont dans `features/taches/projets/ListeProjets.jsx` (partagés avec la colonne de
   gauche du maître-détail). Ici : iPhone et largeurs < 1024 px, « la liste, puis le projet ».
   R2-067 — au bureau (≥ 1024 px), `/taches/projets` seul ouvre le premier projet actif (`/taches/projets/<id>`, la liste
   y est à gauche) ; sans aucun projet actif, la page garde son état vide (ou la liste des projets en pause).
   ========================================================================== */

export default function Projets() {
  const lieu = useLocation()
  const bureau = useMaitreDetail()
  const liste = useListeProjets()
  const premier = liste.actifs[0]
  if (bureau && liste.lu && premier) {
    // la requête (`?nouveau=1` de la palette) suit : la feuille s'ouvre sur le projet
    return <Navigate to={`/taches/projets/${premier.id}${lieu.search}`} replace />
  }
  return (
    <CoquilleTaches ecran="projets" titre="Projets" actionsEcran={liste.actionsEcran} feuille={liste.feuilleNouveau}>
      <CorpsListeProjets liste={liste} />
    </CoquilleTaches>
  )
}
