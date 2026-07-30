import { useState } from 'react'
import { Users, Plus, FileText } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'

/* ============================================================================
   WIR143 — Écran P1 « Familles & élèves » (NTEDU2). CRUD famille + élève
   (numéro de dossier attribué côté serveur, jamais côté client) + certificat
   de scolarité PDF à la demande (NTEDU18).
   ========================================================================== */

const FAMILLE_VIDE = {
  nom: '', parent1_nom: '', parent1_telephone: '', parent1_email: '',
}
const ELEVE_VIDE = { famille: '', nom: '', prenom: '', date_naissance: '', sexe: 'M' }

export default function FamillesElevesPage() {
  const { data: familles, loading: loadingFamilles, reload: reloadFamilles } =
    useEducationResource(educationApi.familles.list)
  const { data: eleves, loading: loadingEleves, reload: reloadEleves } =
    useEducationResource(educationApi.eleves.list)
  const { data: classes } = useEducationResource(educationApi.classes.list)

  const [familleForm, setFamilleForm] = useState(FAMILLE_VIDE)
  const [eleveForm, setEleveForm] = useState(ELEVE_VIDE)
  const [saving, setSaving] = useState(false)

  const familleNom = (id) => familles.find((f) => f.id === Number(id))?.nom || `Famille #${id}`
  const classeNom = (id) => classes.find((c) => c.id === Number(id))?.nom || null

  const creerFamille = async (e) => {
    e.preventDefault()
    if (!familleForm.nom.trim()) return
    setSaving(true)
    try {
      await educationApi.familles.create(familleForm)
      toast.success('Famille créée.')
      setFamilleForm(FAMILLE_VIDE)
      reloadFamilles()
    } catch {
      toast.error('Impossible de créer la famille.')
    } finally {
      setSaving(false)
    }
  }

  const creerEleve = async (e) => {
    e.preventDefault()
    if (!eleveForm.famille || !eleveForm.nom.trim() || !eleveForm.prenom.trim()) return
    setSaving(true)
    try {
      await educationApi.eleves.create(eleveForm)
      toast.success('Élève créé.')
      setEleveForm({ ...ELEVE_VIDE, famille: eleveForm.famille })
      reloadEleves()
    } catch {
      toast.error("Impossible de créer l'élève.")
    } finally {
      setSaving(false)
    }
  }

  const telechargerCertificat = async (eleve) => {
    try {
      const res = await educationApi.eleves.certificatScolarite(eleve.id)
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `certificat-scolarite-${eleve.id}.pdf`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      toast.error('Certificat indisponible (aucune année scolaire active ?).')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Users size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Familles &amp; élèves</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Familles</h2>
      <form onSubmit={creerFamille} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <input placeholder="Nom de famille" value={familleForm.nom}
          onChange={(e) => setFamilleForm({ ...familleForm, nom: e.target.value })}
          aria-label="Nom de famille" />
        <input placeholder="Parent 1 — nom" value={familleForm.parent1_nom}
          onChange={(e) => setFamilleForm({ ...familleForm, parent1_nom: e.target.value })}
          aria-label="Nom du parent 1" />
        <input placeholder="Téléphone" value={familleForm.parent1_telephone}
          onChange={(e) => setFamilleForm({ ...familleForm, parent1_telephone: e.target.value })}
          aria-label="Téléphone du parent 1" />
        <input placeholder="Email" value={familleForm.parent1_email}
          onChange={(e) => setFamilleForm({ ...familleForm, parent1_email: e.target.value })}
          aria-label="Email du parent 1" />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
      </form>
      {loadingFamilles ? <p>Chargement…</p> : (
        <ul style={{ marginBottom: 24 }}>
          {familles.map((f) => <li key={f.id}>{f.nom} — {f.parent1_nom} ({f.parent1_telephone || 'sans téléphone'})</li>)}
          {familles.length === 0 && <li style={{ color: '#64748b', listStyle: 'none' }}>Aucune famille</li>}
        </ul>
      )}

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Élèves</h2>
      <form onSubmit={creerEleve} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select value={eleveForm.famille}
          onChange={(e) => setEleveForm({ ...eleveForm, famille: e.target.value })}
          aria-label="Famille">
          <option value="">Famille…</option>
          {familles.map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
        </select>
        <input placeholder="Nom" value={eleveForm.nom}
          onChange={(e) => setEleveForm({ ...eleveForm, nom: e.target.value })} aria-label="Nom de l'élève" />
        <input placeholder="Prénom" value={eleveForm.prenom}
          onChange={(e) => setEleveForm({ ...eleveForm, prenom: e.target.value })} aria-label="Prénom de l'élève" />
        <input type="date" value={eleveForm.date_naissance}
          onChange={(e) => setEleveForm({ ...eleveForm, date_naissance: e.target.value })}
          aria-label="Date de naissance" />
        <select value={eleveForm.sexe} onChange={(e) => setEleveForm({ ...eleveForm, sexe: e.target.value })} aria-label="Sexe">
          <option value="M">Masculin</option>
          <option value="F">Féminin</option>
        </select>
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
      </form>
      {loadingEleves ? <p>Chargement…</p> : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th>Nom</th><th>Famille</th><th>Classe</th><th>N° dossier</th><th>Statut</th><th /></tr>
          </thead>
          <tbody>
            {eleves.map((el) => (
              <tr key={el.id}>
                <td>{el.nom} {el.prenom}</td>
                <td>{familleNom(el.famille)}</td>
                <td>{el.classe ? (classeNom(el.classe) || `#${el.classe}`) : '—'}</td>
                <td>{el.numero_dossier}</td>
                <td><Badge tone={el.statut === 'inscrit' || el.statut === 'reinscrit' ? 'success' : 'neutral'}>{el.statut}</Badge></td>
                <td>
                  <Button variant="ghost" onClick={() => telechargerCertificat(el)}>
                    <FileText size={14} strokeWidth={1.75} aria-hidden="true" /> Certificat
                  </Button>
                </td>
              </tr>
            ))}
            {eleves.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>Aucun élève</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
