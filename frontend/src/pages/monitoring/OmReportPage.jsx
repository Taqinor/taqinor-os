import { useEffect, useMemo, useState } from 'react'
import { FileDown, Mail, Send } from 'lucide-react'
import monitoringApi from '../../api/monitoringApi'
import {
  Badge, Button, Card, CardContent, EmptyState, Input, Label, Segmented, Spinner,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { toast } from '../../ui/confirm'
import { formatNumber, formatPercent } from '../../lib/format'
import MonitoringNav from './MonitoringNav'
import SystemPicker from './SystemPicker'
import useSupervisedSystems from './useSupervisedSystems'

/* WR7 — Génération + envoi du rapport O&M périodique (FG289).
   Affiche les données JSON du rapport (/om-report/), permet de télécharger le
   PDF (?format=pdf) et d'envoyer le rapport par e-mail (/email-om-report/). */

const PERIODS = [
  { value: 'monthly', label: 'Mensuel' },
  { value: 'quarterly', label: 'Trimestriel' },
]

export default function OmReportPage() {
  const { systems, loading: loadingSystems } = useSupervisedSystems()
  const [selectedId, setSelectedId] = useState('')
  const [period, setPeriod] = useState('monthly')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [downloading, setDownloading] = useState(false)

  // Dialogue d'envoi e-mail.
  const [emailOpen, setEmailOpen] = useState(false)
  const [recipient, setRecipient] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!selectedId) return undefined
    let active = true
    const load = async () => {
      await Promise.resolve()
      if (!active) return
      setLoading(true)
      try {
        const r = await monitoringApi.getOmReport(selectedId, { period })
        if (active) { setReport(r.data); setError(null) }
      } catch {
        if (active) setError('Impossible de charger le rapport O&M.')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [selectedId, period])

  const download = () => {
    setDownloading(true)
    monitoringApi.getOmReportPdf(selectedId, { period })
      .then((r) => {
        const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
        const a = document.createElement('a')
        a.href = url
        a.download = `rapport-om-${report?.reference || selectedId}.pdf`
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
      })
      .catch(() => toast.error('Échec du téléchargement du PDF.'))
      .finally(() => setDownloading(false))
  }

  const sendEmail = (e) => {
    e.preventDefault()
    setSending(true)
    monitoringApi.emailOmReport(selectedId, {
      period,
      ...(recipient.trim() ? { recipient: recipient.trim() } : {}),
    })
      .then((r) => {
        if (r.data?.sent) {
          toast.success('Rapport envoyé par e-mail.')
          setEmailOpen(false)
          setRecipient('')
        } else {
          toast.error('Aucun destinataire : renseignez une adresse e-mail.')
        }
      })
      .catch(() => toast.error('Échec de l’envoi du rapport.'))
      .finally(() => setSending(false))
  }

  const cards = useMemo(() => (report ? [
    { label: 'Production période', value: `${formatNumber(report.period_kwh, { decimals: 0 })} kWh` },
    { label: 'PR', value: report.pr_pct != null ? formatPercent(report.pr_pct, { decimals: 1 }) : '—' },
    { label: 'Disponibilité', value: report.availability_pct != null ? formatPercent(report.availability_pct, { decimals: 1 }) : '—' },
  ] : []), [report])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Rapports O&M</h1>
        <div className="page-subtitle">
          Rapport périodique d’un système : indicateurs, alarmes, recommandations, PDF et envoi e-mail.
        </div>
      </div>
      <MonitoringNav />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <SystemPicker
          systems={systems}
          loading={loadingSystems}
          value={selectedId}
          onChange={setSelectedId}
        />
        <Segmented
          size="sm"
          options={PERIODS}
          value={period}
          onChange={setPeriod}
          aria-label="Période du rapport"
        />
      </div>

      {!loadingSystems && systems.length === 0 ? (
        <EmptyState
          title="Aucun système supervisé"
          description="Configurez la supervision d'un système depuis l'écran Relevés pour générer son rapport."
          className="my-6"
        />
      ) : !selectedId ? (
        <EmptyState
          title="Choisissez un système"
          description="Sélectionnez un système supervisé pour générer son rapport O&M."
          className="my-6"
        />
      ) : loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : error ? (
        <EmptyState title="Erreur" description={error} className="my-6" />
      ) : report ? (
        <div className="flex flex-col gap-4" data-testid="om-report">
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button variant="outline" onClick={download} loading={downloading}>
              <FileDown /> Télécharger le PDF
            </Button>
            <Button onClick={() => setEmailOpen(true)}>
              <Mail /> Envoyer par e-mail
            </Button>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            {cards.map((c) => (
              <Card key={c.label}>
                <CardContent className="p-4">
                  <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{c.label}</div>
                  <div className="mt-2 font-display text-2xl font-semibold tabular-nums">{c.value}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardContent className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm font-semibold">Alarmes</span>
                <Badge tone={report.open_alarms > 0 ? 'danger' : 'success'}>
                  {report.open_alarms > 0
                    ? `${report.open_alarms} alarme(s) ouverte(s)`
                    : 'Aucune alarme ouverte'}
                </Badge>
                {report.soiling_suspected && <Badge tone="warning">Salissure suspectée</Badge>}
              </div>
              <div>
                <div className="mb-1 text-sm font-semibold">Recommandations</div>
                <ul className="list-inside list-disc text-sm text-muted-foreground">
                  {(report.recommendations ?? []).map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* Dialogue d'envoi e-mail */}
      <ResponsiveDialog
        open={emailOpen}
        onOpenChange={setEmailOpen}
        title="Envoyer le rapport O&M"
        description="Sans destinataire, le rapport est envoyé à l'e-mail du client du système."
      >
        <form onSubmit={sendEmail} noValidate className="flex flex-col gap-3">
          <div>
            <Label htmlFor="om-recipient">Destinataire (optionnel)</Label>
            <Input
              id="om-recipient"
              type="email"
              placeholder="client@exemple.ma"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setEmailOpen(false)}>Annuler</Button>
            <Button type="submit" loading={sending}><Send /> Envoyer</Button>
          </div>
        </form>
      </ResponsiveDialog>
    </div>
  )
}
