/**
 * FG35 — Lead express quick capture.
 *
 * Formulaire minimal (nom + téléphone + canal + owner=me) pour saisir un lead
 * rapidement (walk-in, salon, terrain mobile) sans ouvrir le lourd LeadForm.
 *
 * Comportement :
 *   - Vérification inline de doublons après saisie du téléphone (>= 8 chiffres)
 *     via GET /crm/leads/check-duplicates/?phone=… — avertissement non bloquant.
 *   - POST vers l'endpoint existant /crm/leads/ (identique au LeadForm).
 *   - Après création : appelle onSaved(lead) et se ferme.
 *   - XSAL8 — « Scanner une carte » (photo) pré-remplit le formulaire via
 *     l'OCR existant (503 douce sans clé configurée : message clair, aucune
 *     répétition automatique — l'utilisateur retombe sur la saisie manuelle).
 */
import { useState, useEffect, useId, useRef } from 'react'
import crmApi from '../../../api/crmApi'
import useCanaux from '../../../features/crm/useCanaux'
import { Button } from '../../../ui'

// Dédoublonnage grossier : on retire les non-chiffres pour comparer.
function normalizePhone(raw) {
  return (raw || '').replace(/\D/g, '')
}

// VX240(e) — dernier canal utilisé (localStorage, modifiable), même patron
// que VX93 (lireLastTva/lireDernierMode) : le canal ne reset plus en dur à
// 'walk_in' à chaque ouverture (un salon/terrain saisit rafale sur le même
// canal, retaper à chaque lead coûtait un clic évitable).
const LEAD_EXPRESS_CANAL_KEY = 'taqinor.leadExpress.lastCanal'
const lireLastCanal = () => {
  try { return window.localStorage.getItem(LEAD_EXPRESS_CANAL_KEY) || 'walk_in' }
  catch { return 'walk_in' }
}
const ecrireLastCanal = (v) => {
  try { if (v) window.localStorage.setItem(LEAD_EXPRESS_CANAL_KEY, v) }
  catch { /* localStorage indisponible (navigation privée, quota) : no-op */ }
}

