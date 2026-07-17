// NTUX5 — Édition en masse avec aperçu AVANT/APRÈS et confirmation
// explicite. Composant GÉNÉRIQUE (aucune app cible codée en dur) : chaque
// écran (Devis/Factures/Stock/Tickets…) fournit `onConfirm(rows, newValue)`
// qui appelle SON propre endpoint `POST .../bulk-update/` (réutilise le
// `services.py` de son app, jamais d'écriture cross-app directe — cf.
// CLAUDE.md). Contrat de retour attendu de `onConfirm` :
//   { updated: [{ id, before, after, updated_at? }], failed: [{ id, label?, reason }] }
// Un échec partiel N'ANNULE PAS le reste : les lignes réussies restent
// appliquées, les lignes en échec sont listées avec leur raison.
import { useState } from 'react'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button,
} from '..'

export default function BulkEditDialog({
  open, onOpenChange, rows = [], fieldLabel,
  getRowLabel = (row) => String(row?.id ?? ''),
  getOldValue, newValue, formatValue = (v) => String(v ?? '—'),
  onConfirm, onDone,
}) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null) // { updated, failed } après confirmation

  const reset = () => { setBusy(false); setResult(null) }
  const handleClose = () => { reset(); onOpenChange?.(false) }

  const handleConfirm = async () => {
    setBusy(true)
    try {
      const res = await onConfirm(rows, newValue)
      const normalized = { updated: res?.updated || [], failed: res?.failed || [] }
      setResult(normalized)
      onDone?.(normalized)
      // Tout a réussi : fermeture automatique (rien à examiner). Un échec
      // partiel garde le dialogue ouvert pour montrer QUI a échoué et pourquoi.
      if (normalized.failed.length === 0) handleClose()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose() }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Modifier {fieldLabel} — {rows.length} ligne{rows.length > 1 ? 's' : ''}</DialogTitle>
          <DialogDescription>
            Vérifiez les changements avant de confirmer — chaque ligne affiche sa valeur
            actuelle et la nouvelle valeur.
          </DialogDescription>
        </DialogHeader>

        {!result && (
          <div className="max-h-72 overflow-y-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-muted text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Ligne</th>
                  <th className="px-3 py-2 text-left">Avant</th>
                  <th className="px-3 py-2 text-left">Après</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={getRowLabel(row)} className="border-t border-border" data-testid="bed-preview-row">
                    <td className="px-3 py-2 font-medium">{getRowLabel(row)}</td>
                    <td className="px-3 py-2 text-muted-foreground">{formatValue(getOldValue(row))}</td>
                    <td className="px-3 py-2 font-medium text-foreground">{formatValue(newValue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {result && (
          <div className="flex flex-col gap-2" data-testid="bed-result">
            {result.updated.length > 0 && (
              <p className="flex items-center gap-1.5 text-sm text-success">
                <CheckCircle2 className="size-4" aria-hidden="true" />
                {result.updated.length} ligne{result.updated.length > 1 ? 's' : ''} mise{result.updated.length > 1 ? 's' : ''} à jour.
              </p>
            )}
            {result.failed.length > 0 && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <p className="mb-1 flex items-center gap-1.5 font-medium">
                  <AlertTriangle className="size-4" aria-hidden="true" />
                  {result.failed.length} échec{result.failed.length > 1 ? 's' : ''} — les autres lignes ont bien été appliquées.
                </p>
                <ul className="list-disc pl-5">
                  {result.failed.map((f) => (
                    <li key={f.id}>{f.label || f.id} — {f.reason || 'échec inconnu'}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {result ? (
            <Button type="button" onClick={handleClose}>Fermer</Button>
          ) : (
            <>
              <Button type="button" variant="ghost" onClick={handleClose} disabled={busy}>
                Annuler
              </Button>
              <Button type="button" loading={busy} disabled={rows.length === 0} onClick={handleConfirm}>
                {busy ? 'Application…' : 'Confirmer'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
