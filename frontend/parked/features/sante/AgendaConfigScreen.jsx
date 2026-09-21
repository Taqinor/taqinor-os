import { useEffect, useState } from 'react'
import { CalendarCog, Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import santeApi from '../../api/santeApi'

/* ============================================================================
   WIR142 — Écran d'administration « Configuration agenda » (NTSAN30/32/35).
   Quatre paramétrages légers rattachés au praticien : horaires d'ouverture,
   indisponibilités ponctuelles, sites/salles rattachés, motifs de
   consultation prédéfinis. Tous ADDITIFS — un praticien sans ligne garde son
   comportement par défaut (jamais de régression).
   ========================================================================== */

const JOURS = [
  { value: '0', label: 'Lundi' }, { value: '1', label: 'Mardi' },
  { value: '2', label: 'Mercredi' }, { value: '3', label: 'Jeudi' },
  { value: '4', label: 'Vendredi' }, { value: '5', label: 'Samedi' },
  { value: '6', label: 'Dimanche' },
]

export default function AgendaConfigScreen() {
  const [praticiens, setPraticiens] = useState([])
  const [salles, setSalles] = useState([])
  const [horaires, setHoraires] = useState([])
  const [indisponibilites, setIndisponibilites] = useState([])
  const [motifs, setMotifs] = useState([])
  const [sites, setSites] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [horaireForm, setHoraireForm] = useState({ praticien: '', jour_semaine: '0', heure_debut: '08:00', heure_fin: '18:00' })
  const [indispoForm, setIndispoForm] = useState({ praticien: '', date_debut: '', date_fin: '', motif: '' })
  const [motifForm, setMotifForm] = useState({ libelle: '' })
  const [siteForm, setSiteForm] = useState({ praticien: '', salle: '' })

  const load = () => {
    setLoading(true)
    Promise.all([
      santeApi.praticiens.list(),
      santeApi.salles.list(),
      santeApi.horairesOuverturePraticien.list(),
      santeApi.indisponibilitesPraticien.list(),
      santeApi.motifsConsultation.list(),
      santeApi.sitesPraticien.list(),
    ])
      .then(([praRes, salRes, horRes, indRes, motRes, siteRes]) => {
        setPraticiens(praRes.data?.results ?? praRes.data ?? [])
        setSalles(salRes.data?.results ?? salRes.data ?? [])
        setHoraires(horRes.data?.results ?? horRes.data ?? [])
        setIndisponibilites(indRes.data?.results ?? indRes.data ?? [])
        setMotifs(motRes.data?.results ?? motRes.data ?? [])
        setSites(siteRes.data?.results ?? siteRes.data ?? [])
      })
      .catch(() => toast.error('Impossible de charger la configuration agenda.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  const praticienNom = (id) => {
    const p = praticiens.find((x) => x.id === Number(id))
    return p ? p.nom : `Praticien #${id}`
  }

  const creerHoraire = async (e) => {
    e.preventDefault()
    if (!horaireForm.praticien) return
    setSaving(true)
    try {
      await santeApi.horairesOuverturePraticien.create(horaireForm)
      toast.success('Horaire ajouté.')
      load()
    } catch {
      toast.error("Impossible d'ajouter l'horaire.")
    } finally {
      setSaving(false)
    }
  }

  const creerIndispo = async (e) => {
    e.preventDefault()
    if (!indispoForm.praticien || !indispoForm.date_debut || !indispoForm.date_fin) return
    setSaving(true)
    try {
      await santeApi.indisponibilitesPraticien.create(indispoForm)
      toast.success('Indisponibilité ajoutée.')
      setIndispoForm({ praticien: '', date_debut: '', date_fin: '', motif: '' })
      load()
    } catch {
      toast.error("Impossible d'ajouter l'indisponibilité.")
    } finally {
      setSaving(false)
    }
  }

  const creerMotif = async (e) => {
    e.preventDefault()
    if (!motifForm.libelle.trim()) return
    setSaving(true)
    try {
      await santeApi.motifsConsultation.create(motifForm)
      toast.success('Motif ajouté.')
      setMotifForm({ libelle: '' })
      load()
    } catch {
      toast.error("Impossible d'ajouter le motif.")
    } finally {
      setSaving(false)
    }
  }

  const creerSite = async (e) => {
    e.preventDefault()
    if (!siteForm.praticien || !siteForm.salle) return
    setSaving(true)
    try {
      await santeApi.sitesPraticien.create(siteForm)
      toast.success('Site rattaché.')
      setSiteForm({ praticien: '', salle: '' })
      load()
    } catch {
      toast.error('Impossible de rattacher ce site.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p>Chargement…</p>

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <CalendarCog size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Configuration agenda</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Horaires d&apos;ouverture</h2>
      <form onSubmit={creerHoraire} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select value={horaireForm.praticien} onChange={(e) => setHoraireForm({ ...horaireForm, praticien: e.target.value })} aria-label="Praticien (horaire)">
          <option value="">Praticien…</option>
          {praticiens.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
        </select>
        <select value={horaireForm.jour_semaine} onChange={(e) => setHoraireForm({ ...horaireForm, jour_semaine: e.target.value })} aria-label="Jour de la semaine">
          {JOURS.map((j) => <option key={j.value} value={j.value}>{j.label}</option>)}
        </select>
        <input type="time" value={horaireForm.heure_debut} onChange={(e) => setHoraireForm({ ...horaireForm, heure_debut: e.target.value })} aria-label="Heure de début" />
        <input type="time" value={horaireForm.heure_fin} onChange={(e) => setHoraireForm({ ...horaireForm, heure_fin: e.target.value })} aria-label="Heure de fin" />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
      </form>
      <ul style={{ marginBottom: 24 }}>
        {horaires.map((h) => (
          <li key={h.id}>{praticienNom(h.praticien)} — {h.jour_semaine_display} {h.heure_debut}–{h.heure_fin}</li>
        ))}
        {horaires.length === 0 && <li style={{ color: '#64748b', listStyle: 'none' }}>Aucun horaire configuré</li>}
      </ul>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Indisponibilités</h2>
      <form onSubmit={creerIndispo} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select value={indispoForm.praticien} onChange={(e) => setIndispoForm({ ...indispoForm, praticien: e.target.value })} aria-label="Praticien (indisponibilité)">
          <option value="">Praticien…</option>
          {praticiens.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
        </select>
        <input type="datetime-local" value={indispoForm.date_debut} onChange={(e) => setIndispoForm({ ...indispoForm, date_debut: e.target.value })} aria-label="Début de l'indisponibilité" />
        <input type="datetime-local" value={indispoForm.date_fin} onChange={(e) => setIndispoForm({ ...indispoForm, date_fin: e.target.value })} aria-label="Fin de l'indisponibilité" />
        <input placeholder="Motif" value={indispoForm.motif} onChange={(e) => setIndispoForm({ ...indispoForm, motif: e.target.value })} aria-label="Motif de l'indisponibilité" />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
      </form>
      <ul style={{ marginBottom: 24 }}>
        {indisponibilites.map((i) => (
          <li key={i.id}>{praticienNom(i.praticien)} — {i.motif || 'sans motif'}</li>
        ))}
        {indisponibilites.length === 0 && <li style={{ color: '#64748b', listStyle: 'none' }}>Aucune indisponibilité</li>}
      </ul>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Motifs de consultation</h2>
      <form onSubmit={creerMotif} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <input placeholder="Libellé" value={motifForm.libelle} onChange={(e) => setMotifForm({ libelle: e.target.value })} aria-label="Libellé du motif" />
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter</Button>
      </form>
      <ul style={{ marginBottom: 24 }}>
        {motifs.map((m) => (
          <li key={m.id}>{m.libelle} <Badge tone={m.actif ? 'success' : 'neutral'}>{m.actif ? 'Actif' : 'Inactif'}</Badge></li>
        ))}
        {motifs.length === 0 && <li style={{ color: '#64748b', listStyle: 'none' }}>Aucun motif</li>}
      </ul>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Sites du praticien</h2>
      <form onSubmit={creerSite} style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select value={siteForm.praticien} onChange={(e) => setSiteForm({ ...siteForm, praticien: e.target.value })} aria-label="Praticien (site)">
          <option value="">Praticien…</option>
          {praticiens.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
        </select>
        <select value={siteForm.salle} onChange={(e) => setSiteForm({ ...siteForm, salle: e.target.value })} aria-label="Salle">
          <option value="">Salle…</option>
          {salles.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
        </select>
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Rattacher</Button>
      </form>
      <ul>
        {sites.map((s) => (
          <li key={s.id}>{praticienNom(s.praticien)} — {s.salle_nom}</li>
        ))}
        {sites.length === 0 && <li style={{ color: '#64748b', listStyle: 'none' }}>Aucun rattachement</li>}
      </ul>
    </div>
  )
}
