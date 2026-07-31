import { useEffect, useMemo, useState } from 'react'
import { Banknote, Clock, Percent, TrendingUp } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { formatMAD } from '../../lib/format'
import { Card, CardContent, EmptyState, Skeleton } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { Table } from './Table'

/* ============================================================================
   WIR84 — Écran consommateur des trois agrégateurs Quote-to-Cash de `ventes`.
   ----------------------------------------------------------------------------
   Décision : on CÂBLE (on ne replie pas dans `/reporting/`). Les trois
   endpoints étaient complets et testés côté serveur mais n'avaient AUCUN
   appelant — les dashboards existants consomment `/reporting/dashboard/`, qui
   n'expose ni le DSO, ni le cycle quote-to-cash, ni les buckets d'encaissement,
   ni l'analyse de facturation par mois × client × statut. Les replier aurait
   dupliqué cette logique dans `reporting` pour un gain nul.

   Sources (lecture seule, scopées société côté serveur) :
     - GET /ventes/dashboard/                  (FG45) — conversion, DSO, cycle
     - GET /ventes/insights/cash-flow/         (FG47) — buckets d'encaissement
     - GET /ventes/etats/analyse-facturation/  (ZFAC10) — mois × client × statut

   Aucun coût d'achat (`prix_achat`) n'est exposé ici : les trois agrégateurs
   ne renvoient que des montants de vente (HT/TVA/TTC) et des compteurs.
   ========================================================================== */

const mad = (v) => formatMAD(v, { decimals: 0 })
const pct = (v) => (v == null ? '—' : `${v} %`)
const jours = (v) => (v == null ? '—' : `${v} j`)

// Libellés d'affichage des buckets de cash-flow (clés serveur → français).
const BUCKET_LABELS = [
  ['en_retard', 'En retard'],
  ['cette_semaine', 'Cette semaine'],
  ['semaine_suivante', 'Semaine suivante'],
  ['ce_mois', 'Ce mois'],
  ['mois_suivant', 'Mois suivant'],
  ['au_dela', 'Au-delà'],
  ['sans_echeance', 'Sans échéance'],
]

