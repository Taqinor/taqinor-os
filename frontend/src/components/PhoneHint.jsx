// VX239 — Doublons : aperçu de la forme téléphone NORMALISÉE, extrait de
// ClientForm.jsx (seul écran qui l'avait) pour être posé aussi sur
// LeadForm/LeadExpressModal. Aide visuelle UNIQUEMENT : ne modifie jamais la
// valeur tapée/stockée (contrairement au collage — VX237 — qui, lui, nettoie
// la valeur au moment du coller).
import { useMemo } from 'react'
import { canonicalPhoneMA, normalizePhoneE164 } from '../lib/format'

export default function PhoneHint({ value, testId }) {
  const canon = useMemo(() => {
    const typed = (value ?? '').trim()
    if (!typed) return ''
    const c = canonicalPhoneMA(typed)
    if (c && c !== typed) return c
    // 25/08/2026 — LANE NUMÉROS INTERNATIONAUX : un étranger à indicatif
    // explicite ('+' ou '00') n'a pas de forme « +212… » à prévisualiser
    // via canonicalPhoneMA (avant : aucun aperçu, silencieusement ignoré) —
    // on prévisualise quand même sa forme normalisée « +<indicatif>... ».
    const e164 = normalizePhoneE164(typed)
    if (e164 && !e164.startsWith('212')) {
      const withPlus = `+${e164}`
      return withPlus !== typed ? withPlus : ''
    }
    return ''
  }, [value])

  if (!canon) return null
  return (
    <p className="form-hint" data-testid={testId}>
      Forme normalisée : {canon}
    </p>
  )
}
