import { useCallback, useEffect, useState } from 'react'
import { Users, Trash2 } from 'lucide-react'
import esgApi from '../../api/esgApi'
import {
  Card, CardHeader, CardTitle, CardContent, Button, Input, EmptyState, Skeleton,
} from '../../ui'
import { StateBlock } from '../../components/StateBlock'

/* ============================================================================
   NTESG12 — Registre des parties prenantes ESG / matrice de matérialité.
   ----------------------------------------------------------------------------
   Distinct du `PartieInteressee` QHSE (SMQ/ISO) : ce registre est
   spécifiquement la matérialité RSE/extra-financière (CSRD-like, appels
   d'offres). CRUD simple + matrice 2x2 (influence × intérêt) en SVG — chaque
   partie prenante placée selon ses scores 1-5.
   ========================================================================== */

const CATEGORIES = [
  ['client', 'Client'],
  ['fournisseur', 'Fournisseur'],
  ['collaborateur', 'Collaborateur'],
  ['collectivite', 'Collectivité'],
  ['actionnaire', 'Actionnaire'],
]

const CATEGORY_COLOR = {
  client: 'var(--chart-1, #3b82f6)',
  fournisseur: 'var(--chart-2, #f59e0b)',
  collaborateur: 'var(--chart-3, #10b981)',
  collectivite: 'var(--chart-4, #8b5cf6)',
  actionnaire: 'var(--chart-5, #ef4444)',
}

const EMPTY_FORM = {
  nom: '', categorie: 'client', enjeux: '', influence: 3, interet: 3,
}

function MatriceSvg({ parties }) {
  const size = 360
  const pad = 32
  const usable = size - pad * 2
  const scale = (n) => pad + ((n - 1) / 4) * usable

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-md" role="img"
      aria-label="Matrice de matérialité influence × intérêt">
      <rect x={pad} y={pad} width={usable} height={usable}
        fill="none" stroke="var(--border)" strokeWidth="1" />
      <line x1={pad} y1={size / 2} x2={size - pad} y2={size / 2}
        stroke="var(--border)" strokeDasharray="4 4" />
      <line x1={size / 2} y1={pad} x2={size / 2} y2={size - pad}
        stroke="var(--border)" strokeDasharray="4 4" />
      <text x={size / 2} y={size - 8} textAnchor="middle"
        className="fill-muted-foreground text-[10px]">Intérêt →</text>
      <text x={10} y={size / 2} textAnchor="middle"
        className="fill-muted-foreground text-[10px]"
        transform={`rotate(-90 10 ${size / 2})`}>Influence →</text>
      {parties.map((p) => (
        <circle
          key={p.id}
          cx={scale(p.interet)}
          cy={size - scale(p.influence)}
          r={7}
          fill={CATEGORY_COLOR[p.categorie] || 'var(--muted-foreground)'}
          stroke="var(--card)"
          strokeWidth="1.5"
        >
          <title>{`${p.nom} — influence ${p.influence}, intérêt ${p.interet}`}</title>
        </circle>
      ))}
    </svg>
  )
}

