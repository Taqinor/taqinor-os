import { useEffect, useState, useCallback } from 'react'
import { Upload, Wand2 } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  policyPassed, assetPolicyRules, formatMAD, formatNumber,
} from './adsengine'

/* ============================================================================
   ENG27 — Bibliothèque créative du moteur publicitaire.
   ----------------------------------------------------------------------------
   - Grille des `CreativeAsset` (préview, type, perf par asset).
   - Flux policy-check ENG16 : checklist HUMAINE règle par règle (le système
     enregistre les confirmations, il n'évalue pas seul).
   - WIR170 — la check-list vient du SERVEUR (`GET creatifs/checklist/`) et la
     confirmation est postée sous la SEULE clé que le serveur lit :
     `confirmed_keys`. L'ancien payload (`{passed, rules_checked}`) était ignoré
     en silence : le serveur enregistrait zéro règle confirmée, `passed` restait
     faux, et l'écran affichait « Vérifié » de façon purement optimiste. Le
     statut affiché est désormais celui RENVOYÉ par le serveur, jamais deviné.
   - Upload d'un nouvel asset (pattern MinIO — l'asset naît pending policy).
   - Déclenchement de variantes ENG18 (assets enfants créés pending).
   ========================================================================== */

const TYPES = [
  { key: 'reel', label: 'Reel' },
  { key: 'static', label: 'Statique' },
  { key: 'explainer', label: 'Explainer' },
]
const EMPTY_UPLOAD = { designation: '', type: 'static', file: null }