export default function LeadExpressModal({ onClose, onSaved }) {
  const formId = useId()
  const nomRef = useRef(null)
  const scanInputRef = useRef(null)

  const [nom, setNom] = useState('')
  const [telephone, setTelephone] = useState('')
  const [societe, setSociete] = useState('')
  const [email, setEmail] = useState('')
  const [canal, setCanal] = useState(lireLastCanal)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // FG35 — état de la vérification de doublons.
  // dupState: null (pas encore) | 'checking' | { warning: string|null }
  const [dupState, setDupState] = useState(null)
  // XSAL8 — scan de carte de visite : null | 'scanning' | { error } | { ok }
  const [scanState, setScanState] = useState(null)
  // Une fois l'OCR détecté indisponible (clé absente), on masque le bouton
  // pour le reste de la session — évite de retenter un appel voué à échouer.
  const [scanUnavailable, setScanUnavailable] = useState(false)

  const { options: canauxOptions, loaded: canauxLoaded } = useCanaux()

  // Mise au point auto sur le champ nom à l'ouverture.
  useEffect(() => { nomRef.current?.focus() }, [])

  const handleScanFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // permet de rescanner la même photo si besoin
    if (!file) return
    setScanState('scanning')
    try {
      const res = await crmApi.scanCarteVisite(file)
      const data = res.data || {}
      if (data.nom) setNom(data.nom + (data.prenom ? ` ${data.prenom}` : ''))
      if (data.telephone) setTelephone(data.telephone)
      if (data.societe) setSociete(data.societe)
      if (data.email) setEmail(data.email)
      const dups = data.doublons ?? []
      setScanState({
        ok: true,
        warning: dups.length
          ? `Doublon possible : ${dups.slice(0, 2).map((d) => d.nom || '?').join(', ')}.`
          : null,
      })
    } catch (err) {
      if (err?.response?.status === 503) {
        setScanUnavailable(true)
        setScanState(null)
        return
      }
      const detail =
        err?.response?.data?.detail || 'Lecture de la carte impossible — saisie manuelle.'
      setScanState({ error: detail })
    }
  }

  // Vérification de doublons dès que le numéro est suffisamment long.
  useEffect(() => {
    const digits = normalizePhone(telephone)
    if (digits.length < 8) {
      // Pas assez de chiffres — on efface tout résultat précédent lors du prochain tick.
      const id = setTimeout(() => setDupState(null), 0)
      return () => clearTimeout(id)
    }
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDupState('checking')
    crmApi.checkDuplicates({ phone: telephone })
      .then((r) => {
        if (cancelled) return
        const dups = r.data ?? []
        if (dups.length > 0) {
          const names = dups.slice(0, 2).map((d) => d.nom || '?').join(', ')
          setDupState({
            warning: `Doublon possible : ${names}${dups.length > 2 ? ` + ${dups.length - 2} autre(s)` : ''}.`,
          })
        } else {
          setDupState({ warning: null })
        }
      })
      .catch(() => { if (!cancelled) setDupState({ warning: null }) })
    return () => { cancelled = true }
  }, [telephone])

  const dupChecking = dupState === 'checking'
  const dupWarning = dupState && typeof dupState === 'object' ? dupState.warning : null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!nom.trim()) { setError('Le nom est requis.'); return }
    setBusy(true)
    try {
      const payload = {
        nom: nom.trim(),
        telephone: telephone.trim() || null,
        societe: societe.trim() || null,
        email: email.trim() || null,
        canal: canal || null,
        // owner et company sont injectés côté serveur
      }
      const res = await crmApi.createLead(payload)
      ecrireLastCanal(canal)  // VX240(e) — mémorise le canal pour le prochain lead express
      onSaved?.(res.data)
      onClose?.()
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        (typeof err?.response?.data === 'string' ? err.response.data : null) ||
        'Erreur lors de la création du lead.'
      setError(detail)
    } finally {
      setBusy(false)
    }
  }

  // Fermeture par Echap.
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    /* Overlay centré */
    <div
      className="lem-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby={`${formId}-title`}
      onClick={(e) => { if (e.target === e.currentTarget) onClose?.() }}
    >
      <div className="lem-panel">
        <div className="lem-header">
          <h3 id={`${formId}-title`}>⚡ Nouveau lead express</h3>
          <button
            type="button"
            className="lem-close"
            aria-label="Fermer"
            onClick={onClose}
          >✕</button>
        </div>

        <form onSubmit={handleSubmit} noValidate className="lem-form">
          {/* XSAL8 — Scan de carte de visite (photo) : masqué sans clé OCR
              configurée (503 rencontrée une fois → bouton retiré). */}
          {!scanUnavailable && (
            <div className="lem-scan-row">
              <input
                ref={scanInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                capture="environment"
                onChange={handleScanFile}
                style={{ display: 'none' }}
              />
              <Button
                type="button"
                variant="outline"
                disabled={scanState === 'scanning'}
                onClick={() => scanInputRef.current?.click()}
              >
                {scanState === 'scanning' ? 'Lecture…' : '📇 Scanner une carte'}
              </Button>
              {scanState && scanState.error && (
                <p className="lem-scan-error" role="alert">{scanState.error}</p>
              )}
              {scanState && scanState.ok && scanState.warning && (
                <p className="lem-dup-warning" role="alert" aria-live="assertive">
                  ⚠ {scanState.warning}
                </p>
              )}
            </div>
          )}

          {/* Nom */}
          <label className="lem-label" htmlFor={`${formId}-nom`}>
            Nom <span aria-hidden="true" className="lem-required">*</span>
          </label>
          <input
            id={`${formId}-nom`}
            ref={nomRef}
            className="lem-input"
            type="text"
            placeholder="Nom du prospect"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            required
            autoComplete="off"
          />

          {/* Société (pré-remplie par le scan, éditable) */}
          <label className="lem-label" htmlFor={`${formId}-societe`}>Société</label>
          <input
            id={`${formId}-societe`}
            className="lem-input"
            type="text"
            placeholder="Société du prospect"
            value={societe}
            onChange={(e) => setSociete(e.target.value)}
            autoComplete="off"
          />

          {/* Téléphone */}
          <label className="lem-label" htmlFor={`${formId}-tel`}>Téléphone</label>
          <input
            id={`${formId}-tel`}
            className="lem-input"
            type="tel"
            placeholder="06 00 00 00 00"
            value={telephone}
            onChange={(e) => setTelephone(e.target.value)}
            autoComplete="off"
          />
          {dupChecking && (
            <p className="lem-dup-checking" aria-live="polite">
              Vérification des doublons…
            </p>
          )}
          {dupWarning && !dupChecking && (
            <p className="lem-dup-warning" role="alert" aria-live="assertive">
              ⚠ {dupWarning}
            </p>
          )}

          {/* E-mail (pré-rempli par le scan, éditable) */}
          <label className="lem-label" htmlFor={`${formId}-email`}>E-mail</label>
          <input
            id={`${formId}-email`}
            className="lem-input"
            type="email"
            placeholder="contact@exemple.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="off"
          />

          {/* Canal */}
          <label className="lem-label" htmlFor={`${formId}-canal`}>Canal</label>
          <select
            id={`${formId}-canal`}
            className="lem-input"
            value={canal}
            onChange={(e) => setCanal(e.target.value)}
            disabled={!canauxLoaded}
          >
            <option value="">— Choisir —</option>
            {canauxOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          {error && (
            <p className="lem-error" role="alert">{error}</p>
          )}

          <div className="lem-actions">
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              Annuler
            </Button>
            <Button type="submit" disabled={busy || !nom.trim()}>
              {busy ? 'Création…' : 'Créer le lead'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
