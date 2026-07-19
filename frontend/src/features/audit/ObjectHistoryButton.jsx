import { useState } from 'react'
import { History } from 'lucide-react'
import auditApi from '../../api/auditApi'
import {
  Button, Spinner, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../ui'

/* ============================================================================
   WIR19 — bouton « Historique » d'un objet précis (record-scopé).
   ----------------------------------------------------------------------------
   Surface l'endpoint audit VX243b (`/audit/objets/<content_type>/<id>/history/`)
   sur les fiches lead/devis/ticket : un commercial SANS la permission globale
   `journal_activite_voir` peut voir l'historique (AuditLog) d'un objet dont il
   est le PROPRIÉTAIRE (le backend re-vérifie owner/created_by/assigned_to +
   scope société). Un non-propriétaire sans permission reçoit un 403 — affiché
   ici comme un message d'accès non autorisé, jamais un plantage.

   `contentType` = "app_label.model" (ex. "crm.lead", "ventes.devis", "sav.ticket").
   ========================================================================== */
export default function ObjectHistoryButton({
  contentType,
  objectId,
  label = 'Historique',
  variant = 'outline',
  size = 'sm',
}) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [entries, setEntries] = useState([])
  const [error, setError] = useState(null)

  const charger = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await auditApi.getObjectHistory(contentType, objectId)
      setEntries(res?.data?.results ?? [])
    } catch (err) {
      if (err?.response?.status === 403) {
        setError("Vous n'avez pas accès à l'historique de cet objet.")
      } else {
        setError("L'historique n'a pas pu être chargé.")
      }
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  const ouvrir = () => {
    setOpen(true)
    charger()
  }

  if (!objectId) return null

  return (
    <>
      <Button type="button" variant={variant} size={size} onClick={ouvrir} className="gap-1.5">
        <History size={15} aria-hidden="true" /> {label}
      </Button>

      <Dialog open={open} onOpenChange={(o) => { if (!o) setOpen(false) }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Historique</DialogTitle>
            <DialogDescription>Modifications enregistrées sur cet objet (traçabilité).</DialogDescription>
          </DialogHeader>

          {loading && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Spinner className="size-4" /> Chargement de l'historique…
            </div>
          )}

          {!loading && error && (
            <EmptyState title="Historique indisponible" description={error} />
          )}

          {!loading && !error && entries.length === 0 && (
            <EmptyState
              title="Aucun historique"
              description="Aucune modification n'a encore été enregistrée sur cet objet."
            />
          )}

          {!loading && !error && entries.length > 0 && (
            <ul className="flex max-h-96 flex-col gap-2 overflow-y-auto" data-testid="object-history-list">
              {entries.map((e) => (
                <li key={e.id} className="rounded-md border border-border p-2 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{e.action_label || e.action}</span>
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {formatQuand(e.timestamp_local || e.timestamp)}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {e.utilisateur || e.actor_username || 'Système'}
                    {e.detail ? ` · ${e.detail}` : ''}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

function formatQuand(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      dateStyle: 'short',
      timeStyle: 'short',
    })
  } catch {
    return iso
  }
}
