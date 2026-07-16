import { useState } from 'react'
import { useIsAdmin, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { Download, ShieldOff } from 'lucide-react'
import crmApi from '../../api/crmApi'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import {
  Button, toast,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel,
  AlertDialogAction,
} from '../../ui'

// WR9 / FG26 — actions RGPD sur la fiche client.
// - Export d'accès du sujet (JSON téléchargé) : responsable + admin.
// - Anonymisation irréversible des PII : admin uniquement, avec confirmation
//   AlertDialog. La règle vit côté serveur (permissions DRF) — le gate UI
//   n'est qu'un confort ; un rôle non autorisé ne voit pas les boutons.
export default function ClientRgpdActions({ client, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const canExport = useIsAdminOrResponsable()
  const canAnonymize = useIsAdmin()
  if (!canExport && !canAnonymize) return null

  const exporter = async () => {
    const pending = downloadBlobInGesture()
    setBusy(true)
    try {
      const r = await crmApi.clientDataExport(client.id)
      const blob = new Blob(
        [JSON.stringify(r.data, null, 2)], { type: 'application/json' })
      pending.deliver(blob, `client-${client.id}-donnees-rgpd.json`)
      toast.success('Export RGPD téléchargé')
    } catch (err) {
      toast.error(err?.response?.data?.detail
        ?? "Export RGPD impossible — réessayez.")
    } finally {
      setBusy(false)
    }
  }

  const anonymiser = async () => {
    setBusy(true)
    try {
      await crmApi.anonymizeClient(client.id)
      toast.success('Client anonymisé (données personnelles effacées)')
      setConfirmOpen(false)
      onChanged?.()
    } catch (err) {
      toast.error(err?.response?.data?.detail
        ?? 'Anonymisation impossible — réessayez.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="rgpd-actions">
      {canExport && (
        <Button type="button" variant="outline" size="sm"
                disabled={busy} onClick={exporter}>
          <Download /> Export RGPD (JSON)
        </Button>
      )}
      {canAnonymize && !client.is_anonymized && (
        <Button type="button" variant="destructive" size="sm"
                disabled={busy} onClick={() => setConfirmOpen(true)}>
          <ShieldOff /> Anonymiser (RGPD)
        </Button>
      )}
      {client.is_anonymized && (
        <span className="text-xs text-muted-foreground">Client anonymisé.</span>
      )}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Anonymiser ce client ?</AlertDialogTitle>
            <AlertDialogDescription>
              Les données personnelles (nom, email, téléphone, adresse, CIN…)
              seront effacées définitivement. Les devis et factures sont
              conservés, rattachés à une identité neutralisée. Cette action est
              irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Revenir</AlertDialogCancel>
            <AlertDialogAction onClick={(e) => { e.preventDefault(); anonymiser() }}>
              Anonymiser définitivement
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
