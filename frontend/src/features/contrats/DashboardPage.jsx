import { useEffect, useMemo, useState } from 'react'
import {
  FileSignature, RefreshCw, AlertTriangle, TrendingUp, Wallet, PercentCircle,
} from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import {
  Card, Button, Badge, Input, Label, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import { ModuleDashboard } from '../../ui/module'
import { formatMAD, formatNumber, formatPercent } from '../../lib/format'
import SimpleTable from './SimpleTable'

/* ============================================================================
   CONTRAT33 — Tableau de bord des contrats + analytique récurrente.
   ----------------------------------------------------------------------------
   KPI (total / actifs / à renouveler / MRR — tableau-de-bord), cascade MRR
   new/expansion/contraction/churn/net (XCTR7), carte exceptions de facturation
   (XCTR5), cohortes de rétention (XCTR8), campagne de révision tarifaire en
   masse (XCTR11, admin — preview obligatoire avant application). Aucune donnée
   de coût interne.
   ========================================================================== */

const num = (v) => Number(v ?? 0)

export default function DashboardPage() {
  const [board, setBoard] = useState(null)
  const [mrr, setMrr] = useState(null)
  const [exceptions, setExceptions] = useState([])
  const [cohortes, setCohortes] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [campagneOpen, setCampagneOpen] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setLoading(true)
    Promise.all([
      contratsApi.getTableauBord().then((r) => setBoard(r.data)),
      contratsApi.getMrrMouvements().then((r) => setMrr(r.data)).catch(() => setMrr(null)),
      contratsApi.getExceptionsFacturation().then((r) => setExceptions(Array.isArray(r.data) ? r.data : (r.data?.results ?? []))).catch(() => setExceptions([])),
      contratsApi.getCohortesRetention().then((r) => setCohortes(r.data)).catch(() => setCohortes(null)),
    ])
      .catch(() => setError('Impossible de charger le tableau de bord.'))
      .finally(() => setLoading(false))
  }, [])

  const stats = useMemo(() => (board ? [
    { label: 'Contrats', value: formatNumber(board.total), icon: FileSignature, to: '/contrats' },
    { label: 'Actifs', value: formatNumber(board.actifs), icon: TrendingUp, hint: `${formatNumber(board.a_renouveler)} à renouveler` },
    { label: 'Valeur active', value: formatMAD(board.valeur_active), icon: Wallet, hint: `Total : ${formatMAD(board.valeur_totale)}` },
    { label: 'MRR', value: formatMAD(board.mrr), icon: PercentCircle, hint: board.mrr_combine != null ? `Combiné : ${formatMAD(board.mrr_combine)}` : undefined },
  ] : []), [board])

  const mrrWaterfall = mrr ? [
    { label: 'New', value: num(mrr.new), tone: 'success' },
    { label: 'Expansion', value: num(mrr.expansion), tone: 'success' },
    { label: 'Contraction', value: -Math.abs(num(mrr.contraction)), tone: 'warning' },
    { label: 'Churn', value: -Math.abs(num(mrr.churn)), tone: 'danger' },
    { label: 'Net', value: num(mrr.net), tone: num(mrr.net) >= 0 ? 'info' : 'danger' },
  ] : []
  const maxAbs = Math.max(1, ...mrrWaterfall.map((r) => Math.abs(r.value)))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-display text-xl font-semibold tracking-tight">Tableau de bord des contrats</h1>
        <Button variant="outline" onClick={() => setCampagneOpen(true)}>
          <PercentCircle /> Campagne de révision
        </Button>
      </div>

      <ModuleDashboard stats={stats} loading={loading} error={error} />

      {!loading && !error && (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* XCTR7 — cascade MRR. */}
          <Card className="p-4 sm:p-5">
            <h3 className="mb-3 flex items-center gap-2 font-display text-base font-semibold">
              <TrendingUp className="size-4 text-muted-foreground" aria-hidden="true" /> Mouvements MRR (mois courant)
            </h3>
            {mrr ? (
              <ul className="flex flex-col gap-2">
                {mrrWaterfall.map((r) => (
                  <li key={r.label} className="flex items-center gap-3">
                    <span className="w-24 shrink-0 text-sm">{r.label}</span>
                    <span className="h-4 flex-1 overflow-hidden rounded bg-muted">
                      <span
                        className={`block h-full ${r.tone === 'danger' ? 'bg-destructive' : r.tone === 'warning' ? 'bg-warning' : r.tone === 'info' ? 'bg-info' : 'bg-success'}`}
                        style={{ width: `${(Math.abs(r.value) / maxAbs) * 100}%` }}
                      />
                    </span>
                    <span className="w-28 shrink-0 text-right text-sm tabular-nums">{formatMAD(r.value)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Données MRR indisponibles.</p>
            )}
          </Card>

          {/* XCTR5 — exceptions de facturation. */}
          <Card className="p-4 sm:p-5">
            <h3 className="mb-3 flex items-center gap-2 font-display text-base font-semibold">
              <AlertTriangle className="size-4 text-warning" aria-hidden="true" /> Exceptions de facturation
              {exceptions.length > 0 && <Badge tone="warning">{exceptions.length}</Badge>}
            </h3>
            {exceptions.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune exception — tous les cycles ont été facturés.</p>
            ) : (
              <SimpleTable
                emptyText="Aucune exception."
                rows={exceptions.slice(0, 8)}
                columns={[
                  { header: 'Source', cell: (c) => c.source_type_display || c.source_type },
                  { header: 'Période', cell: (c) => c.periode || '—' },
                  { header: 'Statut', cell: (c) => <Badge tone="danger">{c.statut_display || c.statut}</Badge> },
                  {
                    header: '',
                    align: 'right',
                    cell: (c) => (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          try { await contratsApi.rejouerCycle(c.id); toast.success('Cycle rejoué.') }
                          catch (e) { toast.error(e?.response?.data?.detail || 'Rejeu impossible.') }
                        }}
                      >
                        <RefreshCw className="size-3.5" /> Rejouer
                      </Button>
                    ),
                  },
                ]}
              />
            )}
          </Card>
        </div>
      )}

      {/* WIR77 / XCTR9 — valeur vie client (CLV) par client. */}
      {!loading && !error && <ClvCard />}

      {/* XCTR8 — cohortes de rétention. */}
      {!loading && !error && cohortes?.cohortes && Object.keys(cohortes.cohortes).length > 0 && (
        <Card className="p-4 sm:p-5">
          <h3 className="mb-3 font-display text-base font-semibold">Cohortes de rétention (logo %)</h3>
          <CohortesHeatmap cohortes={cohortes} />
        </Card>
      )}

      {campagneOpen && (
        <CampagneRevisionDialog onClose={() => setCampagneOpen(false)} />
      )}
    </div>
  )
}

