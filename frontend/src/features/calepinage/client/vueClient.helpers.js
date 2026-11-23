import { useCallback, useEffect, useRef } from 'react'
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

const DIRECTIONS = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']

/** J1 — l'orientation du toit, SEULEMENT si elle est certaine : la face SERVIE de chaque pan tracé
    (`geometry.azimuthDeg`, 0 = nord, 180 = sud — la face lue par `#rp9-facing-value`) ; un seul pan → « pan sud »,
    tous les pans dans la même direction → « orienté sud » ; une face manquante ou deux directions → rien. */
export function orientationToit(document) {
  const zones = zonesTracees(document)
  if (!zones.length) return ''
  const directions = zones.map((z) => {
    const az = Number(z?.geometry?.azimuthDeg)
    if (z?.geometry?.azimuthDeg == null || !Number.isFinite(az)) return null
    return DIRECTIONS[Math.round((((az % 360) + 360) % 360) / 45) % 8]
  })
  if (directions.some((d) => d === null) || new Set(directions).size !== 1) return ''
  return zones.length === 1 ? `pan ${directions[0]}` : `orienté ${directions[0]}`
}

/** J1 — l'instant du soleil enregistré dans la scène (`scene{sunDay,sunHour}`, CALX88) a-t-il été CHOISI ? Le
    constructeur sérialise toujours l'instant ; le sien par défaut (solstice d'hiver = jour 355, midi —
    `WINTER_SOLSTICE_DAY`, `harnaisDocument`) ne dit pas un choix du commercial. Sans scène : non choisi. */
export const INSTANT_PAR_DEFAUT = { sunDay: 355, sunHour: 12 }
export function instantSoleilChoisi(document) {
  const s = document?.scene
  if (!s || !Number.isFinite(Number(s.sunDay)) || !Number.isFinite(Number(s.sunHour))) return false
  return !(Number(s.sunDay) === INSTANT_PAR_DEFAUT.sunDay && Number(s.sunHour) === INSTANT_PAR_DEFAUT.sunHour)
}

/** La puissance installée du toit ENREGISTRÉ, lue par le serveur sur ce document (`resultat.pose.kwc`,
    `services/electrique.py::resultat_calepinage` → `bloc_pose`) — un fait de la pose, pas une estimation ; dite
    seulement quand cette pose compte LES panneaux dessinés (`panneaux`), sinon omise. */
function puissancePose(resultat, panneaux) {
  const kwc = Number(resultat?.pose?.kwc)
  if (panneaux === null || Number(resultat?.pose?.total_modules) !== panneaux) return null
  return Number.isFinite(kwc) && kwc > 0 ? kwc : null
}

/** ACAL1840 (D-ACAL-88) — l'estimation de la pose : le chiffre que l'atelier affiche déjà comme « Production · estimation de
    la pose » (`figures.productionKwh`, lu sur le constructeur par `panneaux/constructeur.js::lireFigures`) — même source,
    aucun calcul ici. `{ kwh }`, ou `null` quand le constructeur n'en publie pas. */
export function estimationPose(figures) {
  const kwh = Number(figures?.productionKwh)
  return Number.isFinite(kwh) && kwh > 0 ? { kwh } : null
}

/**
 * Les tuiles de la maquette, dans son ordre ; une donnée non servie ⇒ tuile omise.
 * PRODUCTION ET COUVERTURE (H2) : montrées au client SEULEMENT quand le résultat publié est frais ET complet —
 * la règle du devis (`productionPubliee`, `panneaux/sources.js` ; `calepinage/selectors_devis.py`). Un résultat
 * incomplet est une BORNE HAUTE (« au plus » à l'étape Résultats) : jamais présentée au client comme une année
 * moyenne. Restent alors les faits certains : les panneaux posés et la puissance.
 * ACAL1840 (D-ACAL-88) — tant que le résultat n'est pas complet, la tuile de production est l'ESTIMATION DE LA POSE
 * (`estimation`, lue sur l'atelier), dite « estimation de la pose » ; un résultat complet la remplace. Jamais deux
 * chiffres de production à la fois.
 */
