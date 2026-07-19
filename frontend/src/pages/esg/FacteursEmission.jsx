import { useCallback, useEffect, useState } from 'react'
import { Gauge, History, Plus } from 'lucide-react'
import esgApi from '../../api/esgApi'
import {
  Card, CardHeader, CardTitle, CardContent, Badge, Button, Input, Label,
  EmptyState, Skeleton,
} from '../../ui'

/* ============================================================================
   WIR130 — Bibliothèque de facteurs d'émission versionnée (NTESG16).
   Liste (versions actives) + création (qui crée TOUJOURS une nouvelle version
   côté serveur, jamais un écrasement) + historique complet par (catégorie,
   unité). L'app n'expose que le registre : la consommation par qhse est un
   futur lane.
   ========================================================================== */

const EMPTY_FORM = { categorie: '', unite: '', valeur: '', source: '', date_maj: '' }

export default function FacteursEmission() {
  const [facteurs, setFacteurs] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [historique, setHistorique] = useState(null)
  const [historiqueKey, setHistoriqueKey] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    esgApi.facteurs.list()
      .then((res) => {
        setFacteurs(res.data?.results ?? res.data ?? [])
        setLoadError(false)
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const creer = async () => {
    setError('')
    if (!form.categorie.trim() || !form.unite.trim() || form.valeur === '' || !form.date_maj) {
      setError('Catégorie, unité, valeur et date de mise à jour sont requis.')
      return
    }
    setSaving(true)
    try {
      await esgApi.facteurs.create({
        categorie: form.categorie.trim(),
        unite: form.unite.trim(),
        valeur: form.valeur,
        source: form.source.trim(),
        date_maj: form.date_maj,
      })
      setForm(EMPTY_FORM)
      load()
    } catch (err) {
      setError(err?.response?.data?.detail || 'La création a échoué.')
    } finally {
      setSaving(false)
    }
  }

  const voirHistorique = async (f) => {
    setHistoriqueKey(`${f.categorie} · ${f.unite}`)
    setHistorique(null)
    try {
      const res = await esgApi.facteurs.historique(f.categorie, f.unite)
      setHistorique(res.data ?? [])
    } catch {
      setHistorique([])
    }
  }

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Facteurs d'émission</h2>
        <p className="text-sm text-muted-foreground">
          Bibliothèque versionnée (NTESG16) — chaque mise à jour crée une nouvelle
          version et archive l'ancienne, jamais un écrasement.
        </p>
      </div>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus size={18} strokeWidth={1.75} aria-hidden="true" />
            Nouveau facteur / nouvelle version
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label htmlFor="fac-categorie">Catégorie</Label>
              <Input
                id="fac-categorie" value={form.categorie}
                placeholder="ex : Électricité réseau"
                onChange={(e) => setForm((f) => ({ ...f, categorie: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="fac-unite">Unité</Label>
              <Input
                id="fac-unite" value={form.unite} placeholder="ex : kWh"
                onChange={(e) => setForm((f) => ({ ...f, unite: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="fac-valeur">Valeur (kgCO2e)</Label>
              <Input
                id="fac-valeur" type="number" step="any" value={form.valeur}
                onChange={(e) => setForm((f) => ({ ...f, valeur: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="fac-source">Source</Label>
              <Input
                id="fac-source" value={form.source} placeholder="ex : ADEME Base Carbone"
                onChange={(e) => setForm((f) => ({ ...f, source: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="fac-date">Date de mise à jour</Label>
              <Input
                id="fac-date" type="datetime-local" value={form.date_maj}
                onChange={(e) => setForm((f) => ({ ...f, date_maj: e.target.value }))}
              />
            </div>
            <Button size="sm" disabled={saving} onClick={creer}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
          {error && <p className="form-error mt-2" role="alert">{error}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Facteurs actifs</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-24 w-full" />
          ) : loadError ? (
            <p className="form-error" role="alert">
              Impossible de charger les facteurs d'émission.
            </p>
          ) : facteurs.length === 0 ? (
            <EmptyState
              icon={Gauge}
              title="Aucun facteur d'émission"
              description="Créez un premier facteur pour alimenter la bibliothèque."
              className="border-0 py-4"
            />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-2 py-1">Catégorie</th>
                  <th className="px-2 py-1">Unité</th>
                  <th className="px-2 py-1 text-right">Valeur</th>
                  <th className="px-2 py-1">Source</th>
                  <th className="px-2 py-1">Version</th>
                  <th className="px-2 py-1 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {facteurs.map((f) => (
                  <tr key={f.id} className="border-b border-border/60">
                    <td className="px-2 py-1">{f.categorie}</td>
                    <td className="px-2 py-1">{f.unite}</td>
                    <td className="px-2 py-1 text-right">{f.valeur}</td>
                    <td className="px-2 py-1">{f.source || '—'}</td>
                    <td className="px-2 py-1">
                      <Badge tone={f.actif ? 'success' : 'neutral'}>v{f.version}</Badge>
                    </td>
                    <td className="px-2 py-1 text-right">
                      <Button size="sm" variant="outline" onClick={() => voirHistorique(f)}>
                        <History size={14} /> Historique
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {historiqueKey && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Historique — {historiqueKey}</span>
              <Button size="sm" variant="ghost" onClick={() => { setHistoriqueKey(null); setHistorique(null) }}>
                Fermer
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {historique === null ? (
              <Skeleton className="h-16 w-full" />
            ) : historique.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune version.</p>
            ) : (
              <ul className="space-y-1">
                {historique.map((v) => (
                  <li key={v.id} className="flex items-center gap-2 border-b py-1 text-sm">
                    <Badge tone={v.actif ? 'success' : 'neutral'}>v{v.version}</Badge>
                    <span>{v.valeur}</span>
                    <span className="text-muted-foreground">{v.source || '—'}</span>
                    <span className="ml-auto text-muted-foreground">{v.date_maj}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
