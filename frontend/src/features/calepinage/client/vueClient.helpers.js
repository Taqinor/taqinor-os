import { creerRepere, lngLatVersMetres, ORDRE_LNGLAT } from '../repere'
import { modulesDuDocument } from '@roofpro/modulesGeo'
import { formatNumber } from '../../../lib/format'
import { useLectureServie } from '../atelier/coque/etapes/panneaux/lectures'
import { productionPubliee } from '../atelier/coque/etapes/panneaux/sources'

/* ============================================================================
   « MONTRER AU CLIENT » — lectures pures (maquette TelephoneClient).
   Chaque chiffre vient du calepinage ENREGISTRÉ (son document) ou de son résultat
   PUBLIÉ (`GET resultat/`) ; une tuile sans donnée servie est omise. Aucun prix, aucune
   marge, aucun prix d'achat : rien de monétaire n'est lu ici.
   ========================================================================== */

const zonesTracees = (document) => (Array.isArray(document?.zones) ? document.zones : [])
  .filter((z) => z && Array.isArray(z.vertices) && z.vertices.length >= 3)

/** Les pans et les modules du document, en mètres locaux (y vers le nord), ou `null` sans pan. */
export function planDessus(document) {
  const zones = zonesTracees(document)
  if (!zones.length) return null
  const repere = creerRepere({ origine_lnglat: zones[0].vertices[0], ordre: ORDRE_LNGLAT })
  const versM = (p) => lngLatVersMetres(repere, p, ORDRE_LNGLAT)
  const pans = zones.map((z) => z.vertices.map(versM))
  const modules = modulesDuDocument(document).flatMap((pan) => pan.quads.map((q) => q.map(versM)))
  const tous = [...pans.flat(), ...modules.flat()]
  const xs = tous.map((p) => p.x)
  const ys = tous.map((p) => p.y)
  return { pans, modules, minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) }
}

/** Le nombre de panneaux POSÉS dans le document enregistré (centres des modules), ou `null`. */
export function panneauxDuDocument(document) {
  const zones = Array.isArray(document?.zones) ? document.zones : []
  const n = zones.reduce((t, z) => t + (Array.isArray(z?.geometry?.panels) ? z.geometry.panels.length : 0), 0)
  return n > 0 ? n : null
}

/** Le pan actif (sinon le premier) : son libellé, pour la puce du projet. */
export function libellePan(document) {
  const zones = zonesTracees(document)
  const actif = zones.find((z) => String(z.id) === String(document?.activeAreaId)) ?? zones[0]
  return (actif?.label ?? '').trim()
}

/** La puissance installée du toit ENREGISTRÉ, lue par le serveur sur ce document (`resultat.pose.kwc`,
    `services/electrique.py::resultat_calepinage` → `bloc_pose`) — un fait de la pose, pas une estimation ; dite
    seulement quand cette pose compte LES panneaux dessinés (`panneaux`), sinon omise. */
function puissancePose(resultat, panneaux) {
  const kwc = Number(resultat?.pose?.kwc)
  if (panneaux === null || Number(resultat?.pose?.total_modules) !== panneaux) return null
  return Number.isFinite(kwc) && kwc > 0 ? kwc : null
}

/**
 * Les tuiles de la maquette, dans son ordre ; une donnée non servie ⇒ tuile omise.
 * PRODUCTION ET COUVERTURE (H2) : montrées au client SEULEMENT quand le résultat publié est frais ET complet —
 * la règle du devis (`productionPubliee`, `panneaux/sources.js` ; `calepinage/selectors_devis.py`). Un résultat
 * incomplet est une BORNE HAUTE (« au plus » à l'étape Résultats) : jamais présentée au client comme une année
 * moyenne. Restent alors les faits certains : les panneaux posés et la puissance (tuile médiane marine).
 */
export function tuilesClient(document, resultat) {
  const tuiles = []
  const panneaux = panneauxDuDocument(document)
  if (panneaux !== null) tuiles.push({ cle: 'panneaux', valeur: formatNumber(panneaux, { locale: 'fr' }), libelle: 'panneaux' })
  const publiee = productionPubliee(resultat)
  if (publiee && publiee.p50 > 0) {
    tuiles.push({ cle: 'kwh', valeur: formatNumber(Math.round(publiee.p50), { locale: 'fr' }), libelle: 'kWh par an · estimation', marine: true })
    const couverture = Number(resultat?.autoconsommation?.taux_couverture)
    if (resultat?.autoconsommation?.taux_couverture != null && Number.isFinite(couverture)) {
      tuiles.push({ cle: 'couverture', valeur: `${Math.round(couverture * 100)} %`, libelle: 'de votre consommation' })
    }
    return tuiles
  }
  const kwc = puissancePose(resultat, panneaux)
  if (kwc !== null) {
    tuiles.push({ cle: 'kwc', valeur: formatNumber(kwc, { locale: 'fr', decimals: 2 }), libelle: 'kWc de puissance', marine: true })
  }
  return tuiles
}

const ETAT_DOC = { chargement: 'chargement', echec: 'erreur', ok: 'ok' }

/** Les lectures de la vue client (GET seulement, PARTAGÉES avec l'atelier : `panneaux/lectures.js`) : document
    enregistré, contexte, résultat publié. `contexte` déjà chargé par l'atelier : aucune seconde lecture. */
export function useDonneesClient(id, { contexte: contexteServi = null } = {}) {
  const lu = useLectureServie('document', id)
  const contexte = useLectureServie('contexte', id, { servi: contexteServi }).donnees
  const resultat = useLectureServie('resultat', id).donnees
  const donnees = lu.donnees
  const ok = lu.etat === 'ok' && donnees !== null && typeof donnees === 'object'
  const document = ok && donnees.roof_layout && typeof donnees.roof_layout === 'object' ? donnees.roof_layout : {}
  const doc = { etat: ok ? 'ok' : ETAT_DOC[lu.etat] ?? 'chargement', document: ok ? document : null }
  const ville = (contexte?.calepinage?.client_ville ?? '').trim()
  return {
    doc,
    plan: ok ? planDessus(document) : null,
    tuiles: ok ? tuilesClient(document, resultat) : [],
    // Le nom servi du projet ; sinon le client du devis lié (servi) ; sinon le nom que l'atelier donne lui-même
    // au calepinage (« Calepinage N », coque/projet.js).
    titre: (contexte?.calepinage?.titre ?? '').trim() || (contexte?.calepinage?.devis_lie?.client_nom ?? '').trim()
      || (contexte ? `Calepinage ${id}` : ''),
    ville,
    // Le libellé du pan seulement s'il dit quelque chose au client (pas le nom automatique « Zone N »).
    sousTitre: [ville, ok ? libellePan(document).replace(/^Zone \d+$/, '') : ''].filter(Boolean).join(' · '),
  }
}

/** Vrai si le navigateur peut rendre la 3D (WebGL). */
export function webglDisponible() {
  try {
    const toile = document.createElement('canvas')
    return !!(toile.getContext('webgl2') || toile.getContext('webgl'))
  } catch {
    return false
  }
}
