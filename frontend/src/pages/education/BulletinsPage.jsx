import { useEffect, useMemo, useState } from 'react'
import { GraduationCap, Plus, Send, Download } from 'lucide-react'
import { Button, Badge, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'

/* ============================================================================
   WIR212 — Écran admin « Périodes & bulletins » (NTEDU17). Le backend était
   complet (`PeriodeScolaireViewSet`, `BulletinViewSet.publier`,
   `eleves.bulletinPdf`) mais le SEUL chemin d'écriture était l'admin Django —
   sans écran, un bulletin restait à jamais impubliable. Portail parents
   (NTEDU33) reste hors périmètre : cet écran est la face ADMIN uniquement.
   Même patron minimal (inline styles, `useEducationResource`) que les autres
   écrans P1 (`NotesPage.jsx`, `PresencesPage.jsx`) — pas de bulk-saisie
   dédiée côté serveur pour les bulletins : chaque appréciation s'enregistre
   individuellement (create la première fois, update ensuite), et la
   publication est TOUJOURS une action séparée et explicite par élève —
   jamais un PATCH direct sur `publie` (garde-fou serveur, `BulletinViewSet`).
   ========================================================================== */

function unpage(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}

export default function BulletinsPage() {
  const { data: annees } = useEducationResource(educationApi.anneesScolaires.list)
  const { data: periodes, loading: loadingPeriodes, reload: reloadPeriodes } =
    useEducationResource(educationApi.periodes.list)
  const { data: classes } = useEducationResource(educationApi.classes.list)
  const { data: eleves } = useEducationResource(educationApi.eleves.list)

  const [periodeForm, setPeriodeForm] = useState({
    annee_scolaire: '', libelle: '', ordre: '1', date_debut: '', date_fin: '',
  })
  const [saving, setSaving] = useState(false)

  const [periodeChoisie, setPeriodeChoisie] = useState('')
  const [classeChoisie, setClasseChoisie] = useState('')
  const [bulletins, setBulletins] = useState([])
  const [loadingBulletins, setLoadingBulletins] = useState(false)
  const [appreciations, setAppreciations] = useState({})
  const [busyEleve, setBusyEleve] = useState(null)

  const roster = useMemo(
    () => (classeChoisie
      ? eleves.filter((el) => String(el.classe) === String(classeChoisie))
      : []),
    [eleves, classeChoisie],
  )

  const chargerBulletins = (periodeId) => {
    if (!periodeId) { setBulletins([]); return }
    setLoadingBulletins(true)
    educationApi.bulletins.list({ periode: periodeId })
      .then((res) => setBulletins(unpage(res.data)))
      .catch(() => setBulletins([]))
      .finally(() => setLoadingBulletins(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au changement de période
    chargerBulletins(periodeChoisie)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chargerBulletins est stable (pas de dep externe changeante)
  }, [periodeChoisie])

  const bulletinDe = (eleveId) =>
    bulletins.find((b) => String(b.eleve) === String(eleveId))

  const creerPeriode = async (e) => {
    e.preventDefault()
    if (!periodeForm.annee_scolaire || !periodeForm.libelle.trim()
      || !periodeForm.date_debut || !periodeForm.date_fin) return
    setSaving(true)
    try {
      await educationApi.periodes.create({
        annee_scolaire: Number(periodeForm.annee_scolaire),
        libelle: periodeForm.libelle.trim(),
        ordre: Number(periodeForm.ordre) || 1,
        date_debut: periodeForm.date_debut,
        date_fin: periodeForm.date_fin,
      })
      toast.success('Période créée.')
      setPeriodeForm({
        annee_scolaire: periodeForm.annee_scolaire, libelle: '', ordre: '1',
        date_debut: '', date_fin: '',
      })
      reloadPeriodes()
    } catch {
      toast.error('Impossible de créer la période.')
    } finally {
      setSaving(false)
    }
  }

  const enregistrerAppreciation = async (eleve) => {
    const existant = bulletinDe(eleve.id)
    const texte = appreciations[eleve.id] ?? existant?.appreciation_generale ?? ''
    setBusyEleve(eleve.id)
    try {
      if (existant) {
        await educationApi.bulletins.update(existant.id, { appreciation_generale: texte })
      } else {
        await educationApi.bulletins.create({
          eleve: eleve.id, periode: Number(periodeChoisie), appreciation_generale: texte,
        })
      }
      toast.success('Appréciation enregistrée.')
      chargerBulletins(periodeChoisie)
    } catch {
      toast.error("Impossible d'enregistrer l'appréciation.")
    } finally {
      setBusyEleve(null)
    }
  }

  const publier = async (bulletin) => {
    if (!bulletin) return
    setBusyEleve(bulletin.eleve)
    try {
      await educationApi.bulletins.publier(bulletin.id)
      toast.success('Bulletin publié.')
      chargerBulletins(periodeChoisie)
    } catch {
      toast.error('Impossible de publier le bulletin.')
    } finally {
      setBusyEleve(null)
    }
  }

  const telechargerPdf = async (eleve) => {
    try {
      const res = await educationApi.eleves.bulletinPdf(eleve.id, periodeChoisie)
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `bulletin-${eleve.id}-${periodeChoisie}.pdf`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      toast.error('Impossible de générer le PDF.')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <GraduationCap size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Périodes &amp; bulletins</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Nouvelle période</h2>
      <form onSubmit={creerPeriode} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select value={periodeForm.annee_scolaire}
          onChange={(e) => setPeriodeForm({ ...periodeForm, annee_scolaire: e.target.value })}
          aria-label="Année scolaire">
          <option value="">Année scolaire…</option>
          {annees.map((a) => <option key={a.id} value={a.id}>{a.libelle}</option>)}
        </select>
        <input placeholder="Libellé (ex. Trimestre 1)" value={periodeForm.libelle}
          onChange={(e) => setPeriodeForm({ ...periodeForm, libelle: e.target.value })}
          aria-label="Libellé de la période" />
        <input type="number" min="1" value={periodeForm.ordre}
          onChange={(e) => setPeriodeForm({ ...periodeForm, ordre: e.target.value })}
          aria-label="Ordre" style={{ width: 70 }} />
        <input type="date" value={periodeForm.date_debut}
          onChange={(e) => setPeriodeForm({ ...periodeForm, date_debut: e.target.value })}
          aria-label="Date de début de la période" />
        <input type="date" value={periodeForm.date_fin}
          onChange={(e) => setPeriodeForm({ ...periodeForm, date_fin: e.target.value })}
          aria-label="Date de fin de la période" />
        <Button type="submit" disabled={saving}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Créer
        </Button>
      </form>
      {loadingPeriodes ? <p>Chargement…</p> : (
        <ul style={{ marginBottom: 24 }}>
          {periodes.map((p) => <li key={p.id}>{p.libelle}</li>)}
          {periodes.length === 0 && <li style={{ color: '#64748b', listStyle: 'none' }}>Aucune période</li>}
        </ul>
      )}

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Bulletins</h2>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <select value={periodeChoisie} onChange={(e) => setPeriodeChoisie(e.target.value)} aria-label="Période">
          <option value="">Période…</option>
          {periodes.map((p) => <option key={p.id} value={p.id}>{p.libelle}</option>)}
        </select>
        <select value={classeChoisie} onChange={(e) => setClasseChoisie(e.target.value)} aria-label="Classe">
          <option value="">Classe…</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
      </div>

      {periodeChoisie && classeChoisie && (
        loadingBulletins ? <p>Chargement…</p> : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr><th>Élève</th><th>Appréciation générale</th><th>Statut</th><th /></tr>
            </thead>
            <tbody>
              {roster.map((el) => {
                const bulletin = bulletinDe(el.id)
                const busy = busyEleve === el.id
                return (
                  <tr key={el.id}>
                    <td>{el.nom} {el.prenom}</td>
                    <td>
                      <textarea
                        value={appreciations[el.id] ?? bulletin?.appreciation_generale ?? ''}
                        onChange={(e) => setAppreciations({ ...appreciations, [el.id]: e.target.value })}
                        aria-label={`Appréciation de ${el.nom} ${el.prenom}`}
                        rows={2}
                        style={{ width: '100%' }}
                      />
                    </td>
                    <td>
                      <Badge tone={bulletin?.publie ? 'success' : 'neutral'}>
                        {bulletin?.publie ? 'Publié' : 'Brouillon'}
                      </Badge>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        <Button variant="ghost" disabled={busy} onClick={() => enregistrerAppreciation(el)}>
                          Enregistrer
                        </Button>
                        <Button variant="ghost" disabled={busy || !bulletin || bulletin.publie}
                          onClick={() => publier(bulletin)}>
                          <Send size={14} strokeWidth={1.75} aria-hidden="true" /> Publier
                        </Button>
                        <Button variant="ghost" onClick={() => telechargerPdf(el)}>
                          <Download size={14} strokeWidth={1.75} aria-hidden="true" /> PDF
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}
              {roster.length === 0 && (
                <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>Aucun élève dans cette classe</td></tr>
              )}
            </tbody>
          </table>
        )
      )}
    </div>
  )
}
