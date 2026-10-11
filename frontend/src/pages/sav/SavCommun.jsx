// ENF28 (ENF19) — briques d'écran partagées des pages SAV (tickets,
// équipements, contrats de maintenance, réclamations garantie). Chacune
// existait en plusieurs copies recopiées à l'identique ; une seule ici.
import { useState } from 'react'
import { AlertTriangle, Check, ChevronRight, Download, X } from 'lucide-react'
import importApi from '../../api/importApi'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import BarcodeScanner from '../../features/pwa/BarcodeScanner'
import { Button, Card, EmptyState, SelectItem, Skeleton, Spinner } from '../../ui'

/** Section repliable (ouverte par défaut) à titre et icône. */
export function CollapsibleSection({ icon: Icon, title, children }) {
  return (
    <details open className="group flex flex-col gap-3 [&[open]>summary>svg.chevron]:rotate-90">
      <summary className="flex cursor-pointer list-none items-center gap-2 font-display text-base font-semibold text-foreground">
        {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden="true" />}
        <span className="flex-1">{title}</span>
        <ChevronRight className="chevron size-4 rotate-0 text-muted-foreground transition-transform" aria-hidden="true" />
      </summary>
      <div className="flex flex-col gap-3 pt-2">{children}</div>
    </details>
  )
}

/** Squelette de liste pendant le chargement. */
export function SqueletteListe({ lignes = 5 }) {
  return (
    <Card className="space-y-2 p-4">
      {Array.from({ length: lignes }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
    </Card>
  )
}

/** Échec de chargement d'une liste, avec « Réessayer ». */
export function ErreurChargement({ description, onRetry, retryIcon = null }) {
  return (
    <EmptyState
      icon={AlertTriangle}
      title="Chargement impossible"
      description={description}
      action={<Button size="sm" variant="outline" onClick={onRetry}>{retryIcon ? <>{retryIcon} Réessayer</> : 'Réessayer'}</Button>}
    />
  )
}

/** Message d'erreur d'un formulaire de création (rien si aucun message). */
export function ErreurFormulaire({ message }) {
  if (!message) return null
  return (
    <div role="alert"
         className="mt-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">
      <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
      {message}
    </div>
  )
}

/** NTMOB15 — scanner QR plein écran (ouvre la fiche au lieu d'une recherche). */
export function ScannerQrPleinEcran({ onDetected, onClose }) {
  return (
    <div
      className="fixed inset-0 z-[var(--z-overlay)] flex items-center justify-center bg-black/60 p-4"
      role="dialog" aria-modal="true"
    >
      <div className="w-full max-w-md">
        <BarcodeScanner formats={['qr_code']} onDetected={onDetected} onClose={onClose} />
      </div>
    </div>
  )
}

/** Export Excel de la liste affichée (`cible` = cible d'import/export). */
export function BoutonExportExcel({ cible, ids }) {
  const [busy, setBusy] = useState(false)
  return (
    <Button variant="outline" size="sm" disabled={busy}
            onClick={() => {
              const pending = downloadBlobInGesture()
              setBusy(true)
              importApi.exportList(cible, ids)
                .then((r) => pending.deliver(r.data, `${cible}.xlsx`))
                .catch(() => {})
                .finally(() => setBusy(false))
            }}>
      {busy ? <Spinner /> : <Download />} Exporter Excel
    </Button>
  )
}

/** Boutons « Enregistrer » / annuler d'une ligne éditée en place. */
export function BoutonsEdition({ onSave, onCancel }) {
  return (
    <div className="flex gap-2">
      <Button size="sm" variant="outline" onClick={onSave}><Check /> Enregistrer</Button>
      <Button size="sm" variant="ghost" onClick={onCancel}><X /></Button>
    </div>
  )
}

/** Options d'un sélecteur de chantier. */
export function OptionsChantier({ installations }) {
  return installations.map((i) => (
    <SelectItem key={i.id} value={String(i.id)}>
      {i.reference ?? `Chantier ${i.id}`}
    </SelectItem>
  ))
}

/** Options d'un sélecteur d'équipement (produit — n° de série). */
export function OptionsEquipement({ equipements }) {
  return equipements.map((e) => (
    <SelectItem key={e.id} value={String(e.id)}>
      {(e.produit_nom ?? 'Produit')} — {e.numero_serie ?? 'sans n° série'}
    </SelectItem>
  ))
}
