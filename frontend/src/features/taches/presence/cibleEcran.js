/* ============================================================================
   TCH102 — `cibleDepuisEcran` : l'objet de l'ERP que l'écran courant montre, ou `null`.
   C'est l'INVERSE de `liens_cibles.json` (la carte `{modèle: gabarit}` que le serveur lit pour
   `url_de_cible`, spec-6a §3.3-3.4) : pour une URL d'écran, la cible `{cible, id}` à lier.
   Trois cibles seulement (arbitrage A3 : lead, client, devis — celles dont l'app expose un sélecteur de
   visibilité). Aucune autre route ne mène à un lien : pas de bouton, pas de pré-lien.

   Les gabarits ne sont PAS recopiés : chacun se lit dans `entityRoutes.ROUTE` (la table que la recherche et la
   palette utilisent déjà) ; `TachesPresence.test.jsx` prouve que les trois sources — `liens_cibles.json`,
   cette fonction et `entityRoutes.ROUTE` — disent la même chose.
   ========================================================================== */
import { ROUTE, TYPE_LABEL } from '../../../lib/search/entityRoutes'

/** L'événement DOM de saisie UNIQUE (`c t`, palette, « Nouvelle tâche liée ») — celui de la coquille et de la feuille. */
export const EVENEMENT_SAISIR = 'taqinor:taches:saisir'

/** `cible` serveur → type d'entité de `entityRoutes` (les trois cibles liables en F4). */
export const ENTITE_DE_CIBLE = {
  'crm.lead': 'lead',
  'crm.client': 'client',
  'ventes.devis': 'devis',
}

/** Page de détail à segment (`/crm/leads/:id`, route déclarée par `crm/module.config.jsx`) : seul le lead en a une. */
const CHEMIN_DETAIL = { 'crm.lead': /^\/crm\/leads\/(\d+)\/?$/ }

/** « Lead », « Client », « Devis » : le libellé figé d'une cible (`TYPE_LABEL`), jamais un nom d'objet inventé. */
export const libelleDeCible = (cible) => TYPE_LABEL[ENTITE_DE_CIBLE[cible]] ?? ''

/** Les deux morceaux (chemin, paramètre) du gabarit `ROUTE[type]` : « /crm/leads?lead={id} » → ['/crm/leads', 'lead']. */
function decouper(cible) {
  const modele = ROUTE[ENTITE_DE_CIBLE[cible]]?.('{id}')
  if (typeof modele !== 'string') return null
  const [chemin, requete = ''] = modele.split('?')
  const parametre = requete.split('=')[0]
  return parametre ? { chemin, parametre } : null
}

const sansBarreFinale = (chemin) => (chemin.length > 1 ? chemin.replace(/\/+$/, '') : chemin)

/**
 * `{ pathname, search }` (la `location` du routeur) → `{ cible, id }` ou `null`.
 * Une valeur qui n'est pas un entier strictement positif ne donne jamais une cible.
 */
export function cibleDepuisEcran({ pathname = '', search = '' } = {}) {
  const chemin = sansBarreFinale(pathname)
  const requete = new URLSearchParams(search)
  for (const cible of Object.keys(ENTITE_DE_CIBLE)) {
    const detail = CHEMIN_DETAIL[cible]?.exec(chemin)
    const gabarit = decouper(cible)
    const brut = detail ? detail[1] : gabarit && chemin === gabarit.chemin ? requete.get(gabarit.parametre) : null
    if (brut != null && /^\d+$/.test(brut) && Number(brut) > 0) return { cible, id: Number(brut) }
  }
  return null
}

/** Les gabarits que les trois sources doivent partager : `{cible: '/crm/leads?lead={id}'}` (lus dans `ROUTE`). */
export const gabaritDeCible = (cible) => ROUTE[ENTITE_DE_CIBLE[cible]]?.('{id}') ?? null