// XCTR8 — heatmap logo %, cohorte (mois de signature) × ancienneté.
function CohortesHeatmap({ cohortes }) {
  const mois = Object.keys(cohortes.cohortes).sort()
  const maxAnc = cohortes.mois_max ?? 0
  const cols = Array.from({ length: maxAnc + 1 }, (_, i) => i)
  const cell = (pct) => {
    const v = Number(pct ?? 0)
    const bg = v >= 90 ? 'bg-success/70' : v >= 70 ? 'bg-success/40' : v >= 50 ? 'bg-warning/40' : 'bg-destructive/30'
    return bg
  }
  return (
    <div className="overflow-x-auto">
      <table className="text-xs">
        <thead>
          <tr>
            <th className="px-2 py-1 text-left font-medium text-muted-foreground">Cohorte</th>
            {cols.map((c) => <th key={c} className="px-2 py-1 text-center font-medium text-muted-foreground">M{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {mois.map((m) => (
            <tr key={m}>
              <td className="px-2 py-1 font-mono">{m}</td>
              {cols.map((c) => {
                const v = cohortes.cohortes[m]?.[String(c)]
                return (
                  <td key={c} className="px-1 py-1 text-center">
                    {v ? (
                      <span className={`inline-block w-12 rounded px-1 py-0.5 tabular-nums ${cell(v.logo_pct)}`}>
                        {formatPercent(v.logo_pct ?? 0, { decimals: 0 })}
                      </span>
                    ) : <span className="text-muted-foreground/40">—</span>}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// WIR77 / XCTR9 — carte CLV : saisir un client → ARPC, durée de vie, CLV.
// L'endpoint exige un client_id (lien lâche Contrat.client_id) ; clv=null
// quand le calcul est impossible (churn nul/inconnu) — jamais une fausse valeur.
function ClvCard() {
  const [clientId, setClientId] = useState('')
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const chercher = async (e) => {
    e.preventDefault()
    if (clientId === '') { setErr('L’identifiant client est requis.'); return }
    setBusy(true)
    setErr(null)
    try {
      const r = await contratsApi.getClv({ client_id: Number(clientId) })
      setData(r.data)
    } catch (e2) {
      setData(null)
      setErr(e2?.response?.data?.detail || 'Calcul CLV impossible.')
    } finally { setBusy(false) }
  }

  return (
    <Card className="p-4 sm:p-5">
      <h3 className="mb-3 flex items-center gap-2 font-display text-base font-semibold">
        <Wallet className="size-4 text-muted-foreground" aria-hidden="true" /> Valeur vie client (CLV)
      </h3>
      <form onSubmit={chercher} className="flex flex-wrap items-end gap-3" noValidate>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="clv-client">Identifiant client</Label>
          <Input id="clv-client" type="number" step="1" value={clientId}
                 onChange={(e) => setClientId(e.target.value)} placeholder="ex. 42" className="w-40" />
        </div>
        <Button type="submit" variant="outline" disabled={busy}>{busy ? 'Calcul…' : 'Calculer'}</Button>
      </form>
      {err && <p className="mt-2 text-sm text-destructive" role="alert">{err}</p>}
      {data && (
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">ARPC (MRR client)</p>
            <p className="font-display text-lg font-semibold tabular-nums">{formatMAD(data.arpc)}</p>
          </div>
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">Durée de vie estimée</p>
            <p className="font-display text-lg font-semibold tabular-nums">
              {data.duree_vie_mois != null ? `${data.duree_vie_mois} mois` : '—'}
            </p>
          </div>
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">
              CLV{data.plafonnee ? ' (plafonnée)' : ''}{data.used_fallback ? ' (churn estimé)' : ''}
            </p>
            <p className="font-display text-lg font-semibold tabular-nums">
              {data.clv != null ? formatMAD(data.clv) : 'Indisponible'}
            </p>
          </div>
        </div>
      )}
    </Card>
  )
}

// XCTR11 — campagne de révision tarifaire en masse (preview → application).
function CampagneRevisionDialog({ onClose }) {
  const [pct, setPct] = useState('')
  const [dateEffet, setDateEffet] = useState('')
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  // WIR77 — ids d'avenants de la dernière application, pour le rollback (XCTR11).
  const [rollbackIds, setRollbackIds] = useState([])

  const lancerPreview = async (e) => {
    e.preventDefault()
    if (pct === '') { setErr('Le pourcentage est requis.'); return }
    setBusy(true)
    setErr(null)
    try {
      const r = await contratsApi.campagneRevision({ pct: Number(pct), date_effet: dateEffet || undefined, preview: true })
      setPreview(r.data)
    } catch (e2) {
      setErr(e2?.response?.data?.detail || 'Aperçu impossible.')
    } finally { setBusy(false) }
  }

  const appliquer = async () => {
    setBusy(true)
    setErr(null)
    try {
      const r = await contratsApi.campagneRevision({ pct: Number(pct), date_effet: dateEffet || undefined, preview: false })
      toast.success(`Campagne appliquée : ${r.data?.avenants_crees ?? 0} avenant(s).`)
      // WIR77 — on garde la fenêtre ouverte pour offrir le rollback tant que
      // les ids d'avenants sont connus (annulation par avenants compensatoires,
      // jamais de suppression — historique immuable).
      setRollbackIds(Array.isArray(r.data?.rollback_ids) ? r.data.rollback_ids : [])
      setPreview(null)
    } catch (e2) {
      setErr(e2?.response?.data?.detail || 'Application impossible.')
    } finally { setBusy(false) }
  }

  // WIR77 — annule la campagne appliquée (avenants compensatoires).
  const rollback = async () => {
    setBusy(true)
    setErr(null)
    try {
      const r = await contratsApi.campagneRevisionRollback({ avenant_ids: rollbackIds })
      toast.success(`Campagne annulée : ${r.data?.compensations_creees ?? 0} compensation(s).`)
      setRollbackIds([])
      onClose()
    } catch (e2) {
      setErr(e2?.response?.data?.detail || 'Annulation impossible.')
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader><DialogTitle>Campagne de révision tarifaire (admin)</DialogTitle></DialogHeader>
        <form onSubmit={lancerPreview} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="camp-pct">Révision (%)</Label>
              <Input id="camp-pct" type="number" step="any" value={pct} onChange={(e) => setPct(e.target.value)} placeholder="ex. 3.5" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="camp-effet">Date d’effet</Label>
              <Input id="camp-effet" type="date" value={dateEffet} onChange={(e) => setDateEffet(e.target.value)} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            L’aperçu n’écrit rien. L’application crée un avenant d’indexation par contrat couvert (idempotent).
          </p>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <div className="flex justify-end">
            <Button type="submit" variant="outline" disabled={busy}>{busy ? 'Calcul…' : 'Prévisualiser'}</Button>
          </div>
        </form>

        {preview?.lignes && (
          <div className="mt-2">
            <SimpleTable
              emptyText="Aucun contrat couvert par ces filtres."
              rows={preview.lignes}
              columns={[
                { header: 'Contrat', cell: (l) => <span className="font-medium">{l.objet || `#${l.contrat_id}`}</span> },
                { header: 'Ancien', cell: (l) => formatMAD(l.ancien_montant), align: 'right' },
                { header: 'Nouveau', cell: (l) => formatMAD(l.nouveau_montant), align: 'right' },
                { header: 'Delta', cell: (l) => formatMAD(l.delta), align: 'right' },
              ]}
            />
          </div>
        )}

        {/* WIR77 — bandeau rollback après application. */}
        {rollbackIds.length > 0 && (
          <p className="mt-2 rounded-md border border-warning/30 bg-warning/10 p-2 text-xs text-foreground">
            Campagne appliquée sur {rollbackIds.length} avenant(s). Vous pouvez
            l’annuler (chaque avenant sera compensé, sans suppression).
          </p>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
          {rollbackIds.length > 0 && (
            <Button type="button" variant="destructive" disabled={busy} onClick={rollback}>
              <RefreshCw className="size-3.5" /> Annuler la campagne
            </Button>
          )}
          {preview?.lignes?.length > 0 && (
            <Button type="button" disabled={busy} onClick={appliquer}>
              Appliquer à {preview.lignes.length} contrat(s)
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
