/* ADOC30 — helpers de lecture partagés par le navigateur GED et l'écran
   Numériser (une seule copie). */
import { fetchAllPages } from '../../utils/fetchAllPages'

// Le backend pagine certains endpoints (DRF) : on accepte `results` OU le
// tableau brut, comme partout dans le frontend.
export const rows = (r) => r?.data?.results ?? r?.data ?? []

// Une liste GED paginée se lit EN ENTIER (StandardPagination : 50 par défaut,
// 200 max) : jamais la seule première page.
export const toutesLesPages = async (appel, params) => {
  const res = await fetchAllPages(
    (page) => appel({ ...params, page, page_size: 200 }).then((r) => r?.data))
  return Array.isArray(res) ? res : (res?.results ?? [])
}

// Message d'erreur lisible à partir d'une réponse axios (premier champ d'erreur
// DRF, ou message générique). Évite d'afficher un objet brut dans un toast.
export const errText = (e, fallback) => {
  const d = e?.response?.data
  if (typeof d === 'string') return d
  if (d && typeof d === 'object') {
    const first = d.detail ?? Object.values(d)[0]
    if (Array.isArray(first)) return String(first[0])
    if (first) return String(first)
  }
  return fallback
}
