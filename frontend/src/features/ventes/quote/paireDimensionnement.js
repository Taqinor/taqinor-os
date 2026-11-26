// QJR108 — LE SÉLECTEUR `deuxValeursDim`, SORTI DE L'ÉCRAN POUR ÊTRE EXÉCUTÉ.
// ---------------------------------------------------------------------------
// Ces trois définitions vivaient en haut de `DevisGenerator.jsx`, non
// exportées (le fichier n'exporte que des composants — règle react-refresh).
// Elles n'étaient donc vérifiables QUE par expression régulière sur le source,
// c'est-à-dire pas vérifiables du tout : une épingle regex rougit sur un
// reformatage et reste verte sur une régression. Déplacées ici — module PUR,
// sans React — elles sont testées par EXÉCUTION
// (`DevisGeneratorDeuxOptimiseurs.test.mjs`).
//
// DÉPLACEMENT SEUL : pas une ligne de logique n'a changé. Même ordre des
// branches, mêmes valeurs signées (QJR86), même forme rendue `{sans, avec}` —
// le JSX de l'écran est inchangé.
//
// CE QUE CES FONCTIONS ENCODENT (F3, revue adversariale 26/08/2026) : la
// paire affichée « recommandé sans batterie / avec batterie » n'existe qu'à
// SOURCE UNIQUE. Un côté venu du moteur horaire serveur pendant que l'autre
// retombait sur le balayage local, c'étaient deux méthodes de calcul
// DIFFÉRENTES dont l'ÉCART affiché n'était plus comparable. QJR102 a supprimé
// la branche locale (structurellement injoignable) : il ne reste QU'UNE
// source possible, et la règle devient une propriété du type.
import { moteur, absent, estFait } from './valeur.js'
import { SCENARIO_AVEC } from './scenarios.js'

/** Motif d'absence — jamais un chiffre de remplacement (règle #4). */
export const RIEN_A_CHIFFRER = 'aucun dimensionnement chiffré pour cette branche'

/** Recommandation du MOTEUR horaire serveur — publiable telle quelle. */
export const valeurMoteurDim = (srv) => (Number(srv?.panneaux) > 0
  ? moteur({ nbPanneaux: srv.panneaux, kwc: srv.kwc })
  : absent(RIEN_A_CHIFFRER))

/**
 * QJR99 — remplace la CHAÎNE DE TERNAIRES `deuxValeursDim`. Chaque branche
 * devient une VALEUR SIGNÉE (QJR86) : `moteur` = moteur horaire serveur,
 * `absent(motif)` = rien de calculable — jamais un chiffre inventé.
 *
 * Rend `{ sans, avec }`, chacun `{nbPanneaux, kwc}` ou `null`.
 */
export const paireDimensionnement = (srvSans, srvAvec) => {
  const mSans = valeurMoteurDim(srvSans)
  const mAvec = valeurMoteurDim(srvAvec)
  if (estFait(mSans) && estFait(mAvec)) return { sans: mSans.valeur, avec: mAvec.valeur }
  // Une seule branche chiffrée : elle sort SEULE — « sans » avant « avec »,
  // comme la cascade historique.
  if (estFait(mSans)) return { sans: mSans.valeur, avec: null }
  if (estFait(mAvec)) return { sans: null, avec: mAvec.valeur }
  return { sans: null, avec: null }
}

/**
 * LE SÉLECTEUR COMPLET de l'écran : la paire à afficher pour un marché et une
 * réponse du moteur horaire. Hors résidentiel il n'y a PAS de seconde option
 * (ni batterie ni onduleur hybride au devis) — y afficher une valeur « avec »
 * serait un chiffre fabriqué.
 */
export const deuxValeursDim = (modeInstallation, etudeHoraireDonnees) => {
  if (modeInstallation !== 'residentiel') return { sans: null, avec: null }
  const dim = etudeHoraireDonnees?.dimensionnement
  return paireDimensionnement(dim?.recommandation, dim?.recommandation_avec)
}

/** T4-X6-016 / R5A-N3 — CE QUE « Recalculer le dimensionnement » RETIENDRAIT MAINTENANT : `{ retenu }` (la taille servie par
    le moteur, horaire résidentiel ou conseil C&I) ou `{ erreur }` (le message du clic, en français). LE prédicat unique : le
    clic l'applique, et l'écran réécrit avec lui un message de clic encore affiché quand les données changent — un message
    ne contredit donc jamais les lignes « Conseillé », et un clic arrivé avant les données n'est jamais perdu en silence
    (`DIMENSIONNEMENT_PRET` dit de réessayer). */
export const DIMENSIONNEMENT_PRET = 'Dimensionnement prêt — réessayez pour l’appliquer.'
export function issueRecalculDimensionnement({
  modeInstallation, scenario, marcheCi, etudeHoraireDonnees, etudeHoraireChargement, apercuCi,
}) {
  if (modeInstallation === 'residentiel') {
    const dim = etudeHoraireDonnees?.dimensionnement
    const source = (scenario === SCENARIO_AVEC && Number(dim?.recommandation_avec?.panneaux) > 0)
      ? dim.recommandation_avec : dim?.recommandation
    if (Number(source?.panneaux) > 0) {
      return { retenu: { nbPanneaux: Number(source.panneaux), kwcOptimal: source.kwc != null ? Number(source.kwc) : null } }
    }
    // Message FRANÇAIS du serveur quand il en a un (il nomme la donnée manquante), sinon la cause générique — jamais un
    // chiffre supposé ; pendant le calcul, le clic DIT que le calcul n'est pas encore là.
    return {
      erreur: dim?.motivation
        || etudeHoraireDonnees?.avertissements?.[0]
        || (etudeHoraireChargement
          ? 'Dimensionnement en cours de calcul — réessayez dans un instant.'
          : "Le moteur n'a pas pu chiffrer de recommandation : complétez la "
            + 'facture, la ville et le raccordement du client, puis réessayez.'),
    }
  }
  // CIQ126 — C&I : la taille retenue par le moteur serveur (aperçu en direct du profil déclaré) ; sans elle, rien n'est
  // inventé. T4-X6-008 — en édition, l'aperçu décrit les LIGNES : la taille du moteur est son `conseil`.
  const t = apercuCi?.conseil ?? apercuCi?.donnees?.taille
  if (!marcheCi || !(Number(t?.nb_panneaux) > 0)) {
    return {
      erreur: 'Le moteur C&I n\'a pas encore retenu de taille : complétez le '
        + 'profil de consommation du site, puis réessayez.',
    }
  }
  return { retenu: { nbPanneaux: Number(t.nb_panneaux), kwcOptimal: t.retenue_kwc != null ? Number(t.retenue_kwc) : null } }
}
