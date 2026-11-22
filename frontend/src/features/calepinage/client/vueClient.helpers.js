import { creerRepere, lngLatVersMetres, ORDRE_LNGLAT } from '../repere'
import { modulesDuDocument } from '@roofpro/modulesGeo'
import { useEffect, useState } from 'react'
import { formatNumber } from '../../../lib/format'
import calepinageApi from '../../../api/calepinageApi'
import useDocumentCalepinage from '../useDocumentCalepinage'

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

/** Les tuiles de la maquette, dans son ordre ; une donnée non servie ⇒ tuile omise. */
export function tuilesClient(document, resultat) {
  const tuiles = []
  const panneaux = panneauxDuDocument(document)
  if (panneaux !== null) tuiles.push({ cle: 'panneaux', valeur: formatNumber(panneaux, { locale: 'fr' }), libelle: 'panneaux' })
  const frais = resultat?.simule === true && resultat?.simulation_perimee !== true
  const kwh = Number(resultat?.production?.total?.p50_kwh)
  if (frais && Number.isFinite(kwh) && kwh > 0) {
    tuiles.push({ cle: 'kwh', valeur: formatNumber(Math.round(kwh), { locale: 'fr' }), libelle: 'kWh par an · estimation', marine: true })
  }
  const couverture = Number(resultat?.autoconsommation?.taux_couverture)
  if (frais && resultat?.autoconsommation?.taux_couverture != null && Number.isFinite(couverture)) {
    tuiles.push({ cle: 'couverture', valeur: `${Math.round(couverture * 100)} %`, libelle: 'de votre consommation' })
  }
  return tuiles
}

/** Les lectures de la vue client (GET seulement) : document enregistré, contexte, résultat publié. */
export function useDonneesClient(id) {
  const doc = useDocumentCalepinage(id)
  const [contexte, setContexte] = useState(null)
  const [resultat, setResultat] = useState(null)
  useEffect(() => {
    if (!id) return undefined
    let vivant = true
    Promise.resolve(calepinageApi.calepinages.designContext?.(id))
      .then((res) => { if (vivant) setContexte(res?.data ?? null) }).catch(() => {})
    Promise.resolve(calepinageApi.calepinages.resultat?.(id))
      .then((res) => { if (vivant) setResultat(res?.data ?? null) }).catch(() => {})
    return () => { vivant = false }
  }, [id])
  const ok = doc.etat === 'ok'
  const ville = (contexte?.calepinage?.client_ville ?? '').trim()
  return {
    doc,
    plan: ok ? planDessus(doc.document) : null,
    tuiles: ok ? tuilesClient(doc.document, resultat) : [],
    // Le nom servi du projet ; sinon le client du devis lié (servi) ; sinon le nom que l'atelier donne lui-même
    // au calepinage (« Calepinage N », coque/projet.js).
    titre: (contexte?.calepinage?.titre ?? '').trim() || (contexte?.calepinage?.devis_lie?.client_nom ?? '').trim()
      || (contexte ? `Calepinage ${id}` : ''),
    ville,
    // Le libellé du pan seulement s'il dit quelque chose au client (pas le nom automatique « Zone N »).
    sousTitre: [ville, ok ? libellePan(doc.document).replace(/^Zone \d+$/, '') : ''].filter(Boolean).join(' · '),
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
