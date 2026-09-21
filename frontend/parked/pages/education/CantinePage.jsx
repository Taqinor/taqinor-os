import { useState } from 'react'
import { Utensils, Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'

/* ============================================================================
   WIR143 — Écran P1 « Cantine » (NTEDU25). Menus du jour + inscriptions
   cantine (jours de la semaine libres, ex. `["lundi", "mercredi"]`).
   ========================================================================== */

const JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi']

export default function CantinePage() {
  const { data: menus, loading: loadingMenus, reload: reloadMenus } =
    useEducationResource(educationApi.menusCantine.list)
  const { data: inscriptions, loading: loadingInscriptions, reload: reloadInscriptions } =
    useEducationResource(educationApi.inscriptionsCantine.list)
  const { data: eleves } = useEducationResource(educationApi.eleves.list)

  const [menuForm, setMenuForm] = useState({ date: '', description: '', allergenes: '' })
  const [inscriptionForm, setInscriptionForm] = useState({ eleve: '', date_debut: '', jours_semaine: [] })
  const [saving, setSaving] = useState(false)

  const eleveNom = (id) => {
    const e = eleves.find((x) => x.id === Number(id))
    return e ? `${e.nom} ${e.prenom}` : `Élève #${id}`
  }

  const toggleJour = (jour) => {
    setInscriptionForm((prev) => ({
      ...prev,
      jours_semaine: prev.jours_semaine.includes(jour)
        ? prev.jours_semaine.filter((j) => j !== jour)
        : [...prev.jours_semaine, jour],
    }))
  }

  const creerMenu = async (e) => {
    e.preventDefault()
    if (!menuForm.date || !menuForm.description.trim()) return
    setSaving(true)
    try {
      await educationApi.menusCantine.create({
        date: menuForm.date, description: menuForm.description,
        allergenes: menuForm.allergenes
          ? menuForm.allergenes.split(',').map((a) => a.trim()).filter(Boolean)
          : [],
      })
      toast.success('Menu créé.')
      setMenuForm({ date: '', description: '', allergenes: '' })
      reloadMenus()
    } catch {
      toast.error('Impossible de créer le menu (un menu existe peut-être déjà pour ce jour).')
    } finally {
      setSaving(false)
    }
  }

  const creerInscription = async (e) => {
    e.preventDefault()
    if (!inscriptionForm.eleve || !inscriptionForm.date_debut || inscriptionForm.jours_semaine.length === 0) return
    setSaving(true)
    try {
      await educationApi.inscriptionsCantine.create(inscriptionForm)
      toast.success('Inscription cantine créée.')
      setInscriptionForm({ eleve: '', date_debut: '', jours_semaine: [] })
      reloadInscriptions()
    } catch {
      toast.error("Impossible de créer l'inscription cantine.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Utensils size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Cantine</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Menus</h2>
      <form onSubmit={creerMenu} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <input type="date" value={menuForm.date}
          onChange={(e) => setMenuForm({ ...menuForm, date: e.target.value })} aria-label="Date du menu" />
        <input placeholder="Description" value={menuForm.description}
          onChange={(e) => setMenuForm({ ...menuForm, description: e.target.value })} aria-label="Description du menu" />
        <input placeholder="Allergènes (séparés par ,)" value={menuForm.allergenes}
          onChange={(e) => setMenuForm({ ...menuForm, allergenes: e.target.value })} aria-label="Allergènes" />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
      </form>
      {loadingMenus ? <p>Chargement…</p> : (
        <ul style={{ marginBottom: 24 }}>
          {menus.map((m) => (
            <li key={m.id}>{m.date} — {m.description} {(m.allergenes || []).length > 0 && `(allergènes : ${m.allergenes.join(', ')})`}</li>
          ))}
          {menus.length === 0 && <li style={{ color: '#64748b', listStyle: 'none' }}>Aucun menu</li>}
        </ul>
      )}

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Inscriptions cantine</h2>
      <form onSubmit={creerInscription} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={inscriptionForm.eleve} onChange={(e) => setInscriptionForm({ ...inscriptionForm, eleve: e.target.value })} aria-label="Élève">
          <option value="">Élève…</option>
          {eleves.map((el) => <option key={el.id} value={el.id}>{el.nom} {el.prenom}</option>)}
        </select>
        <input type="date" value={inscriptionForm.date_debut}
          onChange={(e) => setInscriptionForm({ ...inscriptionForm, date_debut: e.target.value })} aria-label="Date de début" />
        {JOURS.map((jour) => (
          <label key={jour} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <input type="checkbox" checked={inscriptionForm.jours_semaine.includes(jour)} onChange={() => toggleJour(jour)} />
            {jour}
          </label>
        ))}
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
      </form>
      {loadingInscriptions ? <p>Chargement…</p> : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr><th>Élève</th><th>Depuis</th><th>Jours</th><th>Statut</th></tr></thead>
          <tbody>
            {inscriptions.map((i) => (
              <tr key={i.id}>
                <td>{eleveNom(i.eleve)}</td>
                <td>{i.date_debut}</td>
                <td>{(i.jours_semaine || []).join(', ')}</td>
                <td><Badge tone={i.actif ? 'success' : 'neutral'}>{i.actif ? 'Actif' : 'Inactif'}</Badge></td>
              </tr>
            ))}
            {inscriptions.length === 0 && (
              <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>Aucune inscription cantine</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
