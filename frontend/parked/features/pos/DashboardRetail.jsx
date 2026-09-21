import { useEffect, useState } from 'react'
import posApi from '../../api/posApi'
import api from '../../api/axios'
import { Button, Input, Label, EmptyState, toast } from '../../ui'
import { formatMAD } from '../../lib/format'

/* NTRET16 — Tableau de bord retail (route /pos/dashboard-retail).
   5 KPI : panier moyen, taux de transformation, ventes/m², top
   produits/catégories/vendeurs, comparatif boutique vs boutique. */
const fmt = (v) => formatMAD(v, { withSymbol: false })

function Classement({ titre, lignes }) {
  if (!lignes || lignes.length === 0) return null
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <h3 className="mb-2 text-sm font-medium">{titre}</h3>
      <ul className="flex flex-col gap-1 text-sm">
        {lignes.map((l) => (
          <li key={l.nom} className="flex justify-between gap-3">
            <span className="truncate text-muted-foreground">{l.nom || '—'}</span>
            <span className="tabular-nums">{fmt(l.total)} DH</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Comparatif({ rows }) {
  const entries = Object.entries(rows || {})
  if (entries.length === 0) return null
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <h3 className="mb-2 text-sm font-medium">Comparatif boutiques</h3>
      <ul className="flex flex-col gap-1 text-sm">
        {entries.map(([boutique, total]) => (
          <li key={boutique} className="flex justify-between gap-3">
            <span className="truncate text-muted-foreground">{boutique}</span>
            <span className="tabular-nums">{fmt(total)} DH</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function DashboardRetail() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [boutique, setBoutique] = useState('')

  const load = () => {
    const params = {}
    if (dateDebut) params.date_debut = dateDebut
    if (dateFin) params.date_fin = dateFin
    if (boutique) params.boutique = boutique
    return posApi.getDashboardRetail(params)
      .then((r) => setData(r.data))
      .catch(() => { setData(null); toast.error('Le tableau de bord retail est indisponible.') })
      .finally(() => setLoading(false))
  }
  const charger = () => { setLoading(true); return load() }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleExport = () => {
    const base = api.defaults.baseURL || ''
    window.open(`${base}/api/django${posApi.exportDashboardRetailUrl()}`, '_blank')
  }

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-display text-xl font-semibold">Tableau de bord retail</h1>
        <Button type="button" variant="outline" onClick={handleExport}>Exporter (xlsx)</Button>
      </div>

      <form
        noValidate
        onSubmit={(e) => { e.preventDefault(); charger() }}
        className="flex flex-wrap items-end gap-2"
      >
        <div className="grid gap-1.5">
          <Label htmlFor="dbr-debut">Du</Label>
          <Input id="dbr-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="dbr-fin">Au</Label>
          <Input id="dbr-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="dbr-boutique">Boutique</Label>
          <Input id="dbr-boutique" placeholder="Toutes" value={boutique}
                 onChange={(e) => setBoutique(e.target.value)} />
        </div>
        <Button type="submit">Filtrer</Button>
      </form>

      {loading ? (
        <div className="py-8 text-center text-sm text-muted-foreground">Chargement…</div>
      ) : !data ? (
        <EmptyState title="Aucune donnée" description="Aucune vente comptoir sur la période." />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="dashboard-retail-kpis">
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="text-xs text-muted-foreground">Panier moyen</div>
              <div className="text-lg font-semibold tabular-nums">{fmt(data.panier_moyen)} DH</div>
            </div>
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="text-xs text-muted-foreground">Taux de transformation</div>
              <div className="text-lg font-semibold tabular-nums">{data.taux_transformation_pct} %</div>
            </div>
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="text-xs text-muted-foreground">Ventes / m²</div>
              <div className="text-lg font-semibold tabular-nums">
                {data.ventes_par_m2 != null ? `${fmt(data.ventes_par_m2)} DH` : '—'}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-card p-3">
              <div className="text-xs text-muted-foreground">Total TTC</div>
              <div className="text-lg font-semibold tabular-nums">{fmt(data.total_ttc)} DH</div>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <Classement titre="Top produits" lignes={data.top_produits} />
            <Classement titre="Top catégories" lignes={data.top_categories} />
            <Classement titre="Top vendeurs" lignes={data.top_vendeurs} />
            <Comparatif rows={data.comparatif_boutiques} />
          </div>
        </>
      )}
    </div>
  )
}
