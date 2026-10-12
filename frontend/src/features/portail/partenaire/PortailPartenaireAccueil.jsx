import portailApi from '../../../api/portailApi'
import { Card } from '../../../ui'
import { useTableauDeBordExterne } from '../useTableauDeBordExterne'
import EtatTableauDeBordExterne from '../EtatTableauDeBordExterne'
import { formatMAD } from '../../../lib/format'

/* ============================================================================
   NTPRT27 — Tableau de bord du portail partenaire.
   ----------------------------------------------------------------------------
   Cartes résumé scopées `partenaire_id` côté serveur (aucun identifiant n'est
   envoyé par le client). La carte « territoire assigné » du plan N'EST PAS
   rendue : `TerritoireCommercial` (FG236) porte un `owner_user_id`, pas de
   rattachement à un partenaire — afficher un territoire déduit serait une
   information fausse. Elle arrivera si la relation est modélisée.
   ========================================================================== */

const LIBELLE_STATUT = {
  soumis: 'Soumis',
  qualifie: 'Qualifiés',
  converti: 'Convertis',
  rejete: 'Rejetés',
}

export default function PortailPartenaireAccueil() {
  const etat = useTableauDeBordExterne(portailApi.partenaire.tableauDeBord)
  const { resume } = etat
  if (etat.loading || etat.erreur || !resume) return <EtatTableauDeBordExterne {...etat} />

  const soumissions = resume.soumissions_par_statut || {}

  return (
    <>
      <h1 className="font-display text-xl font-semibold tracking-tight">
        {resume.partenaire_nom || 'Espace partenaire'}
      </h1>

      <h2 className="text-sm font-medium text-muted-foreground">
        Leads soumis
      </h2>
      <div className="grid gap-3 sm:grid-cols-4">
        {Object.entries(soumissions).map(([statut, n]) => (
          <Card key={statut} className="flex flex-col gap-1 p-4">
            <span className="text-sm text-muted-foreground">
              {LIBELLE_STATUT[statut] || statut}
            </span>
            <span className="font-display text-2xl font-semibold">{n}</span>
          </Card>
        ))}
      </div>

      <h2 className="text-sm font-medium text-muted-foreground">Commissions</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <Card className="flex flex-col gap-1 p-4">
          <span className="text-sm text-muted-foreground">Dues</span>
          <span className="font-display text-2xl font-semibold">
            {formatMAD(resume.commissions_dues)}
          </span>
        </Card>
        <Card className="flex flex-col gap-1 p-4">
          <span className="text-sm text-muted-foreground">Payées</span>
          <span className="font-display text-2xl font-semibold">
            {formatMAD(resume.commissions_payees)}
          </span>
        </Card>
      </div>
    </>
  )
}
