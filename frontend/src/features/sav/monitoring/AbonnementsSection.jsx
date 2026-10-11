// ASAV100 (D-ASAV-4 option (b), ASAV93) — abonnements de supervision.
// Liste + création + résiliation (motif obligatoire). Tout vient du serveur
// (contrat `apps/monitoring/contract_samples/abonnements_monitoring.json`) :
// le client est résolu côté serveur depuis le système, le montant est saisi
// (aucun défaut), et la résiliation coupe la supervision du système lié.
import { useState } from 'react'
import { CalendarClock } from 'lucide-react'
import monitoringApi from '../../../api/monitoringApi'
import { getApiError } from '../../../lib/apiError'
import { formatDate, formatMAD } from '../../../lib/format'
import {
  Card, StatusPill, Button, Input, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, toast,
} from '../../../ui'
import SystemPicker from '../../../pages/monitoring/SystemPicker'
import ListeOuVide from './ListeOuVide'
import { libelleSysteme as libelle, useListeServeur } from './partage'

const STATUT_TONES = { actif: 'success', suspendu: 'warning', resilie: 'neutral' }
const FORM_VIDE = { systeme: '', periodicite: 'mensuel', montant: '', date_debut: '' }

export default function AbonnementsSection({ systems, loadingSystems }) {
  const { rows, loading, load } = useListeServeur(monitoringApi.getAbonnements)
  const [form, setForm] = useState(FORM_VIDE)
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [aResilier, setAResilier] = useState(null)
  const [motif, setMotif] = useState('')
  const [erreurMotif, setErreurMotif] = useState(null)

  const libelleSysteme = (installationId) => libelle(systems, installationId)

  const creer = async () => {
    const systeme = systems.find((s) => String(s.id) === form.systeme)
    if (!systeme) return
    setBusy(true)
    setErreur(null)
    try {
      await monitoringApi.creerAbonnement({
        installation_id: systeme.installation,
        periodicite: form.periodicite,
        montant: form.montant,
        date_debut: form.date_debut || undefined,
      })
      toast.success('Abonnement créé')
      setForm(FORM_VIDE)
      load()
    } catch (e) {
      setErreur(getApiError(e, "Création de l'abonnement impossible.").message)
    } finally { setBusy(false) }
  }

  const resilier = async (abonnement) => {
    setBusy(true)
    setErreurMotif(null)
    try {
      await monitoringApi.resilierAbonnement(abonnement.id, motif)
      toast.success('Abonnement résilié — supervision coupée')
      setAResilier(null)
      setMotif('')
      load()
    } catch (e) {
      setErreurMotif(getApiError(e, 'Résiliation impossible.').message)
    } finally { setBusy(false) }
  }

  return (
    <Card role="region" className="flex flex-col gap-3 p-4" aria-label="Abonnements de supervision">
      <h2 className="text-lg font-semibold">Abonnements de supervision</h2>

      <div className="grid gap-3 sm:grid-cols-4">
        <div className="sm:col-span-2">
          <SystemPicker systems={systems} loading={loadingSystems} value={form.systeme}
                        onChange={(v) => setForm((f) => ({ ...f, systeme: v }))} />
        </div>
        <Select value={form.periodicite}
                onValueChange={(v) => setForm((f) => ({ ...f, periodicite: v }))}>
          <SelectTrigger aria-label="Périodicité"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="mensuel">Mensuel</SelectItem>
            <SelectItem value="annuel">Annuel</SelectItem>
          </SelectContent>
        </Select>
        <Input aria-label="Montant par période (MAD)" type="number" step="any"
               placeholder="Montant par période (MAD)" value={form.montant}
               onChange={(e) => setForm((f) => ({ ...f, montant: e.target.value }))} />
        <Input aria-label="Date de début" type="date" value={form.date_debut}
               onChange={(e) => setForm((f) => ({ ...f, date_debut: e.target.value }))} />
        <Button type="button" size="sm" loading={busy}
                disabled={!form.systeme || !form.montant} onClick={creer}>
          Créer l'abonnement
        </Button>
      </div>
      {erreur && <p role="alert" className="text-sm text-destructive">{erreur}</p>}

      <ListeOuVide loading={loading} rows={rows} icon={CalendarClock} title="Aucun abonnement"
                   description="Aucun abonnement de supervision pour la société.">
        <ul className="flex flex-col gap-2">
          {rows.map((a) => (
            <li key={a.id} className="rounded-lg border border-border bg-card p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusPill tone={STATUT_TONES[a.statut] ?? 'neutral'} label={a.statut_display ?? a.statut} />
                  <span className="font-medium">{libelleSysteme(a.installation_id)}</span>
                  <span className="text-sm text-muted-foreground">
                    {a.periodicite_display} — {formatMAD(a.montant)}
                  </span>
                </div>
                {a.statut !== 'resilie' && aResilier !== a.id && (
                  <Button size="sm" variant="outline" onClick={() => { setAResilier(a.id); setMotif('') }}>
                    Résilier
                  </Button>
                )}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Début {formatDate(a.date_debut)} · prochaine échéance {formatDate(a.prochaine_echeance)}
                {a.motif_resiliation ? ` · motif : ${a.motif_resiliation}` : ''}
              </p>
              {aResilier === a.id && (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Input aria-label="Motif de résiliation" className="w-72"
                         placeholder="Motif de résiliation" value={motif}
                         onChange={(e) => setMotif(e.target.value)} />
                  <Button size="sm" variant="destructive" loading={busy} onClick={() => resilier(a)}>
                    Confirmer la résiliation
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setAResilier(null)}>Annuler</Button>
                  {erreurMotif && <p role="alert" className="w-full text-sm text-destructive">{erreurMotif}</p>}
                </div>
              )}
            </li>
          ))}
        </ul>
      </ListeOuVide>
    </Card>
  )
}
