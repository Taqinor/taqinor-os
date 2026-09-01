// VX54 — pagination DRF PARALLÈLE bornée, partagée par tous les slices qui
// doivent lire une liste complète (StockList/DevisList/FactureList/Dashboard
// étaient FAUX dès 101 enregistrements car ils ne lisaient que la page 1 ;
// crm/installations/sav lisaient toutes les pages mais en SÉRIE — un aller-
// retour réseau par page, ce qui gèle les écrans terrain à 250-500 ms de RTT).
//
// Stratégie : page 1 → lire `count` (ou avancer page à page si l'API ne
// renvoie pas `count`) → paralléliser les pages restantes par lots bornés à
// `concurrency`, jamais tout d'un coup — un `concurrency` élevé sur les DEVIS
// multiplie par ~38-109 requêtes SQL/page (QPERF1, non corrigé) côté serveur,
// donc les appelants DEVIS doivent passer une borne basse (~3-5) tant que ce
// N+1 n'est pas corrigé côté backend. Relever la borne devis quand QPERF1
// atterrit (@coord QPERF1).
//
// `fetchPage(page)` doit renvoyer `{ results, count, next }` (forme DRF).
// `onPage(results, { page, first })` (optionnel, PERF-CRM 2026-09-01) : appelé
// dès qu'une page ARRIVE — l'appelant peut afficher la première page tout de
// suite au lieu d'attendre la totalité (premier rendu « à la Odoo »). Le
// retour final reste inchangé (tableau complet, ordre des pages).
export async function fetchAllPages(
  fetchPage, { concurrency = 20, maxPages = 200, onPage } = {},
) {
  const first = await fetchPage(1)
  if (!first || !Array.isArray(first.results)) return first
  onPage?.(first.results, { page: 1, first: true })

  const results = [...first.results]
  const pageSize = first.results.length
  let totalPages = 1

  if (typeof first.count === 'number' && pageSize > 0) {
    totalPages = Math.min(Math.ceil(first.count / pageSize), maxPages)
  } else if (first.next) {
    // Pas de `count` exploitable : on ne connaît pas le total tant qu'on n'a
    // pas suivi `next` jusqu'au bout — on avance par lots bornés en
    // découvrant les pages suivantes au fur et à mesure.
    let page = 2
    let hasNext = true
    while (hasNext && page <= maxPages) {
      const batchPages = []
      for (let i = 0; i < concurrency && page <= maxPages; i += 1, page += 1) {
        batchPages.push(page)
      }
      const batch = await Promise.all(batchPages.map((p) => fetchPage(p)))
      for (const [i, data] of batch.entries()) {
        if (data?.results?.length) {
          results.push(...data.results)
          onPage?.(data.results, { page: batchPages[i], first: false })
        }
        if (!data?.next) hasNext = false
      }
    }
    return results
  }

  if (totalPages <= 1) return results

  // Total connu via `count` : toutes les pages restantes partent en lots
  // parallèles bornés à `concurrency`, jamais en escalier séquentiel.
  for (let start = 2; start <= totalPages; start += concurrency) {
    const batchPages = []
    for (let p = start; p < start + concurrency && p <= totalPages; p += 1) batchPages.push(p)
    const batch = await Promise.all(batchPages.map((p) => fetchPage(p)))
    for (const [i, data] of batch.entries()) {
      if (data?.results) {
        results.push(...data.results)
        onPage?.(data.results, { page: batchPages[i], first: false })
      }
    }
  }

  return results
}

export default fetchAllPages
