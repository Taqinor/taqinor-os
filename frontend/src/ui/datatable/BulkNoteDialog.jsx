// NTUX20 — Notes rapides sur sélection multiple. Composant GÉNÉRIQUE (aucune
// app cible codée en dur, même patron que BulkEditDialog.jsx NTUX5) : chaque
// écran (Leads/Devis/Tickets/Contrats…) fournit `onConfirm(rows, note)` qui
// poste la note via SON PROPRE endpoint `noter` déjà existant (chatter
// historique/noter par app — jamais un nouveau modèle, cf. CLAUDE.md).
// Prévisualisation du nombre d'enregistrements touchés AVANT confirmation
// (même contrat de retour que BulkEditDialog) :
//   { updated: [{ id, ... }], failed: [{ id, label?, reason }] }
// Un échec partiel n'annule pas le reste : les enregistrements réussis
// gardent leur note, les échecs sont listés avec leur raison.
import { useState } from 'react'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button, Textarea,
} from '..'

export default function BulkNoteDialog({
  open, onOpenChange, rows = [],
  getRowLabel = (row) => String(row?.id ?? ''),
  onConfirm, onDone,
}) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null) // { updated, failed } après confirmation

  const reset = () => { setNote(''); setBusy(false); setResult(null) }
  const handleClose = () => { reset(); onOpenChange?.(false) }

  const trimmedNote = note.trim()

  const handleConfirm = async () => {
    if (!trimmedNote) return
    setBusy(true)
    try {
      const res = await onConfirm(rows, trimmedNote)
      const normalized = { updated: res?.updated || [], failed: res?.failed || [] }
      setResult(normalized)
      onDone?.(normalized)
      // Tout a réussi : fermeture automatique. Un échec partiel garde le
      // dialogue ouvert pour montrer QUI a échoué et pourquoi (même patron
      // que BulkEditDialog).
      if (normalized.failed.length === 0) handleClose()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose() }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Ajouter une note — {rows.length} enregistrement{rows.length > 1 ? 's' : ''}</DialogTitle>
          <DialogDescription>
            La même note sera ajoutée à l'historique de chaque enregistrement sélectionné.
          </DialogDescription>
        </DialogHeader>

        {!result && (
          <div className="flex flex-col gap-3">
            <div className="max-h-40 overflow-y-auto rounded-lg border border-border p-2 text-sm text-muted-foreground">
              {rows.map((row) => (
                <div key={getRowLabel(row)} data-testid="bnd-preview-row">{getRowLabel(row)}</div>
              ))}
            </div>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Votre note…"
              aria-label="Contenu de la note"
              rows={3}
              autoFocus
            />
          </div>
        )}

        {result && (
          <div className="flex flex-col gap-2" data-testid="bnd-result">
            {result.updated.length > 0 && (
              <p className="flex items-center gap-1.5 text-sm text-success">
                <CheckCircle2 className="size-4" aria-hidden="true" />
                Note ajoutée sur {result.updated.length} enregistrement{result.updated.length > 1 ? 's' : ''}.
              </p>
            )}
            {result.failed.length > 0 && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <p className="mb-1 flex items-center gap-1.5 font-medium">
                  <AlertTriangle className="size-4" aria-hidden="true" />
                  {result.failed.length} échec{result.failed.length > 1 ? 's' : ''} — les autres ont bien reçu la note.
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
              <Button type="button" loading={busy} disabled={rows.length === 0 || !trimmedNote} onClick={handleConfirm}>
                {busy ? 'Envoi…' : 'Confirmer'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
