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
 */
import { useState, useEffect, useId, useRef } from 'react'
import crmApi from '../../../api/crmApi'
import useCanaux from '../../../features/crm/useCanaux'
import { Button } from '../../../ui'

// Dédoublonnage grossier : on retire les non-chiffres pour comparer.
function normalizePhone(raw) {
  return (raw || '').replace(/\D/g, '')
}

export default function LeadExpressModal({ onClose, onSaved }) {
  const formId = useId()
  const nomRef = useRef(null)

  const [nom, setNom] = useState('')
  const [telephone, setTelephone] = useState('')
  const [canal, setCanal] = useState('walk_in')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // FG35 — état de la vérification de doublons.
  // dupState: null (pas encore) | 'checking' | { warning: string|null }
  const [dupState, setDupState] = useState(null)

  const { options: canauxOptions, loaded: canauxLoaded } = useCanaux()

  // Mise au point auto sur le champ nom à l'ouverture.
  useEffect(() => { nomRef.current?.focus() }, [])

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
        canal: canal || null,
        // owner et company sont injectés côté serveur
      }
      const res = await crmApi.createLead(payload)
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
