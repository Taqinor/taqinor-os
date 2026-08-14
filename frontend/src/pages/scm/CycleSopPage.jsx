import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, RefreshCw, AlertTriangle } from 'lucide-react'
import scmApi from '../../api/scmApi'
import { formatMAD } from '../../lib/format'
import {
  Button, Badge, DataTable, EmptyState, Skeleton, Tabs, TabsList, TabsTrigger,
  TabsContent,
} from '../../ui'
import { StateBlock } from '../../components/StateBlock'
import ChatterTimeline from '../../components/ChatterTimeline'

/* ============================================================================
   NTSCM12-15 — Écran « Cycle S&OP » (Demande / Offre / Finance), 3 vues
   synchronisées sur le MÊME cycle (un seul chargement, un seul id dans
   l'URL). Réservé Administrateur/Directeur (roles du module.config.jsx) —
   donnée de marge/CA sensible (onglet Finance).
   ========================================================================== */

const STATUT_META = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  revue_demande: { label: 'Revue de la demande', tone: 'info' },
  revue_offre: { label: "Revue de l'offre", tone: 'info' },
  revue_finance: { label: 'Revue financière', tone: 'info' },
  reunion_reconciliation: { label: 'Réunion de réconciliation', tone: 'warning' },
  approuve: { label: 'Approuvé', tone: 'success' },
  clos: { label: 'Clos', tone: 'success' },
}

