import { formatNumber } from '../../../../lib/format'

/* Coque — les textes du bandeau du projet, lus sur le contexte servi (jamais inventés). */

/** Le nom du projet : le titre servi (+ la ville servie quand il ne la dit pas). */
export function titreProjet({ devisId, devisReference, calepinageTitre, calepinageId, contexte }) {
  if (devisId) return `Devis ${devisReference || devisId}`
  const titre = calepinageTitre || `Calepinage ${calepinageId || '—'}`
  const ville = (contexte?.calepinage?.client_ville ?? '').trim()
  return ville && !titre.includes(ville) ? `${titre} — ${ville}` : titre
}

/** La ligne sous le nom : rattachement + facture du lead, seulement si servis. */
export function sousTitreProjet({ devisId, devisLabel, contexte }) {
  if (devisId) return devisLabel || ''
  const cal = contexte?.calepinage ?? {}
  const facture = Number(contexte?.consommation_lead?.facture_mensuelle_mad)
  // Jamais un mot seul : le rattachement n'est dit qu'avec la facture servie, sinon le client servi, sinon rien.
  if (facture > 0) {
    const rattachement = cal.lead != null ? 'Lead' : (cal.client != null ? 'Client' : null)
    return [rattachement, `facture ${formatNumber(facture, { locale: 'fr' })} MAD / mois`].filter(Boolean).join(' · ')
  }
  return (cal.devis_lie?.client_nom ?? '').trim()
}

/* H1 (tour 3) — maquettes Électrique / Schéma (« 12 panneaux · 6,96 kWc ») et Résultats / Documents (« … · 1 onduleur
   6 kW ») : à partir de l'étape 3, la ligne sous le nom dit la pose, lue sur le résultat SERVI (`resultat/` : `pose`,
   `electrique.onduleurs`) — la même source que « Ce qui est déjà sûr ». Rien de servi : `''` (la ligne lead + facture
   reste). L'onduleur n'est dit qu'aux étapes qui le montrent, et seulement s'il est servi. */
export const ETAPES_POSE = ['electrique', 'resultats', 'documents']
const AVEC_ONDULEUR = ['resultats', 'documents']

function texteOnduleurs(onduleurs) {
  const lignes = (Array.isArray(onduleurs) ? onduleurs : [])
    .filter((o) => Number(o?.nombre) > 0 && Number(o?.taille_kw) > 0)
    .map((o) => `${o.nombre} onduleur${o.nombre > 1 ? 's' : ''} ${formatNumber(o.taille_kw, { locale: 'fr' })} kW`)
  return lignes.join(' + ')
}

export function sousTitrePose(resultat, etape) {
  if (!ETAPES_POSE.includes(etape)) return ''
  const n = Number(resultat?.pose?.total_modules)
  const kwc = Number(resultat?.pose?.kwc)
  if (!(n > 0) || !(kwc > 0)) return ''
  const morceaux = [`${formatNumber(n, { decimals: 0, locale: 'fr' })} panneau${n > 1 ? 'x' : ''}`, `${formatNumber(kwc, { decimals: 2, locale: 'fr' })} kWc`]
  if (AVEC_ONDULEUR.includes(etape)) morceaux.push(texteOnduleurs(resultat?.electrique?.onduleurs))
  return morceaux.filter(Boolean).join(' · ')
}
