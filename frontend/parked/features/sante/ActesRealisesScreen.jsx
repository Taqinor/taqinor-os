import { useEffect, useState } from 'react'
import { Stethoscope, Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import santeApi from '../../api/santeApi'
import { formatDate } from '../../lib/format'

/* ============================================================================
   WIR142 — Écran d'administration « Actes réalisés » (NTSAN10). Le tarif
   appliqué (`tarif_applique_ttc`) est TOUJOURS calculé côté serveur
   (`services.realiser_acte`) — jamais envoyé depuis ce formulaire.
   ========================================================================== */

const CHAMPS_VIDES = {
  admission: '', patient: '', praticien: '', acte: '', quantite: '1',
}

export default function ActesRealisesScreen() {
  const [realises, setRealises] = useState([])
  const [admissions, setAdmissions] = useState([])
  const [patients, setPatients] = useState([])
  const [praticiens, setPraticiens] = useState([])
  const [actes, setActes] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(CHAMPS_VIDES)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      santeApi.actesRealises.list(),
      santeApi.admissions.list(),
      santeApi.patients.list(),
      santeApi.praticiens.list(),
      santeApi.actesMedicaux.list(),
    ])
      .then(([reaRes, admRes, patRes, praRes, acteRes]) => {
        setRealises(reaRes.data?.results ?? reaRes.data ?? [])
        setAdmissions(admRes.data?.results ?? admRes.data ?? [])
        setPatients(patRes.data?.results ?? patRes.data ?? [])
        setPraticiens(praRes.data?.results ?? praRes.data ?? [])
        setActes(acteRes.data?.results ?? acteRes.data ?? [])
      })
      .catch(() => toast.error('Impossible de charger les actes réalisés.'))
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
  const acteNom = (id) => {
    const a = actes.find((x) => x.id === Number(id))
    return a ? a.libelle : `Acte #${id}`
  }

  const enregistrer = async (e) => {
    e.preventDefault()
    if (!form.admission || !form.patient || !form.praticien || !form.acte) return
    setSaving(true)
    try {
      await santeApi.actesRealises.create({
        admission: form.admission, patient: form.patient,
        praticien: form.praticien, acte: form.acte,
        date_realisation: new Date().toISOString(),
        quantite: form.quantite,
      })
      toast.success('Acte enregistré.')
      setForm(CHAMPS_VIDES)
      load()
    } catch {
      toast.error("Impossible d'enregistrer cet acte.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Stethoscope size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Actes réalisés</h1>
      </div>

      <form onSubmit={enregistrer} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select
          value={form.admission}
          onChange={(e) => setForm({ ...form, admission: e.target.value })}
          aria-label="Admission"
        >
          <option value="">Admission…</option>
          {admissions.map((a) => (
            <option key={a.id} value={a.id}>#{a.id} — {patientNom(a.patient)}</option>
          ))}
        </select>
        <select
          value={form.patient}
          onChange={(e) => setForm({ ...form, patient: e.target.value })}
          aria-label="Patient"
        >
          <option value="">Patient…</option>
          {patients.map((p) => <option key={p.id} value={p.id}>{p.nom} {p.prenom}</option>)}
        </select>
        <select
          value={form.praticien}
          onChange={(e) => setForm({ ...form, praticien: e.target.value })}
          aria-label="Praticien"
        >
          <option value="">Praticien…</option>
          {praticiens.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
        </select>
        <select
          value={form.acte}
          onChange={(e) => setForm({ ...form, acte: e.target.value })}
          aria-label="Acte médical"
        >
          <option value="">Acte…</option>
          {actes.map((a) => <option key={a.id} value={a.id}>{a.libelle}</option>)}
        </select>
        <input
          type="number" min="1"
          value={form.quantite}
          onChange={(e) => setForm({ ...form, quantite: e.target.value })}
          aria-label="Quantité"
          style={{ width: 70 }}
        />
        <Button type="submit" disabled={saving}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Enregistrer
        </Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th>Patient</th><th>Praticien</th><th>Acte</th><th>Date</th>
              <th>Qté</th><th>Tarif appliqué TTC</th><th>Facturé</th>
            </tr>
          </thead>
          <tbody>
            {realises.map((r) => (
              <tr key={r.id}>
                <td>{patientNom(r.patient)}</td>
                <td>{praticienNom(r.praticien)}</td>
                <td>{acteNom(r.acte)}</td>
                <td>{formatDate(r.date_realisation)}</td>
                <td>{r.quantite}</td>
                <td>{r.tarif_applique_ttc}</td>
                <td>
                  <Badge tone={r.facture_sante ? 'success' : 'neutral'}>
                    {r.facture_sante ? 'Facturé' : 'Non facturé'}
                  </Badge>
                </td>
              </tr>
            ))}
            {realises.length === 0 && (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: '#64748b' }}>Aucun acte réalisé</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