export default function CycleSopPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [cycle, setCycle] = useState(null)
  const [lignesDemande, setLignesDemande] = useState([])
  const [lignesOffre, setLignesOffre] = useState([])
  const [finance, setFinance] = useState(null)
  // NTSCM44 — fil d'activité (chatter générique) du cycle.
  const [historique, setHistorique] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [avancerBusy, setAvancerBusy] = useState(false)
  const [avancerErr, setAvancerErr] = useState(null)

  const charger = useCallback(() => {
    setLoading(true)
    setLoadError(null)
    return scmApi.cycleSop(id)
      .then((r) => {
        setCycle(r.data)
        return Promise.allSettled([
          scmApi.lignesDemandeCycleSop(id),
          scmApi.ecartsCycleSop(id),
          scmApi.impactFinancierCycleSop(id),
          scmApi.historiqueCycleSop(id),
        ])
      })
      .then(([demandeRes, offreRes, financeRes, historiqueRes]) => {
        setLignesDemande(demandeRes.status === 'fulfilled' ? (demandeRes.value.data ?? []) : [])
        setLignesOffre(offreRes.status === 'fulfilled' ? (offreRes.value.data ?? []) : [])
        setFinance(financeRes.status === 'fulfilled' ? financeRes.value.data : null)
        setHistorique(historiqueRes.status === 'fulfilled' ? (historiqueRes.value.data ?? []) : [])
      })
      .catch((e) => setLoadError(
        e?.response?.status === 404
          ? 'Cycle S&OP introuvable.'
          : (e?.response?.data?.detail ?? "Le cycle n'a pas pu être chargé.")))
      .finally(() => setLoading(false))
  }, [id])

  // Différé d'un microtask : `charger` pose `loading`/l'erreur de façon
  // synchrone (react-hooks/set-state-in-effect). Comportement inchangé.
  useEffect(() => { Promise.resolve().then(charger) }, [charger])

  const avancerStatut = async () => {
    setAvancerBusy(true); setAvancerErr(null)
    try {
      await scmApi.avancerStatutCycleSop(id)
      charger()
    } catch (e) {
      setAvancerErr(e?.response?.data?.statut
        ?? e?.response?.data?.detail
        ?? "L'avancement du cycle a échoué.")
    } finally {
      setAvancerBusy(false)
    }
  }

  const colonnesDemande = useMemo(() => [
    { id: 'produit_nom', header: 'Produit', accessor: (r) => r.produit_nom },
    {
      id: 'quantite_prevision_systeme', header: 'Système (gelé)', align: 'right', width: 130,
      accessor: (r) => Number(r.quantite_prevision_systeme) || 0,
      cell: (v, r) => <span className="tabular-nums">{r.quantite_prevision_systeme}</span>,
    },
    {
      id: 'quantite_ajustee_commercial', header: 'Ajusté (commercial)', align: 'right', width: 150,
      accessor: (r) => Number(r.quantite_ajustee_commercial) || 0,
      cell: (v, r) => (
        <span className="tabular-nums">
          {r.quantite_ajustee_commercial ?? <span className="text-muted-foreground">—</span>}
        </span>
      ),
    },
    {
      id: 'quantite_finale', header: 'Finale', align: 'right', width: 110,
      accessor: (r) => Number(r.quantite_finale) || 0,
      cell: (v, r) => <span className="font-semibold tabular-nums">{r.quantite_finale}</span>,
    },
    { id: 'motif_ajustement', header: "Motif de l'ajustement", accessor: (r) => r.motif_ajustement || '' },
  ], [])

  const colonnesOffre = useMemo(() => [
    { id: 'produit_nom', header: 'Produit', accessor: (r) => r.produit_nom },
    {
      id: 'stock_disponible_snapshot', header: 'Stock disponible', align: 'right', width: 140,
      accessor: (r) => Number(r.stock_disponible_snapshot) || 0,
      cell: (v, r) => <span className="tabular-nums">{r.stock_disponible_snapshot}</span>,
    },
    {
      id: 'capacite_appro_fournisseur_estimee', header: 'En commande fournisseur', align: 'right', width: 170,
      accessor: (r) => Number(r.capacite_appro_fournisseur_estimee) || 0,
      cell: (v, r) => <span className="tabular-nums">{r.capacite_appro_fournisseur_estimee}</span>,
    },
    {
      id: 'quantite_finale_demande', header: 'Demande finale', align: 'right', width: 130,
      accessor: (r) => Number(r.quantite_finale_demande) || 0,
      cell: (v, r) => <span className="tabular-nums">{r.quantite_finale_demande ?? '—'}</span>,
    },
    {
      id: 'ecart_offre_demande', header: 'Écart offre − demande', align: 'right', width: 170,
      accessor: (r) => Number(r.ecart_offre_demande) || 0,
      cell: (v, r) => {
        const ecart = Number(r.ecart_offre_demande) || 0
        return (
          <span className={`font-semibold tabular-nums ${ecart < 0 ? 'text-destructive' : ''}`}>
            {r.ecart_offre_demande}
          </span>
        )
      },
    },
  ], [])

  if (loading) {
    return (
      <div className="ui-root page">
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (loadError || !cycle) {
    return (
      <div className="ui-root page">
        <StateBlock error={loadError ?? 'Cycle introuvable.'} onRetry={charger} />
      </div>
    )
  }

  const statutMeta = STATUT_META[cycle.statut] ?? { label: cycle.statut, tone: 'neutral' }
  const ecartFinance = finance?.ecart_pct != null ? Number(finance.ecart_pct) : null
  const alerteFinance = !!finance?.alerte_ecart

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <Button type="button" variant="ghost" size="sm" onClick={() => navigate('/scm/sop')}>
          <ArrowLeft /> Retour aux cycles
        </Button>
        <h2>Cycle S&amp;OP — {cycle.periode}</h2>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={statutMeta.tone}>{statutMeta.label}</Badge>
          <Button type="button" variant="outline" size="sm" onClick={charger}>
            <RefreshCw /> Actualiser
          </Button>
          {cycle.statut !== 'clos' && (
            <Button type="button" size="sm" loading={avancerBusy} onClick={avancerStatut}>
              <ArrowRight /> Passer à l&apos;étape suivante
            </Button>
          )}
          {avancerErr && <span className="text-sm text-destructive" role="alert">{avancerErr}</span>}
        </div>
      </div>

      <Tabs defaultValue="demande">
        <TabsList>
          <TabsTrigger value="demande">Demande</TabsTrigger>
          <TabsTrigger value="offre">Offre</TabsTrigger>
          <TabsTrigger value="finance">Finance</TabsTrigger>
          <TabsTrigger value="historique">Historique</TabsTrigger>
        </TabsList>

        <TabsContent value="demande">
          {lignesDemande.length === 0 ? (
            <EmptyState
              icon={ArrowRight}
              title="Aucune demande gelée"
              description="La demande se gèle automatiquement au passage brouillon → revue de la demande."
            />
          ) : (
            <DataTable
              data={lignesDemande} columns={colonnesDemande}
              getRowId={(r) => r.id} pageSize={25}
              aria-label="Demande consensuelle du cycle S&OP"
            />
          )}
        </TabsContent>

        <TabsContent value="offre">
          {lignesOffre.length === 0 ? (
            <EmptyState
              icon={ArrowRight}
              title="Aucune ligne d'offre calculée"
              description="Calculez l'offre depuis l'onglet Demande une fois le cycle en revue."
            />
          ) : (
            <DataTable
              data={lignesOffre} columns={colonnesOffre}
              getRowId={(r) => r.id} pageSize={25}
              aria-label="Offre et écarts du cycle S&OP"
            />
          )}
        </TabsContent>

        <TabsContent value="finance">
          {!finance ? (
            <EmptyState
              icon={AlertTriangle}
              title="Impact financier indisponible"
              description="Réservé aux administrateurs, ou aucune donnée de demande gelée pour ce cycle."
            />
          ) : (
            <div className="flex flex-col gap-4">
              {alerteFinance && (
                <div
                  role="alert"
                  className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm font-medium text-destructive"
                >
                  <AlertTriangle size={18} strokeWidth={1.75} aria-hidden="true" />
                  Écart de {finance.ecart_pct}% avec le forecast CA — au-delà du seuil
                  d&apos;alerte de {finance.seuil_alerte_pct}%.
                </div>
              )}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-border bg-muted/20 p-4">
                  <div className="text-xs text-muted-foreground">CA prévisionnel (plan de demande)</div>
                  <div className="mt-1 text-xl font-semibold tabular-nums">
                    {formatMAD(finance.ca_previsionnel_ht)}
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-muted/20 p-4">
                  <div className="text-xs text-muted-foreground">CA forecast (historique)</div>
                  <div className="mt-1 text-xl font-semibold tabular-nums">
                    {finance.ca_forecast_ht != null ? formatMAD(finance.ca_forecast_ht) : '—'}
                  </div>
                </div>
                <div className={`rounded-xl border p-4 ${alerteFinance ? 'border-destructive/40 bg-destructive/10' : 'border-border bg-muted/20'}`}>
                  <div className="text-xs text-muted-foreground">Écart</div>
                  <div className={`mt-1 text-xl font-semibold tabular-nums ${alerteFinance ? 'text-destructive' : ''}`}>
                    {ecartFinance != null ? `${ecartFinance}%` : '—'}
                  </div>
                </div>
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="historique">
          {/* NTSCM44 — fil d'activité : chaque changement de statut du cycle
              génère une entrée automatique horodatée + utilisateur (déjà
              journalisée côté serveur par `services.avancer_statut_cycle`/
              `reouvrir_cycle`, NTSCM12). */}
          <ChatterTimeline
            entries={historique}
            emptyLabel="Aucune activité pour le moment."
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
