// QJR87 — LA MACHINE À ÉTATS DU DIMENSIONNEMENT (module PUR).
// ---------------------------------------------------------------------------
// Remplace, sur le papier d'abord (vague M4 : ajouté testé, IMPORTÉ PAR
// PERSONNE ; la bascule est QJR99), SIX `useRef` de `DevisGenerator.jsx`
// (`modeTouched`, `structureTouched`, `tensionTouched`, `pompeAlimTouched`,
// `nbPanneauxTouched`, `scenarioTouched` — vérifiés lignes 326-339) et les
// chaînes de ternaires/gardes en ligne qui les lisent.
//
// POURQUOI DE L'ÉTAT ET PLUS DES REFS. Un `useRef` n'est ni sérialisé, ni
// énumérable, ni observable : rien ne peut lister « ce que le vendeur a
// touché » (c'est la cause mécanique du prix tapé qui revient à `false` et de
// la taxe « tout nouveau champ auto-rempli doit inventer son propre drapeau »
// — voir QJR88 qui énumère ces mêmes drapeaux). En ÉTAT, chaque drapeau est
// lisible, testable et sérialisable vers le registre d'overrides.
//
// LES TROIS INVARIANTS ENCODÉS ICI (et testés dans sizingReducer.test.mjs) :
//   1. `SAISI` sur `nbPanneaux`/`kwcCible` pose le drapeau, et AUCUN
//      `MOTEUR_A_REPONDU` ultérieur ne l'écrase (invariant existant
//      `DevisGenerator.jsx:825/833` + `:1045`, préservé à l'identique).
//   2. `MARCHE_CHANGE` CONSULTE `touche.scenario` : aujourd'hui `onModeChange`
//      (`:1206-1230`) appelle `setScenario` SANS CONDITION et jette en silence
//      un choix explicite du commercial. Ici le défaut du marché ne s'applique
//      qu'à un scénario INTACT.
//   3. `RECALCUL_DEMANDE` rouvre le drapeau ET restaure sa valeur ANTÉRIEURE
//      dans la MÊME transition — plus de fenêtre de déverrouillage entre deux
//      instructions (la danse `recalcDimPriorTouched` de `:2646-2731`, dont la
//      revue F1/F2 a déjà montré qu'une frappe pouvait s'y engouffrer).
//
// CE QUE CE MODULE NE MODÉLISE PAS (volontairement) : tout ce qui exige le
// CATALOGUE ou le RÉSEAU. Le balayage local (`computeAutoSizing`) et la
// recommandation serveur sont RÉSOLUS PAR L'APPELANT et arrivent en charge
// utile d'action — un reducer pur ne va jamais chercher un chiffre.
import { panneauxPourKwc } from '../solar.js'

// Vocabulaire EXACT du moteur PDF (constantes SCENARIO_* d'apps/ventes/
// services.py, recopiées à l'identique par `DevisGenerator.jsx:119-121`) :
// jamais reformulé ici.
export const SCENARIO_LES_DEUX = 'Les deux (Sans + Avec)'
export const SCENARIO_SANS = 'Sans batterie'
export const SCENARIO_AVEC = 'Avec batterie'
export const SCENARIOS_VALIDES = [SCENARIO_LES_DEUX, SCENARIO_SANS, SCENARIO_AVEC]

/** Les quatre marchés canoniques (miroir de `autoQuote.LEAD_TYPE_TO_MODE`). */
export const MODES = ['residentiel', 'industriel', 'commercial', 'agricole']

/** Scénario par DÉFAUT d'un marché — ne s'applique qu'à un scénario intact. */
export const DEFAUT_SCENARIO_PAR_MODE = {
  // ORDRE FONDATEUR (24/08) : deux options par défaut en résidentiel.
  residentiel: SCENARIO_LES_DEUX,
  // Industriel/commercial : l'auto-remplissage met batterie + onduleur hybride
  // à zéro — le double scénario n'y est pas servable.
  industriel: SCENARIO_SANS,
  commercial: SCENARIO_SANS,
  // Pompage : ni batterie ni onduleur — le scénario n'est PAS touché.
  agricole: null,
}

/** Scénario choisi par le client dans le tunnel (crm.Lead.batterie_souhaitee). */
export const BATTERIE_LEAD_VERS_SCENARIO = {
  sans: SCENARIO_SANS, avec: SCENARIO_AVEC, les_deux: SCENARIO_LES_DEUX,
}

