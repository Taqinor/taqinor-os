import { lazy, useEffect, useRef, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { ecouterResultat } from './simulationFraiche'

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
  { cle: 'toit', libelle: 'Toit', action: 'Poser les panneaux', // ACAL868 — le bouton de la barre fixe : ouvre l'étape suivante
    onglets: ['plan', 'pente', 'coupe', 'terrain', 'ombriere', 'horizon', 'course-soleil', 'releve', 'reprise-visite', 'photos', 'detection-toit'] },
  { cle: 'panneaux', libelle: 'Panneaux', action: 'Raccorder les panneaux',
    onglets: ['fiches', 'affectation', 'masse-lestage', 'fixation', 'pompage'] },
  { cle: 'electrique', libelle: 'Électrique', action: 'Voir les résultats',
    onglets: ['equipements-electriques', 'cheminement-cables', 'raccordement', 'verdict-electrique',
      'materiel-electrique', 'saisies-electriques', 'decisions-electriques', 'controle-chaine', 'schema'] },
  { cle: 'resultats', libelle: 'Résultats', action: 'Préparer les documents',
    onglets: ['production', 'pertes', 'postes-pertes', 'series', 'batterie', 'economie', 'variantes', 'optimiser', 'consommation-mesuree', 'livre-prevu'] },
  { cle: 'documents', libelle: 'Documents',
    onglets: ['documents', 'dossiers', 'activite', 'versions', 'diff-versions', 'approbation', 'pose-reelle', 'projet'] },
]

// ACAL1190 — l'étape Toit ne montre d'office que `pente` (la maquette : UN panneau) ; `terrain` et `ombriere`
// passent au niveau expert (visibles d'office en expert, et un `?onglet=` les ouvre encore).
export const ESSENTIELS = [
  'pente', 'fiches', 'verdict-electrique', 'schema',
  'production', 'pertes', 'documents',
]
// ACAL1192 — l'étape Résultats se limite à la production et à ses pertes ; `batterie` et `economie` sont experts
// (visibles d'office en expert, et `?onglet=economie` les ouvre encore, `ongletsVisibles`).
// ACAL1193 — l'étape Documents ne montre d'office que `documents` (l'écran de fin d'ACAL867) ; `dossiers` et
// `approbation` sont experts, mais `?onglet=approbation` l'ouvre encore (le lien d'une demande d'approbation).

export const ETATS = ['a_faire', 'en_cours', 'fait', 'bloque']

/* T4-X3-007 — les quatre panneaux dont le lien profond (`/calepinage/<id>/<cle>`, `?onglet=<cle>`) retombait sur
   l'écran ORDINAIRE de leur étape (Le toit, Les panneaux, Les résultats) : leur panneau n'est monté que dans le rail
   de la feuille « Avancé », qui restait fermée. Les douze autres clés s'affichent déjà dans l'étape. */
const ONGLETS_DE_LA_FEUILLE = ['fiches', 'pente', 'production', 'pertes']

/** Vrai quand `?onglet=<cleOnglet>` n'est lisible que dans la feuille « Avancé » (mode guidé) : la coque l'ouvre alors. */
export function ongletDansLaFeuille(cleOnglet, expert = false) {
  return !expert && ONGLETS_DE_LA_FEUILLE.includes(cleOnglet)
}

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

/* ACAL1731 — la dernière étape visitée, par calepinage, dans la mémoire LOCALE de cet appareil (jamais au serveur).
   Stockage refusé ou valeur qui n'est pas une étape : `null` (repli : la première étape non faite). */
const cleMemoireEtape = (calepinageId) => `calepinage.etape.${calepinageId}`

export function lireEtapeMemorisee(calepinageId) {
  if (!calepinageId) return null
  try {
    const cle = window.localStorage.getItem(cleMemoireEtape(calepinageId))
    return ETAPES.some((e) => e.cle === cle) ? cle : null
  } catch {
    return null // stockage refusé : pas de mémoire, l'atelier retombe sur la première étape non faite
  }
}

export function memoriserEtape(calepinageId, cleEtape) {
  if (!calepinageId || !ETAPES.some((e) => e.cle === cleEtape)) return
  try {
    window.localStorage.setItem(cleMemoireEtape(calepinageId), cleEtape)
  } catch {
    return // stockage refusé : rien à mémoriser, l'étape reste dans l'URL
  }
}

/** L'étape active : celle de l'onglet ouvert, sinon la dernière étape mémorisée (`memorisee`), sinon la première
    non `fait`, sinon `toit`. */
export function etapeActive(cleOnglet, etatsParEtape = {}, memorisee = null) {
  const deLOnglet = etapeDeOnglet(cleOnglet)
  if (deLOnglet) return deLOnglet
  if (memorisee && ETAPES.some((e) => e.cle === memorisee)) return memorisee
  const premiere = ETAPES.find((e) => etatsParEtape[e.cle] && etatsParEtape[e.cle] !== 'fait')
  return (premiere ?? ETAPES[0]).cle
}

