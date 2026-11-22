import { Link, useParams } from 'react-router-dom'
import { Icone } from '../atelier/coque/primitives'

/* Coque — « Montrer au client » (`/calepinage/:id/client`, maquette TelephoneClient).
   Gabarit L0, refait par la lane L7 (3D plein écran du MÊME constructeur, curseur du soleil,
   trois chiffres lus sur le calepinage enregistré, « Envoyer le lien »). Aucun chiffre ici. */
export default function VueClient() {
  const { id } = useParams()
  return (
    <div className="page" data-testid="cal-vue-client">
      <Link to={`/calepinage/${id}`} className="inline-flex min-h-11 items-center gap-2 text-base font-semibold text-foreground">
        <Icone nom="retour" taille={20} epaisseur={2} />
        Retour à l’atelier
      </Link>
      <p className="mt-4 text-sm text-muted-foreground">
        La vue à montrer au client s’ouvre ici. En attendant, la 3D se présente depuis l’atelier.
      </p>
    </div>
  )
}
