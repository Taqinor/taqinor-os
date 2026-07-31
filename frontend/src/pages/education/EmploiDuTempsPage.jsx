import { useMemo, useState } from 'react'
import { CalendarDays, Plus } from 'lucide-react'
import { Button, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'

/* ============================================================================
   WIR143 — Écran P1 « Emploi du temps » (NTEDU21). Un conflit
   (classe/enseignant/salle sur un créneau qui chevauche déjà un créneau
   actif) est REJETÉ EN 400 EXPLICITE par le serveur — le formulaire relaie
   simplement le message d'erreur, jamais de contournement côté client.
   ========================================================================== */

const JOURS = [
  { value: '0', label: 'Lundi' }, { value: '1', label: 'Mardi' },
  { value: '2', label: 'Mercredi' }, { value: '3', label: 'Jeudi' },
  { value: '4', label: 'Vendredi' }, { value: '5', label: 'Samedi' },
  { value: '6', label: 'Dimanche' },
]
const JOUR_LABEL = Object.fromEntries(JOURS.map((j) => [j.value, j.label]))

export default function EmploiDuTempsPage() {
  const { data: classes } = useEducationResource(educationApi.classes.list)
  const { data: matieresClasse } = useEducationResource(educationApi.matieresClasse.list)
  const [classeChoisie, setClasseChoisie] = useState('')
  const { data: creneaux, loading, reload } = useEducationResource(
    educationApi.emploiDuTemps.list,
    classeChoisie ? { classe: classeChoisie } : {},
    [classeChoisie],
  )

  const [form, setForm] = useState({
    matiere_classe: '', jour_semaine: '0', heure_debut: '', heure_fin: '', salle: '',
  })
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const matieresDeLaClasse = useMemo(
    () => matieresClasse.filter((mc) => String(mc.classe) === String(classeChoisie)),
    [matieresClasse, classeChoisie],
  )

  const creer = async (e) => {
    e.preventDefault()
    if (!classeChoisie || !form.matiere_classe || !form.heure_debut || !form.heure_fin) return
    setSaving(true)
    setServerError(null)
    try {
      await educationApi.emploiDuTemps.create({ ...form, classe: classeChoisie })
      toast.success('Créneau ajouté.')
      setForm({ matiere_classe: '', jour_semaine: '0', heure_debut: '', heure_fin: '', salle: '' })
      reload()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || (typeof data === 'string' ? data : "Conflit d'horaire — impossible d'ajouter ce créneau."))
    } finally {
      setSaving(false)
    }
  }

  const supprimer = async (creneau) => {
    try {
      await educationApi.emploiDuTemps.remove(creneau.id)
      toast.success('Créneau supprimé.')
      reload()
    } catch {
      toast.error('Impossible de supprimer ce créneau.')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <CalendarDays size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Emploi du temps</h1>
      </div>

      <select value={classeChoisie} onChange={(e) => setClasseChoisie(e.target.value)} aria-label="Classe" style={{ marginBottom: 16 }}>
        <option value="">Classe…</option>
        {classes.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
      </select>

      {classeChoisie && (
        <>
          <form onSubmit={creer} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            <select value={form.matiere_classe} onChange={(e) => setForm({ ...form, matiere_classe: e.target.value })} aria-label="Matière">
              <option value="">Matière…</option>
              {matieresDeLaClasse.map((mc) => (
                <option key={mc.id} value={mc.id}>{mc.matiere_nom || `Matière #${mc.matiere}`}</option>
              ))}
            </select>
            <select value={form.jour_semaine} onChange={(e) => setForm({ ...form, jour_semaine: e.target.value })} aria-label="Jour de la semaine">
              {JOURS.map((j) => <option key={j.value} value={j.value}>{j.label}</option>)}
            </select>
            <input type="time" value={form.heure_debut}
              onChange={(e) => setForm({ ...form, heure_debut: e.target.value })} aria-label="Heure de début" />
            <input type="time" value={form.heure_fin}
              onChange={(e) => setForm({ ...form, heure_fin: e.target.value })} aria-label="Heure de fin" />
            <input placeholder="Salle" value={form.salle}
              onChange={(e) => setForm({ ...form, salle: e.target.value })} aria-label="Salle" style={{ width: 90 }} />
            <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
          </form>
          {serverError && <p role="alert" style={{ color: '#dc2626', marginBottom: 12 }}>{serverError}</p>}

          {loading ? <p>Chargement…</p> : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr><th>Jour</th><th>Horaire</th><th>Matière</th><th>Salle</th><th /></tr></thead>
              <tbody>
                {creneaux.map((c) => (
                  <tr key={c.id}>
                    <td>{JOUR_LABEL[String(c.jour_semaine)] || c.jour_semaine}</td>
                    <td>{c.heure_debut}–{c.heure_fin}</td>
                    <td>{matieresClasse.find((mc) => mc.id === c.matiere_classe)?.matiere_nom || `#${c.matiere_classe}`}</td>
                    <td>{c.salle || '—'}</td>
                    <td><Button variant="ghost" onClick={() => supprimer(c)}>Supprimer</Button></td>
                  </tr>
                ))}
                {creneaux.length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>Aucun créneau</td></tr>
                )}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  )
}