/** Les SIX drapeaux « touché », ex-refs — désormais énumérables (QJR88). */
export const DRAPEAUX_TOUCHE = [
  'mode', 'structure', 'tension', 'pompeAlim', 'nbPanneaux', 'scenario',
]

export const ETAT_INITIAL = Object.freeze({
  // Champs (défauts identiques à `DevisGenerator.jsx:433-621`).
  nbPanneaux: '',
  panelW: '710',
  kwcCible: '',
  scenario: SCENARIO_LES_DEUX,
  modeInstallation: 'residentiel',
  structure: 'acier',
  tension: 'bt',
  pompeAlim: 'tri',
  // Les six drapeaux, COMME ÉTAT.
  touche: Object.freeze({
    mode: false, structure: false, tension: false,
    pompeAlim: false, nbPanneaux: false, scenario: false,
  }),
  // Justificatif du balayage local (« palier retenu ») — null dès que la
  // taille vient d'ailleurs (frappe, moteur serveur).
  sizingInfo: null,
  // Le moteur SERVEUR a-t-il une recommandation à appliquer ? (ex-`attenteSizingServeur`)
  attenteMoteur: false,
  // Refus du moteur, texte FR VERBATIM du serveur — jamais reformulé.
  motifMoteur: null,
  // Compteur (jamais les champs eux-mêmes) : un recalcul qui retombe sur le
  // MÊME compte de panneaux doit quand même relancer la composition.
  compositionSeq: 0,
  // Fenêtre d'UNE transition ouverte par RECALCUL_DEMANDE (voir invariant 3).
  recalcul: null,
})

const nombre = (v) => {
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : 0
}

/** kWc affiché pour un compte de panneaux (miroir de `onNbPanneauxChange`). */
const kwcDepuisPanneaux = (nbPanneaux, panelW) => {
  const puissance = nombre(nbPanneaux) * nombre(panelW) / 1000
  return puissance > 0 ? String(Math.round(puissance * 100) / 100) : ''
}

const avecTouche = (etat, champ, valeur = true) => ({
  ...etat, touche: { ...etat.touche, [champ]: valeur },
})

/** Mode canonique d'un `type_installation` de lead/profil, sinon null. */
export const modeDepuisTypeInstallation = (type) =>
  (MODES.includes(type) ? type : null)

/**
 * Transition de MARCHÉ — partagée par `MARCHE_CHANGE` et par l'application
 * d'un lead / d'un profil site, pour qu'elles vivent dans UNE SEULE
 * transition. C'est ce qui rend impossible le bug QJR38 (`applySiteProfile`
 * branchait sur le mode du rendu PRÉCÉDENT parce que `setState` ne
 * rafraîchit pas la constante fermée) : ici le mode visé EST dans l'état rendu.
 *
 * INVARIANT 2 — le défaut de scénario du marché ne s'applique QUE si le
 * scénario est encore INTACT (`!touche.scenario`).
 */
function appliquerMarche(etat, mode, { marquerTouche = false } = {}) {
  const cible = modeDepuisTypeInstallation(mode)
  if (!cible) return etat
  let suivant = marquerTouche ? avecTouche(etat, 'mode') : etat
  if (cible === suivant.modeInstallation) return suivant
  suivant = { ...suivant, modeInstallation: cible }
  const defaut = DEFAUT_SCENARIO_PAR_MODE[cible]
  if (defaut && !suivant.touche.scenario) suivant = { ...suivant, scenario: defaut }
  return suivant
}

/** Pose un compte de panneaux SANS marquer le drapeau (pré-remplissages). */
const poserPanneaux = (etat, n) => ({
  ...etat,
  nbPanneaux: String(n),
  kwcCible: kwcDepuisPanneaux(n, etat.panelW),
})

/**
 * Reducer. Toute action INCONNUE rend l'état inchangé (jamais d'exception :
 * un écran ne casse pas sur une action de trop).
 *
 * `recalcul` est une fenêtre d'UNE transition : toute action autre que
 * `RECALCUL_DEMANDE` la referme.
 */
