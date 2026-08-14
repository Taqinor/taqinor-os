import { useEffect, useState } from 'react'
import { AlertTriangle, Check, Download, RefreshCw } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import {
  Badge, Button, Input, Label, Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue, Spinner, toast,
} from '../../ui'
import { frenchError } from '../../lib/frenchError'
import { openPdfBlob } from '../../utils/pdfBlob'
import { filenameFromResponse } from '../../utils/downloadBlob'
// VX120 — même garde que le QR TOTP : un SVG rendu CÔTÉ SERVEUR (planche
// PV40 `schema_unifilaire_devis`) ne s'injecte QUE si `isTrustedSvg` le juge
// sûr (aucun `<script`, gestionnaire `on...=`, ou `javascript:`).
import { renderTrustedSvg } from '../../lib/trustedSvg'

/* ============================================================================
   PV43 — Panneau « Conception électrique » de la fiche devis.
   ----------------------------------------------------------------------------
   Rend l'étude électrique agrégée (PV41 — `apps.ventes.electrical_service`) en
   lecture depuis `GET .../conception-electrique/` (calcule au vol si absente),
   et la RECALCULE via le MÊME endpoint en `POST` avec des surcharges
   (`dc_m`/`ac_m`/`phases`) saisies dans un petit formulaire — jamais un
   deuxième chemin de calcul. La planche « schéma unifilaire » (PV40) est
   récupérée en SVG inline (`?format=json`) pour l'aperçu, et en PDF (blob)
   pour le téléchargement. Aucun prix, aucune marge : le moteur électrique n'en
   connaît aucun (règle du dépôt) — ce panneau ne rend que ce que le contrat
   partagé `apps/ventes/contract_samples/conception_electrique.json` porte.
   ========================================================================== */

// Repris de `apps/ventes/electrical_service.py` (DC_M_MINIMUM /
// DC_M_PAR_CHAINE) — UNIQUEMENT pour préremplir le formulaire avant la
// première réponse serveur ; la valeur AFFICHÉE vient toujours de
// `design.parametres.dc_m`, jamais de ce calcul recopié.
const DC_M_MINIMUM = 10
const DC_M_PAR_CHAINE = 20
const AC_M_DEFAUT = 15

function defaultDcM(nStrings) {
  return Math.max(DC_M_MINIMUM, (nStrings || 0) * DC_M_PAR_CHAINE)
}

