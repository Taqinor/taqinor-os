import { useMemo, useState } from 'react'
import { FileText, Plus, Save, Send, Download } from 'lucide-react'
import { Button, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'
import { downloadBlobInGesture, filenameFromResponse } from '../../utils/downloadBlob'

/* ============================================================================
   WIR212 — Écran « Périodes & bulletins » (NTEDU17/NTEDU33).

   Constat réparé : le SEUL chemin d'écriture de `publie` est l'action serveur
   `bulletins/<id>/publier/` (le serializer déclare `publie`/`date_publication`
   en lecture seule) — et AUCUN écran ne l'appelait. Un bulletin ne pouvait donc
   être publié que depuis l'admin Django, et le PDF (`eleves/<id>/bulletin/
   ?periode=<id>`) n'avait lui non plus aucun appelant.

   Le portail parents (NTEDU33) est HORS PÉRIMÈTRE : cet écran est le versant
   ADMINISTRATION — créer une période, saisir l'appréciation par élève, publier,
   sortir le PDF.
   ========================================================================== */

const EMPTY_PERIODE = { annee_scolaire: '', libelle: '', ordre: '1', date_debut: '', date_fin: '' }

export default function BulletinsPage() {
  const { data: annees } = useEducationResource(educationApi.anneesScolaires.list)
  const { data: periodes, reload: reloadPeriodes } =
    useEducationResource(educationApi.periodes.list)
  const { data: eleves } = useEducationResource(educationApi.eleves.list)
  const { data: bulletins, reload: reloadBulletins } =
    useEducationResource(educationApi.bulletins.list)

  const [periodeForm, setPeriodeForm] = useState(EMPTY_PERIODE)
  const [periodeChoisie, setPeriodeChoisie] = useState('')
  const [appreciations, setAppreciations] = useState({}) // eleveId → texte
  const [saving, setSaving] = useState(false)

  // Bulletins de la période affichée, indexés par élève : c'est ce qui dit si
  // un bulletin existe déjà (donc s'il est publiable) — jamais une supposition.
  const bulletinParEleve = useMemo(() => {
    const map = new Map()
    bulletins
      .filter((b) => String(b.periode) === String(periodeChoisie))
      .forEach((b) => map.set(String(b.eleve), b))
    return map
  }, [bulletins, periodeChoisie])

  const creerPeriode = async (e) => {
    e.preventDefault()
    if (!periodeForm.annee_scolaire || !periodeForm.libelle
      || !periodeForm.date_debut || !periodeForm.date_fin) return
    setSaving(true)
    try {
      const res = await educationApi.periodes.create(periodeForm)
      toast.success('Période créée.')
      setPeriodeForm({ ...EMPTY_PERIODE, annee_scolaire: periodeForm.annee_scolaire })
      reloadPeriodes()
      setPeriodeChoisie(String(res.data.id))
    } catch {
      toast.error('Impossible de créer la période.')
    } finally {
      setSaving(false)
    }
  }

  // Crée le bulletin s'il n'existe pas encore, sinon met à jour l'appréciation.
  const enregistrerAppreciation = async (eleve) => {
    if (!periodeChoisie) return
    const texte = appreciations[eleve.id] ?? bulletinParEleve.get(String(eleve.id))?.appreciation_generale ?? ''
    setSaving(true)
    try {
      const existant = bulletinParEleve.get(String(eleve.id))
      if (existant) {
        await educationApi.bulletins.update(existant.id, { appreciation_generale: texte })
      } else {
        await educationApi.bulletins.create({
          eleve: eleve.id, periode: periodeChoisie, appreciation_generale: texte,
        })
      }
      toast.success('Appréciation enregistrée.')
      reloadBulletins()
    } catch {
      toast.error("Impossible d'enregistrer l'appréciation.")
    } finally {
      setSaving(false)
    }
  }

  // NTEDU33 — publier = rendre visible au portail parents. Action DÉDIÉE :
  // un PATCH de `publie` serait ignoré en silence (champ read-only).
  const publier = async (eleve) => {
    const existant = bulletinParEleve.get(String(eleve.id))
    if (!existant) { toast.error("Enregistrez d'abord l'appréciation."); return }
    setSaving(true)
    try {
      await educationApi.bulletins.publier(existant.id)
      toast.success('Bulletin publié (visible sur le portail parents).')
      reloadBulletins()
    } catch {
      toast.error('Publication impossible.')
    } finally {
      setSaving(false)
    }
  }

  // NTEDU17 — le PDF arrive en BINAIRE ; 503 = moteur PDF indisponible sur
  // cette installation (on le DIT, on ne livre jamais un fichier vide).
  const telechargerPdf = async (eleve) => {
    if (!periodeChoisie) return
    const pending = downloadBlobInGesture()
    setSaving(true)
    try {
      const res = await educationApi.eleves.bulletinPdf(eleve.id, periodeChoisie)
      pending.deliver(res.data,
        filenameFromResponse(res, `bulletin_${eleve.id}_${periodeChoisie}.pdf`))
    } catch (err) {
      toast.error(err?.response?.status === 503
        ? "Génération PDF indisponible sur cette installation."
        : 'Téléchargement du bulletin impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <FileText size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Périodes &amp; bulletins</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Nouvelle période</h2>
      <form onSubmit={creerPeriode} data-testid="edu-periode-form"
        style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select value={periodeForm.annee_scolaire} aria-label="Année scolaire"
          onChange={(e) => setPeriodeForm({ ...periodeForm, annee_scolaire: e.target.value })}>
          <option value="">Année scolaire…</option>
          {annees.map((a) => (
            <option key={a.id} value={a.id}>{a.libelle || `Année #${a.id}`}</option>
          ))}
        </select>
        <input value={periodeForm.libelle} aria-label="Libellé de la période"
          placeholder="Trimestre 1"
          onChange={(e) => setPeriodeForm({ ...periodeForm, libelle: e.target.value })} />
        <input type="number" min="1" value={periodeForm.ordre} aria-label="Ordre dans l'année"
          style={{ width: 70 }}
          onChange={(e) => setPeriodeForm({ ...periodeForm, ordre: e.target.value })} />
        <input type="date" value={periodeForm.date_debut} aria-label="Date de début"
          onChange={(e) => setPeriodeForm({ ...periodeForm, date_debut: e.target.value })} />
        <input type="date" value={periodeForm.date_fin} aria-label="Date de fin"
          onChange={(e) => setPeriodeForm({ ...periodeForm, date_fin: e.target.value })} />
        <Button type="submit" disabled={saving}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Créer
        </Button>
      </form>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Bulletins de la période</h2>
      <select value={periodeChoisie} aria-label="Période"
        data-testid="edu-periode-select" style={{ marginBottom: 12 }}
        onChange={(e) => setPeriodeChoisie(e.target.value)}>
        <option value="">Période…</option>
        {periodes.map((p) => (
          <option key={p.id} value={p.id}>{p.libelle} ({p.date_debut} → {p.date_fin})</option>
        ))}
      </select>

      {periodeChoisie && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th>Élève</th><th>Appréciation générale</th><th>Statut</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {eleves.map((el) => {
              const b = bulletinParEleve.get(String(el.id))
              return (
                <tr key={el.id} data-testid="edu-bulletin-row">
                  <td>{el.nom} {el.prenom}</td>
                  <td>
                    <input
                      aria-label={`Appréciation de ${el.nom} ${el.prenom}`}
                      value={appreciations[el.id] ?? b?.appreciation_generale ?? ''}
                      onChange={(e) => setAppreciations(
                        { ...appreciations, [el.id]: e.target.value })}
                      style={{ width: '100%' }} />
                  </td>
                  <td data-testid={`edu-bulletin-statut-${el.id}`}>
                    {b ? (b.publie ? 'Publié' : 'Brouillon') : 'Aucun bulletin'}
                  </td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    <Button type="button" disabled={saving}
                      data-testid={`edu-bulletin-save-${el.id}`}
                      onClick={() => enregistrerAppreciation(el)}>
                      <Save size={15} strokeWidth={1.75} aria-hidden="true" /> Enregistrer
                    </Button>
                    <Button type="button" disabled={saving || !b || b.publie}
                      data-testid={`edu-bulletin-publier-${el.id}`}
                      onClick={() => publier(el)}>
                      <Send size={15} strokeWidth={1.75} aria-hidden="true" /> Publier
                    </Button>
                    <Button type="button" disabled={saving}
                      data-testid={`edu-bulletin-pdf-${el.id}`}
                      onClick={() => telechargerPdf(el)}>
                      <Download size={15} strokeWidth={1.75} aria-hidden="true" /> PDF
                    </Button>
                  </td>
                </tr>
              )
            })}
            {eleves.length === 0 && (
              <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>
                Aucun élève enregistré.</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
