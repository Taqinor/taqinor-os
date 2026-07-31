import { useMemo, useState } from 'react'
import { GraduationCap, Plus, Save } from 'lucide-react'
import { Button, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'

/* ============================================================================
   WIR143 — Écran P1 « Notes » (NTEDU15). Saisie BULK pour une évaluation
   entière EN UN SEUL appel API (`notes.bulkSaisie`) — jamais un appel par
   élève. Upsert (create/update) par (évaluation, élève) côté serveur.
   ========================================================================== */

const TYPES = [
  { value: 'controle', label: 'Contrôle' },
  { value: 'examen', label: 'Examen' },
  { value: 'devoir', label: 'Devoir' },
]

export default function NotesPage() {
  const { data: evaluations, loading: loadingEvaluations, reload: reloadEvaluations } =
    useEducationResource(educationApi.evaluations.list)
  const { data: matieresClasse } = useEducationResource(educationApi.matieresClasse.list)
  const { data: eleves } = useEducationResource(educationApi.eleves.list)

  const [evalForm, setEvalForm] = useState({
    matiere_classe: '', type: 'controle', date: '', bareme: '20',
  })
  const [evaluationChoisie, setEvaluationChoisie] = useState('')
  const [valeurs, setValeurs] = useState({})
  const [saving, setSaving] = useState(false)

  const evaluation = useMemo(
    () => evaluations.find((e) => String(e.id) === String(evaluationChoisie)),
    [evaluations, evaluationChoisie],
  )
  const matiereClasseChoisie = useMemo(
    () => matieresClasse.find((mc) => mc.id === evaluation?.matiere_classe),
    [matieresClasse, evaluation],
  )
  const roster = useMemo(
    () => (matiereClasseChoisie
      ? eleves.filter((el) => String(el.classe) === String(matiereClasseChoisie.classe))
      : []),
    [eleves, matiereClasseChoisie],
  )

  const creerEvaluation = async (e) => {
    e.preventDefault()
    if (!evalForm.matiere_classe || !evalForm.date) return
    setSaving(true)
    try {
      const res = await educationApi.evaluations.create(evalForm)
      toast.success('Évaluation créée.')
      setEvalForm({ matiere_classe: evalForm.matiere_classe, type: 'controle', date: '', bareme: '20' })
      reloadEvaluations()
      setEvaluationChoisie(String(res.data.id))
    } catch {
      toast.error("Impossible de créer l'évaluation.")
    } finally {
      setSaving(false)
    }
  }

  const enregistrerNotes = async () => {
    if (!evaluationChoisie || roster.length === 0) return
    setSaving(true)
    try {
      const notes = roster.map((el) => ({
        eleve: el.id, valeur: valeurs[el.id] !== undefined && valeurs[el.id] !== '' ? valeurs[el.id] : null,
      }))
      await educationApi.notes.bulkSaisie(evaluationChoisie, notes)
      toast.success('Notes enregistrées.')
    } catch {
      toast.error("Impossible d'enregistrer les notes.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <GraduationCap size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Notes</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Nouvelle évaluation</h2>
      <form onSubmit={creerEvaluation} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select value={evalForm.matiere_classe}
          onChange={(e) => setEvalForm({ ...evalForm, matiere_classe: e.target.value })}
          aria-label="Matière de classe">
          <option value="">Matière de classe…</option>
          {matieresClasse.map((mc) => (
            <option key={mc.id} value={mc.id}>{mc.matiere_nom || `Matière #${mc.matiere}`}</option>
          ))}
        </select>
        <select value={evalForm.type} onChange={(e) => setEvalForm({ ...evalForm, type: e.target.value })} aria-label="Type d'évaluation">
          {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <input type="date" value={evalForm.date}
          onChange={(e) => setEvalForm({ ...evalForm, date: e.target.value })} aria-label="Date de l'évaluation" />
        <input type="number" min="1" value={evalForm.bareme}
          onChange={(e) => setEvalForm({ ...evalForm, bareme: e.target.value })} aria-label="Barème" style={{ width: 70 }} />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Créer</Button>
      </form>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Saisie des notes</h2>
      {loadingEvaluations ? <p>Chargement…</p> : (
        <select value={evaluationChoisie} onChange={(e) => setEvaluationChoisie(e.target.value)} aria-label="Évaluation" style={{ marginBottom: 12 }}>
          <option value="">Évaluation…</option>
          {evaluations.map((e) => (
            <option key={e.id} value={e.id}>{e.date} — {e.type} (/{e.bareme})</option>
          ))}
        </select>
      )}

      {evaluation && (
        <>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 12 }}>
            <thead><tr><th>Élève</th><th>Note (/{evaluation.bareme})</th></tr></thead>
            <tbody>
              {roster.map((el) => (
                <tr key={el.id}>
                  <td>{el.nom} {el.prenom}</td>
                  <td>
                    <input
                      type="number" step="any" min="0" max={evaluation.bareme}
                      value={valeurs[el.id] ?? ''}
                      onChange={(e) => setValeurs({ ...valeurs, [el.id]: e.target.value })}
                      aria-label={`Note de ${el.nom} ${el.prenom}`}
                      style={{ width: 80 }}
                    />
                  </td>
                </tr>
              ))}
              {roster.length === 0 && (
                <tr><td colSpan={2} style={{ textAlign: 'center', color: '#64748b' }}>Aucun élève dans cette classe</td></tr>
              )}
            </tbody>
          </table>
          <Button onClick={enregistrerNotes} disabled={saving || roster.length === 0}>
            <Save size={16} strokeWidth={1.75} aria-hidden="true" /> Enregistrer les notes
          </Button>
        </>
      )}
    </div>
  )
}
