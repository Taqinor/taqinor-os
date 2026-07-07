import { useMemo, useState } from 'react'
import { Card, Badge, Button, Input, Label } from '../../../ui'
import stockApi from '../../../api/stockApi'
import installationsApi from '../../../api/installationsApi'
import { sortPickListLignesByBin, pickListProgress } from '../magasin'
import ScanInputBar from './ScanInputBar'
import { playRejectBeep } from './scanFeedback'
import {
  SCAN_MODES, matchPickListLine, nextPickingState, rejectedScan, acceptedScan,
} from './scanFlows'

/* ============================================================================
   XSTK5 — Picking scan-first (`PickingScanPanel`).
   ----------------------------------------------------------------------------
   Scanner un article coche la ligne de pick-list correspondante
   (`installationsApi.updatePickListLigne`, EXISTANT) ; un scan hors bon de
   prélèvement est REFUSÉ (alerte visuelle + sonore), jamais coché au hasard.
   Résolution du code via `stockApi.resolveCode` (réutilisé, pas dupliqué).
   ========================================================================== */
export default function PickingScanPanel({ pickListId }) {
  const [pickList, setPickList] = useState(null)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState(SCAN_MODES.PAR_UNITE)
  const [saisie, setSaisie] = useState('')
  const [lastRejected, setLastRejected] = useState(null)
  const [lastAccepted, setLastAccepted] = useState(null)
  const [busyLigneId, setBusyLigneId] = useState(null)

  const load = async () => {
    if (!pickListId) return
    setLoading(true)
    try {
      const res = await installationsApi.getPickList(pickListId)
      setPickList(res.data)
    } finally {
      setLoading(false)
    }
  }

  useMemo(() => { load() }, [pickListId]) // eslint-disable-line react-hooks/exhaustive-deps

  const lignes = sortPickListLignesByBin(pickList?.lignes)
  const progress = pickListProgress(lignes)

  const handleScan = async (code) => {
    setLastRejected(null)
    let resolved
    try {
      const res = await stockApi.resolveCode(code)
      resolved = res.data
    } catch {
      setLastRejected(rejectedScan(code))
      playRejectBeep()
      return
    }
    const ligne = matchPickListLine(resolved.id, lignes)
    if (!ligne) {
      setLastRejected(rejectedScan(code))
      playRejectBeep()
      return
    }
    setLastAccepted(acceptedScan(ligne))
    const next = nextPickingState(ligne, { mode, saisie })
    setBusyLigneId(ligne.id)
    try {
      const res = await installationsApi.updatePickListLigne(ligne.id, next)
      setPickList((prev) => ({
        ...prev,
        lignes: (prev?.lignes || []).map((l) => (l.id === ligne.id ? res.data : l)),
      }))
      setSaisie('')
    } finally {
      setBusyLigneId(null)
    }
  }

  if (!pickListId) {
    return (
      <Card className="p-4 text-sm text-muted-foreground">
        Sélectionnez un bon de prélèvement à préparer.
      </Card>
    )
  }

  return (
    <Card className="flex flex-col gap-3 p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="font-display text-base font-semibold tracking-tight">
            Picking scan — {pickList?.reference || '…'}
          </h3>
          <p className="text-sm text-muted-foreground">
            {progress.done}/{progress.total} ligne(s) prélevée(s) ({progress.pct}%)
          </p>
        </div>
        {loading && <Badge tone="neutral">Chargement…</Badge>}
      </div>

      <ScanInputBar
        mode={mode}
        onModeChange={setMode}
        onScan={handleScan}
        lastRejected={lastRejected}
      />

      {mode === SCAN_MODES.SAISIE_QUANTITE && (
        <div className="flex flex-col gap-1">
          <Label htmlFor="picking-qte-saisie">Quantité prélevée (prochain scan)</Label>
          <Input
            id="picking-qte-saisie"
            type="number"
            inputMode="decimal"
            step="any"
            noValidate
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
            className="w-32"
          />
        </div>
      )}

      {lastAccepted?.ligne && (
        <div className="rounded-lg border border-border bg-muted/30 p-2 text-sm">
          Dernier scan accepté : <strong>{lastAccepted.ligne.produit_nom || lastAccepted.ligne.designation}</strong>
        </div>
      )}

      <ul className="flex flex-col divide-y divide-border">
        {lignes.map((ligne) => (
          <li key={ligne.id} className="flex items-center gap-3 py-2 text-sm">
            <span className="w-20 shrink-0 font-mono text-xs text-muted-foreground">
              {ligne.bin_code || '—'}
            </span>
            <span className="flex-1">{ligne.produit_nom || ligne.designation}</span>
            <span className="text-muted-foreground">
              {busyLigneId === ligne.id ? '…' : `${ligne.quantite_prelevee ?? 0} / ${ligne.quantite_demandee ?? 0}`}
            </span>
            {ligne.preleve && <Badge tone="success">Prélevé</Badge>}
          </li>
        ))}
      </ul>

      <Button size="sm" variant="outline" onClick={load}>Rafraîchir</Button>
    </Card>
  )
}
