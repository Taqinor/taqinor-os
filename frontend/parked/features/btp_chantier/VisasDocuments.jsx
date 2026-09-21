import { useMemo, useState } from 'react'
import { Stamp } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from './ChantierSelect'
import { useBtpChantierResource } from './useBtpChantierResource'

/* ============================================================================
   PACT64 — Visas de documents techniques (NTCON5). Cycle soumis → en revue →
   approuvé (sans réserve / avec observations) → refusé, délai de revue en
   jours ouvrés, et resoumission AUTOMATIQUE côté serveur dès qu'une nouvelle
   version du document arrive dans la GED (`receivers.py` — rien à faire ici).
   ========================================================================== */

const TYPE_VISA = [
  { value: 'plan_execution', label: "Plan d'exécution" },
  { value: 'note_calcul', label: 'Note de calcul' },
  { value: 'fiche_technique', label: 'Fiche technique' },
  { value: 'methode', label: 'Méthode' },
  { value: 'autre', label: 'Autre' },
]
const STATUT_LABEL = {
  soumis: 'Soumis', en_revue: 'En revue',
  approuve_sans_reserve: 'Approuvé sans réserve',
  approuve_avec_observations: 'Approuvé avec observations', refuse: 'Refusé',
}
const STATUT_TONE = {
  soumis: 'warning', en_revue: 'info', approuve_sans_reserve: 'success',
  approuve_avec_observations: 'success', refuse: 'danger',
}
const STATUTS_DECIDES = ['approuve_sans_reserve', 'approuve_avec_observations', 'refuse']

export default function VisasDocuments() {
  const [chantierId, setChantierId] = useState('')
  const [statut, setStatut] = useState('')

  const params = useMemo(() => ({
    chantier: chantierId || undefined,
    statut: statut || undefined,
  }), [chantierId, statut])

  const { data: visas, loading, reload } = useBtpChantierResource(
    btpChantierApi.visas.list, params, [chantierId, statut],
  )

  // ── Soumission ────────────────────────────────────────────────────────
  const [form, setForm] = useState({
    chantier: '', document_ged_id: '', type_visa: 'autre', delai_revue_jours: 10,
  })
  const [saving, setSaving] = useState(false)

  const soumettre = async (event) => {
    event.preventDefault()
    if (!form.chantier || !form.document_ged_id) return
    setSaving(true)
    try {
      await btpChantierApi.visas.create({
        chantier: form.chantier,
        document_ged_id: Number(form.document_ged_id),
        type_visa: form.type_visa,
        delai_revue_jours: Number(form.delai_revue_jours) || 10,
      })
      toast.success('Visa soumis.')
      setForm({ ...form, document_ged_id: '' })
      reload()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de soumettre ce visa.'))
    } finally {
      setSaving(false)
    }
  }

  // ── Visa sélectionné (revue + décision) ─────────────────────────────────
  const [selectedId, setSelectedId] = useState(null)
  const selected = visas.find((v) => v.id === selectedId) || null
  const [observations, setObservations] = useState('')
  const [avecObservations, setAvecObservations] = useState(false)
  const [acting, setActing] = useState(false)

  const agir = async (action) => {
    if (!selected) return
    setActing(true)
    try {
      if (action === 'observations') {
        await btpChantierApi.visas.soumettreObservations(selected.id, observations)
        toast.success('Observations ajoutées.')
      } else if (action === 'approuver') {
        await btpChantierApi.visas.approuver(selected.id, { avecObservations, observations })
        toast.success('Visa approuvé.')
      } else if (action === 'refuser') {
        await btpChantierApi.visas.refuser(selected.id, observations)
        toast.success('Visa refusé.')
      }
      setObservations('')
      reload()
    } catch (err) {
      toast.error(frenchError(err, 'Action impossible sur ce visa.'))
    } finally {
      setActing(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Stamp size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Visas de documents techniques</h1>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <ChantierSelect value={chantierId} onChange={setChantierId} label="Filtrer par chantier" />
        <select aria-label="Filtrer par statut" value={statut} onChange={(e) => setStatut(e.target.value)}>
          <option value="">Tous statuts</option>
          {Object.entries(STATUT_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      <form onSubmit={soumettre} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <ChantierSelect
          value={form.chantier}
          onChange={(v) => setForm({ ...form, chantier: v })}
          label="Chantier du visa"
          required
        />
        <input
          placeholder="ID du document GED"
          value={form.document_ged_id}
          onChange={(e) => setForm({ ...form, document_ged_id: e.target.value })}
          aria-label="ID du document GED"
          required
        />
        <select
          value={form.type_visa}
          onChange={(e) => setForm({ ...form, type_visa: e.target.value })}
          aria-label="Type de visa"
        >
          {TYPE_VISA.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          Délai de revue (j. ouvrés)
          <input
            type="number"
            min="1"
            value={form.delai_revue_jours}
            onChange={(e) => setForm({ ...form, delai_revue_jours: e.target.value })}
            aria-label="Délai de revue en jours ouvrés"
            style={{ width: 60 }}
          />
        </label>
        <Button type="submit" disabled={saving}>{saving ? 'Envoi…' : 'Soumettre le visa'}</Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
          <thead>
            <tr>
              <th>Référence</th><th>Type</th><th>Date limite</th>
              <th>Resoumissions</th><th>Statut</th><th />
            </tr>
          </thead>
          <tbody>
            {visas.map((v) => (
              <tr key={v.id}>
                <td>{v.reference}</td>
                <td>{TYPE_VISA.find((t) => t.value === v.type_visa)?.label || v.type_visa}</td>
                <td>{v.date_limite || '—'}</td>
                <td>{v.nb_resoumissions}</td>
                <td><Badge tone={STATUT_TONE[v.statut] || 'neutral'}>{STATUT_LABEL[v.statut] || v.statut}</Badge></td>
                <td><Button variant="ghost" onClick={() => setSelectedId(v.id)}>Détails</Button></td>
              </tr>
            ))}
            {visas.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>Aucun visa</td></tr>
            )}
          </tbody>
        </table>
      )}

      {selected && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>
            Visa {selected.reference}{' '}
            <Badge tone={STATUT_TONE[selected.statut] || 'neutral'}>
              {STATUT_LABEL[selected.statut] || selected.statut}
            </Badge>
          </h2>
          {selected.observations && <p>{selected.observations}</p>}

          {!STATUTS_DECIDES.includes(selected.statut) ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <input
                placeholder="Observations"
                value={observations}
                onChange={(e) => setObservations(e.target.value)}
                aria-label="Observations de revue"
              />
              <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <input
                  type="checkbox"
                  checked={avecObservations}
                  onChange={(e) => setAvecObservations(e.target.checked)}
                />
                Approuver avec observations
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                <Button type="button" variant="outline" onClick={() => agir('observations')} disabled={acting}>
                  Ajouter des observations
                </Button>
                <Button type="button" variant="success" onClick={() => agir('approuver')} disabled={acting}>
                  Approuver
                </Button>
                <Button type="button" variant="destructive" onClick={() => agir('refuser')} disabled={acting}>
                  Refuser
                </Button>
              </div>
            </div>
          ) : (
            <p style={{ color: '#64748b' }}>Visa déjà décidé.</p>
          )}
        </div>
      )}
    </div>
  )
}
