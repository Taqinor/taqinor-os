import { useMemo, useState } from 'react'
import { Download, NotebookPen, X } from 'lucide-react'
import { Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from './ChantierSelect'
import { useBtpChantierResource } from './useBtpChantierResource'

/* ============================================================================
   PACT65 — Journal de chantier quotidien (NTCON6). Une entrée par jour et par
   chantier (contrainte d'unicité CÔTÉ SERVEUR — un doublon renvoie 400) :
   météo, effectif interne et sous-traitant, matériel, événements, visiteurs,
   export PDF.
   ========================================================================== */

const METEO_LABEL = {
  ensoleille: 'Ensoleillé', nuageux: 'Nuageux', pluvieux: 'Pluvieux',
  venteux: 'Venteux', autre: 'Autre',
}

// Petit éditeur « métier → nombre » réutilisé pour l'effectif interne ET
// sous-traitant — même forme JSON que `models.py` (`{metier: nombre}`).
function EffectifEditor({ label, valeurs, onChange }) {
  const [metier, setMetier] = useState('')
  const [nombre, setNombre] = useState('1')

  const ajouter = () => {
    if (!metier.trim()) return
    onChange({ ...valeurs, [metier.trim()]: Number(nombre) || 0 })
    setMetier('')
    setNombre('1')
  }

  const retirer = (cle) => {
    const suite = { ...valeurs }
    delete suite[cle]
    onChange(suite)
  }

  return (
    <div>
      <span>{label}</span>
      <div style={{ display: 'flex', gap: 4, alignItems: 'center', margin: '4px 0' }}>
        <input
          placeholder="Métier"
          value={metier}
          onChange={(e) => setMetier(e.target.value)}
          aria-label={`Métier (${label})`}
          style={{ width: 120 }}
        />
        <input
          type="number"
          min="0"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          aria-label={`Nombre (${label})`}
          style={{ width: 60 }}
        />
        <Button type="button" size="sm" variant="outline" onClick={ajouter}>Ajouter</Button>
      </div>
      <ul style={{ listStyle: 'none', padding: 0, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {Object.entries(valeurs).map(([cle, n]) => (
          <li key={cle} style={{ display: 'flex', alignItems: 'center', gap: 2, border: '1px solid #e2e8f0', borderRadius: 999, padding: '2px 8px' }}>
            {cle} : {n}
            <button type="button" aria-label={`Retirer ${cle} (${label})`} onClick={() => retirer(cle)}>
              <X size={12} strokeWidth={1.75} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function JournalChantier() {
  const [chantierId, setChantierId] = useState('')
  const [du, setDu] = useState('')
  const [au, setAu] = useState('')

  const params = useMemo(() => ({
    chantier: chantierId || undefined, du: du || undefined, au: au || undefined,
  }), [chantierId, du, au])

  const { data: entrees, loading, reload } = useBtpChantierResource(
    btpChantierApi.journal.list, params, [chantierId, du, au],
  )

  const [form, setForm] = useState({
    chantier: '', date: '', meteo: '', materiel_present: '', evenements: '',
  })
  const [effectifInterne, setEffectifInterne] = useState({})
  const [effectifSousTraitant, setEffectifSousTraitant] = useState({})
  const [visiteurs, setVisiteurs] = useState([])
  const [visiteurForm, setVisiteurForm] = useState({ nom: '', societe: '', motif: '' })
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)

  const ajouterVisiteur = () => {
    if (!visiteurForm.nom.trim()) return
    setVisiteurs((v) => [...v, visiteurForm])
    setVisiteurForm({ nom: '', societe: '', motif: '' })
  }

  const retirerVisiteur = (index) => {
    setVisiteurs((v) => v.filter((_, i) => i !== index))
  }

  const creer = async (event) => {
    event.preventDefault()
    if (!form.chantier || !form.date) return
    setSaving(true)
    try {
      await btpChantierApi.journal.create({
        chantier: form.chantier,
        date: form.date,
        meteo: form.meteo,
        effectif_interne: effectifInterne,
        effectif_sous_traitant: effectifSousTraitant,
        materiel_present: form.materiel_present,
        evenements: form.evenements,
        visiteurs,
      })
      toast.success('Entrée de journal enregistrée.')
      setForm({ ...form, date: '', materiel_present: '', evenements: '' })
      setEffectifInterne({})
      setEffectifSousTraitant({})
      setVisiteurs([])
      reload()
    } catch (err) {
      // Le doublon jour/chantier renvoie 400 avec le message serveur exact.
      toast.error(frenchError(err, 'Impossible d’enregistrer cette entrée.'))
    } finally {
      setSaving(false)
    }
  }

  const exporterPdf = async () => {
    if (!chantierId) {
      toast.error('Choisissez un chantier pour exporter le journal.')
      return
    }
    setExporting(true)
    try {
      const res = await btpChantierApi.journal.exportPdf({ chantier: chantierId, du, au })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `journal-chantier-${chantierId}.pdf`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(frenchError(err, 'Export PDF impossible.'))
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <NotebookPen size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Journal de chantier</h1>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <ChantierSelect value={chantierId} onChange={setChantierId} label="Filtrer par chantier" />
        <input type="date" value={du} onChange={(e) => setDu(e.target.value)} aria-label="Du" />
        <input type="date" value={au} onChange={(e) => setAu(e.target.value)} aria-label="Au" />
        <Button type="button" variant="outline" onClick={exporterPdf} disabled={exporting}>
          <Download size={16} strokeWidth={1.75} aria-hidden="true" />
          {exporting ? 'Export…' : 'Exporter PDF'}
        </Button>
      </div>

      <form onSubmit={creer} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <ChantierSelect
            value={form.chantier}
            onChange={(v) => setForm({ ...form, chantier: v })}
            label="Chantier de l'entrée"
            required
          />
          <input
            type="date"
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
            aria-label="Date de l'entrée"
            required
          />
          <select
            value={form.meteo}
            onChange={(e) => setForm({ ...form, meteo: e.target.value })}
            aria-label="Météo"
          >
            <option value="">Météo…</option>
            {Object.entries(METEO_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>

        <div style={{ display: 'flex', gap: 24, marginBottom: 8, flexWrap: 'wrap' }}>
          <EffectifEditor label="Effectif interne" valeurs={effectifInterne} onChange={setEffectifInterne} />
          <EffectifEditor
            label="Effectif sous-traitant"
            valeurs={effectifSousTraitant}
            onChange={setEffectifSousTraitant}
          />
        </div>

        <input
          placeholder="Matériel présent"
          value={form.materiel_present}
          onChange={(e) => setForm({ ...form, materiel_present: e.target.value })}
          aria-label="Matériel présent"
          style={{ width: '100%', marginBottom: 8 }}
        />
        <input
          placeholder="Événements"
          value={form.evenements}
          onChange={(e) => setForm({ ...form, evenements: e.target.value })}
          aria-label="Événements"
          style={{ width: '100%', marginBottom: 8 }}
        />

        <div style={{ marginBottom: 8 }}>
          <span>Visiteurs</span>
          <div style={{ display: 'flex', gap: 4, alignItems: 'center', margin: '4px 0' }}>
            <input
              placeholder="Nom"
              value={visiteurForm.nom}
              onChange={(e) => setVisiteurForm({ ...visiteurForm, nom: e.target.value })}
              aria-label="Nom du visiteur"
            />
            <input
              placeholder="Société"
              value={visiteurForm.societe}
              onChange={(e) => setVisiteurForm({ ...visiteurForm, societe: e.target.value })}
              aria-label="Société du visiteur"
            />
            <input
              placeholder="Motif"
              value={visiteurForm.motif}
              onChange={(e) => setVisiteurForm({ ...visiteurForm, motif: e.target.value })}
              aria-label="Motif de la visite"
            />
            <Button type="button" size="sm" variant="outline" onClick={ajouterVisiteur}>Ajouter</Button>
          </div>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {visiteurs.map((v, i) => (
              <li key={`${v.nom}-${i}`}>
                {v.nom} ({v.societe || '—'}) — {v.motif || '—'}
                <button type="button" aria-label={`Retirer le visiteur ${v.nom}`} onClick={() => retirerVisiteur(i)}>
                  <X size={12} strokeWidth={1.75} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        </div>

        <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : "Enregistrer l'entrée"}</Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th>Date</th><th>Météo</th><th>Effectif interne</th><th>Événements</th></tr>
          </thead>
          <tbody>
            {entrees.map((e) => (
              <tr key={e.id}>
                <td>{e.date}</td>
                <td>{METEO_LABEL[e.meteo] || e.meteo || '—'}</td>
                <td>
                  {Object.entries(e.effectif_interne || {}).map(([m, n]) => `${m} (${n})`).join(', ') || '—'}
                </td>
                <td>{e.evenements || '—'}</td>
              </tr>
            ))}
            {entrees.length === 0 && (
              <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>Aucune entrée</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
