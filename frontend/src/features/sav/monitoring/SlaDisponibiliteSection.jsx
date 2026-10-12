// ASAV101 (D-ASAV-4 option (b), ASAV93) — SLA de disponibilité par système.
// Saisie du taux garanti (aucun défaut, CIQ644) + compensation par jour, puis
// « Calculer l'écart » : indice de suivi mesuré vs taux garanti, pénalité
// chiffrée par le serveur (null tant que l'engagement n'est pas validé).
// Contrat : `apps/monitoring/contract_samples/sla_disponibilite.json`.
import { useState } from 'react'
import { Gauge } from 'lucide-react'
import monitoringApi from '../../../api/monitoringApi'
import { getApiError } from '../../../lib/apiError'
import { formatMAD, formatNumber } from '../../../lib/format'
import { Card, Button, Input, StatusPill, toast } from '../../../ui'
import SystemPicker from '../../../pages/monitoring/SystemPicker'
import ListeOuVide from './ListeOuVide'
import { libelleSysteme as libelle, useListeServeur } from './partage'

const FORM_VIDE = { systeme: '', taux: '', compensation: '' }
const pct = (v) => (v === null || v === undefined ? '—' : `${formatNumber(v, { decimals: 2 })} %`)

export default function SlaDisponibiliteSection({ systems, loadingSystems }) {
  const { rows, loading, load } = useListeServeur(monitoringApi.getSlasDisponibilite)
  const [form, setForm] = useState(FORM_VIDE)
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [ecarts, setEcarts] = useState({})

  const libelleSysteme = (installationId) => libelle(systems, installationId)

  const enregistrer = async () => {
    const systeme = systems.find((s) => String(s.id) === form.systeme)
    if (!systeme) return
    const existant = rows.find((r) => r.installation === systeme.installation)
    setBusy(true)
    setErreur(null)
    try {
      await monitoringApi.saveSlaDisponibilite(existant?.id, {
        installation: systeme.installation,
        disponibilite_garantie_pct: form.taux,
        compensation_mad_par_jour_indispo: form.compensation || '0',
      })
      toast.success('SLA de disponibilité enregistré')
      setForm(FORM_VIDE)
      load()
    } catch (e) {
      setErreur(getApiError(e, 'Enregistrement du SLA impossible.').message)
    } finally { setBusy(false) }
  }

  const calculer = async (sla) => {
    try {
      const r = await monitoringApi.getSlaEcart(sla.id)
      setEcarts((m) => ({ ...m, [sla.id]: r.data }))
    } catch (e) {
      toast.error(getApiError(e, "Calcul de l'écart impossible.").message)
    }
  }

  return (
    <Card role="region" className="flex flex-col gap-3 p-4" aria-label="SLA de disponibilité">
      <h2 className="text-lg font-semibold">SLA de disponibilité</h2>

      <div className="grid gap-3 sm:grid-cols-4">
        <div className="sm:col-span-2">
          <SystemPicker systems={systems} loading={loadingSystems} value={form.systeme}
                        onChange={(v) => setForm((f) => ({ ...f, systeme: v }))} />
        </div>
        <Input aria-label="Taux de disponibilité garanti (%)" type="number" step="any"
               placeholder="Taux garanti (%)" value={form.taux}
               onChange={(e) => setForm((f) => ({ ...f, taux: e.target.value }))} />
        <Input aria-label="Compensation par jour d'indisponibilité (MAD)" type="number" step="any"
               placeholder="Compensation / jour (MAD)" value={form.compensation}
               onChange={(e) => setForm((f) => ({ ...f, compensation: e.target.value }))} />
        <Button type="button" size="sm" loading={busy}
                disabled={!form.systeme || !form.taux} onClick={enregistrer}>
          Enregistrer le SLA
        </Button>
      </div>
      {erreur && <p role="alert" className="text-sm text-destructive">{erreur}</p>}

      <ListeOuVide loading={loading} rows={rows} icon={Gauge} title="Aucun SLA de disponibilité"
                   description="Saisissez le taux garanti d'un système pour suivre l'écart.">
        <ul className="flex flex-col gap-2">
          {rows.map((s) => {
            const e = ecarts[s.id]
            return (
              <li key={s.id} className="rounded-lg border border-border bg-card p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{libelleSysteme(s.installation)}</span>
                    <span className="text-sm text-muted-foreground">
                      garanti {pct(s.disponibilite_garantie_pct)} · {formatMAD(s.compensation_mad_par_jour_indispo)} / jour
                    </span>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => calculer(s)}>
                    Calculer l'écart
                  </Button>
                </div>
                {e && (
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                    <StatusPill tone={e.sous_garantie ? 'danger' : 'success'}
                                label={e.sous_garantie ? 'Sous la garantie' : 'Garantie tenue'} />
                    <span>{e.libelle_indicateur} : {pct(e.disponibilite_mesuree_pct)}</span>
                    <span>· écart {pct(e.ecart_pct)}</span>
                    <span>
                      · pénalité {e.penalite_mad === null || e.penalite_mad === undefined
                        ? 'non chiffrée (engagement de production non validé ou données absentes)'
                        : formatMAD(e.penalite_mad)}
                    </span>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </ListeOuVide>
    </Card>
  )
}
