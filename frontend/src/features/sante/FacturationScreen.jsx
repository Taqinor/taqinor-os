import { useEffect, useMemo, useState } from 'react'
import { Receipt, Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import santeApi from '../../api/santeApi'
import { formatDate } from '../../lib/format'

/* ============================================================================
   WIR142 — Écran d'administration « Facturation santé » (NTSAN13/NTSAN15).
   Créer une facture agrège des ActeRealise non facturés d'une admission
   (jamais de ligne libre) ; le split tiers payant/patient et le montant dû
   sont TOUJOURS calculés côté serveur.
   ========================================================================== */

const PAIEMENT_MODES = [
  { value: 'especes', label: 'Espèces' },
  { value: 'carte', label: 'Carte' },
  { value: 'cheque', label: 'Chèque' },
  { value: 'virement', label: 'Virement' },
  { value: 'tiers_payant', label: 'Tiers payant' },
]

export default function FacturationScreen() {
  const [factures, setFactures] = useState([])
  const [admissions, setAdmissions] = useState([])
  const [actesNonFactures, setActesNonFactures] = useState([])
  const [patients, setPatients] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [admissionChoisie, setAdmissionChoisie] = useState('')
  const [actesChoisis, setActesChoisis] = useState([])
  const [paiementForm, setPaiementForm] = useState({ facture_sante: '', montant: '', mode: 'especes' })

  const load = () => {
    setLoading(true)
    Promise.all([
      santeApi.facturesSante.list(),
      santeApi.admissions.list(),
      santeApi.actesRealises.list(),
      santeApi.patients.list(),
    ])
      .then(([factRes, admRes, reaRes, patRes]) => {
        setFactures(factRes.data?.results ?? factRes.data ?? [])
        setAdmissions(admRes.data?.results ?? admRes.data ?? [])
        setActesNonFactures((reaRes.data?.results ?? reaRes.data ?? []).filter((a) => !a.facture_sante))
        setPatients(patRes.data?.results ?? patRes.data ?? [])
      })
      .catch(() => toast.error('Impossible de charger la facturation.'))
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

  const actesDeLAdmission = useMemo(
    () => actesNonFactures.filter((a) => String(a.admission) === String(admissionChoisie)),
    [actesNonFactures, admissionChoisie],
  )

  const toggleActe = (id) => {
    setActesChoisis((prev) => (
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    ))
  }

  const creerFacture = async (e) => {
    e.preventDefault()
    if (!admissionChoisie || actesChoisis.length === 0) return
    setSaving(true)
    try {
      await santeApi.facturesSante.create({
        admission: admissionChoisie, actes_realises: actesChoisis,
      })
      toast.success('Facture créée.')
      setAdmissionChoisie('')
      setActesChoisis([])
      load()
    } catch {
      toast.error('Impossible de créer la facture.')
    } finally {
      setSaving(false)
    }
  }

  const encaisser = async (e) => {
    e.preventDefault()
    if (!paiementForm.facture_sante || !paiementForm.montant) return
    setSaving(true)
    try {
      await santeApi.paiementsSante.create({
        ...paiementForm, date_paiement: new Date().toISOString(),
      })
      toast.success('Paiement enregistré.')
      setPaiementForm({ facture_sante: '', montant: '', mode: 'especes' })
      load()
    } catch {
      toast.error("Impossible d'enregistrer le paiement.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Receipt size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Facturation santé</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Nouvelle facture</h2>
      <form onSubmit={creerFacture} style={{ marginBottom: 24 }}>
        <select
          value={admissionChoisie}
          onChange={(e) => { setAdmissionChoisie(e.target.value); setActesChoisis([]) }}
          aria-label="Admission à facturer"
          style={{ marginBottom: 8 }}
        >
          <option value="">Admission…</option>
          {admissions.map((a) => (
            <option key={a.id} value={a.id}>#{a.id} — {patientNom(a.patient)}</option>
          ))}
        </select>

        {admissionChoisie && (
          <div style={{ marginBottom: 8 }}>
            {actesDeLAdmission.length === 0 && (
              <p style={{ color: '#64748b' }}>Aucun acte non facturé pour cette admission.</p>
            )}
            {actesDeLAdmission.map((a) => (
              <label key={a.id} style={{ display: 'block' }}>
                <input
                  type="checkbox"
                  checked={actesChoisis.includes(a.id)}
                  onChange={() => toggleActe(a.id)}
                />{' '}
                Acte #{a.acte} — {a.tarif_applique_ttc} TTC
              </label>
            ))}
          </div>
        )}

        <Button type="submit" disabled={saving || !admissionChoisie || actesChoisis.length === 0}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Créer la facture
        </Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 24 }}>
          <thead>
            <tr>
              <th>Patient</th><th>Total TTC</th><th>Part patient</th>
              <th>Montant dû</th><th>Statut</th><th>Émise le</th>
            </tr>
          </thead>
          <tbody>
            {factures.map((f) => (
              <tr key={f.id}>
                <td>{patientNom(f.patient)}</td>
                <td>{f.total_ttc}</td>
                <td>{f.part_patient_ttc}</td>
                <td>{f.montant_du}</td>
                <td><Badge tone={f.statut === 'payee' ? 'success' : 'neutral'}>{f.statut_display || f.statut}</Badge></td>
                <td>{f.date_emission ? formatDate(f.date_emission) : '—'}</td>
              </tr>
            ))}
            {factures.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>Aucune facture</td></tr>
            )}
          </tbody>
        </table>
      )}

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Encaissement</h2>
      <form onSubmit={encaisser} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <select
          value={paiementForm.facture_sante}
          onChange={(e) => setPaiementForm({ ...paiementForm, facture_sante: e.target.value })}
          aria-label="Facture à encaisser"
        >
          <option value="">Facture…</option>
          {factures.map((f) => (
            <option key={f.id} value={f.id}>#{f.id} — {patientNom(f.patient)} (dû {f.montant_du})</option>
          ))}
        </select>
        <input
          type="number" step="any"
          placeholder="Montant"
          value={paiementForm.montant}
          onChange={(e) => setPaiementForm({ ...paiementForm, montant: e.target.value })}
          aria-label="Montant du paiement"
        />
        <select
          value={paiementForm.mode}
          onChange={(e) => setPaiementForm({ ...paiementForm, mode: e.target.value })}
          aria-label="Mode de paiement"
        >
          {PAIEMENT_MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
        <Button type="submit" disabled={saving}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Encaisser
        </Button>
      </form>
    </div>
  )
}
