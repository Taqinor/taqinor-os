import { useEffect, useState } from 'react'
import entitesApi from './entitesApi'
import PageHeader from '../../components/layout/PageHeader'
import { Card, EmptyState, Spinner } from '../../ui'
import { toastError } from '../../lib/toast'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTADM25 — Vue consolidée « Groupe », LECTURE SEULE.

   Une colonne de KPI par entité ACTIVE, côte à côte, plus une colonne Total.
   Tous les chiffres viennent du backend (`/entites/entites/groupe/`), qui les
   agrège via les sélecteurs des apps propriétaires (ventes/crm/stock) filtrés
   sur le champ `entite` de NTADM2 — AUCUN calcul ici, et ce n'est PAS une
   consolidation comptable.

   L'écran ne s'affiche qu'à partir de DEUX entités actives (`disponible`) :
   en dessous, un groupe n'existe pas encore.
   ========================================================================== */

const LIGNES = [
  { cle: 'ca', label: 'CA (devis + factures)', money: true },
  { cle: 'ca_devis', label: '— dont devis', money: true },
  { cle: 'ca_factures', label: '— dont factures', money: true },
  { cle: 'pipeline', label: 'Pipeline pondéré', money: true },
  { cle: 'nb_leads', label: 'Leads ouverts' },
  { cle: 'nb_devis', label: 'Devis' },
  { cle: 'nb_factures', label: 'Factures' },
  { cle: 'nb_produits', label: 'Produits au catalogue' },
  { cle: 'effectif', label: 'Effectif' },
]

function valeurAffichee(colonne, ligne) {
  const brut = colonne?.[ligne.cle]
  if (brut === null || brut === undefined) return '—'
  if (!ligne.money) return brut
  const nombre = Number(brut)
  if (Number.isNaN(nombre)) return brut
  return formatMAD(nombre)
}

export default function GroupePage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let vivant = true
    entitesApi.groupe()
      .then((res) => { if (vivant) setData(res.data) })
      .catch(() => {
        if (vivant) toastError('Impossible de charger la vue Groupe.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [])

  const colonnes = data?.entites ?? []

  return (
    <div>
      <PageHeader
        title="Vue Groupe"
        subtitle="Consolidation de lecture, une colonne par entité active"
      />

      {loading && <Spinner />}

      {!loading && !data?.disponible && (
        <EmptyState
          title="Pas encore de groupe"
          description={
            'La vue consolidée apparaît à partir de deux entités actives. '
            + 'Créez vos filiales dans Paramètres → Entités.'
          }
        />
      )}

      {!loading && data?.disponible && (
        <Card className="mt-4 p-0">
          {/* Un tableau large doit défiler DANS son conteneur : la page ne
              défile jamais horizontalement. */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="groupe-table">
              <thead>
                <tr className="border-b">
                  <th className="p-3 text-left font-medium">Indicateur</th>
                  {colonnes.map((c) => (
                    <th key={c.id} className="p-3 text-right font-medium">
                      <span className="font-mono text-xs text-muted-foreground">
                        {c.code}
                      </span>
                      <div>{c.nom}</div>
                    </th>
                  ))}
                  <th className="p-3 text-right font-semibold">
                    {data.total?.nom ?? 'Total groupe'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {LIGNES.map((ligne) => (
                  <tr key={ligne.cle} className="border-b">
                    <td className="p-3">{ligne.label}</td>
                    {colonnes.map((c) => (
                      <td key={c.id} className="p-3 text-right tabular-nums">
                        {valeurAffichee(c, ligne)}
                      </td>
                    ))}
                    <td className="p-3 text-right font-semibold tabular-nums">
                      {valeurAffichee(data.total, ligne)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.effectif_note && (
            <p className="p-3 text-xs text-muted-foreground">
              {data.effectif_note}
            </p>
          )}
        </Card>
      )}
    </div>
  )
}
