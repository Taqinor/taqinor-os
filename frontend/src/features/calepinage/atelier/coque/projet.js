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
