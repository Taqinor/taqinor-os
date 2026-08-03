/* ============================================================================
   AOF181 — Types de clause et corps de création, hors composant.
   ----------------------------------------------------------------------------
   Séparé de `ExigencesPage.jsx` pour que le composant n'exporte QUE des
   composants (react-refresh/only-export-components).

   ── RÉPARATION 03/08/2026 : ce fichier PUBLIAIT un contrat inventé ─────────
   Les six types proposés (`intervalle`, `plafond`, `plancher`, `montant`,
   `duree`, `texte`) n'existaient DANS AUCUN backend, et le corps envoyé
   nommait `affaire`, `type`, `valeur`, `valeur_min`, `valeur_max` — cinq clés
   qu'`ExigenceCPSSerializer` ne déclare pas. DRF ignore silencieusement une
   clé inconnue : la requête partait donc SANS son `appel_offre` obligatoire et
   revenait en 400. Ajouter une clause depuis cet écran était impossible.

   La liste ci-dessous est désormais la RECOPIE EXACTE de
   `ExigenceCPS.TypeExigence` (`apps/ao/models.py`) — valeurs ET libellés. Ne
   PAS y ajouter un type « pratique » : un type absent des choix du modèle est
   refusé par le serveur. Si un type manque, il s'ajoute AU MODÈLE d'abord.

   Le partage numérique/texte suit le modèle, pas une intuition :
   `valeur_num` porte la valeur principale, `valeur_max_num` n'est renseignée
   QUE pour un intervalle (le seul est le ratio DC/AC, « 0,75 → 1 » — c'est le
   commentaire du modèle qui le dit), et `valeur_texte` sert aux clauses non
   chiffrables (pièce administrative, référence normative, autre).
   `est_intervalle` est DÉRIVÉ côté serveur (`valeur_max_num is not None`) et
   déclaré en lecture seule : ne jamais l'envoyer.
   ========================================================================== */

/* Recopie exacte de `ExigenceCPS.TypeExigence` — valeurs serveur. */
export const TYPES_CLAUSE = [
  { value: 'ratio_dc_ac', label: 'Ratio DC/AC (min–max)', intervalle: true },
  { value: 'puissance_onduleur_max', label: "Puissance unitaire max d'onduleur" },
  { value: 'caution_provisoire', label: 'Caution provisoire (montant absolu)' },
  { value: 'caution_definitive_taux', label: 'Caution définitive (taux)' },
  { value: 'validite_offre', label: "Validité de l'offre" },
  { value: 'penalite_retard', label: 'Pénalité de retard' },
  { value: 'piece_administrative', label: 'Pièce administrative exigée', texte: true },
  { value: 'reference_normative', label: 'Référence normative', texte: true },
  { value: 'autre', label: 'Autre clause', texte: true },
]

export function estIntervalle(type) {
  return TYPES_CLAUSE.find((t) => t.value === type)?.intervalle === true
}

/** Une clause dont la valeur n'est PAS chiffrable (pièce exigée, norme, autre) :
    elle part en `valeur_texte`, jamais en `valeur_num`. */
export function estTexte(type) {
  return TYPES_CLAUSE.find((t) => t.value === type)?.texte === true
}

/** Corps de création d'une clause, aux noms de champs RÉELS du sérialiseur.
    Les valeurs partent TELLES QUE TAPÉES (aucun `parseFloat`, aucune virgule
    convertie) : le serveur seul décide de ce qu'il accepte, et son refus
    éventuel est affiché tel quel. */
export function payloadClause(form, affaireId) {
  const corps = {
    appel_offre: affaireId,
    code: (form.code || '').trim() || form.libelle.trim().slice(0, 60),
    libelle: form.libelle.trim(),
    type_exigence: form.type,
    bloquant: Boolean(form.bloquant),
    source_piece: form.sourcePiece.trim(),
    source_page: form.sourcePage.trim() || null,
    unite: form.unite.trim(),
  }
  if (estTexte(form.type)) {
    corps.valeur_texte = form.valeur.trim()
  } else if (estIntervalle(form.type)) {
    corps.valeur_num = form.valeur.trim()
    corps.valeur_max_num = form.valeurMax.trim()
  } else {
    corps.valeur_num = form.valeur.trim()
  }
  return corps
}
