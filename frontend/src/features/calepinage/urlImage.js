import { originFrom } from '../../api/origin'

/* ACAL197 — `image.url` est RELATIVE (`/api/django/…`) : préfixée par l'origine
   de l'API (vide = même origine que la page). Une URL absolue reste telle quelle.
   Lot 2 critique #26 — UN helper pour la liste ET la fiche du calepinage. */
const ORIGINE_API = originFrom(import.meta.env.VITE_API_URL)

export const urlImage = (url) => (url && url.startsWith('/') ? `${ORIGINE_API}${url}` : url)
