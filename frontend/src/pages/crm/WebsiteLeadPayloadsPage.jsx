// QX16 — « Jamais perdre un lead » devient opérationnel : liste des payloads
// bruts du site web dont le mapping a échoué OU qui n'ont jamais été
// rattachés à un lead, avec un rejeu en un clic (même mapping que le
// webhook, jamais une seconde implémentation — voir apps/crm/webhooks.py
// replay_website_lead_payload). Nouveau fichier, isolé de DevisList/
// LeadForm/LeadCard.
import { useEffect, useState } from 'react'
import crmApi from '../../api/crmApi'
import { Table } from '../reporting/Table'

export default function WebsiteLeadPayloadsPage() {
  const [rows, setRows] = useState([])
  const [showAll, setShowAll] = useState(false)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState(null)
  const [replayingId, setReplayingId] = useState(null)

  const load = () => {
    setLoading(true)
    crmApi.getWebsiteLeadPayloads(showAll ? { all: 1 } : {})
      .then(r => setRows(r.data.results ?? r.data))
      .catch(() => setMsg('Chargement impossible.'))
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps -- chargement au montage + rechargement quand showAll change
  useEffect(() => { load() }, [showAll])

  const replay = async (id) => {
    setReplayingId(id)
    setMsg(null)
    try {
      const res = await crmApi.replayWebsiteLeadPayload(id)
      setMsg(res.data?.detail || 'Rejeu effectué.')
      load()
    } catch (e) {
      setMsg(e?.response?.data?.detail ?? 'Rejeu échoué.')
    } finally {
      setReplayingId(null)
    }
  }

  return (
    <div className="page max-w-[1100px]">
      <div className="page-header">
        <h2>Payloads leads site web</h2>
      </div>
      <p className="mb-3 text-sm text-muted-foreground">
        Toute capture du site web est conservée AVANT tout mapping (« jamais perdre un lead »).
        Cette liste montre celles dont le mapping a échoué ou qui ne sont rattachées à aucun lead
        — chacune reste rejouable.
      </p>

      <div className="mb-3 flex items-center gap-2">
        <label className="flex items-center gap-1 text-sm">
          <input
            type="checkbox"
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
          />
          Voir tous les payloads (y compris déjà traités avec succès)
        </label>
      </div>

      {msg && (
        <div className="alert alert-info mb-3 rounded-lg border border-border bg-muted/40 px-[0.85rem] py-[0.6rem]">
          {msg}
        </div>
      )}

      {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}

      <Table
        aria-label="Payloads leads site web"
        getRowKey={(p) => p.id}
        columns={[
          { key: 'id', header: '#', cell: (p) => p.id },
          {
            key: 'received_at',
            header: 'Reçu le',
            cell: (p) => (p.received_at || '').replace('T', ' ').slice(0, 16),
          },
          {
            key: 'processed',
            header: 'Traité',
            cell: (p) => (p.processed ? 'Oui' : 'Non'),
          },
          {
            key: 'error',
            header: 'Erreur',
            cell: (p) => p.error
              ? <span className="text-destructive">{p.error}</span>
              : <span className="text-muted-foreground">—</span>,
          },
          {
            key: 'lead',
            header: 'Lead rattaché',
            cell: (p) => p.lead
              ? <a className="underline" href={`/crm/leads?lead=${p.lead}`}>{p.lead_nom || `#${p.lead}`}</a>
              : <span className="text-muted-foreground">Aucun</span>,
          },
          {
            key: 'actions',
            header: 'Actions',
            cell: (p) => (
              <button
                className="btn btn-sm btn-outline"
                disabled={replayingId === p.id}
                onClick={() => replay(p.id)}
              >
                {replayingId === p.id ? 'Rejeu…' : 'Rejouer'}
              </button>
            ),
          },
        ]}
        rows={rows}
        empty={<span className="text-muted-foreground">Aucun payload en attente d'action.</span>}
      />
    </div>
  )
}
