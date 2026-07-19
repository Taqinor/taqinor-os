import { useEffect, useRef, useState } from 'react'
import marketingApi from '../../api/marketingApi'
import { ruleFormFromRegles, buildRegles, reglesKey } from './segmentRules'

/* ============================================================================
   NTMKT4 — Constructeur de segment no-code + prévisualisation live.
   ----------------------------------------------------------------------------
   Champs lead whitelistés (ville/type d'installation/tags/canal/score/
   facture d'énergie — `apps.crm.selectors.LEAD_SEGMENT_FIELDS`) + activité
   marketing (a ouvert/a cliqué/jamais ouvert) au-dessus de
   `marketing/segments-marketing/`. Une fois le segment créé (nom renseigné,
   premier « Créer »), chaque changement de règle ré-enregistre le brouillon
   (PATCH) puis rappelle `previsualiser/` (compte + échantillon RÉELS,
   ré-évalués côté serveur — jamais mis en cache) : la prévisualisation reste
   TOUJOURS le reflet exact des règles persistées, à <1s d'un changement.
   ========================================================================== */

const TYPES_INSTALLATION = [
  { key: '', label: 'Tous types' },
  { key: 'residentiel', label: 'Résidentiel' },
  { key: 'commercial', label: 'Commercial' },
  { key: 'industriel', label: 'Industriel' },
  { key: 'agricole', label: 'Agricole' },
]
const CANAUX = [
  { key: '', label: 'Tous canaux' },
  { key: 'meta_ads', label: 'Publicité Meta' },
  { key: 'whatsapp_ctwa', label: 'WhatsApp/CTWA' },
  { key: 'site_web', label: 'Site web' },
  { key: 'reference', label: 'Référence' },
  { key: 'telephone', label: 'Téléphone' },
  { key: 'walk_in', label: 'Visite/Walk-in' },
  { key: 'autre', label: 'Autre' },
]
const ACTIVITES = [
  { key: '', label: 'Sans condition' },
  { key: 'a_ouvert', label: 'A ouvert une campagne' },
  { key: 'a_clique', label: 'A cliqué un lien' },
  { key: 'jamais_ouvert', label: "N'a jamais ouvert" },
]

