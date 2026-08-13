import { useMemo, useState } from 'react'
import { FileEdit } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from './ChantierSelect'
import { useBtpChantierResource } from './useBtpChantierResource'

/* ============================================================================
   PACT66 — Avenants de chantier : chiffrage et approbation client (NTCON7/8).
   Écran INTERNE : lignes chiffrées, envoi au client (lien public tokenisé,
   signature loi 53-05), suivi de signature — la page que le client ouvre
   reste hors périmètre de cette tâche.
   ========================================================================== */

const STATUT_LABEL = {
  brouillon: 'Brouillon', soumis_client: 'Soumis au client',
  approuve: 'Approuvé', refuse: 'Refusé',
}
const STATUT_TONE = {
  brouillon: 'neutral', soumis_client: 'warning', approuve: 'success', refuse: 'danger',
}

export default function AvenantsChantier() {
  const [chantierId, setChantierId] = useState('')
  const [statut, setStatut] = useState('')

  const params = useMemo(() => ({
    chantier: chantierId || undefined, statut: statut || undefined,
  }), [chantierId, statut])

  const { data: avenants, loading, reload } = useBtpChantierResource(
    btpChantierApi.avenants.list, params, [chantierId, statut],
  )

  const [form, setForm] = useState({
    chantier: '', description: '', montant_ht: '', impact_delai_jours: '', impact_budget: false,
  })
  const [saving, setSaving] = useState(false)

  const creer = async (event) => {
    event.preventDefault()
    if (!form.chantier || !form.description || !form.montant_ht) return
    setSaving(true)
    try {
      await btpChantierApi.avenants.create({
        chantier: form.chantier,
        description: form.description,
        montant_ht: form.montant_ht,
        impact_delai_jours: form.impact_delai_jours ? Number(form.impact_delai_jours) : undefined,
        impact_budget: form.impact_budget,
      })
      toast.success('Avenant créé.')
      setForm({ ...form, description: '', montant_ht: '', impact_delai_jours: '', impact_budget: false })
      reload()
    } catch (err) {
      toast.error(frenchError(err, "Impossible de créer l'avenant."))
    } finally {
      setSaving(false)
    }
  }

  const [selectedId, setSelectedId] = useState(null)
  const selected = avenants.find((a) => a.id === selectedId) || null
  const [lienPublic, setLienPublic] = useState('')
  const [motifRefus, setMotifRefus] = useState('')
  const [acting, setActing] = useState(false)

  const faireApprouver = async () => {
    if (!selected) return
    setActing(true)
    try {
      const res = await btpChantierApi.avenants.faireApprouver(selected.id)
      setLienPublic(res?.data?.lien_public || '')
      toast.success('Avenant envoyé au client.')
      reload()
    } catch (err) {
      toast.error(frenchError(err, "Impossible d'envoyer l'avenant au client."))
    } finally {
      setActing(false)
    }
  }

  const approuver = async () => {
    if (!selected) return
    setActing(true)
    try {
      await btpChantierApi.avenants.approuver(selected.id)
      toast.success('Avenant approuvé.')
      reload()
    } catch (err) {
      toast.error(frenchError(err, "Impossible d'approuver l'avenant."))
    } finally {
      setActing(false)
    }
  }

  const refuser = async () => {
    if (!selected || !motifRefus) return
    setActing(true)
    try {
      await btpChantierApi.avenants.refuser(selected.id, motifRefus)
      toast.success('Avenant refusé.')
      setMotifRefus('')
      reload()
    } catch (err) {
      toast.error(frenchError(err, "Impossible de refuser l'avenant."))
    } finally {
      setActing(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <FileEdit size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Avenants de chantier</h1>
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
          label="Chantier de l'avenant"
          required
        />
        <input
          placeholder="Description"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          aria-label="Description de l'avenant"
          required
        />
        <input
          type="number" step="0.01"
          placeholder="Montant HT"
          value={form.montant_ht}
          onChange={(e) => setForm({ ...form, montant_ht: e.target.value })}
          aria-label="Montant HT"
          required
        />
        <input
          type="number"
          placeholder="Impact délai (j)"
          value={form.impact_delai_jours}
          onChange={(e) => setForm({ ...form, impact_delai_jours: e.target.value })}
          aria-label="Impact délai en jours"
          style={{ width: 90 }}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <input
            type="checkbox"
            checked={form.impact_budget}
            onChange={(e) => setForm({ ...form, impact_budget: e.target.checked })}
          />
          Impact budget projet (sinon facture d'acompte)
        </label>
        <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : "Créer l'avenant"}</Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
          <thead>
            <tr><th>Référence</th><th>Description</th><th>Montant HT</th><th>Statut</th><th /></tr>
          </thead>
          <tbody>
            {avenants.map((a) => (
              <tr key={a.id}>
                <td>{a.reference}</td>
                <td>{a.description}</td>
                <td>{a.montant_ht}</td>
                <td><Badge tone={STATUT_TONE[a.statut] || 'neutral'}>{STATUT_LABEL[a.statut] || a.statut}</Badge></td>
                <td>
                  <Button variant="ghost" onClick={() => { setSelectedId(a.id); setLienPublic('') }}>
                    Détails
                  </Button>
                </td>
              </tr>
            ))}
            {avenants.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>Aucun avenant</td></tr>
            )}
          </tbody>
        </table>
      )}

      {selected && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>
            Avenant {selected.reference}{' '}
            <Badge tone={STATUT_TONE[selected.statut] || 'neutral'}>
              {STATUT_LABEL[selected.statut] || selected.statut}
            </Badge>
          </h2>
          <p>{selected.description} — {selected.montant_ht} MAD HT</p>

          {selected.statut === 'brouillon' && (
            <Button type="button" onClick={faireApprouver} disabled={acting}>
              Envoyer au client
            </Button>
          )}

          {lienPublic && (
            <p>
              Lien public d'approbation : <code>{lienPublic}</code>
            </p>
          )}

          {(selected.statut === 'brouillon' || selected.statut === 'soumis_client') && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8, flexWrap: 'wrap' }}>
              <Button type="button" variant="success" onClick={approuver} disabled={acting}>
                Approuver en interne
              </Button>
              <input
                placeholder="Motif de refus"
                value={motifRefus}
                onChange={(e) => setMotifRefus(e.target.value)}
                aria-label="Motif de refus de l'avenant"
              />
              <Button type="button" variant="destructive" onClick={refuser} disabled={acting || !motifRefus}>
                Refuser
              </Button>
            </div>
          )}

          {selected.statut === 'approuve' && selected.date_approbation && (
            <p>Approuvé le {selected.date_approbation}.</p>
          )}
          {selected.statut === 'refuse' && selected.motif_refus && (
            <p>Motif de refus : {selected.motif_refus}</p>
          )}
        </div>
      )}
    </div>
  )
}