function KpiCard({ icon, label, value, hint }) {
  return (
    <Card className="flex-1 min-w-[160px]">
      <CardContent className="flex items-center gap-3 p-4">
        <div className="text-muted-foreground">{icon}</div>
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="text-lg font-semibold">{value}</div>
          {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
        </div>
      </CardContent>
    </Card>
  )
}

export default function QuoteToCashPage() {
  const [dash, setDash] = useState(null)
  const [cash, setCash] = useState(null)
  const [analyse, setAnalyse] = useState(null)
  const [loading, setLoading] = useState(true)
  const [errDash, setErrDash] = useState(false)
  const [errCash, setErrCash] = useState(false)
  const [errAnalyse, setErrAnalyse] = useState(false)

  useEffect(() => {
    let active = true
    // Les trois sources sont chargées en parallèle et en best-effort : une
    // source en erreur (ou un 403 sur l'analyse de facturation, réservée
    // responsable/admin) n'empêche pas les autres de s'afficher.
    Promise.allSettled([
      ventesApi.getDashboardQuoteToCash()
        .then((r) => { if (active) { setDash(r.data); setErrDash(false) } })
        .catch(() => { if (active) setErrDash(true) }),
      ventesApi.getCashFlowForecast()
        .then((r) => { if (active) { setCash(r.data); setErrCash(false) } })
        .catch(() => { if (active) setErrCash(true) }),
      ventesApi.getAnalyseFacturation()
        .then((r) => {
          if (active) {
            setAnalyse(Array.isArray(r.data) ? r.data : [])
            setErrAnalyse(false)
          }
        })
        .catch(() => { if (active) setErrAnalyse(true) }),
    ]).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const bucketRows = useMemo(() => {
    const b = cash?.buckets || {}
    return BUCKET_LABELS
      .filter(([key]) => b[key])
      .map(([key, label]) => ({
        key,
        label,
        montant: b[key].montant,
        count: b[key].count,
      }))
  }, [cash])

  return (
    <div className="page">
      <PageHeader
        title="Quote-to-Cash"
        subtitle="Conversion devis → facture → encaissement, DSO, cycle moyen, prévision d'encaissement et analyse de facturation."
      />

      {loading && <Skeleton className="h-24 w-full" />}

      {/* ── KPI (FG45) ─────────────────────────────────────────────────── */}
      {!loading && errDash && (
        <EmptyState title="Tableau de bord indisponible" description="Le tableau de bord Quote-to-Cash n'a pas pu être chargé." />
      )}
      {!loading && !errDash && dash && (
        <>
          <div className="flex flex-wrap gap-3">
            <KpiCard
              icon={<Percent size={18} aria-hidden="true" />}
              label="Taux d'acceptation"
              value={pct(dash.devis?.taux_acceptation_pct)}
              hint={`${dash.devis?.acceptes ?? 0} / ${dash.devis?.envoyes ?? 0} devis`}
            />
            <KpiCard
              icon={<TrendingUp size={18} aria-hidden="true" />}
              label="Valeur pipeline"
              value={mad(dash.devis?.valeur_pipeline)}
            />
            <KpiCard
              icon={<Clock size={18} aria-hidden="true" />}
              label="DSO"
              value={jours(dash.dso_jours)}
            />
            <KpiCard
              icon={<Clock size={18} aria-hidden="true" />}
              label="Cycle quote-to-cash"
              value={jours(dash.cycle_moyen_jours)}
            />
            <KpiCard
              icon={<Banknote size={18} aria-hidden="true" />}
              label="Facturé"
              value={mad(dash.factures?.montant_facture)}
            />
            <KpiCard
              icon={<Banknote size={18} aria-hidden="true" />}
              label="Encaissé"
              value={mad(dash.factures?.montant_encaisse)}
            />
          </div>

          <Card className="mt-4">
            <CardContent className="p-0">
              <Table
                aria-label="Pipeline par commercial"
                caption="Devis actifs et valeur de pipeline par commercial"
                columns={[
                  { key: 'commercial', header: 'Commercial' },
                  { key: 'devis_actifs', header: 'Devis actifs', align: 'right' },
                  {
                    key: 'valeur_pipeline',
                    header: 'Valeur pipeline',
                    align: 'right',
                    cell: (r) => mad(r.valeur_pipeline),
                  },
                ]}
                rows={dash.par_commercial || []}
                getRowKey={(r, i) => `${r.commercial}-${i}`}
                empty={<EmptyState title="Aucun devis actif" />}
              />
            </CardContent>
          </Card>
        </>
      )}

      {/* ── Prévision d'encaissement (FG47) ────────────────────────────── */}
      {!loading && errCash && (
        <EmptyState title="Prévision d'encaissement indisponible" description="La prévision de trésorerie n'a pas pu être chargée." />
      )}
      {!loading && !errCash && cash && (
        <Card className="mt-4">
          <CardContent className="p-0">
            <Table
              aria-label="Prévision d'encaissement"
              caption="Montants dûs par échéance"
              columns={[
                { key: 'label', header: 'Échéance' },
                { key: 'count', header: 'Factures', align: 'right' },
                { key: 'montant', header: 'Montant dû', align: 'right', cell: (r) => mad(r.montant) },
              ]}
              rows={bucketRows}
              getRowKey={(r) => r.key}
              empty={<EmptyState title="Aucune facture ouverte" />}
              footer={(
                <tr>
                  <td className="px-3 py-2 font-semibold">Total en cours</td>
                  <td className="px-3 py-2" />
                  <td className="px-3 py-2 text-right font-semibold">{mad(cash.total_en_cours)}</td>
                </tr>
              )}
            />
          </CardContent>
        </Card>
      )}

      {/* ── Analyse de facturation (ZFAC10) ────────────────────────────── */}
      {!loading && errAnalyse && (
        <EmptyState title="Analyse de facturation indisponible" description="L'analyse de facturation n'a pas pu être chargée (réservée aux responsables et administrateurs)." />
      )}
      {!loading && !errAnalyse && analyse && (
        <Card className="mt-4">
          <CardContent className="p-0">
            <Table
              aria-label="Analyse de facturation"
              caption="Factures par mois, client et statut"
              columns={[
                { key: 'mois', header: 'Mois' },
                { key: 'client_nom', header: 'Client' },
                { key: 'statut', header: 'Statut' },
                { key: 'nb_factures', header: 'Nb', align: 'right' },
                { key: 'total_ht', header: 'Total HT', align: 'right', cell: (r) => mad(r.total_ht) },
                { key: 'total_ttc', header: 'Total TTC', align: 'right', cell: (r) => mad(r.total_ttc) },
              ]}
              rows={analyse}
              getRowKey={(r, i) => `${r.mois}-${r.client_id}-${r.statut}-${i}`}
              empty={<EmptyState title="Aucune facture sur la période" />}
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