export default function SegmentBuilder({ initial, onSaved, onCancel }) {
  const [nom, setNom] = useState(initial?.nom || '')
  const [form, setForm] = useState(ruleFormFromRegles(initial?.regles))
  const [segmentId, setSegmentId] = useState(initial?.id || null)
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [err, setErr] = useState('')
  const lastKey = useRef(null)

  const setChamp = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  // Prévisualisation live : dès qu'un segment existe (id posé) ET que les
  // règles ont réellement changé, on persiste le brouillon puis on
  // re-prévisualise depuis le serveur.
  useEffect(() => {
    if (!segmentId) return
    const key = reglesKey(form)
    if (key === lastKey.current) return
    lastKey.current = key
    let cancelled = false
    setPreviewLoading(true)
    marketingApi.segments.update(segmentId, { regles: buildRegles(form) })
      .then(() => marketingApi.segments.previsualiser(segmentId))
      .then(r => { if (!cancelled) setPreview(r.data) })
      .catch(() => { if (!cancelled) setErr('Prévisualisation impossible.') })
      .finally(() => { if (!cancelled) setPreviewLoading(false) })
    return () => { cancelled = true }
  }, [form, segmentId])

  const creerBrouillon = async () => {
    if (!nom.trim()) { setErr('Nom requis.'); return }
    setErr('')
    try {
      const r = await marketingApi.segments.create({ nom, regles: buildRegles(form) })
      setSegmentId(r.data.id)
    } catch {
      setErr('Création impossible.')
    }
  }

  const enregistrerNom = async () => {
    if (!segmentId) return creerBrouillon()
    try {
      await marketingApi.segments.update(segmentId, { nom })
      onSaved?.()
    } catch {
      setErr('Enregistrement impossible.')
    }
  }

  return (
    <div data-testid="segment-builder" style={{ display: 'grid', gap: '0.6rem', maxWidth: 640 }}>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <input className="form-input" data-testid="segment-nom"
          placeholder="Nom du segment" value={nom}
          onChange={e => setNom(e.target.value)} style={{ flex: 1 }} />
        {!segmentId && (
          <button type="button" className="btn btn-primary"
            data-testid="segment-creer" onClick={creerBrouillon}>
            Créer
          </button>
        )}
      </div>

      <fieldset style={{ border: '1px solid #e2e8f0', borderRadius: 8,
        padding: '0.5rem 0.75rem', display: 'grid', gap: '0.4rem' }}>
        <legend style={{ fontSize: '0.8rem', color: '#475569' }}>Règles (lead)</legend>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <input className="form-input" placeholder="Ville" data-testid="segment-ville"
            value={form.ville} onChange={setChamp('ville')} style={{ flex: '1 1 160px' }} />
          <select className="form-input" data-testid="segment-type-installation"
            value={form.type_installation} onChange={setChamp('type_installation')}
            style={{ flex: '1 1 160px' }}>
            {TYPES_INSTALLATION.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}
          </select>
          <select className="form-input" data-testid="segment-canal"
            value={form.canal} onChange={setChamp('canal')} style={{ flex: '1 1 160px' }}>
            {CANAUX.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
          <input className="form-input" placeholder="Tag" data-testid="segment-tags"
            value={form.tags} onChange={setChamp('tags')} style={{ flex: '1 1 120px' }} />
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <label style={{ fontSize: '0.78rem', color: '#64748b' }}>
            Score ≥
            <input type="number" className="form-input" data-testid="segment-score-gte"
              value={form.score_gte} onChange={setChamp('score_gte')} />
          </label>
          <label style={{ fontSize: '0.78rem', color: '#64748b' }}>
            Score ≤
            <input type="number" className="form-input" data-testid="segment-score-lte"
              value={form.score_lte} onChange={setChamp('score_lte')} />
          </label>
          <label style={{ fontSize: '0.78rem', color: '#64748b' }}>
            Facture énergie ≥
            <input type="number" className="form-input" data-testid="segment-facture-gte"
              value={form.facture_gte} onChange={setChamp('facture_gte')} />
          </label>
          <label style={{ fontSize: '0.78rem', color: '#64748b' }}>
            Facture énergie ≤
            <input type="number" className="form-input" data-testid="segment-facture-lte"
              value={form.facture_lte} onChange={setChamp('facture_lte')} />
          </label>
        </div>
        <select className="form-input" data-testid="segment-activite"
          value={form.activite} onChange={setChamp('activite')}>
          {ACTIVITES.map(a => <option key={a.key} value={a.key}>{a.label}</option>)}
        </select>
      </fieldset>

      <div data-testid="segment-preview"
        style={{ border: '1px dashed #cbd5e1', borderRadius: 8, padding: '0.6rem' }}>
        {!segmentId && (
          <p style={{ color: '#94a3b8', margin: 0 }}>
            Donnez un nom et cliquez « Créer » pour voir le compte en direct.
          </p>
        )}
        {segmentId && previewLoading && <p style={{ margin: 0 }}>Calcul…</p>}
        {segmentId && !previewLoading && preview && (
          <p data-testid="segment-preview-compte" style={{ margin: 0, fontWeight: 600 }}>
            {preview.count} lead(s) correspondant(s)
          </p>
        )}
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        {segmentId && (
          <button type="button" className="btn btn-primary" data-testid="segment-enregistrer"
            onClick={enregistrerNom}>
            Enregistrer
          </button>
        )}
        {onCancel && (
          <button type="button" className="btn btn-light" onClick={onCancel}>Fermer</button>
        )}
      </div>
    </div>
  )
}