/* ============================================================================
   COQUE (refonte maquettes, 22/11) — LE CADRE DÉCLARÉ PAR CHAQUE ÉCRAN D'ÉTAPE.
   La coque plein écran (`atelier/coque/CoqueAtelier.jsx`) lit, pour l'écran guidé
   ouvert, deux champs de CE registre :
     - `cadre` : `CADRES.CARTE`  = la carte au centre + le panneau d'étape à droite
                                    (Toit, Panneaux, Électrique) ;
                 `CADRES.PLEIN`  = l'écran occupe TOUT le centre, ni carte ni panneau
                                    (Résultats, Documents) ;
                 `CADRES.PLEIN_PANNEAU` = l'écran au centre ET le panneau à droite (Schéma) ;
     - `titre` : l'intitulé du panneau d'étape (« Le toit »), sous « Étape N sur 5 ».
   La carte n'est JAMAIS démontée : un cadre plein la masque seulement (`hidden`).
   Le bouton de l'étape suivante vient de `ETAPES[].action` (prop `action` de l'écran) ;
   un écran qui pose son propre pied le rend dans `<PiedEtape>` (coque/emplacements.jsx).
   ========================================================================== */
export const CADRES = { CARTE: 'carte', PLEIN: 'plein', PLEIN_PANNEAU: 'plein-panneau' }

/* ACAL395 — l'ÉCRAN GUIDÉ d'une étape : en mode guidé, les panneaux listés
   s'ouvrent dans UNE page (sections repliables) au lieu d'autant d'onglets.
   `ouverture` = l'onglet visible qui porte la page ; `libelle` = son intitulé. */
export const ECRANS_ETAPE = {
  // Coque — Toit et Panneaux : écrans d'étape (gabarits de la coque, refaits par leurs lanes).
  toit: {
    ouverture: 'pente',
    libelle: 'Pente',
    titre: 'Le toit',
    cadre: CADRES.CARTE,
    onglets: ['pente'],
    composant: lazy(() => import('./coque/etapes/EtapeToit')),
  },
  panneaux: {
    ouverture: 'fiches',
    libelle: 'Fiches équipements',
    titre: 'Les panneaux',
    cadre: CADRES.CARTE,
    onglets: ['fiches'],
    composant: lazy(() => import('./coque/etapes/EtapePanneaux')),
  },
  // Coque — le schéma électrique : sous-écran de l'étape Électrique, au centre avec le panneau.
  schema: {
    ouverture: 'schema',
    libelle: 'Schéma unifilaire',
    titre: 'Le schéma électrique',
    cadre: CADRES.PLEIN_PANNEAU,
    onglets: ['schema'],
    composant: lazy(() => import('./coque/etapes/EtapeSchema')),
  },
  electrique: {
    titre: 'Le raccordement',
    cadre: CADRES.CARTE,
    ouverture: 'verdict-electrique',
    libelle: 'Électrique — synthèse',
    onglets: ['equipements-electriques', 'cheminement-cables', 'raccordement', 'verdict-electrique',
      'materiel-electrique', 'saisies-electriques', 'decisions-electriques', 'controle-chaine'],
    composant: lazy(() => import('../electrique/EtapeElectrique')),
  },
  // ACAL396 — Résultats : le diagramme ET l'édition d'un poste dans un seul
  // panneau ; `postes-pertes` y devient un alias expert de `pertes`.
  resultats: {
    titre: 'Les résultats',
    cadre: CADRES.PLEIN,
    ouverture: 'pertes',
    libelle: 'Pertes',
    onglets: ['pertes', 'postes-pertes'],
    composant: lazy(() => import('./PanneauPertesUnifie')),
  },
  // ACAL867 — Documents : écran de FIN de parcours (« Prêt à envoyer ? », « Générer le devis », documents).
  documents: {
    titre: 'Les documents',
    cadre: CADRES.PLEIN,
    ouverture: 'documents',
    libelle: 'Documents',
    onglets: ['documents'],
    composant: lazy(() => import('../documents/EtapeDocuments')),
  },
}

/** L'écran guidé qui porte l'onglet `cleOnglet` (ou `null`). */
export function ecranGuideDeOnglet(cleOnglet) {
  return Object.values(ECRANS_ETAPE).find((e) => e.onglets.includes(cleOnglet)) ?? null
}

/** La vue du rail pour l'onglet ouvert : l'écran guidé qui le porte, la clé visible, l'étape active.
    UNE fonction pour le rail d'onglets ET la coque : les deux lisent l'URL, jamais deux états. */
