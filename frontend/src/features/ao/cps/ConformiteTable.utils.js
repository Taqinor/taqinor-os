/* ============================================================================
   AOF181 — Règles pures de conformité du CPS (verdicts, blocage, valeurs).
   ----------------------------------------------------------------------------
   Séparé de `ConformiteTable.jsx` pour que le composant n'exporte QUE des
   composants (react-refresh/only-export-components). **Aucun chiffre de
   conformité n'est calculé ici** (garde AOF94) : ces fonctions ne font que
   LIRE et METTRE EN FORME ce que le serveur a déjà tranché.

   ── RÉPARATION 03/08/2026 : `valeurExigee` lisait quatre champs fantômes ───
   Elle lisait `exigence.type`, `exigence.valeur`, `exigence.valeur_min` et
   `exigence.valeur_max` — AUCUN n'est servi. `ExigenceCPSSerializer` déclare
   `type_exigence`, `valeur_num` et `valeur_max_num`. Conséquences mesurées :
   toute clause CHIFFRÉE s'affichait « — » (les trois porteurs de valeur étant
   `undefined`), et le préfixe « ≤ »/« ≥ » ne s'affichait JAMAIS puisqu'il se
   décidait sur `exigence.type === 'plafond' | 'plancher'`, deux valeurs qui
   n'existent dans aucun backend. Seules les clauses en `valeur_texte`
   fonctionnaient — ce qui rendait la panne invisible à la relecture.

   **Le préfixe ne s'invente pas.** Il n'est affiché que pour un type dont le
   MODÈLE porte lui-même la direction (cf. `PREFIXE_PAR_TYPE`) ; pour tous les
   autres, aucun préfixe — un comparateur faux est pire qu'un comparateur
   absent sur une clause qui se défend devant une commission.
   ========================================================================== */

export const CONFORME = 'conforme'
export const NON_CONFORME = 'non_conforme'
export const NON_EVALUE = 'non_evalue'

/** Statut de conformité TEL QUE LE SERVEUR le donne (`conformite.statut` ou
    `statut_conformite`), `non_evalue` à défaut. Jamais déduit d'une
    comparaison de valeurs.

    ⚠ ANNOTATION NON SERVIE À CE JOUR (vérifié le 03/08/2026).
    `ExigenceCPSSerializer` (`apps/ao/serializers.py`) ne déclare NI
    `conformite` NI `statut_conformite`, et aucun code d'`apps/ao` ne les
    produit : sur les données réelles, TOUTE clause retombe donc sur
    `non_evalue`, et `motifBlocageDepot` ci-dessous renvoie toujours `null`
    (l'écran ne bloque jamais le dépôt — c'est le serveur qui reste la porte,
    AOF146). Ce n'est PAS un affichage faux : « Non évalué » est exactement
    l'état réel du dossier, et c'est pourquoi la lecture est conservée plutôt
    que supprimée. Elle reste prête pour le jour où AOF99/AOF146 annoteront
    les clauses. Tant que ce jour n'est pas venu : n'ajouter AUCUN affichage
    qui DÉPENDE de ce verdict pour avoir du contenu — ce serait un placeholder
    perpétuel de plus (c'est ainsi que les colonnes « Constaté » et « Origine
    du constat » ont été retirées de `ConformiteTable.jsx`). */
export function statutConformite(exigence) {
  return exigence?.conformite?.statut || exigence?.statut_conformite || NON_EVALUE
}

/** Sévérité d'AFFICHAGE (clé de `STATUT_CONTROLE`), ou `null` quand le serveur
    n'a pas évalué la clause — un « non évalué » n'est ni vert ni rouge. */
export function severiteAffichee(exigence) {
  const statut = statutConformite(exigence)
  if (statut === CONFORME) return 'ok'
  if (statut === NON_CONFORME) return exigence?.bloquant ? 'bloquant' : 'avertissement'
  return null
}

/** Les clauses BLOQUANTES que le serveur déclare non satisfaites. */
export function exigencesBloquantes(exigences) {
  return (exigences || []).filter(
    (e) => e.bloquant && statutConformite(e) === NON_CONFORME,
  )
}

/** Motif AFFICHABLE du blocage de `pret_a_deposer`, `null` si rien ne bloque. */
export function motifBlocageDepot(exigences) {
  const premiere = exigencesBloquantes(exigences)[0]
  if (!premiere) return null
  return premiere.conformite?.message
    || premiere.libelle
    || premiere.code
    || 'exigence bloquante non satisfaite'
}

/* Préfixe comparateur par type d'exigence — UNIQUEMENT quand le modèle porte
   lui-même la direction. Établi en relisant `ExigenceCPS.TypeExigence` et
   `CLAUSES_REFERENCE_CPS` (`apps/ao/models.py`) :

     • `puissance_onduleur_max` → « ≤ » : le nom du choix, son libellé modèle
       (« Puissance unitaire max d'onduleur ») et celui de la clause de
       référence (« Puissance unitaire MAXIMALE d'un onduleur ») disent tous
       trois le plafond. Direction portée par le modèle : préfixe légitime.
     • `ratio_dc_ac` → aucun : c'est le SEUL intervalle (« Ratio DC/AC
       (min–max) », 0,75 → 1) ; il s'affiche « 0,75 – 1 », la borne haute
       venant de `valeur_max_num`. Un intervalle n'a pas de comparateur.
     • `validite_offre` → AUCUN, à dessein. L'intuition dit « plancher » (une
       offre vaut AU MOINS 75 jours), mais le modèle ne l'écrit nulle part :
       ni le choix (« Validité de l'offre »), ni la clause de référence
       (« Durée de validité de l'offre », 75 jours) ne portent de direction.
       Consigne suivie : quand le modèle ne tranche pas, ne rien préfixer
       plutôt qu'afficher un « ≥ » que rien ne fonde.
     • `caution_provisoire` (montant absolu), `caution_definitive_taux` (taux
       de 3 %), `penalite_retard` (1 ‰/jour) → aucun : ce sont des valeurs
       EXACTES, pas des bornes.
     • `piece_administrative`, `reference_normative`, `autre` → non chiffrés,
       ils partent en `valeur_texte` et sortent avant d'arriver ici.

   Ajouter une entrée ici EXIGE que la direction soit lisible dans le modèle. */
const PREFIXE_PAR_TYPE = {
  puissance_onduleur_max: '≤ ',
}

const estRempli = (v) => v != null && v !== ''

/** Valeur EXIGÉE, assemblée en texte à partir de ce que porte la clause.
    Assemblage de chaînes uniquement — aucune arithmétique, aucun arrondi :
    « 0,75 » servi par le serveur ressort « 0,75 ». */
export function valeurExigee(exigence) {
  if (!exigence) return '—'
  if (exigence.valeur_texte) return exigence.valeur_texte
  const unite = exigence.unite ? ` ${exigence.unite}` : ''
  // Noms RÉELS du sérialiseur : `valeur_num` / `valeur_max_num`.
  const min = exigence.valeur_num
  const max = exigence.valeur_max_num
  if (estRempli(min) && estRempli(max)) return `${min} – ${max}${unite}`
  const seule = [min, max].find(estRempli)
  if (!estRempli(seule)) return '—'
  const prefixe = PREFIXE_PAR_TYPE[exigence.type_exigence] || ''
  return `${prefixe}${seule}${unite}`
}
