import { useEffect, useState } from 'react'
import posApi from '../../api/posApi'
import api from '../../api/axios'
import { Button, Input, Label, EmptyState, toast } from '../../ui'
import { formatMAD } from '../../lib/format'

/* XPOS11 — Tableau de bord des ventes comptoir (route /pos/dashboard).
   6 axes (jour / session / caissier / mode / produit / catégorie) + KPIs
   (nb ventes, total TTC, panier moyen, taux de retour) + export xlsx. */
const fmt = (v) => formatMAD(v, { withSymbol: false })

function Breakdown({ titre, rows, valeur }) {
  const entries = Object.entries(rows || {})
  if (entries.length === 0) return null
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <h3 className="mb-2 text-sm font-medium">{titre}</h3>
      <ul className="flex flex-col gap-1 text-sm">
        {entries.map(([k, v]) => (
          <li key={k} className="flex justify-between gap-3">
            <span className="truncate text-muted-foreground">{k || '—'}</span>
            <span className="tabular-nums">{fmt(valeur ? valeur(v) : v)} DH</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function DashboardScreen() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')

  const load = () => {
    const params = {}
    if (dateDebut) params.date_debut = dateDebut
    if (dateFin) params.date_fin = dateFin
    return posApi.getDashboard(params)
      .then((r) => setData(r.data))
      .catch(() => { setData(null); toast.error('Le tableau de bord est indisponible.') })
      .finally(() => setLoading(false))
  }
  const charger = () => { setLoading(true); return load() }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleExport = () => {
    // Export xlsx : ouverture directe (cookie httpOnly envoyé par le navigateur).
    const base = api.defaults.baseURL || ''
    window.open(`${base}/api/django${posApi.exportDashboardUrl()}`, '_blank')
  }

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-display text-xl font-semibold">Ventes comptoir — tableau de bord</h1>
        <Button type="button" variant="outline" onClick={handleExport}>Exporter (xlsx)</Button>
      </div>

      <form
        noValidate
        onSubmit={(e) => { e.preventDefault(); charger() }}
        className="flex flex-wrap items-end gap-2"
      >
        <div className="grid gap-1.5">
          <Label htmlFor="db-debut">Du</Label>
          <Input id="db-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="db-fin">Au</Label>
          <Input id="db-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
        </div>
        <Button type="submit">Filtrer</Button>
      </form>

      {loading ? (
        <div className="py-8 text-center text-sm text-muted-foreground">Chargement…</div>
      ) : !data ? (
        <EmptyState title="Aucune donnée" description="Aucune vente comptoir sur la période." />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="dashboard-kpis">
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="text-xs text-muted-foreground">Ventes</div>
              <div className="text-lg font-semibold tabular-nums">{data.nb_ventes}</div>
            </div>
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="text-xs text-muted-foreground">Total TTC</div>
              <div className="text-lg font-semibold tabular-nums">{fmt(data.total_ttc)} DH</div>
            </div>
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="text-xs text-muted-foreground">Panier moyen</div>
              <div className="text-lg font-semibold tabular-nums">{fmt(data.panier_moyen)} DH</div>
            </div>
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="text-xs text-muted-foreground">Taux de retour</div>
              <div className="text-lg font-semibold tabular-nums">{data.taux_retour_pct} %</div>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <Breakdown titre="Par jour" rows={data.par_jour} />
            <Breakdown titre="Par caissier" rows={data.par_caissier} />
            <Breakdown titre="Par mode de paiement" rows={data.par_mode_paiement} />
            <Breakdown titre="Par catégorie" rows={data.par_categorie} />
            <Breakdown titre="Par produit" rows={data.par_produit} valeur={(v) => v.total} />
          </div>
        </>
      )}
    </div>
  )
}
