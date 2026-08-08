import { useMemo, useState } from 'react'
import { FileQuestion } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from './ChantierSelect'
import { useBtpChantierResource } from './useBtpChantierResource'

/* ============================================================================
   PACT63 — Demandes d'information technique (RFI, NTCON3/4). Question
   numérotée par chantier (serveur), délai en jours ouvrés converti en date
   limite CÔTÉ SERVEUR (jamais recalculé côté client), alerte de retard
   (`en_retard`, déjà calculé par le serializer), fil de réponses, clôture.
   ========================================================================== */

const STATUT_LABEL = { ouvert: 'Ouvert', repondu: 'Répondu', clos: 'Clos' }
const STATUT_TONE = { ouvert: 'warning', repondu: 'info', clos: 'success' }

export default function RFI() {
  const [chantierId, setChantierId] = useState('')
  const [statut, setStatut] = useState('')

  const params = useMemo(() => ({
    chantier: chantierId || undefined,
    statut: statut || undefined,
  }), [chantierId, statut])

  const { data: rfis, loading, reload } = useBtpChantierResource(
    btpChantierApi.rfi.list, params, [chantierId, statut],
  )

  // ── Création ─────────────────────────────────────────────────────────────
  const [form, setForm] = useState({
    chantier: '', question: '', destinataire_texte: '', delai_jours: 5,
  })
  const [saving, setSaving] = useState(false)

  const creer = async (event) => {
    event.preventDefault()
    if (!form.chantier || !form.question) return
    setSaving(true)
    try {
      await btpChantierApi.rfi.create({
        chantier: form.chantier,
        question: form.question,
        destinataire_texte: form.destinataire_texte,
        delai_jours: Number(form.delai_jours) || 5,
      })
      toast.success('RFI posé.')
      setForm({ chantier: form.chantier, question: '', destinataire_texte: '', delai_jours: 5 })
      reload()
    } catch (err) {
      toast.error(frenchError(err, "Impossible de poser cette demande d'information."))
    } finally {
      setSaving(false)
    }
  }

  // ── RFI sélectionné (réponses + actions) ────────────────────────────────
  const [selectedId, setSelectedId] = useState(null)
  const selected = rfis.find((r) => r.id === selectedId) || null
  const [reponseTexte, setReponseTexte] = useState('')
  const [acting, setActing] = useState(false)

  const repondre = async (event) => {
    event.preventDefault()
    if (!selected || !reponseTexte) return
    setActing(true)
    try {
      await btpChantierApi.rfi.repondre(selected.id, reponseTexte)
      toast.success('Réponse ajoutée.')
      setReponseTexte('')
      reload()
    } catch (err) {
      toast.error(frenchError(err, "Impossible d'enregistrer la réponse."))
    } finally {
      setActing(false)
    }
  }

  const clore = async () => {
    if (!selected) return
    setActing(true)
    try {
      await btpChantierApi.rfi.clore(selected.id)
      toast.success('RFI clos.')
      reload()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de clore ce RFI.'))
    } finally {
      setActing(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <FileQuestion size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Demandes d'information technique (RFI)</h1>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <ChantierSelect value={chantierId} onChange={setChantierId} label="Filtrer par chantier" />
        <select aria-label="Filtrer par statut" value={statut} onChange={(e) => setStatut(e.target.value)}>
          <option value="">Tous statuts</option>
          {Object.entries(STATUT_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      <form onSubmit={creer} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <ChantierSelect
          value={form.chantier}
          onChange={(v) => setForm({ ...form, chantier: v })}
          label="Chantier de la demande"
          required
        />
        <input
          placeholder="Question"
          value={form.question}
          onChange={(e) => setForm({ ...form, question: e.target.value })}
          aria-label="Question"
          required
        />
        <input
          placeholder="Destinataire (MOE/BE)"
          value={form.destinataire_texte}
          onChange={(e) => setForm({ ...form, destinataire_texte: e.target.value })}
          aria-label="Destinataire"
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          Délai (j. ouvrés)
          <input
            type="number"
            min="1"
            value={form.delai_jours}
            onChange={(e) => setForm({ ...form, delai_jours: e.target.value })}
            aria-label="Délai en jours ouvrés"
            style={{ width: 60 }}
          />
        </label>
        <Button type="submit" disabled={saving}>{saving ? 'Envoi…' : 'Poser la question'}</Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
          <thead>
            <tr>
              <th>N°</th><th>Question</th><th>Destinataire</th>
              <th>Date limite</th><th>Statut</th><th />
            </tr>
          </thead>
          <tbody>
            {rfis.map((r) => (
              <tr key={r.id}>
                <td>{r.numero}</td>
                <td>{r.question}</td>
                <td>{r.destinataire_texte || '—'}</td>
                <td>
                  {r.date_limite_reponse || '—'}
                  {r.en_retard && (
                    <Badge tone="danger" style={{ marginLeft: 6 }}>En retard</Badge>
                  )}
                </td>
                <td><Badge tone={STATUT_TONE[r.statut] || 'neutral'}>{STATUT_LABEL[r.statut] || r.statut}</Badge></td>
                <td><Button variant="ghost" onClick={() => setSelectedId(r.id)}>Détails</Button></td>
              </tr>
            ))}
            {rfis.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>Aucun RFI</td></tr>
            )}
          </tbody>
        </table>
      )}

      {selected && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>
            RFI #{selected.numero}{' '}
            <Badge tone={STATUT_TONE[selected.statut] || 'neutral'}>
              {STATUT_LABEL[selected.statut] || selected.statut}
            </Badge>
          </h2>
          <p>{selected.question}</p>

          {(selected.reponses || []).length > 0 && (
            <ul>
              {selected.reponses.map((rep) => (
                <li key={rep.id}>{rep.texte}</li>
              ))}
            </ul>
          )}

          {selected.statut !== 'clos' && (
            <form onSubmit={repondre} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
              <input
                placeholder="Réponse"
                value={reponseTexte}
                onChange={(e) => setReponseTexte(e.target.value)}
                aria-label="Texte de la réponse"
              />
              <Button type="submit" disabled={acting || !reponseTexte}>Répondre</Button>
            </form>
          )}

          {selected.statut !== 'clos' && (
            <Button type="button" variant="outline" onClick={clore} disabled={acting}>Clore</Button>
          )}
        </div>
      )}
    </div>
  )
}
