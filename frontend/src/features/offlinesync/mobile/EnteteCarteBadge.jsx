import { Badge, CardHeader, CardTitle, CardDescription } from '../../../ui'

/* En-tête des cartes d'accueil mobile (leads du jour, approbations,
   interventions de l'équipe…) : icône + titre, description, puis pastille de
   compte à droite quand `compte` est un nombre > 0. */
export default function EnteteCarteBadge({ icone, titre, description, compte, tonCompte }) {
  const Icone = icone
  return (
    <CardHeader>
      <div className="flex items-center justify-between gap-2">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Icone className="size-4 text-muted-foreground" aria-hidden="true" />
            {titre}
          </CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        {compte > 0 && <Badge tone={tonCompte}>{compte}</Badge>}
      </div>
    </CardHeader>
  )
}