export function sizingReducer(etat = ETAT_INITIAL, action = {}) {
  const base = etat.recalcul ? { ...etat, recalcul: null } : etat
  switch (action.type) {
    // ── Saisie du vendeur : la source la plus forte ────────────────────────
    case 'SAISI': {
      const { champ, valeur } = action
      switch (champ) {
        case 'nbPanneaux':
          // `onNbPanneauxChange` : rien n'est jamais « snappé » — le champ
          // garde EXACTEMENT ce qui est tapé ; la cible en kWc suit.
          return {
            ...avecTouche(base, 'nbPanneaux'),
            nbPanneaux: valeur,
            kwcCible: kwcDepuisPanneaux(valeur, base.panelW),
            sizingInfo: null,
          }
        case 'kwcCible': {
          // `onKwcCibleChange` : bidirectionnel, mais la conversion ne
          // s'applique qu'une fois le nombre lisible.
          const n = panneauxPourKwc(valeur, base.panelW)
          const suivant = { ...base, kwcCible: valeur }
          if (!(n > 0)) return suivant
          return {
            ...avecTouche(suivant, 'nbPanneaux'),
            nbPanneaux: String(n),
            sizingInfo: null,
          }
        }
        case 'panelW':
          // Pas de drapeau propre (comme aujourd'hui) : la puissance panneau
          // suit la frappe et la cible se recale sur le compte courant.
          return {
            ...base, panelW: valeur,
            kwcCible: kwcDepuisPanneaux(base.nbPanneaux, valeur) || base.kwcCible,
          }
        case 'mode':
          return appliquerMarche(base, valeur, { marquerTouche: true })
        case 'scenario':
          return { ...avecTouche(base, 'scenario'), scenario: valeur }
        case 'structure':
          return { ...avecTouche(base, 'structure'), structure: valeur }
        case 'tension':
          return { ...avecTouche(base, 'tension'), tension: valeur }
        case 'pompeAlim':
          return { ...avecTouche(base, 'pompeAlim'), pompeAlim: valeur }
        default:
          return base
      }
    }

    // ── Changement de marché (UI ou programmatique) ────────────────────────
    // `origine: 'utilisateur'` (défaut) marque `touche.mode` — c'est le seul
    // chemin où le commercial choisit lui-même son marché (`:3332`).
    case 'MARCHE_CHANGE':
      return appliquerMarche(base, action.mode, {
        marquerTouche: (action.origine ?? 'utilisateur') === 'utilisateur',
      })

    // ── Pré-remplissage depuis un LEAD (`applyLead`, :1478-1580) ───────────
    case 'LEAD_APPLIQUE': {
      const lead = action.lead || {}
      let s = base
      // 1. Mode du lead — seulement si le commercial n'a pas déjà choisi.
      if (!s.touche.mode) {
        const modeLead = modeDepuisTypeInstallation(lead.type_installation)
        if (modeLead) s = appliquerMarche(s, modeLead)
      }
      // 2. Le mode VISÉ est celui de l'état qu'on vient de produire.
      const modeCible = s.modeInstallation
      // 3. Scénario du lead : un choix DÉJÀ FAIT (tunnel) — jamais en pompage.
      if (!s.touche.scenario && modeCible !== 'agricole') {
        const scenarioLead = BATTERIE_LEAD_VERS_SCENARIO[String(lead.batterie_souhaitee ?? '')]
        if (scenarioLead) s = { ...s, scenario: scenarioLead }
      }
      // 4. Structure préférée.
      if (!s.touche.structure
          && (lead.structure_pref === 'acier' || lead.structure_pref === 'aluminium')) {
        s = { ...s, structure: lead.structure_pref }
      }
      // 5. Tension déjà posée par le tunnel (QXMT).
      if (!s.touche.tension) {
        const t = String(lead.web_questionnaire?.tension_raccordement ?? '').toLowerCase()
        if (t === 'bt' || t === 'mt') s = { ...s, tension: t }
      }
      // 6. Pompage : l'alimentation suit le raccordement tant qu'elle est intacte.
      if (modeDepuisTypeInstallation(lead.type_installation) === 'agricole'
          && !s.touche.pompeAlim) {
        if (lead.raccordement === 'monophase') s = { ...s, pompeAlim: 'mono' }
        else if (lead.raccordement === 'triphase') s = { ...s, pompeAlim: 'tri' }
      }
      // 7. Taille souhaitée (kWc) → panneaux, PRIORITAIRE sur la facture, et
      //    seulement tant que le champ n'a pas été touché. Ne pose PAS le
      //    drapeau (comportement actuel : un pré-remplissage n'est pas une saisie).
      const tailleKwc = nombre(lead.taille_souhaitee_kwc)
      const fromTaille = (!s.touche.nbPanneaux && tailleKwc > 0)
        ? panneauxPourKwc(tailleKwc, s.panelW) : 0
      if (fromTaille > 0) s = poserPanneaux(s, fromTaille)
      // 8. Facture : le résidentiel ATTEND le moteur serveur (U3-900, plus de
      //    repli « panneaux/900 MAD ») ; les autres marchés n'ont que le
      //    balayage local, résolu par l'appelant (`action.sizingLocal`).
      //    QJR208 — la branche « balayage local » (indus/commercial/agricole)
      //    reçoit la MÊME garde `!s.touche.nbPanneaux` que la transition
      //    miroir PROFIL_SITE_APPLIQUE (:276) : sans elle, appliquer un lead
      //    écrasait silencieusement un compte de panneaux DÉJÀ TAPÉ par le
      //    vendeur sur ces trois marchés. Le cas résidentiel (attente moteur)
      //    reste INCHANGÉ — ce n'est pas la branche visée par le défaut.
      if (nombre(lead.facture_hiver) > 0 && fromTaille <= 0) {
        if (modeCible === 'residentiel') {
          s = { ...s, sizingInfo: null, attenteMoteur: true, motifMoteur: null }
        } else if (!s.touche.nbPanneaux) {
          s = appliquerSizingLocal(s, action.sizingLocal)
        }
      }
      return s
    }

    // ── Pré-remplissage depuis le PROFIL SITE (`applySiteProfile`, :1588) ──
    // Miroir d'applyLead : mêmes garde-fous, sans scénario/structure/tension
    // ni taille souhaitée (le profil ne les porte pas).
    case 'PROFIL_SITE_APPLIQUE': {
      const p = action.profil
      if (!p) return base
      let s = base
      if (!s.touche.mode) {
        const modeProfil = modeDepuisTypeInstallation(p.type_installation)
        if (modeProfil) s = appliquerMarche(s, modeProfil)
      }
      const modeCible = s.modeInstallation
      if (modeDepuisTypeInstallation(p.type_installation) === 'agricole'
          && !s.touche.pompeAlim) {
        if (p.raccordement === 'monophase') s = { ...s, pompeAlim: 'mono' }
        else if (p.raccordement === 'triphase') s = { ...s, pompeAlim: 'tri' }
      }
      if (nombre(p.facture_hiver) > 0 && !s.touche.nbPanneaux) {
        s = (modeCible === 'residentiel')
          ? { ...s, sizingInfo: null, attenteMoteur: true, motifMoteur: null }
          : appliquerSizingLocal(s, action.sizingLocal)
      }
      return s
    }

    // ── Le moteur SERVEUR a répondu ────────────────────────────────────────
    // INVARIANT 1 : une frappe manuelle gagne TOUJOURS — la réponse est
    // abandonnée, jamais appliquée par-dessus.
    case 'MOTEUR_A_REPONDU': {
      if (!base.attenteMoteur) return base
      if (base.touche.nbPanneaux) return { ...base, attenteMoteur: false }
      const reco = action.recommandation || {}
      if (!(nombre(reco.panneaux) > 0)) return base
      let s = {
        ...base,
        attenteMoteur: false,
        motifMoteur: null,
        nbPanneaux: String(reco.panneaux),
      }
      if (reco.panel_watt) s = { ...s, panelW: String(reco.panel_watt) }
      if (reco.kwc != null) s = { ...s, kwcCible: String(reco.kwc) }
      return s
    }

    // ── Le moteur SERVEUR a refusé (motif FR VERBATIM, jamais un chiffre) ──
    case 'MOTEUR_A_REFUSE': {
      if (!base.attenteMoteur) return base
      if (base.touche.nbPanneaux) return { ...base, attenteMoteur: false }
      return { ...base, attenteMoteur: false, motifMoteur: action.motif ?? null }
    }

    // ── « Appliquer cette taille » d'une ligne de dimensionnement (:2586) ──
    case 'TAILLE_APPLIQUEE': {
      const ligne = action.ligne || {}
      if (!(nombre(ligne.panneaux) > 0)) return base
      let s = {
        ...avecTouche(base, 'nbPanneaux'),
        sizingInfo: null,
        kwcCible: ligne.kwc != null ? String(ligne.kwc) : '',
        nbPanneaux: String(ligne.panneaux),
        attenteMoteur: false,
      }
      if (ligne.panel_watt) s = { ...s, panelW: String(ligne.panel_watt) }
      // Relance la composition par le chemin EXACT de l'Auto-remplir.
      return { ...s, compositionSeq: s.compositionSeq + 1 }
    }

    // ── Réouverture d'un brouillon (?edit=ID, :1706-1781) ──────────────────
    // Le mode ET le scénario du devis sont des choix DÉJÀ POSÉS : ils
    // ferment leurs drapeaux (sinon l'enregistrement suivant écrase le choix
    // du client par le défaut du marché). Le compte de panneaux relu des
    // lignes ne ferme PAS `touche.nbPanneaux` (comportement actuel vérifié,
    // `:2604-2607`).
    case 'REOUVERTURE': {
      const d = action.devis || {}
      let s = base
      if (d.mode_installation) {
        s = appliquerMarche(s, d.mode_installation, { marquerTouche: true })
      }
      if (nombre(d.panneaux) > 0) s = poserPanneaux(s, nombre(d.panneaux))
      if (SCENARIOS_VALIDES.includes(d.scenario)) {
        s = { ...avecTouche(s, 'scenario'), scenario: d.scenario }
      }
      return s
    }

    // ── « Recalculer le dimensionnement » (:2647-2731) ─────────────────────
    // INVARIANT 3 — la valeur retenue (résolue par l'appelant : recommandation
    // SERVEUR en résidentiel, balayage local ailleurs) est posée, le drapeau
    // est ROUVERT POUR LA COMPOSITION QUI SUIT et sa valeur ANTÉRIEURE est
    // restaurée DANS LA MÊME TRANSITION : il n'existe plus aucune fenêtre
    // entre les deux instructions où une frappe puisse s'engouffrer.
    case 'RECALCUL_DEMANDE': {
      const retenu = action.retenu
      if (!retenu || !(nombre(retenu.nbPanneaux) > 0)) return base
      return {
        ...base,
        // `sizingInfo` reste NUL en résidentiel : son encart parle de « palier
        // retenu », une notion du balayage local qui ne décrit pas le moteur.
        sizingInfo: base.modeInstallation === 'residentiel' ? null : retenu,
        kwcCible: retenu.kwcOptimal != null ? String(retenu.kwcOptimal) : '',
        nbPanneaux: String(retenu.nbPanneaux),
        attenteMoteur: false,
        motifMoteur: null,
        // touche.nbPanneaux : INCHANGÉ (= restauré) — voir invariant 3.
        compositionSeq: base.compositionSeq + 1,
        recalcul: Object.freeze({
          seq: base.compositionSeq + 1,
          ignorerToucheNbPanneaux: true,
        }),
      }
    }

    default:
      return base
  }
}

/**
 * Balayage LOCAL (industriel/commercial/agricole) résolu par l'appelant :
 * `null` = rien de chiffrable → aucun compte posé et le justificatif est
 * effacé (jamais un chiffre supposé).
 */
function appliquerSizingLocal(etat, sizing) {
  if (!sizing || !(nombre(sizing.nbPanneaux) > 0)) return { ...etat, sizingInfo: null }
  return { ...poserPanneaux(etat, sizing.nbPanneaux), sizingInfo: sizing }
}

/**
 * Drapeau « nbPanneaux touché » TEL QUE LA COMPOSITION DOIT LE LIRE. Seule la
 * transition `RECALCUL_DEMANDE` le fait répondre `false` alors que l'état
 * conserve sa valeur réelle — c'est le déverrouillage explicite demandé par le
 * fondateur, borné à cette unique transition.
 */
export const toucheNbPanneauxPourComposition = (etat) =>
  (etat.recalcul?.ignorerToucheNbPanneaux ? false : etat.touche.nbPanneaux)

/** Liste ÉNUMÉRABLE des drapeaux posés — la lecture que six refs interdisaient. */
export const drapeauxPoses = (etat) =>
  DRAPEAUX_TOUCHE.filter((d) => !!etat.touche[d])
