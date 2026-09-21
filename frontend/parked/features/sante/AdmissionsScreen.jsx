import { useEffect, useState } from 'react'
import { BedDouble, Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import santeApi from '../../api/santeApi'
import { formatDate } from '../../lib/format'

/* ============================================================================
   WIR142 — Écran d'administration « Admissions » (NTSAN6). Ouvrir une
   admission (patient + praticien + type) et la clôturer via l'action serveur
   dédiée (`cloturer/`) — jamais de mutation directe du statut côté client.
   ========================================================================== */

const CHAMPS_VIDES = { patient: '', praticien: '', type: 'consultation' }

const TYPE_OPTIONS = [
  { value: 'consultation', label: 'Consultation' },
  { value: 'hospitalisation', label: 'Hospitalisation' },
  { value: 'acte_technique', label: 'Acte technique' },
]

export default function AdmissionsScreen() {
  const [admissions, setAdmissions] = useState([])
  const [patients, setPatients] = useState([])
  const [praticiens, setPraticiens] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(CHAMPS_VIDES)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      santeApi.admissions.list(),
      santeApi.patients.list(),
      santeApi.praticiens.list(),
    ])
      .then(([admRes, patRes, praRes]) => {
        setAdmissions(admRes.data?.results ?? admRes.data ?? [])
        setPatients(patRes.data?.results ?? patRes.data ?? [])
        setPraticiens(praRes.data?.results ?? praRes.data ?? [])
      })
      .catch(() => toast.error('Impossible de charger les admissions.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  const patientNom = (id) => {
    const p = patients.find((x) => x.id === Number(id))
    return p ? `${p.nom} ${p.prenom || ''}`.trim() : `Patient #${id}`
  }
  const praticienNom = (id) => {
    const p = praticiens.find((x) => x.id === Number(id))
    return p ? p.nom : `Praticien #${id}`
  }

  const ouvrir = async (e) => {
    e.preventDefault()
    if (!form.patient || !form.praticien) return
    setSaving(true)
    try {
      await santeApi.admissions.create({
        patient: form.patient, praticien: form.praticien, type: form.type,
        date_admission: new Date().toISOString(),
      })
      toast.success('Admission ouverte.')
      setForm(CHAMPS_VIDES)
      load()
    } catch {
      toast.error("Impossible d'ouvrir l'admission.")
    } finally {
      setSaving(false)
    }
  }

  const cloturer = async (admission) => {
    try {
      await santeApi.admissions.cloturer(admission.id)
      toast.success('Admission clôturée.')
      load()
    } catch {
      toast.error('Impossible de clôturer cette admission.')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <BedDouble size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Admissions</h1>
      </div>

      <form onSubmit={ouvrir} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select
          value={form.patient}
          onChange={(e) => setForm({ ...form, patient: e.target.value })}
          aria-label="Patient"
        >
          <option value="">Patient…</option>
          {patients.map((p) => (
            <option key={p.id} value={p.id}>{p.nom} {p.prenom}</option>
          ))}
        </select>
        <select
          value={form.praticien}
          onChange={(e) => setForm({ ...form, praticien: e.target.value })}
          aria-label="Praticien"
        >
          <option value="">Praticien…</option>
          {praticiens.map((p) => (
            <option key={p.id} value={p.id}>{p.nom}</option>
          ))}
        </select>
        <select
          value={form.type}
          onChange={(e) => setForm({ ...form, type: e.target.value })}
          aria-label="Type d'admission"
        >
          {TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <Button type="submit" disabled={saving}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ouvrir
        </Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th>Patient</th><th>Praticien</th><th>Type</th>
              <th>Admise le</th><th>Statut</th><th />
            </tr>
          </thead>
          <tbody>
            {admissions.map((a) => (
              <tr key={a.id}>
                <td>{patientNom(a.patient)}</td>
                <td>{praticienNom(a.praticien)}</td>
                <td>{a.type_display || a.type}</td>
                <td>{formatDate(a.date_admission)}</td>
                <td>
                  <Badge tone={a.statut === 'cloturee' ? 'neutral' : 'success'}>
                    {a.statut_display || a.statut}
                  </Badge>
                </td>
                <td>
                  {a.statut !== 'cloturee' && (
                    <Button variant="ghost" onClick={() => cloturer(a)}>
                      Clôturer
                    </Button>
                  )}
                </td>
              </tr>
            ))}
            {admissions.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>
                Aucune admission
              </td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
