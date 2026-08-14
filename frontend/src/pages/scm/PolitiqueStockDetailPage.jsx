import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, FileDown, RefreshCw } from 'lucide-react'
import scmApi from '../../api/scmApi'
import { Button, Badge, Input, Label, Skeleton, Tabs, TabsList, TabsTrigger, TabsContent } from '../../ui'
import { StateBlock } from '../../components/StateBlock'
import ChatterTimeline from '../../components/ChatterTimeline'

/* ============================================================================
   NTSCM44 — Fiche « Politique de stock » : détail (classe ABC, niveau de
   service, ROP, stock min/max, stock de sécurité calculé vs manuel) +
   fil d'activité (chaque révision de `service_level_pct`/
   `stock_securite_manuel`/`stock_min`/`stock_max` génère une entrée
   automatique horodatée + utilisateur, journalisée côté serveur —
   `views.PolitiqueStockViewSet.perform_update`).
   ========================================================================== */

const CHAMPS_EDITABLES = [
  { key: 'service_level_pct', label: 'Niveau de service (%)' },
  { key: 'stock_min', label: 'Stock min' },
  { key: 'stock_max', label: 'Stock max' },
  { key: 'stock_securite_manuel', label: 'Stock de sécurité (override manuel)' },
]

export default function PolitiqueStockDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [politique, setPolitique] = useState(null)
  const [historique, setHistorique] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [form, setForm] = useState({})
  const [saveBusy, setSaveBusy] = useState(false)
  const [saveErr, setSaveErr] = useState(null)

  const charger = useCallback(() => {
    setLoading(true)
    setLoadError(null)
    return Promise.allSettled([
      scmApi.politiqueStock(id),
      scmApi.historiquePolitiqueStock(id),
    ]).then(([polRes, histRes]) => {
      if (polRes.status === 'fulfilled') {
        setPolitique(polRes.value.data)
        setForm(polRes.value.data)
      } else {
        setLoadError(
          polRes.reason?.response?.status === 404
            ? 'Politique de stock introuvable.'
            : "La politique de stock n'a pas pu être chargée.")
      }
      setHistorique(histRes.status === 'fulfilled' ? (histRes.value.data ?? []) : [])
    }).finally(() => setLoading(false))
  }, [id])

  useEffect(() => { Promise.resolve().then(charger) }, [charger])

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const enregistrer = async () => {
    setSaveBusy(true); setSaveErr(null)
    try {
      const body = {}
      CHAMPS_EDITABLES.forEach(({ key }) => { body[key] = form[key] })
      const r = await scmApi.majPolitiqueStock(id, body)
      setPolitique(r.data)
      setForm(r.data)
      charger()
    } catch (e) {
      setSaveErr(e?.response?.data?.detail ?? "L'enregistrement a échoué.")
    } finally {
      setSaveBusy(false)
    }
  }

  const telechargerFiche = async () => {
    const res = await scmApi.fichePdfPolitiqueStock(id)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `politique-stock-${id}.pdf`
    a.click()
    window.URL.revokeObjectURL(url)
  }

  const stockSecuriteEffectif = useMemo(() => {
    if (!politique) return null
    return politique.stock_securite_manuel ?? politique.stock_securite_calcule
  }, [politique])

  if (loading) {
    return (
      <div className="ui-root page">
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (loadError || !politique) {
    return (
      <div className="ui-root page">
        <StateBlock error={loadError ?? 'Politique introuvable.'} onRetry={charger} />
      </div>
    )
  }

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <Button type="button" variant="ghost" size="sm" onClick={() => navigate('/scm/reappro')}>
          <ArrowLeft /> Retour
        </Button>
        <h2>Politique de stock — {politique.produit_nom}</h2>
        <div className="flex flex-wrap items-center gap-2">
          {politique.classe_abc && <Badge tone="neutral">Classe {politique.classe_abc}</Badge>}
          <Button type="button" variant="outline" size="sm" onClick={charger}>
            <RefreshCw /> Actualiser
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={telechargerFiche}>
            <FileDown /> Fiche PDF (interne)
          </Button>
        </div>
      </div>

      <Tabs defaultValue="reglages">
        <TabsList>
          <TabsTrigger value="reglages">Réglages</TabsTrigger>
          <TabsTrigger value="historique">Historique</TabsTrigger>
        </TabsList>

        <TabsContent value="reglages">
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-border bg-muted/20 p-4">
                <div className="text-xs text-muted-foreground">Point de commande (ROP)</div>
                <div className="mt-1 text-xl font-semibold tabular-nums">{politique.point_commande}</div>
              </div>
              <div className="rounded-xl border border-border bg-muted/20 p-4">
                <div className="text-xs text-muted-foreground">Stock de sécurité calculé</div>
                <div className="mt-1 text-xl font-semibold tabular-nums">{politique.stock_securite_calcule}</div>
              </div>
              <div className="rounded-xl border border-border bg-muted/20 p-4">
                <div className="text-xs text-muted-foreground">Stock de sécurité effectif</div>
                <div className="mt-1 text-xl font-semibold tabular-nums">{stockSecuriteEffectif}</div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {CHAMPS_EDITABLES.map(({ key, label }) => (
                <div key={key}>
                  <Label htmlFor={`pol-${key}`}>{label}</Label>
                  <Input
                    id={`pol-${key}`} type="number" step="any" noValidate
                    value={form[key] ?? ''}
                    onChange={(e) => setField(key, e.target.value)}
                  />
                </div>
              ))}
            </div>
            {saveErr && <span className="text-sm text-destructive" role="alert">{saveErr}</span>}
            <div>
              <Button type="button" loading={saveBusy} onClick={enregistrer}>
                Enregistrer
              </Button>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="historique">
          {/* NTSCM44 — révision de service_level_pct/stock_securite_manuel/
              stock_min/stock_max : chaque changement RÉEL génère une entrée
              automatique (ancienne/nouvelle valeur, horodatée + utilisateur),
              journalisée côté serveur (`perform_update`). */}
          <ChatterTimeline
            entries={historique}
            emptyLabel="Aucune révision pour le moment."
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
