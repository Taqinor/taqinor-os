// QJR90 — moitié PURE de `useComposition`.
//
// LA PROPRIÉTÉ STRUCTURELLE : la composition rend TOUJOURS
// `{ lignes, source: 'serveur' | 'local', raison }`, et `raison` n'est JAMAIS
// vide. L'appelant ne peut donc pas afficher des lignes sans dire d'où elles
// viennent — la bannière QJR36 (« composition locale de secours ») cesse d'être
// un `if` qu'on peut oublier et devient une propriété du type de retour.
//
// Aujourd'hui le repli local de `handleAutoFill` (`DevisGenerator.jsx:2495-2520`)
// est SILENCIEUX : quand le dry-run serveur échoue, l'écran affiche des lignes
// composées par une AUTRE implémentation sans le dire (incident du 20/08 —
// câbles, marques, ordre, arrondi panneaux divergeaient).
//
// Module AJOUTÉ TESTÉ, IMPORTÉ PAR PERSONNE (vague M4).

export const RAISON_SERVEUR = 'composition chiffrée par le serveur (dry-run)'
export const RAISON_RIEN = 'aucune ligne composée : renseignez le nombre de panneaux'

/** Repli après un échec réseau/serveur — la cause est NOMMÉE, jamais tue. */
export const raisonRepli = (cause) =>
  "le serveur n'a pas pu composer ce devis"
  + (cause ? ` (${cause})` : '')
  + ' — composition locale de secours, chiffres à vérifier'

/**
 * Résout la composition à afficher.
 *
 * @param serveur  `{ lignes }` du dry-run, ou null.
 * @param local    sortie d'un module de marché QJR89 (`{ lignes, raison }`),
 *                 ou null.
 * @param erreur   cause FR de l'échec serveur, si échec il y a eu.
 * @param marche   clé du marché (pour la raison par défaut).
 */
export function resoudreComposition({
  serveur = null, local = null, erreur = null, marche = '',
} = {}) {
  const lignesServeur = serveur?.lignes
  if (Array.isArray(lignesServeur) && lignesServeur.length) {
    return { lignes: lignesServeur, source: 'serveur', raison: RAISON_SERVEUR }
  }
  const lignesLocales = local?.lignes
  if (Array.isArray(lignesLocales) && lignesLocales.length) {
    return {
      lignes: lignesLocales,
      source: 'local',
      // Un repli APRÈS échec serveur se dit autrement qu'un marché qui n'a
      // simplement pas de dry-run (industriel/commercial/agricole).
      raison: erreur
        ? raisonRepli(erreur)
        : (local.raison
          || `aucun dry-run serveur pour le marché ${marche} — composition locale`),
    }
  }
  return {
    lignes: [],
    source: 'local',
    raison: erreur ? raisonRepli(erreur) : (local?.motif || RAISON_RIEN),
  }
}
