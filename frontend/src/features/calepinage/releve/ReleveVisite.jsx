import { Link, useParams } from 'react-router-dom'
import PanneauReleve from '../atelier/PanneauReleve'
import { Icone } from '../atelier/coque/primitives'

/* Coque — « Relevé de visite » au téléphone (`/calepinage/:id/releve`, maquette Telephone).
   Gabarit L0, refait par la lane L7 : l'en-tête « ‹ Relevé de visite » et le relevé terrain
   EXISTANT (PanneauReleve), pour que l'écran soit utilisable dès aujourd'hui. */
export default function ReleveVisite() {
  const { id } = useParams()
  return (
    <div className="page" data-testid="cal-releve">
      <Link to={`/calepinage/${id}`} className="inline-flex min-h-11 items-center gap-2 text-base font-semibold text-foreground">
        <Icone nom="retour" taille={20} epaisseur={2} />
        Relevé de visite
      </Link>
      <PanneauReleve calepinageId={id} />
    </div>
  )
}