export function tuilesClient(document, resultat, estimation = null) {
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
  const kwhEstimes = estimation?.kwh > 0 ? Math.round(estimation.kwh) : null
  if (kwhEstimes) {
    tuiles.push({
      cle: 'kwh', valeur: formatNumber(kwhEstimes, { locale: 'fr' }), libelle: 'kWh par an · estimation de la pose',
      marine: true, nature: 'estimation',
    })
  }
  if (kwc !== null) {
    tuiles.push({ cle: 'kwc', valeur: formatNumber(kwc, { locale: 'fr', decimals: 2 }), libelle: 'kWc de puissance', marine: !kwhEstimes })
  }
  return tuiles
}

const ETAT_DOC = { chargement: 'chargement', echec: 'erreur', ok: 'ok' }

/** J1 — une lecture échouée (délai dépassé sous charge) est relue seule, une fois, après ce délai (GET). */
export const RELECTURE_MS = 5000

/** Relit une fois, après `RELECTURE_MS`, chaque lecture en échec ; `reessayer()` relit tout de suite celles en échec. */
function useRelectures(lectures) {
  const relues = useRef(new Set())
  const etats = lectures.map((l) => l.etat).join('|')
  useEffect(() => {
    const minuteurs = lectures.map((l, i) => {
      if (l.etat !== 'echec' || relues.current.has(i)) return null
      return window.setTimeout(() => { relues.current.add(i); l.reessayer() }, RELECTURE_MS)
    })
    return () => minuteurs.forEach((m) => m && window.clearTimeout(m))
  }, [etats]) // eslint-disable-line react-hooks/exhaustive-deps -- relancé sur les états seuls
  const enEchec = lectures.filter((l) => l.etat === 'echec')
  return useCallback(() => enEchec.forEach((l) => l.reessayer()), [etats]) // eslint-disable-line react-hooks/exhaustive-deps
}

/** Les lectures de la vue client (GET seulement, PARTAGÉES avec l'atelier : `panneaux/lectures.js`) : document
    enregistré, contexte, résultat publié. `contexte` déjà chargé par l'atelier : aucune seconde lecture ;
    `lireContexte: false` (l'atelier démarre et le lira) : le contexte n'est pas lu ici.
    J1 — tenues par la vue client HORS de l'atelier : les tuiles ne dépendent pas du démarrage de la 3D. */
export function useDonneesClient(id, { contexte: contexteServi = null, lireContexte = true } = {}) {
  const lu = useLectureServie('document', id)
  const lectureContexte = useLectureServie('contexte', id, { servi: contexteServi, actif: lireContexte })
  const lectureResultat = useLectureServie('resultat', id)
  const contexte = lectureContexte.donnees
  const resultat = lectureResultat.donnees
  const reessayer = useRelectures([lu, lectureResultat, lectureContexte])
  const donnees = lu.donnees
  const ok = lu.etat === 'ok' && donnees !== null && typeof donnees === 'object'
  const document = ok && donnees.roof_layout && typeof donnees.roof_layout === 'object' ? donnees.roof_layout : {}
  const doc = { etat: ok ? 'ok' : ETAT_DOC[lu.etat] ?? 'chargement', document: ok ? document : null }
  const ville = (contexte?.calepinage?.client_ville ?? '').trim()
  return {
    doc,
    plan: ok ? planDessus(document) : null,
    tuiles: ok ? tuilesClient(document, resultat) : [],
    // ACAL1840 — les mêmes tuiles avec l'estimation de la pose lue sur l'atelier (3D) : `estimation` = `estimationPose(figures)`.
    tuilesAvec: (estimation) => (ok ? tuilesClient(document, resultat, estimation) : []),
    // Le nom servi du projet ; sinon le client du devis lié (servi) ; sinon le nom que l'atelier donne lui-même
    // au calepinage (« Calepinage N », coque/projet.js).
    titre: (contexte?.calepinage?.titre ?? '').trim() || (contexte?.calepinage?.devis_lie?.client_nom ?? '').trim()
      || (contexte ? `Calepinage ${id}` : ''),
    ville,
    // J1 — l'orientation seulement si elle est certaine (face servie de chaque pan), jamais le nom d'un pan.
    sousTitre: [ville, ok ? orientationToit(document) : ''].filter(Boolean).join(' · '),
    reessayer,
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
