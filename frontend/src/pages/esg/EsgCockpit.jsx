import { useCallback, useEffect, useState } from 'react'
import { Leaf, Users, Landmark, FileText, FileSpreadsheet, Lock } from 'lucide-react'
import esgApi from '../../api/esgApi'
import {
  Card, CardHeader, CardTitle, CardContent, Badge, Button, Progress,
  EmptyState, Skeleton,
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
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    return Promise.allSettled([
      esgApi.catalogue.couverture(),
      esgApi.periodes.list(),
    ]).then(([couvRes, periodesRes]) => {
      setCouverture(couvRes.status === 'fulfilled' ? couvRes.value.data : null)
      const rows = periodesRes.status === 'fulfilled'
        ? (periodesRes.value.data?.results ?? periodesRes.value.data ?? [])
        : []
      setPeriodes(rows)
      setLoadError(couvRes.status === 'rejected' && periodesRes.status === 'rejected')
    }).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

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
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>ESG / RSE</h2>
        <p className="text-sm text-muted-foreground">
          Reporting ESG/durabilité consolidé — agrégation en lecture seule des
          indicateurs QHSE/RH/flotte, jamais de chiffre inventé.
        </p>
      </div>

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
                      </div>
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
