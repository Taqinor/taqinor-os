import { useEffect, useState } from 'react'
import api from '../../api/axios'
import { Badge, Button, Spinner } from '../../ui'

// Panneau détail client (L4) — lecture seule : devis, factures et chantiers
// liés au client, avec référence / statut / total (montants client-facing
// uniquement, jamais de prix d'achat ni de marge). Source : l'endpoint scopé
// société GET /crm/clients/<id>/documents/.

const formatDateFR = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '—')

const formatMAD = (v) => {
  const n = Number(v ?? 0)
  if (!Number.isFinite(n)) return '—'
  return `${n.toLocaleString('fr-MA')} MAD`
}

function DocTable({ titre, rows, withTotal, withDate, emptyLabel }) {
  return (
    <section className="mb-4">
      <h4 className="font-medium mb-2">
        {titre} <span className="count-badge">{rows.length}</span>
      </h4>
      {rows.length === 0 ? (
        <p className="text-muted-foreground">{emptyLabel}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th className="py-1 pr-2">Référence</th>
              <th className="py-1 pr-2">Statut</th>
              {withDate && <th className="py-1 pr-2">Date</th>}
              {withTotal && <th className="py-1 text-right">Total TTC</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t">
                <td className="py-1 pr-2 font-medium">{r.reference || '—'}</td>
                <td className="py-1 pr-2">
                  <Badge tone="neutral">{r.statut || '—'}</Badge>
                </td>
                {withDate && <td className="py-1 pr-2">{formatDateFR(r.date)}</td>}
                {withTotal && (
                  <td className="py-1 text-right">{formatMAD(r.total_ttc)}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

export default function ClientDetailPanel({ client, onClose, onNewDevis }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    setError(false)
    api.get(`/crm/clients/${client.id}/documents/`)
      .then((res) => { if (alive) setData(res.data) })
      .catch(() => { if (alive) setError(true) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [client.id])

  const nomComplet = [client.nom, client.prenom].filter(Boolean).join(' ')

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Fiche client — {nomComplet || '—'}</h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {loading && (
            <p className="page-loading"><Spinner /> Chargement des documents…</p>
          )}
          {error && (
            <p className="page-error">
              Impossible de charger les documents — réessayez.
            </p>
          )}
          {data && (
            <>
              <DocTable
                titre="Devis"
                rows={data.devis}
                withTotal
                withDate
                emptyLabel="Aucun devis lié."
              />
              <DocTable
                titre="Factures"
                rows={data.factures}
                withTotal
                withDate
                emptyLabel="Aucune facture liée."
              />
              <DocTable
                titre="Chantiers"
                rows={data.chantiers}
                emptyLabel="Aucun chantier lié."
              />
            </>
          )}
        </div>
        <div className="modal-footer">
          <Button variant="outline" onClick={() => onNewDevis(client)}>
            Nouveau devis
          </Button>
          <Button onClick={onClose}>Fermer</Button>
        </div>
      </div>
    </div>
  )
}
