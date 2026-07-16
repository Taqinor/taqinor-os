import { useEffect, useState } from 'react'
import { AlarmClock, Gauge, ShieldAlert, Timer, Plus } from 'lucide-react'
import savApi from '../../api/savApi'
import { useHasPermission } from '../../hooks/useHasPermission'
import { formatMAD, formatPercent, formatDateTime } from '../../lib/format'
import {
  Badge, Button, Input, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, toast,
} from '../../ui'

const fmtDate = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}
const fmtDateTime = (iso) => formatDateTime(iso)

/**
 * XSAV15/XSAV16/XSAV17 — Fiabilité (MTBF/MTTR/coût cumulé), disponibilité %,
 * journal d'immobilisation (downtime) et relevés compteur (heures/kWh) d'UN
 * équipement. Le coût cumulé + réparer-vs-remplacer ne sont affichés que si
 * l'utilisateur porte la permission `prix_achat_voir` — le backend les omet
 * déjà de la réponse sans cette permission (double garde, jamais un seul
 * niveau de défense pour une donnée sensible).
 */
export default function EquipementFiabilitePanel({ equipementId }) {
  const canSeeCouts = useHasPermission('prix_achat_voir')

  const [fiabilite, setFiabilite] = useState(null)
  const [dispo, setDispo] = useState(null)
  const [downtimes, setDowntimes] = useState([])
  const [releves, setReleves] = useState([])
  const [estimations, setEstimations] = useState(null)
  const [loading, setLoading] = useState(true)

  const [releveForm, setReleveForm] = useState({ type: 'heures', valeur: '' })
  const [releveBusy, setReleveBusy] = useState(false)
  const [downtimeBusy, setDowntimeBusy] = useState(false)

  const load = () => Promise.all([
    savApi.getEquipementFiabilite(equipementId).then((r) => r.data).catch(() => null),
    savApi.getEquipementDisponibilite(equipementId).then((r) => r.data).catch(() => null),
    savApi.getEquipementDowntime(equipementId).then((r) => r.data).catch(() => []),
    savApi.getEquipementReleves(equipementId).then((r) => r.data).catch(() => []),
    // ZMFG11 — prochaine défaillance estimée (MTBF) + prochain entretien dû.
    savApi.getEquipementEstimations(equipementId).then((r) => r.data).catch(() => null),
  ]).then(([f, d, dt, rv, est]) => {
    setFiabilite(f)
    setDispo(d)
    setDowntimes(dt || [])
    setReleves(rv || [])
    setEstimations(est)
  }).finally(() => setLoading(false))

  const charger = () => { setLoading(true); return load() }

  useEffect(() => { load() }, [equipementId]) // eslint-disable-line react-hooks/exhaustive-deps

  const enCours = downtimes.find((d) => d.en_cours)

  const ouvrirDowntime = async () => {
    setDowntimeBusy(true)
    try {
      await savApi.ouvrirEquipementDowntime(equipementId, {})
      toast.success('Immobilisation ouverte')
      charger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? "Impossible d'ouvrir l'immobilisation.")
    } finally { setDowntimeBusy(false) }
  }
  const cloturerDowntime = async () => {
    if (!enCours) return
    setDowntimeBusy(true)
    try {
      await savApi.cloturerEquipementDowntime(equipementId, enCours.id)
      toast.success('Immobilisation clôturée')
      charger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? "Impossible de clôturer l'immobilisation.")
    } finally { setDowntimeBusy(false) }
  }

  const addReleve = async () => {
    if (!releveForm.valeur) return
    setReleveBusy(true)
    try {
      const r = await savApi.addEquipementReleve(equipementId, releveForm)
      setReleveForm({ type: releveForm.type, valeur: '' })
      if (r.data?.ticket_genere) {
        toast.success(`Relevé enregistré — ticket ${r.data.ticket_genere.reference} généré (seuil atteint)`)
      } else {
        toast.success('Relevé enregistré')
      }
      charger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Relevé invalide.')
    } finally { setReleveBusy(false) }
  }

  if (loading) return <p className="text-sm text-muted-foreground">Chargement…</p>

  return (
    <div className="flex flex-col gap-4" data-testid="equipement-fiabilite-panel">
      {/* XSAV15 — MTBF/MTTR */}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex items-center gap-2 text-sm">
          <Timer className="size-4 text-muted-foreground" aria-hidden="true" />
          <span className="font-medium">MTBF :</span>
          <span>{fiabilite?.mtbf_jours != null ? `${fiabilite.mtbf_jours} j` : '—'}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Timer className="size-4 text-muted-foreground" aria-hidden="true" />
          <span className="font-medium">MTTR :</span>
          <span>{fiabilite?.mttr_jours != null ? `${fiabilite.mttr_jours} j` : '—'}</span>
        </div>
        {canSeeCouts && fiabilite?.cout_cumule != null && (
          <div className="flex items-center gap-2 text-sm sm:col-span-2">
            <span className="font-medium">Coût cumulé (interne) :</span>
            <span>{formatMAD(fiabilite.cout_cumule, { withSymbol: false })} DH</span>
            {fiabilite.reparer_vs_remplacer && (
              <Badge tone={fiabilite.reparer_vs_remplacer === 'remplacer' ? 'warning' : 'neutral'}>
                {fiabilite.reparer_vs_remplacer === 'remplacer' ? 'À remplacer' : 'Réparable'}
              </Badge>
            )}
          </div>
        )}
        {/* ZMFG11 — prochaine défaillance estimée (MTBF) + prochain entretien dû. */}
        {estimations?.prochaine_defaillance_estimee && (
          <div className="flex items-center gap-2 text-sm sm:col-span-2">
            <span className="font-medium">Prochaine défaillance estimée :</span>
            <span>{fmtDate(estimations.prochaine_defaillance_estimee)}</span>
          </div>
        )}
        {estimations?.prochain_entretien_du && (
          <div className="flex items-center gap-2 text-sm sm:col-span-2">
            <span className="font-medium">Prochain entretien dû :</span>
            <span>{fmtDate(estimations.prochain_entretien_du)}</span>
          </div>
        )}
      </div>

      {/* XSAV16 — Disponibilité % */}
      <div className="flex items-center gap-2 text-sm">
        <Gauge className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="font-medium">Disponibilité (30 j) :</span>
        <span>{dispo?.disponibilite_pct != null ? formatPercent(dispo.disponibilite_pct, { decimals: 1 }) : '—'}</span>
      </div>

      {/* XSAV16 — Immobilisation en cours / historique */}
      <div className="flex flex-col gap-2">
        <span className="flex items-center gap-2 text-sm font-medium">
          <ShieldAlert className="size-4 text-muted-foreground" aria-hidden="true" />
          Immobilisation
        </span>
        {enCours ? (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge tone="danger">En cours depuis {fmtDateTime(enCours.debut)}</Badge>
            <Button type="button" size="sm" variant="outline" loading={downtimeBusy} onClick={cloturerDowntime}>
              Clôturer
            </Button>
          </div>
        ) : (
          <Button type="button" size="sm" variant="outline" loading={downtimeBusy} onClick={ouvrirDowntime}>
            <Plus /> Ouvrir une immobilisation
          </Button>
        )}
        {downtimes.length > 0 && (
          <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
            {downtimes.slice(0, 5).map((d) => (
              <li key={d.id}>
                {fmtDateTime(d.debut)} → {d.fin ? fmtDateTime(d.fin) : 'en cours'}
                {d.motif ? ` — ${d.motif}` : ''}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* XSAV17 — Relevés compteur */}
      <div className="flex flex-col gap-2">
        <span className="flex items-center gap-2 text-sm font-medium">
          <AlarmClock className="size-4 text-muted-foreground" aria-hidden="true" />
          Relevés compteur
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={releveForm.type}
                  onValueChange={(v) => setReleveForm((f) => ({ ...f, type: v }))}>
            <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="heures">Heures</SelectItem>
              <SelectItem value="kwh">kWh</SelectItem>
            </SelectContent>
          </Select>
          <Input type="number" step="any" placeholder="Valeur" className="w-32"
                 value={releveForm.valeur}
                 onChange={(e) => setReleveForm((f) => ({ ...f, valeur: e.target.value }))} />
          <Button type="button" size="sm" variant="outline" loading={releveBusy} onClick={addReleve}>
            <Plus /> Enregistrer
          </Button>
        </div>
        {releves.length > 0 && (
          <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
            {releves.slice(0, 5).map((r) => (
              <li key={r.id}>
                {fmtDate(r.date)} — {r.valeur} {r.type === 'kwh' ? 'kWh' : 'h'}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
