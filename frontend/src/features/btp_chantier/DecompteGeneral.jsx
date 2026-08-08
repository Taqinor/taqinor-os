import { useEffect, useMemo, useState } from 'react'
import { Calculator, Download } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import btpChantierApi from '../../api/btpChantierApi'
import { frenchError } from '../../lib/frenchError'
import ChantierSelect from './ChantierSelect'
import { useBtpChantierResource } from './useBtpChantierResource'

/* ============================================================================
   PACT67 — Décompte général et définitif (DGD, NTCON9/10) + comparatif
   déboursé sec vs facturé du chantier (NTCON11). Solde recalculé CÔTÉ
   SERVEUR, verrouillage définitif avec déverrouillage admin JOURNALISÉ,
   cycle notifier → contester ou finaliser.
   ========================================================================== */

const STATUT_LABEL = {
  projet: 'Projet', notifie: 'Notifié', accepte: 'Accepté',
  conteste: 'Contesté', definitif: 'Définitif',
}
const STATUT_TONE = {
  projet: 'neutral', notifie: 'warning', accepte: 'info',
  conteste: 'danger', definitif: 'success',
}

export default function DecompteGeneral() {
  const [chantierId, setChantierId] = useState('')

  const params = useMemo(() => ({ chantier: chantierId || undefined }), [chantierId])

  const { data: decomptes, loading, reload } = useBtpChantierResource(
    btpChantierApi.decomptes.list, params, [chantierId],
  )

  // ── Déboursé sec vs facturé (admin/responsable only) ────────────────────
  const [debourse, setDebourse] = useState(null)
  const [debourseErreur, setDebourseErreur] = useState('')

  useEffect(() => {
    if (!chantierId) {
      setDebourse(null)
      setDebourseErreur('')
      return
    }
    let cancelled = false
    btpChantierApi.debourseVsFacture(chantierId)
      .then((res) => { if (!cancelled) setDebourse(res.data) })
      .catch((err) => {
        if (cancelled) return
        setDebourse(null)
        setDebourseErreur(frenchError(err, 'Comparatif indisponible.'))
      })
    return () => { cancelled = true }
  }, [chantierId])

  // ── Création ─────────────────────────────────────────────────────────────
  const [form, setForm] = useState({ chantier: '', montant_marche_initial_ht: '' })
  const [saving, setSaving] = useState(false)

  const creer = async (event) => {
    event.preventDefault()
    if (!form.chantier) return
    setSaving(true)
    try {
      await btpChantierApi.decomptes.create({
        chantier: form.chantier,
        montant_marche_initial_ht: form.montant_marche_initial_ht || 0,
      })
      toast.success('DGD créé.')
      setForm({ ...form, montant_marche_initial_ht: '' })
      reload()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de créer ce DGD.'))
    } finally {
      setSaving(false)
    }
  }

  // ── DGD sélectionné (cycle + export) ────────────────────────────────────
  const [selectedId, setSelectedId] = useState(null)
  const selected = decomptes.find((d) => d.id === selectedId) || null
  const [motif, setMotif] = useState('')
  const [acting, setActing] = useState(false)
  const [exporting, setExporting] = useState(false)

  const agir = async (action) => {
    if (!selected) return
    setActing(true)
    try {
      if (action === 'notifier') {
        await btpChantierApi.decomptes.notifier(selected.id)
        toast.success('DGD notifié.')
      } else if (action === 'contester') {
        await btpChantierApi.decomptes.contester(selected.id, motif)
        toast.success('DGD contesté.')
      } else if (action === 'finaliser') {
        await btpChantierApi.decomptes.finaliser(selected.id)
        toast.success('DGD finalisé — verrouillé.')
      } else if (action === 'deverrouiller') {
        await btpChantierApi.decomptes.deverrouiller(selected.id, motif)
        toast.success('DGD déverrouillé.')
      }
      setMotif('')
      reload()
    } catch (err) {
      toast.error(frenchError(err, 'Action impossible sur ce DGD.'))
    } finally {
      setActing(false)
    }
  }

  const exporterPdf = async () => {
    if (!selected) return
    setExporting(true)
    try {
      const res = await btpChantierApi.decomptes.exportPdf(selected.id)
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `dgd-${selected.reference}.pdf`
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
        <Calculator size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Décompte général et définitif</h1>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <ChantierSelect value={chantierId} onChange={setChantierId} label="Filtrer par chantier" />
      </div>

      {chantierId && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16, marginBottom: 16 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, marginTop: 0 }}>Déboursé sec vs facturé</h2>
          {debourseErreur && <p style={{ color: '#ef4444' }}>{debourseErreur}</p>}
          {debourse && (
            <table style={{ borderCollapse: 'collapse' }}>
              <tbody>
                <tr><td>Main-d'œuvre</td><td>{debourse.main_oeuvre}</td></tr>
                <tr><td>Sous-traitance</td><td>{debourse.sous_traitance}</td></tr>
                <tr><td>Matériel</td><td>{debourse.materiel}</td></tr>
                <tr><td><strong>Déboursé sec total</strong></td><td><strong>{debourse.debourse_sec_total}</strong></td></tr>
                <tr><td>Situations facturées</td><td>{debourse.situations_facturees}</td></tr>
                <tr><td>Avenants approuvés</td><td>{debourse.avenants_approuves}</td></tr>
                <tr><td><strong>Facturé total</strong></td><td><strong>{debourse.facture_total}</strong></td></tr>
                <tr><td><strong>Marge</strong></td><td><strong>{debourse.marge}</strong></td></tr>
              </tbody>
            </table>
          )}
        </div>
      )}

      <form onSubmit={creer} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <ChantierSelect
          value={form.chantier}
          onChange={(v) => setForm({ ...form, chantier: v })}
          label="Chantier du DGD"
          required
        />
        <input
          type="number" step="0.01"
          placeholder="Montant marché initial HT"
          value={form.montant_marche_initial_ht}
          onChange={(e) => setForm({ ...form, montant_marche_initial_ht: e.target.value })}
          aria-label="Montant marché initial HT"
        />
        <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer le DGD'}</Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
          <thead>
            <tr>
              <th>Référence</th><th>Total avenants HT</th><th>Facturé HT</th>
              <th>Solde dû HT</th><th>Statut</th><th />
            </tr>
          </thead>
          <tbody>
            {decomptes.map((d) => (
              <tr key={d.id}>
                <td>{d.reference}</td>
                <td>{d.total_avenants_ht}</td>
                <td>{d.total_situations_facturees_ht}</td>
                <td>{d.solde_du_ht}</td>
                <td><Badge tone={STATUT_TONE[d.statut] || 'neutral'}>{STATUT_LABEL[d.statut] || d.statut}</Badge></td>
                <td><Button variant="ghost" onClick={() => setSelectedId(d.id)}>Détails</Button></td>
              </tr>
            ))}
            {decomptes.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>Aucun DGD</td></tr>
            )}
          </tbody>
        </table>
      )}

      {selected && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>
            DGD {selected.reference}{' '}
            <Badge tone={STATUT_TONE[selected.statut] || 'neutral'}>
              {STATUT_LABEL[selected.statut] || selected.statut}
            </Badge>
          </h2>
          <p>Solde dû HT : {selected.solde_du_ht}</p>

          <Button type="button" variant="outline" onClick={exporterPdf} disabled={exporting} style={{ marginBottom: 8 }}>
            <Download size={16} strokeWidth={1.75} aria-hidden="true" />
            {exporting ? 'Export…' : 'Exporter PDF'}
          </Button>

          {selected.statut !== 'definitif' ? (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <Button type="button" onClick={() => agir('notifier')} disabled={acting}>Notifier</Button>
              <input
                placeholder="Motif de contestation"
                value={motif}
                onChange={(e) => setMotif(e.target.value)}
                aria-label="Motif de contestation du DGD"
              />
              <Button type="button" variant="destructive" onClick={() => agir('contester')} disabled={acting || !motif}>
                Contester
              </Button>
              <Button type="button" variant="success" onClick={() => agir('finaliser')} disabled={acting}>
                Finaliser (verrouiller)
              </Button>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                placeholder="Motif de déverrouillage"
                value={motif}
                onChange={(e) => setMotif(e.target.value)}
                aria-label="Motif de déverrouillage du DGD"
              />
              <Button type="button" variant="outline" onClick={() => agir('deverrouiller')} disabled={acting || !motif}>
                Déverrouiller (admin)
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
