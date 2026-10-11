import portailApi from '../../../api/portailApi'
import { Card } from '../../../ui'
import { useTableauDeBordExterne } from '../useTableauDeBordExterne'
import EtatTableauDeBordExterne from '../EtatTableauDeBordExterne'
import { formatMAD } from '../../../lib/format'

/* ============================================================================
   NTPRT20 — Tableau de bord du portail fournisseur.
   ----------------------------------------------------------------------------
   Cartes résumé scopées `fournisseur_id` côté serveur (le frontend n'envoie
   aucun identifiant : le scope vient du compte connecté). Seules les cartes
   dont la donnée EXISTE aujourd'hui sont affichées — « livraisons annoncées »
   (ASN, NTPRT22) et « documents légaux expirant » (NTPRT24) ne sont pas encore
   modélisées et ne sont donc pas rendues : une carte à zéro qui ne mesure rien
   ment plus qu'une carte absente.
   ========================================================================== */

export default function PortailFournisseurAccueil() {
  const etat = useTableauDeBordExterne(portailApi.fournisseur.tableauDeBord)
  const { resume } = etat
  if (etat.loading || etat.erreur || !resume) return <EtatTableauDeBordExterne {...etat} />

  const cartes = [
    { cle: 'bcf_a_confirmer', label: 'Commandes à confirmer',
      valeur: resume.bcf_a_confirmer },
    { cle: 'bcf_en_cours', label: 'Commandes en cours',
      valeur: resume.bcf_en_cours },
    { cle: 'receptions_recentes', label: 'Réceptions enregistrées',
      valeur: resume.receptions_recentes },
    { cle: 'factures_a_payer', label: 'Factures en attente de règlement',
      valeur: resume.factures_a_payer,
      detail: formatMAD(resume.montant_a_payer) },
  ]

  return (
    <>
      <h1 className="font-display text-xl font-semibold tracking-tight">
        {resume.fournisseur_nom || 'Espace fournisseur'}
      </h1>
      <div className="grid gap-3 sm:grid-cols-2">
        {cartes.map((c) => (
          <Card key={c.cle} className="flex flex-col gap-1 p-4">
            <span className="text-sm text-muted-foreground">{c.label}</span>
            <span className="font-display text-2xl font-semibold">
              {c.valeur}
            </span>
            {c.detail && (
              <span className="text-sm text-muted-foreground">{c.detail}</span>
            )}
          </Card>
        ))}
      </div>
    </>
  )
}
