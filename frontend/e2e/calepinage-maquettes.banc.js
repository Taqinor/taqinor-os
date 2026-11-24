// ACAL1748 / ACAL1806 — le BANC de `calepinage-maquettes.spec.js` : l'état de départ que chaque maquette suppose, posé PAR L'API
// (le tracé à la souris n'est pas l'objet de la spec). Un calepinage de banc a TOUJOURS un point de site (latitude et
// longitude du lead + `pin` du document) : sans lui la simulation ne tourne pas sur un vrai serveur.
//   • variante « complet » : UN pan de 12 modules (2 rangées de 6) dont le module du catalogue est CHOISI, pente de départ
//     jamais confirmée, module et onduleur désignés (longueurs de câble saisies), série météo SYNTHÉTIQUE déposée puis
//     simulation lancée et attendue (borne `delaiSimulationMs`) ;
//   • variante « releve »  : le même pan, pente MESURÉE au téléphone (le bouton « Mesurer encore » n'existe que pour elle).
// Chaque étape facultative (matériel, simulation) dit pourquoi elle n'a pas abouti au lieu d'échouer : la spec écrit alors
// « non atteint » dans la légende de la planche. Le banc ne pose NI cheminement de câble, NI matrice d'ombrage, et ne règle
// rien sur la société (norme électrique, réglages de pertes) : ce qui en dépend se lit sur la planche comme « à régler ».
// Rien n'est jamais supprimé.
import { expect } from '@playwright/test'
import { uniq, API_DJANGO, lireJson, telephoneMobileUnique } from './helpers'

const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 120_000 }
const LATITUDE = 33.5 // le point du contour de l'exemple du contrat (région de Casablanca) : pin, contour et lead s'accordent
const LONGITUDE = -7.6
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

/** Le document du contrat, ramené à UN pan de toiture au point du site : 12 modules (2 rangées de 6), le module du
 *  catalogue choisi sur ce pan quand le catalogue de la pile en offre un. */
function documentDuBanc(exemple, variante, module) {
  const doc = JSON.parse(JSON.stringify(exemple))
  doc.poseSurfaces = [] // toiture seule : pas de champ au sol, donc pas de choix de surfaces à faire
  doc.pin = { lat: LATITUDE, lng: LONGITUDE }
  doc.horizonProfile = {
    source: 'saisie',
    points: [0, 45, 90, 135, 180, 225, 270, 315].map((a, i) => ({ azimuthDeg: a, heightDeg: [2, 3, 6, 4, 1, 3, 8, 3][i] })),
    hauteurMaxDeg: 8,
  }
  doc.zones = [doc.zones[0]]
  const zone = doc.zones[0]
  // Le contour : un rectangle de 12,4 × 8,6 m posé au point du site, en [lng, lat] (l'exemple du contrat donne des sommets en mètres).
  const dLat = 1 / 111_320
  const dLng = dLat / Math.cos((LATITUDE * Math.PI) / 180)
  const coin = (x, y) => [LONGITUDE + x * dLng, LATITUDE + y * dLat]
  zone.vertices = [coin(0, 0), coin(12.4, 0), coin(12.4, 8.6), coin(0, 8.6)]
  doc.outline = [...zone.vertices].map(([lng, lat]) => [lat, lng])
  // T4-B4 (banc) — l'exemple du contrat décrit plusieurs objets EN MÈTRES (obstacle, zone d'exclusion, mesure) : posés
  // tels quels, ils tombaient à (lng 3, lat 2) / (0, 0) — le cadrage de la carte, de la 3D et de l'aperçu du plan de pose
  // englobait l'Afrique (« un point vert », échelle 1/13 660 116). Ils sont ramenés au toit, en [lng, lat] ; ce qui n'a
  // pas de sens sur la pile (fond de plan sans pièce jointe → 409, parcelle de 200 m, repère à 2 km) est retiré.
  zone.obstacles = (zone.obstacles || []).map((o) => {
    const [centerLng, centerLat] = coin(Number(o.centerLng) || 0, Number(o.centerLat) || 0)
    return { ...o, centerLng, centerLat }
  })
  doc.exclusionZones = (doc.exclusionZones || []).map((z) => ({ ...z, vertices: z.vertices.map(([x, y]) => coin(x, y)) }))
  doc.measurements = (doc.measurements || []).map((m) => ({ ...m, points: m.points.map(([x, y]) => coin(x, y)) }))
  delete doc.underlay
  delete doc.parcelle
  doc.reperesChantier = []
  doc.activeAreaId = zone.id
  const modules = []
  for (let rangee = 0; rangee < 2; rangee += 1) {
    // Pas des rangées 3,0 m (> 2,4 m de longueur du module) : à 1,8 m les deux rangées se chevauchaient sur la planche.
    for (let i = 0; i < 6; i += 1) modules.push({ n: rangee * 6 + i + 1, cx: 1.2 * i + 1.2, cy: 3.0 * rangee + 1.6, rangee: rangee === 0 ? 'A' : 'B' })
  }
  // Les centres des panneaux sont en mètres (est, nord) dans le repère `geometry.origin` = le coin (0, 0) du toit.
  zone.geometry = { ...zone.geometry, origin: coin(0, 0), panels: modules, count: modules.length }
  zone.neededPanels = modules.length
  if (module) {
    // Le module du pan = une ligne du catalogue `modules[]` de la racine, désignée par `geometry.moduleId` (là où l'atelier
    // et le serveur le lisent : `pans_du_document`) et CHOISIE (`geometry.moduleChoisi`, ACAL1415).
    doc.modules = [{ ...doc.modules[0], id: `produit-${module.id}`, produitId: module.id, libelle: module.libelle, source: 'catalogue' }]
    zone.geometry.moduleId = doc.modules[0].id
    zone.geometry.moduleChoisi = true
  }
  if (variante === 'releve') {
    zone.pitchDeg = 24
    zone.roofType = 'pitched'
    zone.pitchSource = { mode: 'degres', degres: 24, provenance: 'telephone' }
  } else {
    zone.pitchDeg = 22 // valeur de départ : jamais confirmée, jamais mesurée
    delete zone.pitchSource
  }
  // La pose suit la pente du pan (l'exemple gardait 15° : l'aperçu du plan de pose disait 15° quand l'écran disait 22°).
  zone.geometry.tiltDeg = zone.pitchDeg
  return doc
}

