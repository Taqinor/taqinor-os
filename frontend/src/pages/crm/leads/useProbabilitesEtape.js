import { useEffect, useState } from 'react'
import reportingApi from '../../../api/reportingApi'

// AANA67 — LA table des probabilités par étape est SERVIE (AANA66,
// contrat reporting/contract_samples/probabilites_etape.json) : lue UNE fois
// par session, jamais de table locale. `null` = pas encore chargée / en erreur.
let _lecture = null
const charger = () => {
  _lecture ??= Promise.resolve()
    .then(() => reportingApi.getProbabilitesEtape())
    .then((r) => r?.data?.probabilites ?? null)
    .catch(() => null)
    .then((t) => { if (!t) _lecture = null; return t })
  return _lecture
}

export function useProbabilitesEtape() {
  const [table, setTable] = useState(null)
  useEffect(() => {
    let vivant = true
    charger().then((t) => { if (vivant) setTable(t) })
    return () => { vivant = false }
  }, [])
  return table
}

// Pondéré d'un montant à une étape ; `null` tant que la table manque (⇒ « — »).
export const ponderer = (table, stage, montant) =>
  (table ? montant * (table[stage] ?? 0) : null)
