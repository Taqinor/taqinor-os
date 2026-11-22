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
  const parties = [
    cal.lead != null ? 'Lead' : (cal.client != null ? 'Client' : null),
    facture > 0 ? `facture ${formatNumber(facture, { locale: 'fr' })} MAD / mois` : null,
  ].filter(Boolean)
  return parties.join(' · ')
}