/** Les premiers module et onduleur à fiche COMPLÈTE du catalogue de la pile (`null` : le catalogue n'en offre pas). */
async function candidatsMateriel(request, id) {
  const lu = await lireJson(await request.get(`${CAL}/calepinages/${id}/entree-electrique/`, T), 'entrée électrique')
  return {
    module: (lu.candidats?.modules || []).find((c) => c.fiche_complete) || null,
    onduleur: (lu.candidats?.onduleurs || []).find((c) => c.fiche_complete) || null,
  }
}

async function designerMateriel(request, id, { module, onduleur }) {
  if (!module || !onduleur) {
    return { ok: false, raison: `le catalogue de cette pile n'offre pas ${!module ? 'un module' : 'un onduleur'} à fiche complète` }
  }
  const r = await request.post(`${CAL}/calepinages/${id}/entree-electrique/`, {
    ...T,
    data: { module_produit: module.id, onduleur_produit: onduleur.id, optimiseur_produit: null, dc_m: 14, ac_m: 10, temperature_min_c: 0, temperature_max_c: 70, phases: 1, inclure_prise_terre: true },
  })
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
  const candidats = variante === 'complet' ? await candidatsMateriel(request, cal.id) : { module: null, onduleur: null }
  const lu = await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/layout/`, T), 'layout')
  await lireJson(await request.post(`${CAL}/calepinages/${cal.id}/layout/`, {
    ...T, headers: { 'If-Match': `"${lu.empreinte_document || ''}"` }, data: { roof_layout: documentDuBanc(exemple, variante, candidats.module) },
  }), 'écriture du layout')
  const banc = { calId: cal.id, leadId: lead.id, variante, materiel: null, simulation: { etat: 'non_lancee', raison: 'variante sans simulation' } }
  if (variante !== 'complet') return banc
  banc.materiel = await designerMateriel(request, cal.id, candidats)
  banc.simulation = banc.materiel.ok
    ? await simuler(request, cal.id, delaiSimulationMs)
    : { etat: 'non_lancee', raison: `pas de simulation sans matériel : ${banc.materiel.raison}` }
  return banc
}
