import { useMemo, useState } from 'react'
import { Card, Badge, Button, Input, Label } from '../../../ui'
import stockApi from '../../../api/stockApi'
import useStockFlags from '../../parametres/useStockFlags'
import ScanInputBar from './ScanInputBar'
import { playRejectBeep } from './scanFeedback'
import {
  SCAN_MODES, matchBcfLigne, nextReceptionQuantite, rejectedScan, acceptedScan,
} from './scanFlows'

/* ============================================================================
   XSTK5 — Réception scan-first (`ReceptionScanPanel`).
   ----------------------------------------------------------------------------
   Scanner un produit/EAN sur un BCF envoyé incrémente sa quantité reçue via
   l'action serveur EXISTANTE `recevoirBcf` (`POST
   /stock/bons-commande-fournisseur/{id}/recevoir/`, body
   `{receptions:[{ligne, quantite}]}`) — jamais un endpoint inventé. Le code
   scanné est résolu en produit via `stockApi.resolveCode` (N20/XSTK3/XSTK4 :
   GTIN/EAN nu + composite GS1-128/DataMatrix, décomposition lot/série déjà
   faite CÔTÉ SERVEUR — `data.gs1` préremplit `numero_lot`/`numeros_serie`
   quand le code scanné est un GS1 composite).

   NOTE (reportée, pas un blocage) : l'action `recevoir` ne persiste
   aujourd'hui QUE `ligne`+`quantite` — les numéros de série/lot capturés ici
   sont conservés dans l'état local du panneau (affichés, exportables) mais
   ne sont PAS encore écrits sur `LigneReceptionFournisseur`/`SerieEntrepot`
   par cette action ; un futur wiring backend devra étendre `recevoir` (ou
   router via `ReceptionFournisseur` + ses lignes) pour les persister — hors
   scope de ce ticket qui doit réutiliser l'action existante sans en créer
   une nouvelle.
   ========================================================================== */
export default function ReceptionScanPanel({ bonCommandeId }) {
  // ZSTK13 — capacités stock : True par défaut = comportement inchangé.
  const { stock_scan_actif: scanActif, stock_lots_series_actif: lotsSeriesActif } = useStockFlags()
  const [bcf, setBcf] = useState(null)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState(SCAN_MODES.PAR_UNITE)
  const [saisie, setSaisie] = useState('')
  const [lastRejected, setLastRejected] = useState(null)
  const [lastAccepted, setLastAccepted] = useState(null)
  const [capture, setCapture] = useState({ numeros_serie: '', numero_lot: '' })
  const [busy, setBusy] = useState(false)

  const load = async () => {
    if (!bonCommandeId) return
    setLoading(true)
    try {
      const res = await stockApi.getBonCommandeFournisseur(bonCommandeId)
      setBcf(res.data)
    } finally {
      setLoading(false)
    }
  }

  useMemo(() => { load() }, [bonCommandeId]) // eslint-disable-line react-hooks/exhaustive-deps

  const lignes = bcf?.lignes || []

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
    const ligne = matchBcfLigne(resolved.id, lignes)
    if (!ligne) {
      setLastRejected(rejectedScan(code))
      playRejectBeep()
      return
    }
    setLastAccepted(acceptedScan(ligne))
    if (resolved.gs1) {
      setCapture({
        numeros_serie: resolved.gs1.numero_serie || '',
        numero_lot: resolved.gs1.numero_lot || '',
      })
    }
    const qte = nextReceptionQuantite(ligne, { mode, saisie })
    if (qte <= 0) return
    setBusy(true)
    try {
      await stockApi.recevoirBcf(bonCommandeId, [{ ligne: ligne.id, quantite: qte }])
      await load()
      setSaisie('')
    } finally {
      setBusy(false)
    }
  }

  // ZSTK13 — panneau scan désactivé pour cette société (Paramètres → Stock) :
  // la saisie manuelle (quantités) reste disponible ailleurs sur l'écran.
  if (!scanActif) {
    return (
      <Card className="p-4 text-sm text-muted-foreground">
        Scan code-barres désactivé pour cette société (Paramètres → Stock).
      </Card>
    )
  }

  if (!bonCommandeId) {
    return (
      <Card className="p-4 text-sm text-muted-foreground">
        Sélectionnez un bon de commande fournisseur à réceptionner.
      </Card>
    )
  }

  return (
    <Card className="flex flex-col gap-3 p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="font-display text-base font-semibold tracking-tight">
            Réception scan — {bcf?.reference || '…'}
          </h3>
          <p className="text-sm text-muted-foreground">
            Scannez un produit/EAN pour incrémenter sa quantité reçue.
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
          <Label htmlFor="reception-qte-saisie">Quantité à recevoir (prochain scan)</Label>
          <Input
            id="reception-qte-saisie"
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
          {' '}({lastAccepted.ligne.quantite_recue}/{lastAccepted.ligne.quantite})
          {lotsSeriesActif && (capture.numeros_serie || capture.numero_lot) && (
            <div className="mt-1 text-xs text-muted-foreground">
              {capture.numeros_serie && <span>Série : {capture.numeros_serie} </span>}
              {capture.numero_lot && <span>Lot : {capture.numero_lot}</span>}
            </div>
          )}
        </div>
      )}

      <ul className="flex flex-col divide-y divide-border">
        {lignes.map((ligne) => (
          <li key={ligne.id} className="flex items-center gap-3 py-2 text-sm">
            <span className="flex-1">{ligne.produit_nom || ligne.designation}</span>
            <span className="text-muted-foreground">
              {ligne.quantite_recue ?? 0} / {ligne.quantite}
            </span>
          </li>
        ))}
      </ul>

      <Button size="sm" variant="outline" disabled={busy} onClick={load}>
        Rafraîchir
      </Button>
    </Card>
  )
}
