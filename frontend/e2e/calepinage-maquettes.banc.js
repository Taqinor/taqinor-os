// ACAL1748 — le BANC de `calepinage-maquettes.spec.js` : l'état de départ que chaque maquette suppose, posé PAR L'API
// (le tracé à la souris n'est pas l'objet de la spec). Un calepinage de banc a TOUJOURS un point de site (latitude et
// longitude du lead + `pin` du document) : sans lui la simulation ne tourne pas sur un vrai serveur.
//   • variante « complet » : toit non confirmé (pente de départ), module et onduleur désignés, série météo
//     SYNTHÉTIQUE déposée puis simulation lancée et attendue (borne `delaiSimulationMs`) ;
//   • variante « releve »  : pente MESURÉE au téléphone (le bouton « Mesurer encore » n'existe que pour elle).
// Chaque étape facultative (matériel, simulation) dit pourquoi elle n'a pas abouti au lieu d'échouer : la spec écrit
// alors « non atteint » dans la légende de la planche. Rien n'est jamais supprimé ni réglé sur la société.
import { expect } from '@playwright/test'
import { uniq, API_DJANGO, lireJson, telephoneMobileUnique } from './helpers'

const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 120_000 }
const LATITUDE = 33.5731 // Casablanca
const LONGITUDE = -7.5898
const ETATS_FINAUX = ['done', 'failed', 'error', 'erreur']

/** Un an d'heures SYNTHÉTIQUES (ensoleillement en cloche, saison sinusoïdale) : déterministe, hors ligne. Ce n'est PAS
 *  une mesure — le fournisseur déposé le dit. */
function serieMeteoSynthetique() {
  const lignes = ['horodatage;gi_w_m2;t2m_c;ws10m']
  const debut = Date.UTC(2020, 0, 1, 0, 0, 0)
  for (let h = 0; h < 366 * 24; h += 1) {
    const jour = Math.floor(h / 24)
    const saison = 0.65 + 0.35 * Math.sin(((jour - 80) / 366) * 2 * Math.PI)
    const soleil = Math.max(0, Math.sin((((h % 24) - 6) / 12) * Math.PI))
    const t = new Date(debut + h * 3_600_000).toISOString().replace('.000Z', 'Z')
    lignes.push(`${t};${Math.round(950 * saison * soleil)};${(16 + 6 * saison + 5 * soleil).toFixed(1)};3.2`)
  }
  return Buffer.from(lignes.join('\n'))
}

/** Le document du contrat, ramené à une toiture seule posée au point du site. */
function documentDuBanc(exemple, variante) {
  const doc = JSON.parse(JSON.stringify(exemple))
  doc.poseSurfaces = [] // toiture seule : pas de champ au sol, donc pas de choix de surfaces à faire
  doc.pin = { lat: LATITUDE, lng: LONGITUDE }
  doc.horizonProfile = {
    source: 'saisie',
    points: [0, 45, 90, 135, 180, 225, 270, 315].map((a, i) => ({ azimuthDeg: a, heightDeg: [2, 3, 6, 4, 1, 3, 8, 3][i] })),
    hauteurMaxDeg: 8,
  }
  for (const zone of doc.zones) {
    if (variante === 'releve') {
      zone.pitchDeg = 24
      zone.roofType = 'pitched'
      zone.pitchSource = { mode: 'degres', degres: 24, provenance: 'telephone' }
    } else {
      zone.pitchDeg = 22 // valeur de départ : jamais confirmée, jamais mesurée
      delete zone.pitchSource
    }
  }
  return doc
}

