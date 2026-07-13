// VX239 — Doublons : avertissement EN DIRECT (non bloquant) extrait de
// LeadForm.jsx (seul écran qui l'avait) pour être posé aussi sur
// ClientForm/ClientQuickCreateModal — jusqu'ici limités à l'autocomplete NOM,
// aucun signal sur un téléphone/email déjà connu tapé à la main. Réutilise
// TEL QUEL l'endpoint existant `crmApi.checkDuplicates` (recherche parmi les
// leads de la société — la majorité des clients en proviennent, donc « ce
// contact existe déjà » reste le signal utile même à la création d'un
// client). Debounce léger (400 ms), jamais bloquant.
import { useEffect, useState } from 'react'
import crmApi from '../api/crmApi'

export function useDuplicateCheck(phone, email, { exclude } = {}) {
  const [dupMatches, setDupMatches] = useState([])

  useEffect(() => {
    const p = (phone ?? '').trim()
    const e = (email ?? '').trim()
    const t = setTimeout(() => {
      if (!p && !e) { setDupMatches([]); return }
      const params = {}
      if (p) params.telephone = p
      if (e) params.email = e
      if (exclude != null) params.exclude = exclude
      crmApi.checkDuplicates(params)
        .then((r) => setDupMatches(r.data || []))
        .catch(() => setDupMatches([]))
    }, 400)
    return () => clearTimeout(t)
  }, [phone, email, exclude])

  return dupMatches
}

export default useDuplicateCheck
