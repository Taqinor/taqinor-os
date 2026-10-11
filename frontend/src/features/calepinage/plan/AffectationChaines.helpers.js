// ENF22 — helpers extraits de AffectationChaines.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/* ============================================================================
   CAL234 — AFFECTER LES CHAÎNES À LA MAIN, AVEC LE VERDICT EN DIRECT.
   ----------------------------------------------------------------------------
   LE TROU QU'IL BOUCHE. CAL124 affecte AUTOMATIQUEMENT et CAL126 dessine le
   résultat, mais rien ne permettait à un installateur de CORRIGER
   l'affectation : le plan automatique était à prendre ou à laisser. Or
   sélectionner une suite de modules pour en faire une chaîne est le geste de
   base des outils comparés. Cet écran le donne : on GLISSE sur les modules,
   on les affecte à une chaîne / une entrée MPPT, et le serveur dit
   immédiatement si ça tient.

   AUCUN DIMENSIONNEMENT CÔTÉ ÉCRAN — C'EST LA RÈGLE CENTRALE.
   Cet écran ne calcule NI une longueur de chaîne admissible, NI une tension à
   froid, NI un nombre de chaînes par entrée. Il ne fait que deux choses :
     1. il AFFICHE la table d'affectation SERVEUR (`electrique.affectation`,
        contrat `calepinage_resultat.json`, CAL125), ligne par ligne, avec sa
        `source` (« automatique » ou « affectation manuelle ») ;
     2. il PROPOSE une affectation au serveur et RECOPIE son verdict.
   Un écran qui re-partitionnerait produirait une AUTRE partition que celle qui
   a été dimensionnée — exactement le raisonnement déjà écrit dans CAL126.

   LES DEUX CHEMINS, UNE SEULE FORME DE DONNÉE (posée par la moitié backend).
     * `POST calepinages/<pk>/evaluer-electrique/` avec
       `{ entree_electrique: { affectation_manuelle: [...] } }` : VERDICTE sans
       rien persister (garde en LECTURE). C'est l'appel anti-rebond du glissé.
     * `POST calepinages/<pk>/entree-electrique/` avec
       `{ affectation_manuelle: [...] }` : ENREGISTRE, et répond avec le
       `resultat` recalculé — les lignes touchées y portent alors
       `source: « affectation manuelle »`. Aucun second appel n'est enchaîné.
   Une ligne d'affectation est `{module, chaine, mppt, onduleur}` — les quatre
   seules clés admises par `normaliser_affectation_imposee`.

   LE REFUS VIENT DU SERVEUR, TOUJOURS. Les bloquants sont RECOPIÉS tels quels
   (ils NOMMENT la contrainte, le pan et la chaîne) ; un refus 400 est affiché
   SOUS le champ que le serveur nomme (règle fondateur du 08/09/2026 : jamais
   un « non enregistré » générique). L'écran n'invente aucun message.

   RELANCER L'AUTOMATIQUE NE PEUT PAS ÊTRE ACCIDENTEL. Effacer une affectation
   faite à la main demande une CONFIRMATION explicite : le premier clic arme,
   le second exécute. C'est la garantie exigée par le Done de la tâche.

   CALX53 — LES AVERTISSEMENTS DU SERVEUR SONT AFFICHÉS, PAS AVALÉS.
   `resultat.avertissements` (contrat `calepinage_resultat.json`) est rendu EN
   HAUT du panneau, avant la grille et les bornes de chaîne : c'est là que le
   serveur NOMME, par exemple, un coefficient de température non sourcé —
   `temp_coeff_voc_pct_c` / `temp_coeff_pmax_pct_c` tombés sur le défaut du
   noyau. Les bornes restent calculées ; l'utilisateur sait seulement qu'elles
   reposent sur une valeur que sa fiche produit ne publie pas. Les messages
   sont RECOPIÉS tels quels — cet écran n'en reformule ni n'en filtre aucun.
   ========================================================================== */

/* ── LA TEINTE DES CHAÎNES — SERVIE PAR LE SERVEUR (ACAL324) ───────────────
   Chaque ligne de `electrique.affectation[]` porte `couleur_chaine` et
   `couleur_mppt` (gris pour un module non affecté) : la même valeur colore
   cet écran, la 3D et le plan de câblage PDF. Aucune palette n'est recopiée
   ici — une copie locale, c'est une couleur qui dérive. */

/** La couleur SERVIE d'une ligne pour le mode affiché, ou `null`. */
export function couleurServie(ligne, mode) {
  const couleur = mode === 'chaine' ? ligne.couleur_chaine : ligne.couleur_mppt
  return typeof couleur === 'string' && couleur ? couleur : null
}

/** Clé de groupe d'une ligne. `null` = module non affecté (gris). */
export function cleGroupe(ligne, mode) {
  if (mode === 'chaine') return ligne.chaine == null ? null : `c${ligne.chaine}`
  if (ligne.mppt == null) return null
  return `o${ligne.onduleur ?? 1}m${ligne.mppt}`
}

/** Libellé lisible d'un groupe, pour la légende. */
export function libelleGroupe(ligne, mode) {
  if (mode === 'chaine') {
    return ligne.chaine == null ? 'Non affecté' : `Chaîne ${ligne.chaine}`
  }
  if (ligne.mppt == null) return 'Non affecté'
  return ligne.onduleur == null
    ? `MPPT ${ligne.mppt}`
    : `Onduleur ${ligne.onduleur} — MPPT ${ligne.mppt}`
}

/**
 * `module -> couleur` + légende, construits sur la SEULE table servie.
 * Ordre de première apparition, « Non affecté » en dernier — comme CAL126.
 */
export function couleurParModule(lignes, mode) {
  const couleurs = new Map()
  const parCle = new Map()
  const ordre = []
  for (const ligne of lignes || []) {
    if (!ligne || typeof ligne.module !== 'string') continue
    const cle = cleGroupe(ligne, mode)
    let entree = parCle.get(cle)
    if (!entree) {
      // ACAL324 — la pastille du groupe prend la couleur SERVIE par sa
      // première ligne (ordre de première apparition, comme le serveur).
      const couleur = couleurServie(ligne, mode)
      entree = { cle, libelle: libelleGroupe(ligne, mode), couleur, nombre: 0 }
      parCle.set(cle, entree)
      ordre.push(cle)
    }
    entree.nombre += 1
    couleurs.set(ligne.module, couleurServie(ligne, mode) || entree.couleur)
  }
  const legende = ordre
    .map((c) => parCle.get(c))
    .sort((a, b) => (a.cle === null ? 1 : 0) - (b.cle === null ? 1 : 0))
  return { couleurs, legende }
}