export function vueParcours(cleOnglet, etats = {}, expert = false, memorisee = null) {
  const ecran = expert ? null : ecranGuideDeOnglet(cleOnglet)
  const cleVue = ecran ? ecran.ouverture : cleOnglet
  return { ecran, cleVue, cleEtape: etapeActive(cleVue, etats, memorisee) }
}

/** L'onglet qu'ouvre un clic sur l'étape `cle` (son premier onglet visible). */
export function premierOngletEtape(cle, expert = false) {
  return ongletsVisibles(cle, null, expert)[0] ?? ETAPES.find((e) => e.cle === cle)?.onglets[0] ?? null
}

/** Coque — l'écran guidé à monter pour l'étape active : l'écran qui porte l'onglet ouvert, sinon
    l'onglet ouvert lui-même s'il n'est pas celui qu'ouvre l'étape (lien profond `?onglet=variantes`),
    sinon l'écran de l'étape. `{ composant, cadre, titre }` ou `null` (expert : le rail d'onglets). */
export function ecranCoque(cleOnglet, onglet, etats = {}, expert = false, memorisee = null) {
  if (expert) return null
  const { ecran, cleEtape } = vueParcours(cleOnglet, etats, false, memorisee)
  const deLEtape = ECRANS_ETAPE[cleEtape] ?? null
  if (ecran) return { ...ecran, titre: ecran.titre ?? deLEtape?.titre, cadre: ecran.cadre ?? CADRES.CARTE }
  if (onglet?.composant && cleOnglet !== premierOngletEtape(cleEtape)) {
    return { composant: onglet.composant, titre: deLEtape?.titre ?? onglet.libelle, cadre: deLEtape?.cadre ?? CADRES.CARTE }
  }
  return deLEtape
}

/** Le nombre de points à régler d'une étape, tel que le parcours le sert (`manque`, hors « info »). */
export function aReglerDeLEtape(manque, cle) {
  return (Array.isArray(manque) ? manque : [])
    .filter((m) => m?.etape === cle && m?.gravite !== 'info')
    .reduce((n, m) => n + (Number.isFinite(Number(m?.nombre)) && Number(m.nombre) > 0 ? Number(m.nombre) : 1), 0)
}

/** Les états par étape et « ce qui manque » ; vides tant que le serveur n'a pas répondu.
    T4-U1-023 (rejeu R5B, 26/11) — `relecture` (l'heure du dernier enregistrement) : le parcours est RELU après chaque
    enregistrement. Lu une seule fois à l'ouverture, il gardait « aucune ombre signalée » après qu'une cheminée et un
    voisin ont été posés et enregistrés, pendant que l'Expert, lui, les voyait. */
export function useParcours(calepinageId, relecture = null) {
  // ACAL1731 — lue UNE fois à l'ouverture : la coque et le rail d'onglets partagent la même étape de départ.
  // Revue de T4-U1-023 (26/11) — l'étape de départ : celle mémorisée sur cet appareil, sinon le choix AUTOMATIQUE (première
  // étape non faite) fait UNE fois, à la première réponse, puis TENU : une relecture après un enregistrement met à jour les
  // états (pastilles, carte des ombres) sans jamais changer d'écran — l'étape ne change que par un geste de l'utilisateur.
  const [memorisee, setMemorisee] = useState(() => lireEtapeMemorisee(calepinageId))
  const [parcours, setParcours] = useState({ etats: {}, manque: [] })
  // ACAL1653 (revue) — la fin d'un calcul (un `calcule_le` nouveau dans le résultat publié) relit le parcours : la pastille
  // « N à régler » du rail ne garde pas le compte d'avant le calcul. Les relectures du MÊME calcul ne le relisent pas.
  const [apresCalcul, setApresCalcul] = useState(0)
  const dernierCalcul = useRef(undefined)
  useEffect(() => {
    dernierCalcul.current = undefined
    return ecouterResultat(calepinageId, (resultat) => {
      const calcule = resultat?.calcule_le ?? null
      if (dernierCalcul.current !== undefined && dernierCalcul.current !== calcule) setApresCalcul((n) => n + 1)
      dernierCalcul.current = calcule
    })
  }, [calepinageId])
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
        const etats = Object.fromEntries(
          liste.filter((e) => ETATS.includes(e?.etat)).map((e) => [e.cle, e.etat]),
        )
        setParcours({ etats, manque })
        setMemorisee((tenue) => tenue ?? etapeActive(null, etats, null))
      })
      .catch(() => {})
    return () => { vivant = false }
  }, [calepinageId, relecture, apresCalcul])
  return { ...parcours, memorisee }
}

/** Les états par étape (ACAL393). */
export function useEtatsParcours(calepinageId) {
  return useParcours(calepinageId).etats
}
