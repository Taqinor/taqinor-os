import { useMemo, useState } from 'react'
import { Card, Badge, Button, Input, Label } from '../../../ui'
import stockApi from '../../../api/stockApi'
import installationsApi from '../../../api/installationsApi'
import ScanInputBar from './ScanInputBar'
import { playRejectBeep } from './scanFeedback'
import {
  SCAN_MODES, matchComptageLine, nextComptageQuantite, rejectedScan, acceptedScan,
} from './scanFlows'

/* ============================================================================
   XSTK5 — Comptage scan-first (`ComptageScanPanel`).
   ----------------------------------------------------------------------------
   Scanner un produit sélectionne sa ligne dans la `SessionComptage` en
   cours ; la quantité comptée est alors saisie (mode saisie-quantité) ou
   incrémentée de 1 par scan (mode scan-par-unité) via
   `installationsApi.updateComptageLigne` (EXISTANT — `PATCH
   /installations/comptage-lignes/{id}/`). Un SKU scanné mais absent de la
   session (jamais ajouté via `ajouter-ligne`) est REFUSÉ — la session ne
   compte que ce qui lui a été explicitement ajouté.
   ========================================================================== */
export default function ComptageScanPanel({ sessionId }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState(SCAN_MODES.SAISIE_QUANTITE)
  const [saisie, setSaisie] = useState('')
  const [lastRejected, setLastRejected] = useState(null)
  const [lastAccepted, setLastAccepted] = useState(null)
  const [busyLigneId, setBusyLigneId] = useState(null)

  const load = async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const res = await installationsApi.getSessionComptage(sessionId)
      setSession(res.data)
    } finally {
      setLoading(false)
    }
  }

  useMemo(() => { load() }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  const lignes = session?.lignes || []

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
    const ligne = matchComptageLine(resolved.id, lignes)
    if (!ligne) {
      setLastRejected(rejectedScan(code))
      playRejectBeep()
      return
    }
    setLastAccepted(acceptedScan(ligne))
    // En saisie-quantité, on attend que l'opérateur ait tapé une valeur
    // avant d'écrire (le scan seul ne fait que SÉLECTIONNER la ligne).
    if (mode === SCAN_MODES.SAISIE_QUANTITE && saisie === '') return
    const qte = nextComptageQuantite(ligne, { mode, saisie })
    setBusyLigneId(ligne.id)
    try {
      const res = await installationsApi.updateComptageLigne(ligne.id, {
        quantite_comptee: qte, compte: true,
      })
      setSession((prev) => ({
        ...prev,
        lignes: (prev?.lignes || []).map((l) => (l.id === ligne.id ? res.data : l)),
      }))
      setSaisie('')
    } finally {
      setBusyLigneId(null)
    }
  }

  if (!sessionId) {
    return (
      <Card className="p-4 text-sm text-muted-foreground">
        Sélectionnez une session de comptage tournant en cours.
      </Card>
    )
  }

  return (
    <Card className="flex flex-col gap-3 p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="font-display text-base font-semibold tracking-tight">
            Comptage scan — {session?.reference || '…'}
          </h3>
          <p className="text-sm text-muted-foreground">
            Scannez un produit puis saisissez le compte constaté.
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
          <Label htmlFor="comptage-qte-saisie">Quantité comptée (prochain scan)</Label>
          <Input
            id="comptage-qte-saisie"
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
          Ligne sélectionnée : <strong>{lastAccepted.ligne.produit_nom || lastAccepted.ligne.designation}</strong>
          {' '}(théorique {lastAccepted.ligne.quantite_theorique})
        </div>
      )}

      <ul className="flex flex-col divide-y divide-border">
        {lignes.map((ligne) => (
          <li key={ligne.id} className="flex items-center gap-3 py-2 text-sm">
            <span className="flex-1">{ligne.produit_nom || ligne.designation}</span>
            <span className="text-muted-foreground">
              {busyLigneId === ligne.id ? '…' : `${ligne.quantite_comptee ?? '—'} (théo. ${ligne.quantite_theorique})`}
            </span>
            {ligne.compte && <Badge tone="success">Compté</Badge>}
          </li>
        ))}
      </ul>

      <Button size="sm" variant="outline" onClick={load}>Rafraîchir</Button>
    </Card>
  )
}
