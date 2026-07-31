import { useEffect, useState } from 'react'
import portailApi from '../../../api/portailApi'
import { Card, EmptyState, Spinner } from '../../../ui'
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
  const [resume, setResume] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)

  useEffect(() => {
    let annule = false
    portailApi.fournisseur.tableauDeBord()
      .then((r) => { if (!annule) setResume(r.data) })
      .catch(() => { if (!annule) setErreur(true) })
      .finally(() => { if (!annule) setLoading(false) })
    return () => { annule = true }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de votre tableau de bord…
      </div>
    )
  }

  if (erreur || !resume) {
    return (
      <EmptyState
        title="Tableau de bord indisponible"
        description="Vos données n’ont pas pu être chargées. Réessayez plus tard."
      />
    )
  }

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
