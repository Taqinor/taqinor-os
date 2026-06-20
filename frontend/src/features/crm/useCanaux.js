import { useEffect, useState } from 'react'
import crmApi from '../../api/crmApi'
import { CANAL_LABELS } from './stages'

// L8 — référentiel Canal géré (Paramètres → CRM). Source unique pour les
// libellés et options de canal partagés par LeadForm, FilterBar et ChartsView,
// au lieu des constantes figées. On part TOUJOURS des libellés statiques (clés
// canoniques du modèle Lead) puis on superpose les canaux gérés non archivés
// renvoyés par /crm/canaux/ — un canal ajouté en Paramètres apparaît ainsi
// sans redéploiement. Repli silencieux sur les constantes si l'appel échoue.
//
// Renvoie :
//   labels  : { cle → libellé }  (statiques + gérés)
//   options : [{ value, label }] triées (ordre géré, sinon ordre des statiques)
export default function useCanaux() {
  const [managed, setManaged] = useState(null)

  useEffect(() => {
    let alive = true
    crmApi.getCanaux()
      .then((r) => {
        if (!alive) return
        const rows = r.data?.results ?? r.data ?? []
        setManaged(Array.isArray(rows) ? rows : [])
      })
      .catch(() => { if (alive) setManaged([]) })
    return () => { alive = false }
  }, [])

  // Libellés : statiques d'abord, écrasés/complétés par les canaux gérés actifs.
  const labels = { ...CANAL_LABELS }
  const orderHints = {}
  if (managed) {
    for (const c of managed) {
      if (!c || c.archived || !c.cle) continue
      labels[c.cle] = c.libelle || c.cle
      if (typeof c.ordre === 'number') orderHints[c.cle] = c.ordre
    }
  }

  // Options triées : par `ordre` géré quand présent, sinon ordre d'insertion
  // (les clés statiques gardent leur ordre d'origine).
  const keys = Object.keys(labels)
  const options = keys
    .map((k, i) => ({ value: k, label: labels[k], _o: orderHints[k] ?? (100 + i) }))
    .sort((a, b) => a._o - b._o)
    .map(({ value, label }) => ({ value, label }))

  return { labels, options, loaded: managed !== null }
}
