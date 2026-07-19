import { useCallback, useEffect, useState } from 'react'
import {
  Leaf, Users, Landmark, FileText, FileSpreadsheet, Lock, Award, Plus,
  GitCompare, FileDown,
} from 'lucide-react'
import esgApi from '../../api/esgApi'
import {
  Card, CardHeader, CardTitle, CardContent, Badge, Button, Progress,
  EmptyState, Skeleton, Dialog, DialogContent, DialogFooter, DialogHeader,
  DialogTitle, Input, Label,
} from '../../ui'
import { downloadXlsx } from '../../api/importApi'
import { downloadBlob } from '../../utils/downloadBlob'
import { StateBlock } from '../../components/StateBlock'

/* ============================================================================
   NTESG6 — Cockpit ESG consolidé.
   ----------------------------------------------------------------------------
   Trois blocs :
   • Cartes par pilier E/S/G : couverture du catalogue GRI-lite (NTESG3),
     jamais de graphique à zéro — un pilier sans indicateur affiche un état
     vide explicite plutôt qu'une valeur inventée (checked-facts-only).
   • Liste des périodes de reporting (NTESG1) : statut, bouton « Figer la
     période » (irréversible) et « Télécharger » (PDF/xlsx, NTESG4/5).
   Lecture seule côté cockpit : la création d'une période se fait via l'API
   (wizard de clôture guidé = NTESG18, hors périmètre de ce lane).
   ========================================================================== */

const PILIER_META = {
  environnement: { label: 'Environnement', icon: Leaf, tone: 'success' },
  social: { label: 'Social', icon: Users, tone: 'info' },
  gouvernance: { label: 'Gouvernance', icon: Landmark, tone: 'warning' },
}

const STATUT_LABELS = {
  brouillon: 'Brouillon',
  figee: 'Figée',
  publiee: 'Publiée',
}

const STATUT_TONE = {
  brouillon: 'neutral',
  figee: 'warning',
  publiee: 'success',
}

