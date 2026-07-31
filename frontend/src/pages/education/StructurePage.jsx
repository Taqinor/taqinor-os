import { useState } from 'react'
import { School, Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'

/* ============================================================================
   WIR143 — Écran P1 « Structure » (NTEDU1) : année scolaire / niveau / classe.
   Trois listes minimales — une classe affiche son effectif courant vs
   `capacite_max` (propriété calculée côté serveur).
   ========================================================================== */

const CYCLES = [
  { value: 'prescolaire', label: 'Préscolaire' },
  { value: 'primaire', label: 'Primaire' },
  { value: 'college', label: 'Collège' },
  { value: 'lycee', label: 'Lycée' },
  { value: 'formation', label: 'Formation' },
]

export default function StructurePage() {
  const { data: annees, loading: loadingAnnees, reload: reloadAnnees } =
    useEducationResource(educationApi.anneesScolaires.list)
  const { data: niveaux, loading: loadingNiveaux, reload: reloadNiveaux } =
    useEducationResource(educationApi.niveaux.list)
  const { data: classes, loading: loadingClasses, reload: reloadClasses } =
    useEducationResource(educationApi.classes.list)

  const [anneeForm, setAnneeForm] = useState({ libelle: '', date_debut: '', date_fin: '' })
  const [niveauForm, setNiveauForm] = useState({ nom: '', cycle: 'primaire', ordre: '1' })
  const [classeForm, setClasseForm] = useState({ annee_scolaire: '', niveau: '', nom: '', capacite_max: '30' })
  const [saving, setSaving] = useState(false)

  const niveauNom = (id) => niveaux.find((n) => n.id === Number(id))?.nom || `Niveau #${id}`

  const creerAnnee = async (e) => {
    e.preventDefault()
    if (!anneeForm.libelle.trim()) return
    setSaving(true)
    try {
      await educationApi.anneesScolaires.create(anneeForm)
      toast.success('Année scolaire créée.')
      setAnneeForm({ libelle: '', date_debut: '', date_fin: '' })
      reloadAnnees()
    } catch {
      toast.error("Impossible de créer l'année scolaire.")
    } finally {
      setSaving(false)
    }
  }

  const creerNiveau = async (e) => {
    e.preventDefault()
    if (!niveauForm.nom.trim()) return
    setSaving(true)
    try {
      await educationApi.niveaux.create(niveauForm)
      toast.success('Niveau créé.')
      setNiveauForm({ nom: '', cycle: 'primaire', ordre: '1' })
      reloadNiveaux()
    } catch {
      toast.error('Impossible de créer le niveau.')
    } finally {
      setSaving(false)
    }
  }

  const creerClasse = async (e) => {
    e.preventDefault()
    if (!classeForm.annee_scolaire || !classeForm.niveau || !classeForm.nom.trim()) return
    setSaving(true)
    try {
      await educationApi.classes.create(classeForm)
      toast.success('Classe créée.')
      setClasseForm({ annee_scolaire: classeForm.annee_scolaire, niveau: '', nom: '', capacite_max: '30' })
      reloadClasses()
    } catch {
      toast.error('Impossible de créer la classe.')
    } finally {
      setSaving(false)
    }
  }

  const exporterClasse = async (classe) => {
    try {
      const res = await educationApi.classes.export(classe.id, 'xlsx')
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `classe-${classe.id}.xlsx`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      toast.error("Impossible d'exporter la classe.")
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <School size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Structure de l&apos;établissement</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Années scolaires</h2>
      <form onSubmit={creerAnnee} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <input placeholder="Libellé (ex. 2026-2027)" value={anneeForm.libelle}
          onChange={(e) => setAnneeForm({ ...anneeForm, libelle: e.target.value })}
          aria-label="Libellé de l'année scolaire" />
        <input type="date" value={anneeForm.date_debut}
          onChange={(e) => setAnneeForm({ ...anneeForm, date_debut: e.target.value })}
          aria-label="Date de début" />
        <input type="date" value={anneeForm.date_fin}
          onChange={(e) => setAnneeForm({ ...anneeForm, date_fin: e.target.value })}
          aria-label="Date de fin" />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
      </form>
      {loadingAnnees ? <p>Chargement…</p> : (
        <ul style={{ marginBottom: 24 }}>
          {annees.map((a) => (
            <li key={a.id}>{a.libelle} <Badge tone={a.statut === 'active' ? 'success' : 'neutral'}>{a.statut}</Badge></li>
          ))}
          {annees.length === 0 && <li style={{ color: '#64748b', listStyle: 'none' }}>Aucune année scolaire</li>}
        </ul>
      )}

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Niveaux</h2>
      <form onSubmit={creerNiveau} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <input placeholder="Nom (ex. CE1)" value={niveauForm.nom}
          onChange={(e) => setNiveauForm({ ...niveauForm, nom: e.target.value })}
          aria-label="Nom du niveau" />
        <select value={niveauForm.cycle} onChange={(e) => setNiveauForm({ ...niveauForm, cycle: e.target.value })} aria-label="Cycle">
          {CYCLES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <input type="number" min="1" value={niveauForm.ordre}
          onChange={(e) => setNiveauForm({ ...niveauForm, ordre: e.target.value })}
          aria-label="Ordre" style={{ width: 70 }} />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
      </form>
      {loadingNiveaux ? <p>Chargement…</p> : (
        <ul style={{ marginBottom: 24 }}>
          {niveaux.map((n) => <li key={n.id}>{n.nom} — {n.cycle}</li>)}
          {niveaux.length === 0 && <li style={{ color: '#64748b', listStyle: 'none' }}>Aucun niveau</li>}
        </ul>
      )}

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Classes</h2>
      <form onSubmit={creerClasse} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select value={classeForm.annee_scolaire}
          onChange={(e) => setClasseForm({ ...classeForm, annee_scolaire: e.target.value })}
          aria-label="Année scolaire">
          <option value="">Année scolaire…</option>
          {annees.map((a) => <option key={a.id} value={a.id}>{a.libelle}</option>)}
        </select>
        <select value={classeForm.niveau}
          onChange={(e) => setClasseForm({ ...classeForm, niveau: e.target.value })}
          aria-label="Niveau">
          <option value="">Niveau…</option>
          {niveaux.map((n) => <option key={n.id} value={n.id}>{n.nom}</option>)}
        </select>
        <input placeholder="Nom (ex. CE1-A)" value={classeForm.nom}
          onChange={(e) => setClasseForm({ ...classeForm, nom: e.target.value })}
          aria-label="Nom de la classe" />
        <input type="number" min="1" value={classeForm.capacite_max}
          onChange={(e) => setClasseForm({ ...classeForm, capacite_max: e.target.value })}
          aria-label="Capacité maximale" style={{ width: 90 }} />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
      </form>
      {loadingClasses ? <p>Chargement…</p> : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th>Classe</th><th>Niveau</th><th>Effectif / Capacité</th><th /></tr>
          </thead>
          <tbody>
            {classes.map((c) => (
              <tr key={c.id}>
                <td>{c.nom}</td>
                <td>{c.niveau_nom || niveauNom(c.niveau)}</td>
                <td>{c.effectif} / {c.capacite_max}</td>
                <td><Button variant="ghost" onClick={() => exporterClasse(c)}>Exporter (xlsx)</Button></td>
              </tr>
            ))}
            {classes.length === 0 && (
              <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>Aucune classe</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
