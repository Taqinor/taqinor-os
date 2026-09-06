// MRY29 — Cockpit CRM : panneau KPI du moteur de relances. Deux appels
// (`kpi_premier_contact` + `kpi_cadences`, contrats MRY25/MRY19/MRY21),
// jamais un chiffre inventé — `null` (dénominateur 0) rend « — », jamais 0 %.
// Distinct de `CrmInsightsPanel.jsx` (SLA en heures, ROI, objectifs) —
// inchangé.
import { useEffect, useState } from 'react'
import { Target } from 'lucide-react'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Spinner,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { formatPercent } from '../../lib/format'

const PERIODES = [
  { value: '7', label: '7 jours' },
  { value: '30', label: '30 jours' },
  { value: '90', label: '90 jours' },
]

// `null` (dénominateur 0, règle « aucun chiffre inventé ») → tiret, jamais 0.
const dash = (v) => (v === null || v === undefined ? '—' : v)
const pct = (v) => (v === null || v === undefined ? '—' : formatPercent(v, { decimals: 1 }))

function Metric({ label, value, hint }) {
  return (
    <div className="rounded-lg border border-border bg-card p-2.5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-display text-lg font-semibold tabular-nums">{value}</div>
      {hint && <div className="text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  )
}

export default function KpiRelancesPanel() {
  const [jours, setJours] = useState('30')
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [contact, setContact] = useState(null)
  const [cadences, setCadences] = useState(null)

  useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) { setLoading(true); setErreur(false) } })
    Promise.all([
      crmApi.getKpiPremierContact({ jours }),
      crmApi.getKpiCadences({ jours }),
    ]).then(([c, k]) => {
      if (!active) return
      setContact(c.data)
      setCadences(k.data)
    }).catch(() => { if (active) setErreur(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [jours])

  // F6 — jamais un objectif INVENTÉ côté écran : `null` (pendant le
  // chargement, sur erreur, ou si une future réponse omettait ce champ)
  // affiche « — » dans le titre (ci-dessous), JAMAIS un « 5 » par défaut qui
  // mentirait sur l'objectif réel de la société
  // (`CompanyProfile.premier_contact_objectif_min`) — le titre était rendu
  // AVANT la résolution du chargement (hors du if/else loading ci-dessous),
  // donc affichait « 5 » en dur à chaque ouverture d'écran, même pour une
  // société qui a configuré un autre objectif.
  const objectif = contact?.objectif_minutes ?? null

  return (
    <Card data-testid="kpi-relances-panel">
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-4 w-4" /> Premier contact &amp; cadences
          </CardTitle>
          <CardDescription>
            Objectif « rappelé en moins de {objectif ?? '—'} min ouvrées » et bilan des cadences.
          </CardDescription>
        </div>
        <Select value={jours} onValueChange={setJours}>
          <SelectTrigger className="w-28" aria-label="Période"><SelectValue /></SelectTrigger>
          <SelectContent>
            {PERIODES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Spinner />
        ) : erreur ? (
          <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Metric label={`% touchés < ${objectif ?? '—'} min`} value={pct(contact?.pct_sous_objectif)} />
            <Metric label="Médiane (min ouvrées)" value={dash(contact?.mediane_minutes_ouvrees)} />
            <Metric
              label="Nuit rappelés avant 9 h 30"
              value={dash(contact?.nb_nuit_rappeles_avant_930)}
              hint={contact ? `sur ${contact.nb_nuit} lead(s) de nuit` : undefined}
            />
            <Metric label="Joints sous 5 j ouvrés" value={pct(cadences?.joints_sous_5j_pct)} />
            <Metric label="Cadences complètes" value={dash(cadences?.cadences_completes)} />
            <Metric label="Arrêtées (joint)" value={dash(cadences?.cadences_arretees_joint)} />
            <Metric label="Perdus avec motif" value={pct(cadences?.perdus_avec_motif_pct)} />
            <Metric label="Signatures" value={dash(cadences?.signatures)} />
            <Metric label="Devis envoyés" value={dash(cadences?.devis_envoyes)} />
            <Metric label="Tentatives avant abandon" value={dash(cadences?.tentatives_moy_avant_abandon)} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