export default function CreativeLibraryScreen() {
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(true)
  const [checkingId, setCheckingId] = useState(null)
  const [confirmed, setConfirmed] = useState(() => new Set()) // règles cochées
  const [upload, setUpload] = useState(EMPTY_UPLOAD)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  // WIR170 — règles INTERDITES telles que le serveur les définit (la policy est
  // par société) ; vide tant que la check-list n'a pas répondu → repli local.
  const [serverRules, setServerRules] = useState([])

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.creatives.list()
      .then(r => setAssets(Array.isArray(r.data) ? r.data : (r.data?.results || [])))
      .catch(() => setAssets([]))
      .finally(() => setLoading(false))
  }, [])

  const loadChecklist = useCallback(() => {
    adsengineApi.creatives.checklist()
      .then(r => {
        const forbidden = Array.isArray(r?.data?.forbidden) ? r.data.forbidden : []
        setServerRules(forbidden.filter(x => x && x.key))
      })
      .catch(() => setServerRules([]))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load(); loadChecklist() }, [load, loadChecklist])

  // Règles à confirmer : celles du serveur dès qu'elles sont connues, sinon le
  // repli local (l'écran reste utilisable si la check-list ne répond pas).
  const rulesFor = useCallback(
    (asset) => (serverRules.length ? serverRules : assetPolicyRules(asset)),
    [serverRules])

  const openCheck = (id) => { setCheckingId(id); setConfirmed(new Set()); setMsg('') }
  const toggleRule = (key) => setConfirmed(s => {
    const next = new Set(s)
    if (next.has(key)) next.delete(key); else next.add(key)
    return next
  })

  const validatePolicy = async (asset) => {
    const rules = rulesFor(asset)
    // Seules les clés RÉELLEMENT cochées partent au serveur — jamais la liste
    // complète « parce qu'on a cliqué Valider ».
    const confirmedKeys = rules.map(r => r.key).filter(k => confirmed.has(k))
    setBusy(true); setMsg('')
    try {
      const res = await adsengineApi.creatives.policyCheck(asset.id, {
        confirmed_keys: confirmedKeys,
      })
      const updated = res?.data && typeof res.data === 'object' ? res.data : null
      const passed = !!(updated
        && (updated.is_policy_passed ?? updated.policy_stamp?.passed))
      // Le statut affiché est celui que le SERVEUR renvoie — jamais optimiste.
      setAssets(list => list.map(a => (a.id === asset.id
        ? { ...a, ...(updated || {}) }
        : a)))
      if (passed) {
        setCheckingId(null)
        setMsg('Conformité enregistrée.')
      } else {
        const stamp = updated?.policy_stamp || {}
        setMsg(stamp.consent_block_label
          || 'Le serveur n\'a pas validé la conformité : l\'asset reste à vérifier.')
      }
    } catch {
      setMsg('Enregistrement de la conformité impossible.')
    } finally {
      setBusy(false)
    }
  }

  const submitUpload = async (e) => {
    e.preventDefault()
    if (!upload.file) { setMsg('Choisissez un fichier.'); return }
    setBusy(true); setMsg('')
    const fd = new FormData()
    fd.append('file', upload.file)
    fd.append('designation', upload.designation)
    fd.append('type', upload.type)
    try {
      await adsengineApi.creatives.upload(fd)
      setUpload(EMPTY_UPLOAD)
      setMsg('Créatif téléversé (en attente de vérification).')
      load()
    } catch {
      setMsg('Téléversement impossible.')
    } finally {
      setBusy(false)
    }
  }

  const generateVariants = async (id) => {
    setBusy(true); setMsg('')
    try {
      await adsengineApi.creatives.generateVariants(id)
      setMsg('Génération de variantes lancée (pending policy-check).')
      load()
    } catch {
      setMsg('Génération de variantes impossible.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page ae-creatives">
      <div className="page-header">
        <h2>Bibliothèque créative</h2>
      </div>

      {msg && <p data-testid="ae-creative-msg" style={{ color: '#475569' }}>{msg}</p>}

      {/* Upload d'un nouvel asset */}
      <form onSubmit={submitUpload} data-testid="ae-creative-upload-form"
        className="card" style={{ padding: '1rem', marginBottom: '1.25rem',
          display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'end' }}>
        <label style={{ display: 'grid', gap: '0.2rem', flex: '2 1 220px' }}>
          <span style={{ fontSize: '0.85rem', color: '#475569' }}>Désignation</span>
          <input className="form-input" data-testid="ae-creative-upload-designation"
            value={upload.designation}
            onChange={e => setUpload(u => ({ ...u, designation: e.target.value }))} />
        </label>
        <label style={{ display: 'grid', gap: '0.2rem', flex: '1 1 140px' }}>
          <span style={{ fontSize: '0.85rem', color: '#475569' }}>Type</span>
          <select className="form-input" data-testid="ae-creative-upload-type"
            value={upload.type}
            onChange={e => setUpload(u => ({ ...u, type: e.target.value }))}>
            {TYPES.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}
          </select>
        </label>
        <label style={{ display: 'grid', gap: '0.2rem', flex: '2 1 220px' }}>
          <span style={{ fontSize: '0.85rem', color: '#475569' }}>Fichier</span>
          <input className="form-input" type="file" data-testid="ae-creative-upload-file"
            onChange={e => setUpload(u => ({ ...u, file: e.target.files?.[0] || null }))} />
        </label>
        <button type="submit" className="btn btn-primary" data-testid="ae-creative-upload-submit"
          disabled={busy} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
          <Upload size={15} aria-hidden="true" /> Téléverser
        </button>
      </form>

      {/* Grille des assets */}
      {loading
        ? <p className="page-loading">Chargement…</p>
        : assets.length === 0
          ? <p data-testid="ae-creative-empty" style={{ color: '#64748b' }}>Aucun créatif.</p>
          : (
            <div style={{ display: 'grid', gap: '1rem',
              gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))' }}>
              {assets.map(a => {
                const passed = policyPassed(a)
                const rules = rulesFor(a)
                const allConfirmed = rules.every(r => confirmed.has(r.key))
                return (
                  <article key={a.id} className="card ae-creative-card" data-testid="ae-creative-card"
                    style={{ padding: '0.75rem', border: '1px solid #e2e8f0' }}>
                    {(() => {
                      const src = a.preview_url || a.file_url
                      // ADSDEEP15 — un reel/explainer se rend en <video> ; les
                      // statiques en <img>. `is_video` (backend) prime, repli
                      // sur le type d'asset.
                      const isVideo = a.is_video ?? ['reel', 'explainer'].includes(a.asset_type || a.type)
                      if (!src) {
                        return (
                          <div style={{ height: 90, background: '#f1f5f9', borderRadius: 6,
                            display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
                            {a.type || a.asset_type || 'créatif'}
                          </div>
                        )
                      }
                      return isVideo
                        ? <video data-testid="ae-creative-video" src={src} controls
                            style={{ width: '100%', maxHeight: 150, borderRadius: 6 }} />
                        : <img data-testid="ae-creative-img" src={src} alt={a.designation || 'Créatif'}
                            style={{ width: '100%', maxHeight: 150, objectFit: 'cover', borderRadius: 6 }} />
                    })()}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
                      <strong>{a.designation || 'Créatif'}</strong>
                      <span className="badge" data-testid={`ae-creative-status-${a.id}`}
                        style={{ background: passed ? '#dcfce7' : '#fef9c3',
                          color: passed ? '#166534' : '#854d0e' }}>
                        {passed ? 'Vérifié' : 'À vérifier'}
                      </span>
                    </div>
                    {/* Perf par asset */}
                    <p style={{ margin: '0.4rem 0 0', color: '#64748b', fontSize: '0.85rem' }}>
                      {formatNumber(a.reponses_whatsapp ?? a.perf?.reponses_whatsapp ?? 0)} réponses WhatsApp
                      {' · '}{formatMAD(a.cout_mad ?? a.perf?.cout_mad)}
                    </p>

                    {/* Flux policy-check (checklist humaine règle par règle) */}
                    {!passed && checkingId !== a.id && (
                      <button type="button" className="btn btn-light" data-testid={`ae-creative-check-${a.id}`}
                        onClick={() => openCheck(a.id)} style={{ marginTop: '0.5rem' }}>
                        Vérifier la conformité
                      </button>
                    )}
                    {!passed && checkingId === a.id && (
                      <div data-testid={`ae-creative-checklist-${a.id}`} style={{ marginTop: '0.5rem' }}>
                        <p style={{ margin: '0 0 0.35rem', fontSize: '0.85rem', color: '#475569' }}>
                          Confirmez chaque règle :
                        </p>
                        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.3rem' }}>
                          {rules.map(r => (
                            <li key={r.key}>
                              <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'flex-start' }}>
                                <input type="checkbox"
                                  data-testid={`ae-creative-rule-${a.id}-${r.key}`}
                                  checked={confirmed.has(r.key)} onChange={() => toggleRule(r.key)} />
                                <span style={{ fontSize: '0.85rem' }}>{r.label}</span>
                              </label>
                            </li>
                          ))}
                        </ul>
                        <button type="button" className="btn btn-success"
                          data-testid={`ae-creative-validate-${a.id}`}
                          disabled={busy || !allConfirmed} onClick={() => validatePolicy(a)}
                          style={{ marginTop: '0.5rem' }}>
                          Valider la conformité
                        </button>
                      </div>
                    )}

                    {/* Variantes ENG18 (sur un asset vérifié) */}
                    {passed && (
                      <button type="button" className="btn btn-light" data-testid={`ae-creative-variants-${a.id}`}
                        disabled={busy} onClick={() => generateVariants(a.id)}
                        style={{ marginTop: '0.5rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                        <Wand2 size={14} aria-hidden="true" /> Générer des variantes
                      </button>
                    )}
                  </article>
                )
              })}
            </div>
          )}
    </div>
  )
}
