// VX239 — Doublons : aperçu de la forme téléphone NORMALISÉE, extrait de
// ClientForm.jsx (seul écran qui l'avait) pour être posé aussi sur
// LeadForm/LeadExpressModal. Aide visuelle UNIQUEMENT : ne modifie jamais la
// valeur tapée/stockée (contrairement au collage — VX237 — qui, lui, nettoie
// la valeur au moment du coller).
import { useMemo } from 'react'
import { canonicalPhoneMA } from '../lib/format'

export default function PhoneHint({ value, testId }) {
  const canon = useMemo(() => {
    const typed = (value ?? '').trim()
    if (!typed) return ''
    const c = canonicalPhoneMA(typed)
    return c && c !== typed ? c : ''
  }, [value])

  if (!canon) return null
  return (
    <p className="form-hint" data-testid={testId}>
      Forme normalisée : {canon}
    </p>
  )
}