async function designerMateriel(request, id) {
  const lu = await lireJson(await request.get(`${CAL}/calepinages/${id}/entree-electrique/`, T), 'entrée électrique')
  const module = (lu.candidats?.modules || []).find((c) => c.fiche_complete)
  const onduleur = (lu.candidats?.onduleurs || []).find((c) => c.fiche_complete)
  if (!module || !onduleur) {
    return { ok: false, raison: `le catalogue de cette pile n'offre pas ${!module ? 'un module' : 'un onduleur'} à fiche complète` }
  }
  const r = await request.post(`${CAL}/calepinages/${id}/entree-electrique/`, { ...T, data: { module_produit: module.id, onduleur_produit: onduleur.id, optimiseur_produit: null } })
  return r.ok() ? { ok: true, module: module.libelle, onduleur: onduleur.libelle } : { ok: false, raison: `le serveur a refusé la désignation (HTTP ${r.status()})` }
}

async function simuler(request, id, delaiMs) {
  const meteo = await request.post(`${CAL}/calepinages/${id}/meteo-fichier/`, {
    ...T,
    multipart: {
      fichier: { name: 'banc-maquettes-synthetique.csv', mimeType: 'text/csv', buffer: serieMeteoSynthetique() },
      fournisseur: 'banc de la spec des maquettes (série synthétique, pas une mesure)',
    },
  })
  if (!meteo.ok()) return { etat: 'non_lancee', raison: `la série météo du banc a été refusée (HTTP ${meteo.status()})` }
  const lancement = await request.post(`${CAL}/calepinages/${id}/simuler/`, { ...T, data: { forcer: true } })
  if (!lancement.ok()) return { etat: 'non_lancee', raison: `le serveur a refusé la simulation (HTTP ${lancement.status()})` }
  const { job_id: job } = await lancement.json()
  let dernier = null
  try {
    await expect.poll(async () => {
      dernier = await (await request.get(`${CAL}/moteur/resultat/${job}/`, T)).json()
      return ETATS_FINAUX.includes(dernier.statut)
    }, { intervals: [3_000], timeout: delaiMs }).toBe(true)
  } catch {
    return { etat: 'delai', raison: `la simulation n'était pas finie après ${Math.round(delaiMs / 1000)} s (${dernier?.statut || 'sans réponse'} ${dernier?.progress_pct ?? '?'} %)` }
  }
  return dernier.statut === 'done'
    ? { etat: 'terminee', raison: null }
    : { etat: 'echec', raison: `la simulation a échoué : ${String(dernier.message_erreur || dernier.statut).slice(0, 160)}` }
}

/** Pose un lead + un calepinage de banc. Retourne { calId, leadId, variante, materiel, simulation }. */
export async function poserBanc(request, { exemple, variante = 'complet', delaiSimulationMs = 180_000 }) {
  const lead = await lireJson(await request.post(`${API_DJANGO}/crm/leads/`, {
    ...T,
    data: {
      nom: uniq('K2 — Maquettes'), ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel',
      facture_hiver: '900', gps_lat: LATITUDE.toFixed(6), gps_lng: LONGITUDE.toFixed(6),
    },
  }), 'lead')
  const cal = await lireJson(await request.post(`${CAL}/calepinages/`, { ...T, data: { lead: lead.id, titre: uniq('K2 — Maquettes') } }), 'calepinage')
  await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context (amorce)')
  const lu = await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/layout/`, T), 'layout')
  await lireJson(await request.post(`${CAL}/calepinages/${cal.id}/layout/`, {
    ...T, headers: { 'If-Match': `"${lu.empreinte_document || ''}"` }, data: { roof_layout: documentDuBanc(exemple, variante) },
  }), 'écriture du layout')
  const banc = { calId: cal.id, leadId: lead.id, variante, materiel: null, simulation: { etat: 'non_lancee', raison: 'variante sans simulation' } }
  if (variante !== 'complet') return banc
  banc.materiel = await designerMateriel(request, cal.id)
  banc.simulation = banc.materiel.ok
    ? await simuler(request, cal.id, delaiSimulationMs)
    : { etat: 'non_lancee', raison: `pas de simulation sans matériel : ${banc.materiel.raison}` }
  return banc
}
