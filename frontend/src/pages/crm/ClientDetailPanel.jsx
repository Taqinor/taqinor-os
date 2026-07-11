import { useEffect, useState } from 'react'
import api from '../../api/axios'
import { Badge, Button, Spinner } from '../../ui'
import { Table } from '../reporting/Table'
import ClientRgpdActions from './ClientRgpdActions'
import { formatMAD } from '../../lib/format'
import { telHref, waHref } from '../../lib/contactLinks'

// Panneau détail client (L4) — lecture seule : devis, factures et chantiers
// liés au client, avec référence / statut / total (montants client-facing
// uniquement, jamais de prix d'achat ni de marge). Source : l'endpoint scopé
// société GET /crm/clients/<id>/documents/.

const formatDateFR = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '—')

function DocTable({ titre, rows, withTotal, withDate, emptyLabel }) {
  // VX152 — un seul moteur de table : la fiche client rejoint le primitif `Table`
  // partagé (reporting) au lieu d'un troisième moteur `DocTable` maison.
  const columns = [
    { key: 'reference', header: 'Référence', cellClassName: 'font-medium', cell: (r) => r.reference || '—' },
    { key: 'statut', header: 'Statut', cell: (r) => <Badge tone="neutral">{r.statut || '—'}</Badge> },
    ...(withDate ? [{ key: 'date', header: 'Date', cell: (r) => formatDateFR(r.date) }] : []),
    ...(withTotal ? [{ key: 'total', header: 'Total TTC', align: 'right', cell: (r) => formatMAD(r.total_ttc) }] : []),
  ]
  return (
    <section className="mb-4">
      <h4 className="font-medium mb-2">
        {titre} <span className="count-badge">{rows.length}</span>
      </h4>
      {rows.length === 0 ? (
        <p className="text-muted-foreground">{emptyLabel}</p>
      ) : (
        <Table columns={columns} rows={rows} getRowKey={(r) => r.id} aria-label={titre} />
      )}
    </section>
  )
}

export default function ClientDetailPanel({ client, onClose, onNewDevis, onChanged }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // XSAL9 — rollup CA groupe (société mère + filiales). Best-effort : une
  // erreur de chargement n'empêche jamais le reste de la fiche de s'afficher.
  const [consolidation, setConsolidation] = useState(null)

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

  useEffect(() => {
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setConsolidation(null)
    api.get(`/crm/clients/${client.id}/consolidation/`)
      .then((res) => { if (alive) setConsolidation(res.data) })
      .catch(() => { /* best-effort — la fiche reste utilisable sans rollup */ })
    return () => { alive = false }
  }, [client.id])

  const nomComplet = [client.nom, client.prenom].filter(Boolean).join(' ')
  // VX108 — tap-to-call : le panneau n'affichait jusqu'ici aucun téléphone.
  const tel = telHref(client.telephone)
  const wa = waHref(client.whatsapp)

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Fiche client — {nomComplet || '—'}</h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {(tel || wa) && (
            <div className="mb-4 flex flex-wrap gap-3 text-sm">
              {tel && (
                <a className="link-blue" href={tel} title="Appeler">
                  ☎ {client.telephone}
                </a>
              )}
              {wa && (
                <a className="link-blue" href={wa} target="_blank" rel="noopener noreferrer" title="Ouvrir WhatsApp">
                  WhatsApp
                </a>
              )}
            </div>
          )}
          {loading && (
            <p className="page-loading"><Spinner /> Chargement des documents…</p>
          )}
          {error && (
            <p className="page-error">
              Impossible de charger les documents — réessayez.
            </p>
          )}
          {/* XSAL9 — hiérarchie de comptes : filiales + rollup CA groupe. */}
          {consolidation && consolidation.filiales.length > 0 && (
            <section className="mb-4">
              <h4 className="font-medium mb-2">
                Filiales <span className="count-badge">{consolidation.filiales.length}</span>
              </h4>
              <p className="text-sm mb-2">
                CA groupe (devis) : <strong>{formatMAD(consolidation.ca_devis_total)}</strong>
                {' · '}CA groupe (factures) : <strong>{formatMAD(consolidation.ca_factures_total)}</strong>
              </p>
              <ul className="text-sm">
                {consolidation.filiales.map((f) => (
                  <li key={f.id}>{f.nom}</li>
                ))}
              </ul>
            </section>
          )}
          {client.parent_id != null && (
            <p className="text-sm text-muted-foreground mb-4">
              Filiale de la société mère #{client.parent_id}.
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
          {/* WR9/FG26 — export d'accès du sujet + anonymisation (gatés rôle). */}
          <ClientRgpdActions
            client={client}
            onChanged={() => { onChanged?.(); onClose() }}
          />
          <Button variant="outline" onClick={() => onNewDevis(client)}>
            Nouveau devis
          </Button>
          <Button onClick={onClose}>Fermer</Button>
        </div>
      </div>
    </div>
  )
}
