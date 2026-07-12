// ZSAL4 — Assistant de conversion explicite lead → client (nouveau / lier /
// aucun), mirroir de l'action Odoo « Convert to Opportunity ». Le serveur
// (apps.crm.services.convertir_lead_en_client) résout tout : réutilise le
// client déjà lié le cas échéant, journalise au chatter, jamais de doublon.
import { useState } from 'react'
import crmApi from '../../../api/crmApi'
import { Button } from '../../../ui'
import { Combobox } from '../../../ui/Combobox'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import { searchCompanies, hitsToOptions } from '../../../features/crm/companyLookup'

const MODES = [
  { value: 'nouveau', label: 'Créer un nouveau client' },
  { value: 'lier', label: 'Lier à un client existant' },
  { value: 'aucun', label: 'Aucun (qualifier sans client)' },
]

export default function ConvertirClientDialog({ lead, onClose, onConverted }) {
  const [mode, setMode] = useState('nouveau')
  const [client, setClient] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null) // { mode, client }

  // « Lier » exige un CLIENT existant — le lookup couvre aussi
  // fournisseurs/leads (QC1) : on ne garde que les hits source=client pour ne
  // jamais poser un client_id qui n'en est pas un.
  const onSearchClient = (query) =>
    searchCompanies(query, { searcher: crmApi.searchClients })
      .then((hits) => hitsToOptions(hits.filter((h) => h.source === 'client')))

  const confirm = async () => {
    if (mode === 'lier' && !client) {
      setError('Choisissez un client existant à lier.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const payload = { mode }
      if (mode === 'lier') payload.client_id = client.id
      const res = await crmApi.convertirLeadEnClient(lead.id, payload)
      setResult(res.data)
      onConverted?.(res.data)
    } catch (err) {
      setError(err?.response?.data?.detail
        ?? 'La conversion a échoué — réessayez.')
    } finally {
      setBusy(false)
    }
  }

  const leadNom = `${lead.nom ?? ''} ${lead.prenom ?? ''}`.trim() || 'ce lead'

  return (
    // VX182 — shell fait-main remplacé par ResponsiveDialog (Escape + focus-
    // trap + bottom-sheet mobile) ; en-tête/pied conservés à l'identique.
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Convertir en client</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>

        <div className="modal-body">
          {result == null ? (
            <>
              <p className="sd-intro">
                Que faire de <strong>{leadNom}</strong> ?
              </p>
              <div className="mb-2 flex flex-col gap-1.5">
                {MODES.map((m, i) => (
                  <label key={m.value} className="sd-radio">
                    <input
                      type="radio"
                      name="cc-mode"
                      value={m.value}
                      checked={mode === m.value}
                      onChange={() => setMode(m.value)}
                      autoFocus={i === 0}
                    />
                    <span>{m.label}</span>
                  </label>
                ))}
              </div>
              {mode === 'lier' && (
                <div className="grid gap-1.5">
                  <label className="form-label" htmlFor="cc-client-search">
                    Client existant
                  </label>
                  <Combobox
                    id="cc-client-search"
                    value={client ? String(client.id) : null}
                    onSearch={onSearchClient}
                    onChange={(_v, opt) => setClient(opt?.hit ?? null)}
                    placeholder="Rechercher un client…"
                    searchPlaceholder="Nom ou ICE…"
                    emptyText="Aucun client trouvé"
                  />
                </div>
              )}
              {error && <p className="form-error" role="alert">{error}</p>}
            </>
          ) : (
            <p className="form-success" role="status">
              {result.mode === 'aucun'
                ? `${leadNom} qualifié sans client.`
                : `${leadNom} est maintenant lié au client « ${result.client?.nom ?? ''} ».`}
            </p>
          )}
        </div>

        <div className="modal-footer">
          {result == null ? (
            <>
              <Button type="button" variant="outline" onClick={onClose}>
                Annuler
              </Button>
              <Button type="button" onClick={confirm} loading={busy} disabled={busy}>
                {busy ? 'Conversion…' : 'Confirmer'}
              </Button>
            </>
          ) : (
            <Button type="button" onClick={onClose}>Fermer</Button>
          )}
        </div>
    </ResponsiveDialog>
  )
}
