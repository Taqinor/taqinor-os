import { formatNumber } from '../../../../lib/format'

/* Coque — les textes du bandeau du projet, lus sur le contexte servi (jamais inventés). */

/** ACAL1730 — le nom du lead (sinon du client) que sert le détail du calepinage ; `''` s'il n'en sert pas. */
export function nomClientServi(detail) {
  return String(detail?.lead?.nom || detail?.client?.nom || '').trim()
}

/** Le nom du projet à défaut du nom du lead : le titre servi (+ la ville servie quand il ne la dit pas). */
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

/* H1 (tour 3, repris par ACAL1730) — la ligne sous le nom dit la pose, lue sur le résultat SERVI (`resultat/` :
   `pose`, `electrique.onduleurs`) — la même source que « Ce qui est déjà sûr » : « 12 panneaux · 6,96 kWc · 1 onduleur
   6 kW », À TOUTE ÉTAPE et dans les deux modes (la facture du lead vit dans la carte de cible). Rien de servi :
   `''` (la ligne lead + facture reste). L'onduleur n'est dit que s'il est servi. */

function texteOnduleurs(onduleurs) {
  const lignes = (Array.isArray(onduleurs) ? onduleurs : [])
    .filter((o) => Number(o?.nombre) > 0 && Number(o?.taille_kw) > 0)
    .map((o) => `${o.nombre} onduleur${o.nombre > 1 ? 's' : ''} ${formatNumber(o.taille_kw, { locale: 'fr' })} kW`)
  return lignes.join(' + ')
}

export function sousTitrePose(resultat, vivante = null) {
  // Tant que la scène n'est pas enregistrée, la pose AFFICHÉE par la carte (`{ panneaux, kwc }` lus sur le constructeur) prime
  // sur la servie : changement de module, retraits, remplissage — l'en-tête ne reste pas sur l'ancienne pose. Le kWc n'est dit
  // que lu ; l'onduleur reste celui du résultat servi ; zéro panneau se dit tel quel.
  if (vivante && Number.isFinite(vivante.panneaux)) {
    if (vivante.panneaux <= 0) return 'Aucun panneau posé'
    const n = vivante.panneaux
    return [`${formatNumber(n, { decimals: 0, locale: 'fr' })} panneau${n > 1 ? 'x' : ''}`, vivante.kwc, texteOnduleurs(resultat?.electrique?.onduleurs)]
      .filter(Boolean).join(' · ')
  }
  const n = Number(resultat?.pose?.total_modules)
  const kwc = Number(resultat?.pose?.kwc)
  if (!(n > 0) || !(kwc > 0)) return ''
  const morceaux = [`${formatNumber(n, { decimals: 0, locale: 'fr' })} panneau${n > 1 ? 'x' : ''}`, `${formatNumber(kwc, { decimals: 2, locale: 'fr' })} kWc`]
  morceaux.push(texteOnduleurs(resultat?.electrique?.onduleurs))
  return morceaux.filter(Boolean).join(' · ')
}
