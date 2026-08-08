import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Share2 } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import gedApi from '../../api/gedApi'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from './ChantierSelect'
import { useBtpChantierResource } from './useBtpChantierResource'

/* ============================================================================
   PACT68 — Diffusion contrôlée de plans (NTCON12/13). Diffusion tracée d'une
   version de plan avec accusé de réception par destinataire, et détection
   d'un plan périmé encore consulté (NTCON13) — le risque le plus concret sur
   un chantier.
   ========================================================================== */

export default function DiffusionPlans() {
  const [chantierId, setChantierId] = useState('')
  const [documentId, setDocumentId] = useState('')

  const params = useMemo(() => ({
    chantier: chantierId || undefined, document: documentId || undefined,
  }), [chantierId, documentId])

  const { data: diffusions, loading, reload } = useBtpChantierResource(
    btpChantierApi.diffusions.list, params, [chantierId, documentId],
  )

  // ── Plans périmés encore consultés (NTCON13) ────────────────────────────
  const [alertes, setAlertes] = useState([])

  useEffect(() => {
    if (!chantierId) {
      setAlertes([])
      return
    }
    let cancelled = false
    btpChantierApi.diffusions.plansPerimes(chantierId)
      .then((res) => { if (!cancelled) setAlertes(res.data || []) })
      .catch(() => { if (!cancelled) setAlertes([]) })
    return () => { cancelled = true }
  }, [chantierId])

  // ── Destinataires internes (utilisateurs de la société) ─────────────────
  const [users, setUsers] = useState([])
  useEffect(() => {
    gedApi.getUsers().then((r) => setUsers(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  // ── Création ─────────────────────────────────────────────────────────────
  const [form, setForm] = useState({
    chantier: '', document_ged_id: '', version_diffusee: '1', destinataires_externes: '',
  })
  const [internesChoisis, setInternesChoisis] = useState([])
  const [saving, setSaving] = useState(false)

  const creer = async (event) => {
    event.preventDefault()
    if (!form.chantier || !form.document_ged_id) return
    setSaving(true)
    try {
      await btpChantierApi.diffusions.create({
        chantier: form.chantier,
        document_ged_id: Number(form.document_ged_id),
        version_diffusee: Number(form.version_diffusee) || 1,
        destinataires_internes: internesChoisis.map(Number),
        destinataires_externes: form.destinataires_externes
          .split(',').map((e) => e.trim()).filter(Boolean),
      })
      toast.success('Diffusion créée.')
      setForm({ ...form, document_ged_id: '', destinataires_externes: '' })
      setInternesChoisis([])
      reload()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de créer cette diffusion.'))
    } finally {
      setSaving(false)
    }
  }

  const [selectedId, setSelectedId] = useState(null)
  const selected = diffusions.find((d) => d.id === selectedId) || null
  const [acting, setActing] = useState(false)

  const diffuser = async () => {
    if (!selected) return
    setActing(true)
    try {
      await btpChantierApi.diffusions.diffuser(selected.id)
      toast.success('Plan diffusé.')
      reload()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de diffuser ce plan.'))
    } finally {
      setActing(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Share2 size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Diffusion contrôlée de plans</h1>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <ChantierSelect value={chantierId} onChange={setChantierId} label="Filtrer par chantier" />
        <input
          placeholder="ID du document"
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
          aria-label="Filtrer par document"
        />
      </div>

      {alertes.length > 0 && (
        <div style={{ border: '1px solid #ef4444', borderRadius: 8, padding: 12, marginBottom: 16 }}>
          <p style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, margin: 0 }}>
            <AlertTriangle size={16} strokeWidth={1.75} aria-hidden="true" />
            Plans périmés encore consultés
          </p>
          <ul>
            {alertes.map((a, i) => (
              <li key={`${a.document_ged_id}-${a.destinataire}-${i}`}>
                Document #{a.document_ged_id} — {a.destinataire} a consulté la version {a.version_consultee}{' '}
                (dernière : {a.derniere_version})
              </li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={creer} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <ChantierSelect
          value={form.chantier}
          onChange={(v) => setForm({ ...form, chantier: v })}
          label="Chantier de la diffusion"
          required
        />
        <input
          placeholder="ID du document GED"
          value={form.document_ged_id}
          onChange={(e) => setForm({ ...form, document_ged_id: e.target.value })}
          aria-label="ID du document GED à diffuser"
          required
        />
        <input
          type="number" min="1"
          placeholder="Version"
          value={form.version_diffusee}
          onChange={(e) => setForm({ ...form, version_diffusee: e.target.value })}
          aria-label="Version diffusée"
          style={{ width: 70 }}
        />
        <select
          multiple
          value={internesChoisis}
          onChange={(e) => setInternesChoisis(
            Array.from(e.target.selectedOptions).map((o) => o.value),
          )}
          aria-label="Destinataires internes"
          style={{ minWidth: 160, height: 60 }}
        >
          {users.map((u) => (
            <option key={u.id} value={u.id}>{u.nom || u.username || u.email}</option>
          ))}
        </select>
        <input
          placeholder="Destinataires externes (emails séparés par des virgules)"
          value={form.destinataires_externes}
          onChange={(e) => setForm({ ...form, destinataires_externes: e.target.value })}
          aria-label="Destinataires externes"
          style={{ minWidth: 240 }}
        />
        <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer la diffusion'}</Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
          <thead>
            <tr>
              <th>Document</th><th>Version</th><th>Diffusée le</th>
              <th>Destinataires</th><th />
            </tr>
          </thead>
          <tbody>
            {diffusions.map((d) => (
              <tr key={d.id}>
                <td>#{d.document_ged_id}</td>
                <td>{d.version_diffusee}</td>
                <td>
                  {d.date_diffusion ? d.date_diffusion : <Badge tone="warning">Pas encore diffusée</Badge>}
                </td>
                <td>
                  {(d.destinataires_internes || []).length} interne(s), {(d.destinataires_externes || []).length} externe(s)
                </td>
                <td><Button variant="ghost" onClick={() => setSelectedId(d.id)}>Détails</Button></td>
              </tr>
            ))}
            {diffusions.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>Aucune diffusion</td></tr>
            )}
          </tbody>
        </table>
      )}

      {selected && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>
            Document #{selected.document_ged_id} — version {selected.version_diffusee}
          </h2>
          {!selected.date_diffusion && (
            <Button type="button" onClick={diffuser} disabled={acting}>Diffuser</Button>
          )}
          {selected.date_diffusion && (
            <p>Diffusée le {selected.date_diffusion}.</p>
          )}
          {Object.keys(selected.accuse_reception || {}).length > 0 && (
            <ul>
              {Object.entries(selected.accuse_reception).map(([cle, info]) => (
                <li key={cle}>
                  {cle} — {info.lu ? 'Lu' : 'Non lu'}{info.horodatage ? ` (${info.horodatage})` : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
