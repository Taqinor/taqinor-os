/* ADOC30 — helpers de lecture partagés par le navigateur GED et l'écran
   Numériser (une seule copie). */
import { fetchAllPages } from '../../utils/fetchAllPages'
import { toast } from '../../ui'

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

// AERR55 — l'intercepteur axios (`api/axios.js`) toaste déjà tout échec serveur
// (réponse reçue ou réseau coupé) sauf le 401 et le 404 : l'écran GED ne répète
// pas son message. Il ne parle que si personne n'a parlé (404, erreur locale),
// avec le message servi s'il existe (jamais d'objet brut).
export const toastSiMuet = (e, fallback = 'Une erreur est survenue — réessayez.') => {
  const statut = e?.response?.status
  if ((e?.response && statut !== 404 && statut !== 401) || (!e?.response && e?.request)) return
  const d = e?.response?.data
  const premier = d && typeof d === 'object' ? (d.detail ?? Object.values(d)[0]) : d
  const texte = Array.isArray(premier) ? premier[0] : premier
  toast.error(texte ? String(texte) : fallback)
}
