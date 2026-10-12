// ENF15 — lit TOUTES les pages d'une liste DRF (jamais la seule page 1) et renvoie un tableau.
// `lire(params)` doit renvoyer la promesse axios du wrapper d'API, `params` portant `page`.
import fetchAllPages from '../../utils/fetchAllPages'

export default function toutesLesPages(lire, extra = {}) {
  return fetchAllPages((page) => lire({ ...extra, page }).then((r) => r.data), { concurrency: 3 })
    .then((rows) => (Array.isArray(rows) ? rows : (rows?.results ?? [])))
}
