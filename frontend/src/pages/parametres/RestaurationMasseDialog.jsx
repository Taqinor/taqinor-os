// NTUX26 — Assistant de restauration en masse depuis la corbeille : aperçu
// AVANT confirmation (type par type, avec avertissement quand
// `avertissement_restauration` — ex. responsable d'origine disparu/désactivé,
// cf. `apps/trash/serializers.py::get_avertissement_restauration`), PUIS
// restauration EN BOUCLE (une entrée à la fois, en parallèle) via le SEUL
// endpoint `POST corbeille/<id>/restaurer/` — jamais une restauration SQL
// directe. Un échec ne bloque jamais les autres (`Promise.allSettled`), même
// patron de résultat que `ui/datatable/BulkEditDialog.jsx` (NTUX5).
import { useState } from 'react'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button,
} from '../../ui'
import trashApi from '../../api/trashApi'

export default function RestaurationMasseDialog({ open, onOpenChange, elements = [], onDone }) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null) // { restored: [...], failed: [{id, label, reason}] }

  const reset = () => { setBusy(false); setResult(null) }
  const handleClose = () => { reset(); onOpenChange?.(false) }

  const handleConfirm = async () => {
    setBusy(true)
    const issues = await Promise.allSettled(
      elements.map((el) => trashApi.restaurer(el.id).then((res) => ({ el, res }))),
    )
    const restored = []
    const failed = []
    issues.forEach((issue, index) => {
      const el = elements[index]
      const label = el.libelle_snapshot || el.type_libelle || `#${el.id}`
      if (issue.status === 'fulfilled') {
        restored.push({ id: el.id, label, element: issue.value.res.data?.element })
      } else {
        const detail = issue.reason?.response?.data?.detail
        failed.push({ id: el.id, label, reason: detail || 'échec inconnu' })
      }
    })
    const normalized = { restored, failed }
    setResult(normalized)
    setBusy(false)
    onDone?.(normalized)
    // Tout a réussi : fermeture automatique (rien à examiner). Un échec
    // partiel garde le dialogue ouvert pour montrer QUI a échoué et pourquoi.
    if (failed.length === 0) handleClose()
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose() }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Restaurer la sélection — {elements.length} élément{elements.length > 1 ? 's' : ''}
          </DialogTitle>
          <DialogDescription>
            Vérifiez la liste avant de confirmer — un avertissement n'empêche
            pas la restauration, il signale seulement un enregistrement lié
            qui a changé depuis la suppression.
          </DialogDescription>
        </DialogHeader>

        {!result && (
          <div className="max-h-72 overflow-y-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-muted text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Libellé</th>
                  <th className="px-3 py-2 text-left">Avertissement</th>
                </tr>
              </thead>
              <tbody>
                {elements.map((el) => (
                  <tr key={el.id} className="border-t border-border" data-testid="rmd-preview-row">
                    <td className="px-3 py-2 font-medium">{el.type_libelle || '—'}</td>
                    <td className="px-3 py-2">{el.libelle_snapshot || '—'}</td>
                    <td className="px-3 py-2">
                      {el.avertissement_restauration ? (
                        <span className="flex items-center gap-1 text-warning">
                          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
                          {el.avertissement_restauration}
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {result && (
          <div className="flex flex-col gap-2" data-testid="rmd-result">
            {result.restored.length > 0 && (
              <p className="flex items-center gap-1.5 text-sm text-success">
                <CheckCircle2 className="size-4" aria-hidden="true" />
                {result.restored.length} élément{result.restored.length > 1 ? 's' : ''} restauré{result.restored.length > 1 ? 's' : ''}.
              </p>
            )}
            {result.failed.length > 0 && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <p className="mb-1 flex items-center gap-1.5 font-medium">
                  <AlertTriangle className="size-4" aria-hidden="true" />
                  {result.failed.length} échec{result.failed.length > 1 ? 's' : ''} — les autres éléments ont bien été restaurés.
                </p>
                <ul className="list-disc pl-5">
                  {result.failed.map((f) => (
                    <li key={f.id}>{f.label} — {f.reason}</li>
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
              <Button
                type="button" loading={busy} disabled={elements.length === 0}
                onClick={handleConfirm}
              >
                {busy ? 'Restauration…' : 'Restaurer la sélection'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
