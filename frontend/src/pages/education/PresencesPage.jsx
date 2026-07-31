import { useMemo, useState } from 'react'
import { CalendarCheck, Plus, Save } from 'lucide-react'
import { Button, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'

/* ============================================================================
   WIR143 — Écran P1 « Présences » (NTEDU12). Saisie BULK pour une classe
   entière EN UN SEUL appel API (`presences.bulkSaisie`) — jamais un appel par
   élève. Upsert (create/update) par (séance, élève) côté serveur : rejouer
   la saisie est sans effet de bord supplémentaire.
   ========================================================================== */

const STATUTS = [
  { value: 'present', label: 'Présent' },
  { value: 'absent', label: 'Absent' },
  { value: 'retard', label: 'Retard' },
  { value: 'excuse', label: 'Excusé' },
]

export default function PresencesPage() {
  const { data: seances, loading: loadingSeances, reload: reloadSeances } =
    useEducationResource(educationApi.seances.list)
  const { data: classes } = useEducationResource(educationApi.classes.list)
  const { data: eleves } = useEducationResource(educationApi.eleves.list)

  const [seanceForm, setSeanceForm] = useState({
    classe: '', matiere: '', date: '', heure_debut: '', heure_fin: '',
  })
  const [seanceChoisie, setSeanceChoisie] = useState('')
  const [statuts, setStatuts] = useState({})
  const [saving, setSaving] = useState(false)

  const seance = useMemo(
    () => seances.find((s) => String(s.id) === String(seanceChoisie)),
    [seances, seanceChoisie],
  )
  const roster = useMemo(
    () => (seance ? eleves.filter((el) => String(el.classe) === String(seance.classe)) : []),
    [eleves, seance],
  )

  const creerSeance = async (e) => {
    e.preventDefault()
    if (!seanceForm.classe || !seanceForm.matiere.trim() || !seanceForm.date) return
    setSaving(true)
    try {
      const res = await educationApi.seances.create(seanceForm)
      toast.success('Séance créée.')
      setSeanceForm({ classe: seanceForm.classe, matiere: '', date: '', heure_debut: '', heure_fin: '' })
      reloadSeances()
      setSeanceChoisie(String(res.data.id))
    } catch {
      toast.error('Impossible de créer la séance.')
    } finally {
      setSaving(false)
    }
  }

  const enregistrerPresences = async () => {
    if (!seanceChoisie || roster.length === 0) return
    setSaving(true)
    try {
      const presences = roster.map((el) => ({
        eleve: el.id, statut: statuts[el.id] || 'present',
      }))
      await educationApi.presences.bulkSaisie(seanceChoisie, presences)
      toast.success('Présences enregistrées.')
    } catch {
      toast.error("Impossible d'enregistrer les présences.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <CalendarCheck size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Présences</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Nouvelle séance</h2>
      <form onSubmit={creerSeance} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select value={seanceForm.classe} onChange={(e) => setSeanceForm({ ...seanceForm, classe: e.target.value })} aria-label="Classe">
          <option value="">Classe…</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
        <input placeholder="Matière" value={seanceForm.matiere}
          onChange={(e) => setSeanceForm({ ...seanceForm, matiere: e.target.value })} aria-label="Matière" />
        <input type="date" value={seanceForm.date}
          onChange={(e) => setSeanceForm({ ...seanceForm, date: e.target.value })} aria-label="Date de la séance" />
        <input type="time" value={seanceForm.heure_debut}
          onChange={(e) => setSeanceForm({ ...seanceForm, heure_debut: e.target.value })} aria-label="Heure de début" />
        <input type="time" value={seanceForm.heure_fin}
          onChange={(e) => setSeanceForm({ ...seanceForm, heure_fin: e.target.value })} aria-label="Heure de fin" />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Créer</Button>
      </form>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Saisie des présences</h2>
      {loadingSeances ? <p>Chargement…</p> : (
        <select value={seanceChoisie} onChange={(e) => setSeanceChoisie(e.target.value)} aria-label="Séance" style={{ marginBottom: 12 }}>
          <option value="">Séance…</option>
          {seances.map((s) => (
            <option key={s.id} value={s.id}>
              {s.date} — {s.matiere} ({classes.find((c) => c.id === s.classe)?.nom || `Classe #${s.classe}`})
            </option>
          ))}
        </select>
      )}

      {seance && (
        <>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 12 }}>
            <thead><tr><th>Élève</th><th>Statut</th></tr></thead>
            <tbody>
              {roster.map((el) => (
                <tr key={el.id}>
                  <td>{el.nom} {el.prenom}</td>
                  <td>
                    <select
                      value={statuts[el.id] || 'present'}
                      onChange={(e) => setStatuts({ ...statuts, [el.id]: e.target.value })}
                      aria-label={`Statut de ${el.nom} ${el.prenom}`}
                    >
                      {STATUTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
              {roster.length === 0 && (
                <tr><td colSpan={2} style={{ textAlign: 'center', color: '#64748b' }}>Aucun élève dans cette classe</td></tr>
              )}
            </tbody>
          </table>
          <Button onClick={enregistrerPresences} disabled={saving || roster.length === 0}>
            <Save size={16} strokeWidth={1.75} aria-hidden="true" /> Enregistrer les présences
          </Button>
        </>
      )}
    </div>
  )
}
