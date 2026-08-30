// QJR90 — moitié PURE de `useSizingMoteur` (patron maison
// `etudeHorairePreview.js` 98 l hook + `etudeHorairePreviewPur.js` 289 l pur :
// la décision est testable sous `node --test`, le hook n'enchaîne que le
// réseau et les dispatches).
//
// LA GARDE DE PÉREMPTION, SUR LES **DEUX** BRANCHES. Aujourd'hui
// `DevisGenerator.jsx:1053` ne compare la clé du corps servi qu'en présence de
// `donnees` : la branche d'ÉCHEC (`:1076`) ferme donc le drapeau d'attente et
// ÉPINGLE UN REFUS OBSOLÈTE — le refus d'une facture qu'on vient de remplacer.
// Ici les deux branches exigent que la réponse (succès OU échec) décrive le
// corps qu'on a SOUS LES YEUX.
//
// Module AJOUTÉ TESTÉ, IMPORTÉ PAR PERSONNE (vague M4).

/** Refus générique — n'est utilisé que si le serveur n'a nommé aucune cause. */
export const REFUS_GENERIQUE =
  "Dimensionnement indisponible : le serveur n'a pas pu chiffrer de recommandation."

/**
 * Motif d'un refus, dans l'ordre EXACT de `DevisGenerator.jsx:1085-1089` :
 * un refus PROPRE arrive en `dimensionnement.motivation` (une phrase française
 * qui NOMME la cause) et n'a AUCUN `avertissements` — ne lire que
 * `avertissements[0]` remplaçait la cause réelle par le message générique.
 * Les deux formes sont lues, et rendues VERBATIM (texte du serveur).
 */
export const motifRefus = (donnees, erreur) => (
  donnees?.avertissements?.[0]
  || donnees?.dimensionnement?.motivation
  || erreur
  || REFUS_GENERIQUE
)

/**
 * DÉCISION du moteur de dimensionnement. Rend TOUJOURS `{ action, ... }` :
 *   · `rien`        — aucune attente en cours, on ne touche à rien ;
 *   · `abandonner`  — une frappe manuelle a eu lieu : elle gagne toujours,
 *                     l'attente se referme sans rien appliquer ;
 *   · `attendre`    — réponse en vol, OU réponse PÉRIMÉE (succès ou échec) :
 *                     le drapeau reste OUVERT, aucun refus n'est épinglé ;
 *   · `appliquer`   — recommandation fraîche et chiffrée ;
 *   · `refuser`     — refus frais, avec le motif FR VERBATIM.
 *
 * `cleServie` = clé du corps qui a produit `donnees` (fournie par
 * `useEtudeHorairePreview`), `cleErreur` = clé du corps qui a produit
 * `erreur` (suivie par le hook), `cleCourante` = clé du corps à l'écran.
 */
export function decisionSizing({
  attente = false,
  toucheNbPanneaux = false,
  chargement = false,
  donnees = null,
  erreur = null,
  cleServie = null,
  cleErreur = null,
  cleCourante = null,
} = {}) {
  if (!attente) return { action: 'rien' }
  // Une frappe manuelle gagne TOUJOURS (invariant 1 du reducer QJR87).
  if (toucheNbPanneaux) return { action: 'abandonner', raison: 'saisie-manuelle' }
  if (chargement) return { action: 'attendre', raison: 'en-vol' }
  // BRANCHE SUCCÈS — la réponse doit décrire ce qu'on a sous les yeux.
  if (donnees && cleServie !== cleCourante) {
    return { action: 'attendre', raison: 'reponse-perimee' }
  }
  // BRANCHE ÉCHEC — MÊME exigence (c'est le correctif de cette tâche) : un
  // échec qui décrit un ANCIEN corps ne ferme rien et n'épingle rien. Un
  // échec non attribuable à un corps est traité comme périmé (jamais comme
  // un refus du corps courant).
  if (erreur && cleErreur !== cleCourante) {
    return { action: 'attendre', raison: 'echec-perime' }
  }
  const reco = donnees?.dimensionnement?.recommandation
  if (Number(reco?.panneaux) > 0) {
    return { action: 'appliquer', recommandation: reco }
  }
  if (donnees || erreur) {
    return { action: 'refuser', motif: motifRefus(donnees, erreur) }
  }
  return { action: 'attendre', raison: 'aucune-reponse' }
}
