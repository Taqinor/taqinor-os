import { useEffect, useState } from 'react'
import { ShieldAlert, Plus, Users } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import api from '../../api/axios'

/* ============================================================================
   PACT114 — Stérilisation des instruments : cycles et traçabilité sanitaire.
   ----------------------------------------------------------------------------
   NTSAN23 (`apps/sante`) livrait déjà ``CycleSterilisation``/
   ``InstrumentSterilise`` (endpoints `/sante/cycles-sterilisation/` +
   `/sante/instruments-sterilises/`) et l'action serveur
   `cycles-sterilisation/{id}/patients-concernes/` (NTSAN24) qui retrouve les
   patients exposés — SANS AUCUN client API santé ni écran. Un cycle NON
   CONFORME affiche la liste renvoyée par CETTE action serveur, SANS AUCUN
   recalcul côté client (pas de jointure locale instrument → patient).
   ========================================================================== */

const listOf = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

const STATUTS = [
  { value: 'conforme', label: 'Conforme' },
  { value: 'non_conforme', label: 'Non conforme' },
]

const CYCLE_VIDE = { numero_cycle: '', date_cycle: '', autoclave_ref: '', statut: 'conforme' }
const INSTRUMENT_VIDE = { cycle: '', instrument_ref: '', kit_ref: '' }

