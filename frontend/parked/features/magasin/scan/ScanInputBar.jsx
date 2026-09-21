import { useState } from 'react'
import { Camera, ScanLine, X } from 'lucide-react'
import { Button, Input, Segmented } from '../../../ui'
import BarcodeScanner from '../../pwa/BarcodeScanner'
import useKeyboardWedge from './useKeyboardWedge'
import { scanModeOptions } from './scanFlows'

/* ============================================================================
   XSTK5 — Barre de scan partagée par les 3 flux (réception/picking/comptage).
   ----------------------------------------------------------------------------
   Combine caméra (`BarcodeScanner`, FG384) + clavier-wedge
   (`useKeyboardWedge`) + un champ de secours (saisie manuelle) + le
   sélecteur de mode « scan-par-unité » / « saisie quantité ». Le parent ne
   voit qu'un seul `onScan(code)`, quelle que soit la source du code.
   ========================================================================== */
export default function ScanInputBar({
  mode,
  onModeChange,
  onScan,
  lastRejected,
  className = '',
}) {
  const [cameraOpen, setCameraOpen] = useState(false)
  const [manualCode, setManualCode] = useState('')

  // Le clavier-wedge écoute en permanence (tant que la caméra n'est pas
  // ouverte — évite un double-traitement du même flux de frappes).
  useKeyboardWedge({ onScan, enabled: !cameraOpen })

  const submitManual = (e) => {
    e.preventDefault()
    const code = manualCode.trim()
    if (!code) return
    onScan(code)
    setManualCode('')
  }

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented
          options={scanModeOptions()}
          value={mode}
          onChange={onModeChange}
          aria-label="Mode de scan"
        />
        <Button
          type="button"
          size="sm"
          variant={cameraOpen ? 'outline' : 'default'}
          onClick={() => setCameraOpen((v) => !v)}
        >
          {cameraOpen ? <X className="size-4" aria-hidden="true" /> : <Camera className="size-4" aria-hidden="true" />}
          {cameraOpen ? 'Fermer caméra' : 'Scanner (caméra)'}
        </Button>
      </div>

      {cameraOpen && (
        <BarcodeScanner
          onDetected={(value) => onScan(value)}
          onClose={() => setCameraOpen(false)}
        />
      )}

      <form onSubmit={submitManual} noValidate className="flex items-center gap-2">
        <ScanLine className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <Input
          value={manualCode}
          onChange={(e) => setManualCode(e.target.value)}
          placeholder="Code scanné (douchette clavier-wedge active) ou saisie manuelle…"
          aria-label="Code scanné ou saisi manuellement"
          className="flex-1"
        />
        <Button type="submit" size="sm" variant="outline">Valider</Button>
      </form>

      {lastRejected && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-[12px] text-destructive"
        >
          <span>
            Code « {lastRejected.code} » refusé : article hors liste.
          </span>
        </div>
      )}
    </div>
  )
}
