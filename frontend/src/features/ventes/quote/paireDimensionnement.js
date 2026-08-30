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
