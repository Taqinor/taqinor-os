# NTEDU42 — DÉCISION : synchronisation Massar (ministère marocain de l'Éducation)

**Statut : RESEARCH SPIKE — aucun code livré, comme demandé par le critère
d'acceptation (« livrable = note de faisabilité, aucun code »).**

Type : DECISION (founder-gated). Aucune intégration ne doit être construite
sans validation fondateur explicite (nouvelle architecture + dépendance
externe potentielle).

---

## 1. Contexte

MASSAR est le système d'information du Ministère de l'Éducation Nationale
marocain (gestion des élèves, notes, effectifs) utilisé par la quasi-totalité
des établissements scolaires publics et une partie du privé sous convention.
NTEDU42 demande d'évaluer — AVANT tout code — si une synchronisation
(export élèves/notes vers un format compatible Massar) est réellement
demandée par un client pilote de TAQINOR OS module Éducation.

## 2. Constat (recherche interne au dépôt)

- Aucun client pilote identifié dans ce dépôt (pas de mention Massar dans
  `docs/`, aucun ticket/demande tracée) au moment de cet audit.
- Le module `apps.education` (NTEDU1-41) couvre aujourd'hui : structure
  année/niveau/classe, dossier famille/élève, inscriptions + liste d'attente,
  scolarité (tarifs/remises/échéancier), présences, notes/moyennes,
  discipline, cantine/transport, portail parents. Rien de tout cela ne
  suppose un format d'échange Massar — le module reste autonome et cohérent
  sans cette intégration.
- Massar n'expose PAS d'API publique documentée pour les établissements
  privés/tiers (accès historiquement réservé aux directions
  provinciales/académies, via des exports Excel/CSV manuels côté
  établissement) — toute « synchronisation automatique » serait en réalité
  un export/import de fichiers dans un format propriétaire non stabilisé,
  pas un flux API.

## 3. Ce qui est décidé ici

- **On NE construit RIEN maintenant.** Aucun modèle, aucun champ, aucun
  export dédié Massar n'est ajouté au module éducation par ce spike.
- **Avant tout code futur**, il faut : (a) un client pilote confirmé
  demandant explicitement cette synchronisation, ET (b) une décision
  fondateur explicite sur le point d'entrée technique (export
  Excel/CSV manuel dans un format Massar-compatible — le plus réaliste vu
  l'absence d'API publique — vs. tentative d'intégration plus profonde).
- **Si demandé un jour**, l'option la plus proche du réalisable serait un
  export additif (nouveau bouton d'export dans `apps.education`, même
  patron que NTEDU37/`apps.education.exports`) produisant un fichier au
  format colonnes Massar connu du client pilote — jamais une écriture
  directe dans un système tiers, jamais une dépendance réseau nouvelle par
  défaut.

## 4. Risques identifiés (si activé un jour)

1. **Format non stabilisé** — Massar évolue sans documentation publique
   versionnée ; un export figé peut se désynchroniser silencieusement d'une
   année sur l'autre. Mitigation : traiter tout mapping de colonnes comme
   configurable, jamais hardcodé, et le valider avec le client pilote à
   chaque rentrée.
2. **Données personnelles mineurs** — CIN/date de naissance/nom des parents
   quittent potentiellement le périmètre TAQINOR (export manuel). Mitigation :
   rester sur un export TÉLÉCHARGÉ par l'établissement lui-même (jamais un
   envoi automatique serveur-à-serveur tant qu'aucun accord de traitement de
   données n'est signé).
3. **Aucune garantie d'unicité applicative** — Massar attribue ses propres
   identifiants élève (Massar Code) : toute synchronisation bidirectionnelle
   nécessiterait un champ de correspondance dédié (`Eleve.code_massar`,
   nullable, jamais généré côté TAQINOR) — hors périmètre tant que non
   demandé.

## 5. Recommandation

Ne rien construire. Revisiter uniquement si un client pilote du module
Éducation formule explicitement le besoin — à ce moment, reprendre ce
dossier avec le format d'export réellement attendu par ce client (probable
export Excel/CSV, jamais une intégration temps réel).

## 6. Traçabilité

- Recherche : audit interne du dépôt (`docs/`, `apps/education/`) — aucune
  source externe consultée (spike delivrable = note, zéro appel réseau).
- Module concerné (référence, non modifié) : `backend/django_core/apps/education/`.