export default function EsgCockpit() {
  const [couverture, setCouverture] = useState(null)
  const [periodes, setPeriodes] = useState([])
  const [badge, setBadge] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busyId, setBusyId] = useState(null)
  // WIR129 — création de période.
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState({ libelle: '', date_debut: '', date_fin: '' })
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  // WIR129 — comparateur N / N-1.
  const [comparePeriode, setComparePeriode] = useState('')
  const [compareReference, setCompareReference] = useState('')
  const [compareResult, setCompareResult] = useState(null)
  const [comparing, setComparing] = useState(false)
  const [compareError, setCompareError] = useState('')

  // Fetch seule (aucun setState synchrone) : c'est ce que l'effet de montage
  // appelle — un effet ne doit synchroniser que via des callbacks async
  // (react-hooks/set-state-in-effect). `load` ci-dessous ajoute le flag
  // `loading` synchrone pour les rechargements déclenchés par un événement
  // (retry, figer-période) où setState synchrone est parfaitement légitime.
  const fetchCockpit = useCallback(() => Promise.allSettled([
    esgApi.catalogue.couverture(),
    esgApi.periodes.list(),
    esgApi.catalogue.badgeMaturite(),
  ]).then(([couvRes, periodesRes, badgeRes]) => {
    setCouverture(couvRes.status === 'fulfilled' ? couvRes.value.data : null)
    const rows = periodesRes.status === 'fulfilled'
      ? (periodesRes.value.data?.results ?? periodesRes.value.data ?? [])
      : []
    setPeriodes(rows)
    setBadge(badgeRes.status === 'fulfilled' ? badgeRes.value.data : null)
    setLoadError(couvRes.status === 'rejected' && periodesRes.status === 'rejected')
  }).finally(() => setLoading(false)), [])

  const load = useCallback(() => {
    setLoading(true)
    return fetchCockpit()
  }, [fetchCockpit])

  useEffect(() => { fetchCockpit() }, [fetchCockpit])

  const figerPeriode = async (id) => {
    if (!window.confirm('Figer cette période ? Les chiffres seront gelés définitivement.')) return
    setBusyId(id)
    try {
      await esgApi.periodes.figer(id)
      await load()
    } catch {
      window.alert('Le figeage a échoué (période déjà figée ou erreur serveur).')
    } finally {
      setBusyId(null)
    }
  }

  const telechargerPdf = async (periode) => {
    setBusyId(periode.id)
    try {
      const res = await esgApi.periodes.rapportPdf(periode.id)
      downloadBlob(res.data, `rapport-esg-${periode.id}.pdf`)
    } catch {
      window.alert('Le rapport PDF est indisponible.')
    } finally {
      setBusyId(null)
    }
  }

  const telechargerXlsx = async (periode) => {
    setBusyId(periode.id)
    try {
      const res = await esgApi.periodes.exportXlsx(periode.id)
      downloadXlsx(res.data, `esg-${periode.id}.xlsx`)
    } catch {
      window.alert("L'export xlsx est indisponible.")
    } finally {
      setBusyId(null)
    }
  }

  const telechargerDpef = async (periode) => {
    setBusyId(periode.id)
    try {
      const res = await esgApi.periodes.dpef(periode.id)
      downloadBlob(res.data, `dpef-${periode.id}.md`)
    } catch {
      window.alert("L'export DPEF est indisponible.")
    } finally {
      setBusyId(null)
    }
  }

  const creerPeriode = async () => {
    setCreateError('')
    if (!createForm.libelle.trim() || !createForm.date_debut || !createForm.date_fin) {
      setCreateError('Libellé, date de début et date de fin sont requis.')
      return
    }
    setCreating(true)
    try {
      await esgApi.periodes.create({
        libelle: createForm.libelle.trim(),
        date_debut: createForm.date_debut,
        date_fin: createForm.date_fin,
      })
      setCreateOpen(false)
      setCreateForm({ libelle: '', date_debut: '', date_fin: '' })
      await load()
    } catch (err) {
      const data = err?.response?.data
      const msg = data?.libelle?.[0] || data?.date_fin?.[0] || data?.detail
        || 'La création a échoué.'
      setCreateError(msg)
    } finally {
      setCreating(false)
    }
  }

  const comparer = async () => {
    setCompareError('')
    setCompareResult(null)
    if (!comparePeriode || !compareReference) {
      setCompareError('Sélectionnez une période et sa référence (N-1).')
      return
    }
    if (comparePeriode === compareReference) {
      setCompareError('La période et sa référence doivent être différentes.')
      return
    }
    setComparing(true)
    try {
      const res = await esgApi.periodes.comparer(comparePeriode, compareReference)
      setCompareResult(res.data)
    } catch {
      setCompareError('La comparaison a échoué (serveur indisponible ?).')
    } finally {
      setComparing(false)
    }
  }

  if (loading) {
    return (
      <div className="ui-root page">
        <div className="page-header" style={{ marginBottom: '1.25rem' }}>
          <h2>ESG / RSE</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((unused, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="ui-root page">
        <Card>
          <CardContent className="py-6">
            <StateBlock error="Le cockpit ESG n'a pas pu être chargé (serveur indisponible ?)." onRetry={load} />
          </CardContent>
        </Card>
      </div>
    )
  }

  const piliers = couverture?.piliers ?? {}
  const hasCatalogue = Object.values(piliers).some((p) => p.total > 0)

  return (
    <div className="ui-root page">
      <div className="page-header flex items-start justify-between" style={{ marginBottom: '1.25rem' }}>
        <div>
          <h2>ESG / RSE</h2>
          <p className="text-sm text-muted-foreground">
            Reporting ESG/durabilité consolidé — agrégation en lecture seule des
            indicateurs QHSE/RH/flotte, jamais de chiffre inventé.
          </p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus size={16} /> Nouvelle période
        </Button>
      </div>

      {badge && (
        <Card className="mb-4">
          <CardContent className="flex items-center gap-3 py-4">
            <Award size={22} strokeWidth={1.75} aria-hidden="true" />
            <div>
              <p className="text-2xl font-bold">{badge.score} / 100</p>
              <p className="text-xs text-muted-foreground">{badge.disclaimer}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {!hasCatalogue ? (
        <EmptyState
          icon={Leaf}
          title="Catalogue GRI-lite non seedé"
          description="Aucun indicateur de référence n'est encore rattaché à cette société (python manage.py seed_catalogue_esg)."
          className="mb-4"
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-3 mb-4">
          {Object.entries(PILIER_META).map(([key, meta]) => {
            const bloc = piliers[key]
            const Icon = meta.icon
            return (
              <Card key={key}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Icon size={18} strokeWidth={1.75} aria-hidden="true" />
                    {meta.label}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {!bloc || bloc.total === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Aucun indicateur renseigné pour cette période.
                    </p>
                  ) : (
                    <>
                      <p className="text-2xl font-bold">
                        {bloc.couverts} / {bloc.total}
                      </p>
                      <p className="text-sm text-muted-foreground mb-2">
                        indicateurs renseignés ({bloc.pct} %)
                      </p>
                      <Progress value={bloc.pct} tone={meta.tone} />
                    </>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Périodes de reporting</CardTitle>
        </CardHeader>
        <CardContent className="p-0 sm:p-0">
          {periodes.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="Aucune période de reporting"
              description="Créez une période de reporting ESG pour commencer (API periodes-esg/)."
              className="border-0 py-6"
            />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-3 py-2">Libellé</th>
                  <th className="px-3 py-2">Période</th>
                  <th className="px-3 py-2">Statut</th>
                  <th className="px-3 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {periodes.map((p) => (
                  <tr key={p.id} className="border-b border-border/60">
                    <td className="px-3 py-2">{p.libelle}</td>
                    <td className="px-3 py-2">{p.date_debut} → {p.date_fin}</td>
                    <td className="px-3 py-2">
                      <Badge tone={STATUT_TONE[p.statut] ?? 'neutral'}>
                        {STATUT_LABELS[p.statut] ?? p.statut}
                      </Badge>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex justify-end gap-2">
                        {p.statut === 'brouillon' && (
                          <Button
                            variant="outline" size="sm"
                            disabled={busyId === p.id}
                            onClick={() => figerPeriode(p.id)}
                          >
                            <Lock /> Figer la période
                          </Button>
                        )}
                        <Button
                          variant="outline" size="sm"
                          disabled={busyId === p.id}
                          onClick={() => telechargerPdf(p)}
                        >
                          <FileText /> PDF
                        </Button>
                        <Button
                          variant="outline" size="sm"
                          disabled={busyId === p.id}
                          onClick={() => telechargerXlsx(p)}
                        >
                          <FileSpreadsheet /> xlsx
                        </Button>
                        <Button
                          variant="outline" size="sm"
                          disabled={busyId === p.id}
                          onClick={() => telechargerDpef(p)}
                        >
                          <FileDown /> DPEF
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* WIR129 — Comparateur N vs N-1 (NTESG11). */}
      {periodes.length >= 2 && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitCompare size={18} strokeWidth={1.75} aria-hidden="true" />
              Comparer deux périodes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <Label htmlFor="cmp-periode">Période (N)</Label>
                <select
                  id="cmp-periode" className="form-select"
                  value={comparePeriode}
                  onChange={(e) => setComparePeriode(e.target.value)}
                >
                  <option value="">—</option>
                  {periodes.map((p) => (
                    <option key={p.id} value={p.id}>{p.libelle}</option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="cmp-reference">Référence (N-1)</Label>
                <select
                  id="cmp-reference" className="form-select"
                  value={compareReference}
                  onChange={(e) => setCompareReference(e.target.value)}
                >
                  <option value="">—</option>
                  {periodes.map((p) => (
                    <option key={p.id} value={p.id}>{p.libelle}</option>
                  ))}
                </select>
              </div>
              <Button size="sm" disabled={comparing} onClick={comparer}>
                Comparer
              </Button>
            </div>
            {compareError && (
              <p className="form-error mt-2" role="alert">{compareError}</p>
            )}
            {compareResult && (
              <div className="mt-4 space-y-4">
                {Object.entries(compareResult.piliers ?? {}).length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Aucun indicateur comparable entre ces deux périodes.
                  </p>
                ) : (
                  Object.entries(compareResult.piliers).map(([pilier, lignes]) => (
                    <div key={pilier}>
                      <h4 className="mb-1 font-medium">
                        {PILIER_META[pilier]?.label ?? pilier}
                      </h4>
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-border text-left">
                            <th className="px-2 py-1">Indicateur</th>
                            <th className="px-2 py-1 text-right">N-1</th>
                            <th className="px-2 py-1 text-right">N</th>
                            <th className="px-2 py-1 text-right">Écart</th>
                          </tr>
                        </thead>
                        <tbody>
                          {lignes.map((l) => (
                            <tr key={l.code} className="border-b border-border/60">
                              <td className="px-2 py-1">{l.libelle || l.code}</td>
                              {l.comparable ? (
                                <>
                                  <td className="px-2 py-1 text-right">{l.valeur_reference}</td>
                                  <td className="px-2 py-1 text-right">{l.valeur_n}</td>
                                  <td className="px-2 py-1 text-right">
                                    {l.variation_abs > 0 ? '+' : ''}{l.variation_abs}
                                    {l.variation_pct != null && (
                                      <span className="text-muted-foreground">
                                        {' '}({l.variation_pct > 0 ? '+' : ''}{l.variation_pct} %)
                                      </span>
                                    )}
                                  </td>
                                </>
                              ) : (
                                <td className="px-2 py-1 text-muted-foreground" colSpan={3}>
                                  {l.raison || 'Non comparable'}
                                </td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* WIR129 — Dialogue de création de période. */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouvelle période de reporting</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="periode-libelle">Libellé</Label>
              <Input
                id="periode-libelle" value={createForm.libelle}
                placeholder="ex : Exercice 2026"
                onChange={(e) => setCreateForm((f) => ({ ...f, libelle: e.target.value }))}
              />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <Label htmlFor="periode-debut">Date de début</Label>
                <Input
                  id="periode-debut" type="date" value={createForm.date_debut}
                  onChange={(e) => setCreateForm((f) => ({ ...f, date_debut: e.target.value }))}
                />
              </div>
              <div className="flex-1">
                <Label htmlFor="periode-fin">Date de fin</Label>
                <Input
                  id="periode-fin" type="date" value={createForm.date_fin}
                  onChange={(e) => setCreateForm((f) => ({ ...f, date_fin: e.target.value }))}
                />
              </div>
            </div>
            {createError && (
              <p className="form-error" role="alert">{createError}</p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Annuler</Button>
            <Button disabled={creating} onClick={creerPeriode}>
              {creating ? 'Création…' : 'Créer'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
