/* ============================================================================
   NTMKT1 — MarketingDashboard : logique métier PURE (testable au node).
   ----------------------------------------------------------------------------
   4 KPI calculés depuis les endpoints RÉELS déjà en service
   (`marketing/campagnes/`, `marketing/envois-campagne/`, action `roi` de
   `marketing/campagnes/<id>/roi/`) — jamais de valeur fabriquée. Aucun champ
   `prix_achat`/marge n'entre dans ce calcul (campagnes/envois n'en portent
   pas).
   ========================================================================== */

// Statuts « actifs » d'une campagne (en file d'attente ou en cours d'envoi —
// ni brouillon, ni terminée/annulée). Miroir de `Campagne.Statut` (backend).
const STATUTS_ACTIFS = ['en_file', 'envoi_en_cours']

export function campagnesActives(campagnes) {
  return (campagnes || []).filter(c => STATUTS_ACTIFS.includes(c.statut)).length
}

// Taux d'ouverture moyen (pondéré par nb_envois) des campagnes ENVOYÉES dans
// les `fenetreDays` derniers jours (défaut 30). 0 si aucune campagne éligible
// (pas de division par zéro, pas de NaN affiché).
export function tauxOuvertureMoyen30j(campagnes, { now = new Date(), fenetreDays = 30 } = {}) {
  const seuil = new Date(now.getTime() - fenetreDays * 24 * 60 * 60 * 1000)
  let totalEnvois = 0
  let totalOuvertures = 0
  for (const c of campagnes || []) {
    if (!c.envoyee_le) continue
    const envoyee = new Date(c.envoyee_le)
    if (Number.isNaN(envoyee.getTime()) || envoyee < seuil) continue
    totalEnvois += c.nb_envois || 0
    totalOuvertures += c.nb_ouvertures || 0
  }
  if (!totalEnvois) return 0
  return Math.round((totalOuvertures / totalEnvois) * 1000) / 10
}

// Proxy « leads engagés du mois » (ouvert ou cliqué) — la vraie qualification
// MQL multi-signal vit dans NTMKT18 (non construite ici, XMKT21 threshold
// simple non exposé côté ce dashboard) : compte les contacts DISTINCTS ayant
// ouvert/cliqué un envoi de campagne ce mois-ci, à partir de la trace réelle
// `marketing/envois-campagne/`.
export function leadsEngagesDuMois(envois, { now = new Date() } = {}) {
  const annee = now.getFullYear()
  const mois = now.getMonth()
  const contacts = new Set()
  for (const e of envois || []) {
    if (e.statut !== 'ouvert' && e.statut !== 'clique') continue
    const date = new Date(e.date_creation)
    if (Number.isNaN(date.getTime())) continue
    if (date.getFullYear() !== annee || date.getMonth() !== mois) continue
    contacts.add(e.contact_ref || e.destinataire)
  }
  return contacts.size
}

// ROI cumulé (XMKT17) — agrège les réponses de l'action `roi` par campagne
// (coût réel vs revenu signé attribué). `roiEntries` = tableau de
// `{cout_mad, revenu_ttc_mad}` (chaînes décimales — parsées ici, jamais
// arrondies côté serveur pour l'agrégat). Renvoie 0 si aucun coût engagé.
export function roiCumulePct(roiEntries) {
  let cout = 0
  let revenu = 0
  for (const r of roiEntries || []) {
    cout += Number(r?.cout_mad) || 0
    revenu += Number(r?.revenu_ttc_mad) || 0
  }
  if (!cout) return 0
  return Math.round(((revenu - cout) / cout) * 1000) / 10
}