export default function MatriceMaterialite() {
  const [parties, setParties] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState(null)

  const fetchParties = useCallback(() => (
    esgApi.partiesPrenantes.list()
      .then((res) => {
        setParties(res.data?.results ?? res.data ?? [])
        setLoadError(false)
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  ), [])

  const load = useCallback(() => {
    setLoading(true)
    return fetchParties()
  }, [fetchParties])

  useEffect(() => { fetchParties() }, [fetchParties])

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setFormError(null)
    try {
      await esgApi.partiesPrenantes.create({
        ...form,
        influence: Number(form.influence),
        interet: Number(form.interet),
      })
      setForm(EMPTY_FORM)
      await load()
    } catch (err) {
      setFormError(
        err?.response?.data?.nom?.[0]
        || err?.response?.data?.influence?.[0]
        || err?.response?.data?.interet?.[0]
        || "Impossible d'enregistrer cette partie prenante.")
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('Retirer cette partie prenante du registre ?')) return
    try {
      await esgApi.partiesPrenantes.remove(id)
      await load()
    } catch { /* best-effort */ }
  }

  if (loading) {
    return (
      <div className="ui-root page">
        <div className="page-header" style={{ marginBottom: '1.25rem' }}>
          <h2>Matrice de matérialité ESG</h2>
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="ui-root page">
        <Card>
          <CardContent className="py-6">
            <StateBlock error="Le registre des parties prenantes n'a pas pu être chargé." onRetry={load} />
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Matrice de matérialité ESG</h2>
        <p className="text-sm text-muted-foreground">
          Registre des parties prenantes RSE (distinct des parties intéressées
          QHSE/ISO) — matrice influence × intérêt.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Matrice influence × intérêt</CardTitle>
          </CardHeader>
          <CardContent className="flex justify-center">
            {parties.length === 0 ? (
              <EmptyState
                icon={Users}
                title="Aucune partie prenante"
                description="Ajoutez une partie prenante pour la voir apparaître sur la matrice."
              />
            ) : (
              <MatriceSvg parties={parties} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Ajouter une partie prenante</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submit} className="flex flex-col gap-3">
              <div>
                <label className="text-sm font-medium" htmlFor="pp-nom">Nom</label>
                <Input
                  id="pp-nom" required value={form.nom}
                  onChange={(e) => setForm((f) => ({ ...f, nom: e.target.value }))}
                />
              </div>
              <div>
                <label className="text-sm font-medium" htmlFor="pp-categorie">Catégorie</label>
                <select
                  id="pp-categorie"
                  className="flex h-[var(--control-h)] w-full rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
                  value={form.categorie}
                  onChange={(e) => setForm((f) => ({ ...f, categorie: e.target.value }))}
                >
                  {CATEGORIES.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium" htmlFor="pp-enjeux">Enjeux prioritaires</label>
                <Input
                  id="pp-enjeux" value={form.enjeux}
                  onChange={(e) => setForm((f) => ({ ...f, enjeux: e.target.value }))}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium" htmlFor="pp-influence">Influence (1-5)</label>
                  <Input
                    id="pp-influence" type="number" min={1} max={5} required
                    value={form.influence}
                    onChange={(e) => setForm((f) => ({ ...f, influence: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium" htmlFor="pp-interet">Intérêt (1-5)</label>
                  <Input
                    id="pp-interet" type="number" min={1} max={5} required
                    value={form.interet}
                    onChange={(e) => setForm((f) => ({ ...f, interet: e.target.value }))}
                  />
                </div>
              </div>
              {formError && <p className="text-sm text-destructive">{formError}</p>}
              <Button type="submit" disabled={saving}>Ajouter</Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Registre</CardTitle>
        </CardHeader>
        <CardContent className="p-0 sm:p-0">
          {parties.length === 0 ? (
            <EmptyState
              icon={Users}
              title="Registre vide"
              description="Aucune partie prenante enregistrée pour cette société."
              className="border-0 py-6"
            />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-3 py-2">Nom</th>
                  <th className="px-3 py-2">Catégorie</th>
                  <th className="px-3 py-2">Influence</th>
                  <th className="px-3 py-2">Intérêt</th>
                  <th className="px-3 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {parties.map((p) => (
                  <tr key={p.id} className="border-b border-border/60">
                    <td className="px-3 py-2">{p.nom}</td>
                    <td className="px-3 py-2">{p.categorie_display || p.categorie}</td>
                    <td className="px-3 py-2">{p.influence}</td>
                    <td className="px-3 py-2">{p.interet}</td>
                    <td className="px-3 py-2 text-right">
                      <Button variant="outline" size="sm" onClick={() => remove(p.id)}>
                        <Trash2 />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