export default function SterilisationScreen() {
  const [cycles, setCycles] = useState([])
  const [instruments, setInstruments] = useState([])
  const [loading, setLoading] = useState(true)
  const [formCycle, setFormCycle] = useState(CYCLE_VIDE)
  const [formInstrument, setFormInstrument] = useState(INSTRUMENT_VIDE)
  const [saving, setSaving] = useState(false)
  const [patientsParCycle, setPatientsParCycle] = useState({})
  const [chargementPatients, setChargementPatients] = useState(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get('/sante/cycles-sterilisation/'),
      api.get('/sante/instruments-sterilises/'),
    ])
      .then(([cyclesRes, instrumentsRes]) => {
        setCycles(listOf(cyclesRes.data))
        setInstruments(listOf(instrumentsRes.data))
      })
      .catch(() => toast.error('Impossible de charger les cycles de stérilisation.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  const instrumentsDuCycle = (cycleId) => instruments.filter((i) => i.cycle === cycleId)

  const creerCycle = async (e) => {
    e.preventDefault()
    if (!formCycle.numero_cycle.trim() || !formCycle.date_cycle) return
    setSaving(true)
    try {
      await api.post('/sante/cycles-sterilisation/', formCycle)
      toast.success('Cycle de stérilisation enregistré.')
      setFormCycle(CYCLE_VIDE)
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Impossible de créer ce cycle.')
    } finally {
      setSaving(false)
    }
  }

  const creerInstrument = async (e) => {
    e.preventDefault()
    if (!formInstrument.cycle) return
    setSaving(true)
    try {
      await api.post('/sante/instruments-sterilises/', {
        cycle: Number(formInstrument.cycle),
        instrument_ref: formInstrument.instrument_ref,
        kit_ref: formInstrument.kit_ref,
      })
      toast.success('Instrument ajouté au cycle.')
      setFormInstrument((prev) => ({ ...INSTRUMENT_VIDE, cycle: prev.cycle }))
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Impossible d'ajouter cet instrument.")
    } finally {
      setSaving(false)
    }
  }

  // NTSAN24 — patients exposés, TELS QUE renvoyés par l'action serveur,
  // jamais recalculés côté client.
  const voirPatientsConcernes = async (cycle) => {
    setChargementPatients(cycle.id)
    try {
      const res = await api.get(`/sante/cycles-sterilisation/${cycle.id}/patients-concernes/`)
      setPatientsParCycle((prev) => ({ ...prev, [cycle.id]: res.data?.results ?? [] }))
    } catch {
      toast.error('Impossible de récupérer les patients concernés.')
    } finally {
      setChargementPatients(null)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <ShieldAlert size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Stérilisation des instruments</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Nouveau cycle d’autoclave</h2>
      <form onSubmit={creerCycle} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          placeholder="Numéro de cycle"
          value={formCycle.numero_cycle}
          onChange={(e) => setFormCycle({ ...formCycle, numero_cycle: e.target.value })}
          aria-label="Numéro de cycle"
        />
        <input
          type="datetime-local"
          value={formCycle.date_cycle}
          onChange={(e) => setFormCycle({ ...formCycle, date_cycle: e.target.value })}
          aria-label="Date du cycle"
        />
        <input
          placeholder="Référence autoclave"
          value={formCycle.autoclave_ref}
          onChange={(e) => setFormCycle({ ...formCycle, autoclave_ref: e.target.value })}
          aria-label="Référence de l'autoclave"
        />
        <select
          value={formCycle.statut}
          onChange={(e) => setFormCycle({ ...formCycle, statut: e.target.value })}
          aria-label="Statut du cycle"
        >
          {STATUTS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
        <Button type="submit" disabled={saving}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Enregistrer
        </Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 24 }}>
          <thead>
            <tr>
              <th>N° cycle</th><th>Date</th><th>Autoclave</th><th>Statut</th>
              <th>Instruments</th><th>Patients concernés</th>
            </tr>
          </thead>
          <tbody>
            {cycles.map((c) => (
              <tr key={c.id} data-testid={`cycle-${c.id}`}>
                <td>{c.numero_cycle}</td>
                <td>{c.date_cycle ? new Date(c.date_cycle).toLocaleString('fr-FR') : '—'}</td>
                <td>{c.autoclave_ref || '—'}</td>
                <td>
                  <Badge tone={c.statut === 'non_conforme' ? 'danger' : 'success'}>
                    {c.statut === 'non_conforme' ? 'Non conforme' : 'Conforme'}
                  </Badge>
                </td>
                <td>{instrumentsDuCycle(c.id).length}</td>
                <td>
                  {c.statut === 'non_conforme' ? (
                    <div>
                      <Button
                        variant="ghost" size="sm"
                        onClick={() => voirPatientsConcernes(c)}
                        disabled={chargementPatients === c.id}
                      >
                        <Users size={14} strokeWidth={1.75} aria-hidden="true" />
                        {chargementPatients === c.id ? 'Recherche…' : 'Voir les patients concernés'}
                      </Button>
                      {patientsParCycle[c.id] && (
                        <ul data-testid={`patients-concernes-${c.id}`} style={{ marginTop: 4 }}>
                          {patientsParCycle[c.id].length === 0 && (
                            <li style={{ color: '#64748b' }}>Aucun patient concerné.</li>
                          )}
                          {patientsParCycle[c.id].map((p) => (
                            <li key={p.id}>{p.nom} {p.prenom}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ) : '—'}
                </td>
              </tr>
            ))}
            {cycles.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>Aucun cycle enregistré</td></tr>
            )}
          </tbody>
        </table>
      )}

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Instruments passés dans un cycle</h2>
      <form onSubmit={creerInstrument} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select
          value={formInstrument.cycle}
          onChange={(e) => setFormInstrument({ ...formInstrument, cycle: e.target.value })}
          aria-label="Cycle"
        >
          <option value="">Cycle…</option>
          {cycles.map((c) => <option key={c.id} value={c.id}>{c.numero_cycle}</option>)}
        </select>
        <input
          placeholder="Référence instrument"
          value={formInstrument.instrument_ref}
          onChange={(e) => setFormInstrument({ ...formInstrument, instrument_ref: e.target.value })}
          aria-label="Référence de l'instrument"
        />
        <input
          placeholder="Référence kit"
          value={formInstrument.kit_ref}
          onChange={(e) => setFormInstrument({ ...formInstrument, kit_ref: e.target.value })}
          aria-label="Référence du kit"
        />
        <Button type="submit" disabled={saving}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter
        </Button>
      </form>

      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th>Cycle</th><th>Instrument</th><th>Kit</th></tr>
          </thead>
          <tbody>
            {instruments.map((i) => (
              <tr key={i.id}>
                <td>{cycles.find((c) => c.id === i.cycle)?.numero_cycle || `#${i.cycle}`}</td>
                <td>{i.instrument_ref || '—'}</td>
                <td>{i.kit_ref || '—'}</td>
              </tr>
            ))}
            {instruments.length === 0 && (
              <tr><td colSpan={3} style={{ textAlign: 'center', color: '#64748b' }}>Aucun instrument enregistré</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
