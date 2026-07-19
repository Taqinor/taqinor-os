import { useEffect, useState } from 'react'
import adminopsApi from './adminopsApi'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Card, Label, NumberInput, Spinner, Switch } from '../../ui'
import { toastError, toastSuccess } from '../../lib/toast'
import { downloadBlobInGesture } from '../../utils/downloadBlob'

/* ============================================================================
   NTADM33/34 — Réglages « Administration » : durée sandbox (7-30j), délai de
   grâce, seuil d'alerte sièges (%), rétention des événements d'usage (30-365j),
   autorisation des sandbox.
   ========================================================================== */

export default function AdminSettingsPage() {
  const [form, setForm] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    adminopsApi
      .getSettings()
      .then((res) => setForm(res.data))
      .catch(() => toastError('Impossible de charger les réglages.'))
      .finally(() => setLoading(false))
  }, [])

  // WIR69 — téléchargement du journal d'administration en PDF (un clic).
  const [journalBusy, setJournalBusy] = useState(false)
  const downloadJournal = () => {
    const pending = downloadBlobInGesture()
    setJournalBusy(true)
    adminopsApi.journalAdminPdf()
      .then((res) => pending.deliver(res.data, 'journal-admin.pdf'))
      .catch(() => toastError('Téléchargement du journal impossible.'))
      .finally(() => setJournalBusy(false))
  }

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const setNum = (k) => (e) => {
    const n = parseInt(e.target.value, 10)
    set(k, Number.isNaN(n) ? '' : n)
  }

  const save = async () => {
    setSaving(true)
    try {
      const res = await adminopsApi.updateSettings(form)
      setForm(res.data)
      toastSuccess('Réglages enregistrés.')
    } catch (err) {
      const data = err?.response?.data
      const msg = data ? Object.values(data).flat().join(' ') : 'Enregistrement impossible.'
      toastError(msg)
    } finally {
      setSaving(false)
    }
  }

  if (loading || !form) return <Spinner />

  return (
    <div>
      <PageHeader title="Réglages Administration" subtitle="Sandbox, alertes sièges, rétention analytics" />
      <Card className="mt-4 max-w-lg space-y-4 p-6">
        <div>
          <Label>Durée par défaut d'un sandbox (jours, 7-30)</Label>
          <NumberInput
            value={form.sandbox_duree_defaut_jours}
            onChange={setNum('sandbox_duree_defaut_jours')}
          />
        </div>
        <div>
          <Label>Délai de grâce avant purge (jours)</Label>
          <NumberInput
            value={form.sandbox_grace_purge_jours}
            onChange={setNum('sandbox_grace_purge_jours')}
          />
        </div>
        <div>
          <Label>Seuil d'alerte sièges (%)</Label>
          <NumberInput
            value={form.seuil_alerte_sieges_pct}
            onChange={setNum('seuil_alerte_sieges_pct')}
          />
        </div>
        <div>
          <Label>Rétention des événements d'usage (jours, 30-365)</Label>
          <NumberInput
            value={form.retention_evenements_usage_jours}
            onChange={setNum('retention_evenements_usage_jours')}
          />
        </div>
        <div className="flex items-center gap-3">
          <Switch
            checked={form.sandbox_autorise}
            onCheckedChange={(v) => set('sandbox_autorise', v)}
          />
          <Label>Autoriser la création de sandbox</Label>
        </div>
        <Button onClick={save} disabled={saving}>Enregistrer</Button>
      </Card>

      {/* WIR69 — journal d'administration téléchargeable en PDF (IsAdministrateur). */}
      <Card className="mt-4 max-w-lg space-y-3 p-6">
        <div>
          <Label>Journal d'administration</Label>
          <p className="text-sm text-muted-foreground">
            Export PDF des actions d'administration (paramètres, rôles, sièges…).
          </p>
        </div>
        <Button variant="outline" onClick={downloadJournal} disabled={journalBusy}>
          {journalBusy ? 'Génération…' : 'Télécharger le journal (PDF)'}
        </Button>
      </Card>
    </div>
  )
}