export default function ConceptionElectrique({ devisId }) {
  const [design, setDesign] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [recalculating, setRecalculating] = useState(false)
  const [svg, setSvg] = useState(null)
  const [svgLoading, setSvgLoading] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)
  const [dcM, setDcM] = useState('')
  const [acM, setAcM] = useState(String(AC_M_DEFAUT))
  const [phases, setPhases] = useState('1')

  // Le retour de promesse permet à `handleRecalculer` d'attendre le rechargement
  // du schéma après un recalcul (setSvgLoading géré par l'appelant : effet ou
  // handler, jamais deux fois pour le même appel).
  const chargerSchema = () => ventesApi.getSchemaUnifilaireDevis(devisId)
    .then((res) => setSvg(res.data?.svg || null))
    .catch(() => setSvg(null))
    .finally(() => setSvgLoading(false))

  useEffect(() => {
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect -- amorçage du chargement, aucune cascade (comme PdfCanvas.jsx)
    setLoading(true)
    setError(null)
    ventesApi.getConceptionElectrique(devisId)
      .then((res) => {
        if (cancelled) return
        const data = res.data
        setDesign(data)
        setDcM(String(data?.parametres?.dc_m ?? defaultDcM(data?.chaines?.length)))
        setAcM(String(data?.parametres?.ac_m ?? AC_M_DEFAUT))
        setPhases(String(data?.parametres?.phases ?? 1))
      })
      .catch((err) => {
        if (!cancelled) setError(frenchError(err, "Étude électrique indisponible."))
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [devisId])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- amorçage du chargement, aucune cascade (comme PdfCanvas.jsx)
    setSvgLoading(true)
    chargerSchema()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [devisId])

  const handleRecalculer = async (e) => {
    e.preventDefault()
    setRecalculating(true)
    try {
      const overrides = {
        dc_m: dcM === '' ? undefined : Number(dcM),
        ac_m: acM === '' ? undefined : Number(acM),
        phases: Number(phases),
      }
      const res = await ventesApi.recalculerConceptionElectrique(devisId, overrides)
      setDesign(res.data)
      setError(null)
      setSvgLoading(true)
      await chargerSchema()
      toast.success('Étude électrique recalculée.')
    } catch (err) {
      toast.error(frenchError(err, 'Recalcul impossible.'))
    } finally {
      setRecalculating(false)
    }
  }

  const handleTelechargerPdf = async () => {
    setPdfBusy(true)
    try {
      const res = await ventesApi.getSchemaUnifilairePdf(devisId)
      openPdfBlob(res.data, filenameFromResponse(res, `schema-unifilaire-${devisId}.pdf`))
    } catch {
      toast.error('PDF du schéma unifilaire indisponible.')
    } finally {
      setPdfBusy(false)
    }
  }

  if (loading) {
    return <p className="text-xs text-muted-foreground">Chargement de l'étude électrique…</p>
  }
  if (error && !design) {
    return <p className="text-sm text-destructive">{error}</p>
  }
  if (!design) return null

  const chaines = design.chaines || []
  const conformite = design.conformite || { conforme: true, bloquants: [], alertes: [] }

  return (
    <div className="space-y-4">
      {/* Résumé de conformité */}
      <div className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          {conformite.conforme ? (
            <Badge tone="success" data-testid="conception-conformite-badge">
              <Check className="size-3" aria-hidden="true" />
              Conforme
            </Badge>
          ) : (
            <Badge tone="danger" data-testid="conception-conformite-badge">
              <AlertTriangle className="size-3" aria-hidden="true" />
              Non conforme
            </Badge>
          )}
          {design.ratio_dc_ac != null && (
            <span className="text-xs text-muted-foreground">
              Ratio DC/AC : {design.ratio_dc_ac}
            </span>
          )}
        </div>
        {conformite.bloquants.length > 0 && (
          <ul className="space-y-0.5 text-sm text-destructive">
            {conformite.bloquants.map((b, i) => <li key={i}>{b}</li>)}
          </ul>
        )}
        {conformite.alertes.length > 0 && (
          <ul className="space-y-0.5 text-sm text-warning">
            {conformite.alertes.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        )}
      </div>

      {/* Chaînes par MPPT */}
      <div className="overflow-x-auto">
        {chaines.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune chaîne calculée.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Pan</th>
                <th>MPPT</th>
                <th>Modules</th>
                <th>Vmp froid</th>
                <th>Voc froid</th>
                <th>Vmp chaud</th>
                <th>Conforme</th>
              </tr>
            </thead>
            <tbody>
              {chaines.map((c, i) => (
                <tr key={i}>
                  <td>{c.pan}</td>
                  <td>{c.mppt}</td>
                  <td>{c.nb_modules}</td>
                  <td>{c.vmp_froid_v} V</td>
                  <td>{c.voc_froid_v} V</td>
                  <td>{c.vmp_chaud_v} V</td>
                  <td>
                    {c.conforme
                      ? <Check className="size-3.5 text-success" aria-hidden="true" />
                      : <AlertTriangle className="size-3.5 text-destructive" aria-hidden="true" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Aperçu du schéma unifilaire */}
      <div>
        <div className="mb-1.5 flex items-center justify-between gap-2">
          <p className="text-xs font-medium text-muted-foreground">Schéma unifilaire</p>
          <Button size="sm" variant="outline" onClick={handleTelechargerPdf} disabled={pdfBusy}>
            {pdfBusy ? <Spinner className="size-3.5" /> : <Download className="size-3.5" aria-hidden="true" />}
            Télécharger le PDF
          </Button>
        </div>
        {svgLoading ? (
          <p className="text-xs text-muted-foreground">Chargement du schéma…</p>
        ) : renderTrustedSvg(svg) ? (
          <div
            role="img"
            aria-label="Schéma unifilaire"
            className="max-w-2xl rounded border border-border p-2 [&_svg]:h-auto [&_svg]:max-w-full"
            dangerouslySetInnerHTML={renderTrustedSvg(svg)}
          />
        ) : (
          <p className="text-xs text-muted-foreground">Schéma indisponible.</p>
        )}
      </div>

      {/* Surcharges + recalcul */}
      <form noValidate onSubmit={handleRecalculer} className="flex flex-wrap items-end gap-3">
        <div>
          <Label htmlFor={`ce-dcm-${devisId}`}>Liaison DC (m)</Label>
          <Input
            id={`ce-dcm-${devisId}`} type="number" min="0" step="any"
            className="w-28"
            value={dcM} onChange={(e) => setDcM(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor={`ce-acm-${devisId}`}>Liaison AC (m)</Label>
          <Input
            id={`ce-acm-${devisId}`} type="number" min="0" step="any"
            className="w-28"
            value={acM} onChange={(e) => setAcM(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor={`ce-phases-${devisId}`}>Phases</Label>
          <Select value={phases} onValueChange={setPhases}>
            <SelectTrigger id={`ce-phases-${devisId}`} className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">Monophasé</SelectItem>
              <SelectItem value="3">Triphasé</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button type="submit" size="sm" disabled={recalculating}>
          {recalculating ? <Spinner className="size-3.5" /> : <RefreshCw className="size-3.5" aria-hidden="true" />}
          Recalculer
        </Button>
      </form>
    </div>
  )
}
