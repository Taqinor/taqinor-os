// ASAV102 (D-ASAV-4 option (b), ASAV93) — registre des certificats carbone.
// Émission pour un système et une période : les tCO₂ sont CALCULÉES par le
// serveur depuis la production mesurée (jamais saisies), la référence est
// posée par le serveur, un doublon exact est refusé (anti-double-comptage).
// Contrat : `apps/monitoring/contract_samples/certificats_carbone.json`.
import { useState } from 'react'
import { Leaf } from 'lucide-react'
import monitoringApi from '../../../api/monitoringApi'
import { getApiError } from '../../../lib/apiError'
import { formatDate, formatNumber } from '../../../lib/format'
import { Card, Button, Input, toast } from '../../../ui'
import SystemPicker from '../../../pages/monitoring/SystemPicker'
import ListeOuVide from './ListeOuVide'
import { libelleSysteme, useListeServeur } from './partage'

const FORM_VIDE = { systeme: '', periode_debut: '', periode_fin: '' }

export default function CertificatsCarboneSection({ systems, loadingSystems }) {
  const { rows, loading, load } = useListeServeur(monitoringApi.getCertificatsCarbone)
  const [form, setForm] = useState(FORM_VIDE)
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)

  const cible = (c) => (c.installation_id
    ? libelleSysteme(systems, c.installation_id)
    :`Client #${c.client_id} (consolidé)`)

  const emettre = async () => {
    const systeme = systems.find((s) => String(s.id) === form.systeme)
    if (!systeme) return
    setBusy(true)
    setErreur(null)
    try {
      const r = await monitoringApi.emettreCertificatCarbone({
        installation_id: systeme.installation,
        periode_debut: form.periode_debut,
        periode_fin: form.periode_fin,
      })
      toast.success(`Certificat ${r.data?.reference ?? ''} émis`)
      setForm(FORM_VIDE)
      load()
    } catch (e) {
      setErreur(getApiError(e, 'Émission du certificat impossible.').message)
    } finally { setBusy(false) }
  }

  return (
    <Card role="region" className="flex flex-col gap-3 p-4" aria-label="Certificats carbone">
      <h2 className="text-lg font-semibold">Certificats carbone</h2>
      <p className="text-xs text-muted-foreground">
        Les tonnes de CO₂ évitées sont calculées depuis la production mesurée de la période.
      </p>

      <div className="grid gap-3 sm:grid-cols-4">
        <div className="sm:col-span-2">
          <SystemPicker systems={systems} loading={loadingSystems} value={form.systeme}
                        onChange={(v) => setForm((f) => ({ ...f, systeme: v }))} />
        </div>
        <Input aria-label="Début de période" type="date" value={form.periode_debut}
               onChange={(e) => setForm((f) => ({ ...f, periode_debut: e.target.value }))} />
        <Input aria-label="Fin de période" type="date" value={form.periode_fin}
               onChange={(e) => setForm((f) => ({ ...f, periode_fin: e.target.value }))} />
        <Button type="button" size="sm" loading={busy}
                disabled={!form.systeme || !form.periode_debut || !form.periode_fin}
                onClick={emettre}>
          Émettre le certificat
        </Button>
      </div>
      {erreur && <p role="alert" className="text-sm text-destructive">{erreur}</p>}

      <ListeOuVide loading={loading} rows={rows} icon={Leaf} title="Aucun certificat émis"
                   description="Le registre des certificats carbone est vide.">
        <ul className="flex flex-col gap-2">
          {rows.map((c) => (
            <li key={c.id} className="rounded-lg border border-border bg-card p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{c.reference}</span>
                <span className="text-sm text-muted-foreground">{cible(c)}</span>
                <span className="text-sm">{formatNumber(c.tco2_evitees, { decimals: 3 })} tCO₂ évitées</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Période {formatDate(c.periode_debut)} → {formatDate(c.periode_fin)} · émis le {formatDate(c.created_at)}
              </p>
            </li>
          ))}
        </ul>
      </ListeOuVide>
    </Card>
  )
}
