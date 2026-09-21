import { useState } from 'react'
import { ShieldAlert, Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'

/* ============================================================================
   WIR143 — Écran P1 « Discipline » (NTEDU27). Workflow
   ouvert → en_traitement → clos passe TOUJOURS par les actions serveur
   dédiées — jamais un PATCH statut direct. La notification parent est
   déclenchée côté serveur à la création (signals).
   ========================================================================== */

const TYPES = [
  { value: 'retard', label: 'Retard' },
  { value: 'comportement', label: 'Comportement' },
  { value: 'absence_injustifiee', label: 'Absence injustifiée' },
  { value: 'autre', label: 'Autre' },
]
const GRAVITES = [
  { value: 'mineur', label: 'Mineur' },
  { value: 'moyen', label: 'Moyen' },
  { value: 'majeur', label: 'Majeur' },
]
const STATUT_TONE = { ouvert: 'warning', en_traitement: 'neutral', clos: 'success' }

export default function DisciplinePage() {
  const { data: incidents, loading, reload } = useEducationResource(educationApi.incidents.list)
  const { data: eleves } = useEducationResource(educationApi.eleves.list)

  const [form, setForm] = useState({
    eleve: '', date: '', type: 'comportement', gravite: 'mineur', description: '',
  })
  const [saving, setSaving] = useState(false)

  const eleveNom = (id) => {
    const e = eleves.find((x) => x.id === Number(id))
    return e ? `${e.nom} ${e.prenom}` : `Élève #${id}`
  }

  const creer = async (e) => {
    e.preventDefault()
    if (!form.eleve || !form.date) return
    setSaving(true)
    try {
      await educationApi.incidents.create(form)
      toast.success('Incident signalé.')
      setForm({ eleve: '', date: '', type: 'comportement', gravite: 'mineur', description: '' })
      reload()
    } catch {
      toast.error("Impossible de signaler l'incident.")
    } finally {
      setSaving(false)
    }
  }

  const agir = async (action, incident) => {
    try {
      if (action === 'demarrer') await educationApi.incidents.demarrerTraitement(incident.id)
      else if (action === 'cloturer') await educationApi.incidents.cloturer(incident.id)
      reload()
    } catch {
      toast.error('Action impossible.')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <ShieldAlert size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Discipline</h1>
      </div>

      <form onSubmit={creer} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select value={form.eleve} onChange={(e) => setForm({ ...form, eleve: e.target.value })} aria-label="Élève">
          <option value="">Élève…</option>
          {eleves.map((el) => <option key={el.id} value={el.id}>{el.nom} {el.prenom}</option>)}
        </select>
        <input type="date" value={form.date}
          onChange={(e) => setForm({ ...form, date: e.target.value })} aria-label="Date de l'incident" />
        <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} aria-label="Type d'incident">
          {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <select value={form.gravite} onChange={(e) => setForm({ ...form, gravite: e.target.value })} aria-label="Gravité">
          {GRAVITES.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
        </select>
        <input placeholder="Description" value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })} aria-label="Description de l'incident" />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Signaler</Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr><th>Élève</th><th>Date</th><th>Type</th><th>Gravité</th><th>Statut</th><th /></tr></thead>
          <tbody>
            {incidents.map((i) => (
              <tr key={i.id}>
                <td>{eleveNom(i.eleve)}</td>
                <td>{i.date}</td>
                <td>{TYPES.find((t) => t.value === i.type)?.label || i.type}</td>
                <td>{GRAVITES.find((g) => g.value === i.gravite)?.label || i.gravite}</td>
                <td><Badge tone={STATUT_TONE[i.statut] || 'neutral'}>{i.statut}</Badge></td>
                <td style={{ display: 'flex', gap: 4 }}>
                  {i.statut === 'ouvert' && (
                    <Button variant="ghost" onClick={() => agir('demarrer', i)}>Démarrer traitement</Button>
                  )}
                  {i.statut === 'en_traitement' && (
                    <Button variant="ghost" onClick={() => agir('cloturer', i)}>Clôturer</Button>
                  )}
                </td>
              </tr>
            ))}
            {incidents.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>Aucun incident</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
