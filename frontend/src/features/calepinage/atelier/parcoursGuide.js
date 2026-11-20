import { lazy, useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'

/* ============================================================================
   ACAL393 — LA TABLE DU PARCOURS GUIDÉ : étape → panneaux de l'atelier.
   ----------------------------------------------------------------------------
   Cinq étapes (celles du contrat `calepinage_parcours_guide.json`, servies par
   `GET calepinages/<id>/parcours/`), chacune avec SES panneaux. Les clés sont
   celles du registre `onglets.js` (qui n'est pas rouvert) ; un test garantit
   que chaque clé du registre figure UNE fois ici. `ESSENTIELS` = les panneaux
   montrés d'office ; les autres sont `expert` (les montrer : ACAL394). Un
   `?onglet=<cle>` d'un panneau expert l'ouvre quand même, dans son étape.
   ========================================================================== */

export const ETAPES = [
  { cle: 'toit', libelle: 'Toit',
    onglets: ['plan', 'pente', 'coupe', 'terrain', 'ombriere', 'horizon', 'course-soleil', 'releve', 'reprise-visite'] },
  { cle: 'panneaux', libelle: 'Panneaux',
    onglets: ['fiches', 'affectation', 'masse-lestage', 'fixation', 'pompage'] },
  { cle: 'electrique', libelle: 'Électrique',
    onglets: ['equipements-electriques', 'cheminement-cables', 'raccordement', 'verdict-electrique',
      'materiel-electrique', 'saisies-electriques', 'decisions-electriques', 'schema'] },
  { cle: 'resultats', libelle: 'Résultats',
    onglets: ['production', 'pertes', 'postes-pertes', 'series', 'batterie', 'economie'] },
  { cle: 'documents', libelle: 'Documents',
    onglets: ['documents', 'dossiers', 'activite', 'versions', 'diff-versions', 'approbation', 'pose-reelle', 'projet'] },
]

export const ESSENTIELS = [
  'pente', 'terrain', 'ombriere', 'fiches', 'verdict-electrique', 'schema',
  'production', 'pertes', 'batterie', 'economie', 'documents', 'dossiers', 'approbation',
]

export const ETATS = ['a_faire', 'en_cours', 'fait', 'bloque']

/** L'étape (clé) qui porte l'onglet `cleOnglet`, ou `null`. */
export function etapeDeOnglet(cleOnglet) {
  return ETAPES.find((e) => e.onglets.includes(cleOnglet))?.cle ?? null
}

/** Les clés d'onglets montrées pour l'étape : ses essentiels, + `ouvert` s'il en fait partie. */
export function ongletsVisibles(cleEtape, ouvert = null, expert = false) {
  const etape = ETAPES.find((e) => e.cle === cleEtape)
  if (!etape) return []
  if (expert) return [...etape.onglets] // ACAL394 : tout, rangé sous l'étape
  return etape.onglets.filter((c) => ESSENTIELS.includes(c) || c === ouvert)
}

/** L'étape active : celle de l'onglet ouvert, sinon la première non `fait`, sinon `toit`. */
export function etapeActive(cleOnglet, etatsParEtape = {}) {
  const deLOnglet = etapeDeOnglet(cleOnglet)
  if (deLOnglet) return deLOnglet
  const premiere = ETAPES.find((e) => etatsParEtape[e.cle] && etatsParEtape[e.cle] !== 'fait')
  return (premiere ?? ETAPES[0]).cle
}

/* ACAL395 — l'ÉCRAN GUIDÉ d'une étape : en mode guidé, les panneaux listés
   s'ouvrent dans UNE page (sections repliables) au lieu d'autant d'onglets.
   `ouverture` = l'onglet visible qui porte la page ; `libelle` = son intitulé. */
export const ECRANS_ETAPE = {
  electrique: {
    ouverture: 'verdict-electrique',
    libelle: 'Électrique — synthèse',
    onglets: ['equipements-electriques', 'cheminement-cables', 'raccordement', 'verdict-electrique',
      'materiel-electrique', 'saisies-electriques', 'decisions-electriques'],
    composant: lazy(() => import('../electrique/EtapeElectrique')),
  },
  // ACAL396 — Résultats : le diagramme ET l'édition d'un poste dans un seul
  // panneau ; `postes-pertes` y devient un alias expert de `pertes`.
  resultats: {
    ouverture: 'pertes',
    libelle: 'Pertes',
    onglets: ['pertes', 'postes-pertes'],
    composant: lazy(() => import('./PanneauPertesUnifie')),
  },
}

/** L'écran guidé qui porte l'onglet `cleOnglet` (ou `null`). */
export function ecranGuideDeOnglet(cleOnglet) {
  return Object.values(ECRANS_ETAPE).find((e) => e.onglets.includes(cleOnglet)) ?? null
}

/** Les états par étape et « ce qui manque », lus une fois ; vides tant que le serveur n'a pas répondu. */
export function useParcours(calepinageId) {
  const [parcours, setParcours] = useState({ etats: {}, manque: [] })
  useEffect(() => {
    if (!calepinageId) return undefined
    let vivant = true
    Promise.resolve()
      .then(() => calepinageApi.calepinages.parcours(calepinageId))
      .then((rep) => {
        if (!vivant) return
        const liste = Array.isArray(rep?.data?.etapes) ? rep.data.etapes : []
        const manque = Array.isArray(rep?.data?.manque)
          ? rep.data.manque.filter((m) => m && typeof m === 'object') : []
        setParcours({
          etats: Object.fromEntries(
            liste.filter((e) => ETATS.includes(e?.etat)).map((e) => [e.cle, e.etat]),
          ),
          manque,
        })
      })
      .catch(() => {})
    return () => { vivant = false }
  }, [calepinageId])
  return parcours
}

/** Les états par étape (ACAL393). */
export function useEtatsParcours(calepinageId) {
  return useParcours(calepinageId).etats
}
