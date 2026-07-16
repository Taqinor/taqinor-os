# DÉCISION — Unification RIB paie ↔ RH (ARC25)

**Statut : contrôle croisé (lecture seule) livré. Toute UNIFICATION du RIB est
une DÉCISION FONDATEUR explicitement NON PRISE ici — à trancher par Reda.**

## Contexte

Deux champs `rib` cohabitent, indépendants, sans rien qui les rapproche :

- `paie.ProfilPaie.rib` (paramètre de paie du salarié) — c'est la SOURCE des
  lignes de l'ordre de virement (PAIE30, `LigneVirement.rib`) ;
- `rh.DossierEmploye.rib` (fiche RH maître) — le RIB de référence côté dossier
  employé.

Les copies figées (`LigneVirement.rib` de l'ordre de virement, et toute demande
d'approbation de changement de RIB) sont des **snapshots INTENTIONNELS** — elles
doivent rester ce qu'elles étaient au moment T (traçabilité du fichier de
virement réellement émis). Ce ne sont pas des bugs et ARC25 n'y touche pas.

Le risque réel : un RIB mis à jour d'un seul côté (ex. changement de banque saisi
dans la fiche RH mais pas dans le profil paie, ou l'inverse) fait qu'un virement
part sur un compte périmé, sans qu'aucune alerte ne se déclenche.

## Ce qui est livré (ARC25 — additif, ZÉRO risque)

Un **contrôle croisé en LECTURE SEULE**, déclenché au moment de la génération de
l'ordre de virement (`paie.services.generer_ordre_virement`) :

- `apps/rh/selectors.py::ribs_par_employe(company, employe_ids)` expose le RIB
  brut du dossier RH, scopé société (jamais un import de `rh.models` côté paie) ;
- `apps/paie/selectors.py::divergences_rib_periode(periode)` compare, pour les
  profils PAYÉS PAR VIREMENT, `ProfilPaie.rib` au RIB RH — comparaison robuste au
  formatage (espaces retirés), SANS normalisation au-delà ;
- `apps/paie/services.py::controler_coherence_rib(periode)` : divergence →
  **notification interne** aux responsables paie ; concordance → **silence**.
  Best-effort et non bloquant (jamais dans la transaction, un échec d'envoi
  n'empêche jamais la génération de l'ordre).

**Sémantique anti-faux-positif :** un écart n'est signalé QUE si les DEUX RIB
sont non vides et diffèrent. Un RIB paie vide est déjà couvert par
l'avertissement bloquant `rib_manquant_virement` (ZPAI2) ; un RIB RH vide
signifie « référence non renseignée », pas « conflit ».

## Ce qui n'est PAS fait (GATE FONDATEUR)

**Aucune fusion / unification du RIB.** Faire du `DossierEmploye.rib` la source
unique (ou l'inverse), ou synchroniser automatiquement l'un vers l'autre, est une
décision structurelle non prise ici. Rayon d'impact à mesurer AVANT toute
unification :

- **fichiers de virement** (FG134 / PAIE30 : `fichier_virement_paie`,
  `fichier_virement_paie_simt` SIMT) — un RIB changé silencieusement change le
  compte crédité d'un virement de masse ;
- les **snapshots figés** (`LigneVirement`, demandes d'approbation de RIB) qui
  doivent rester des instantanés et ne jamais être « rattrapés » par une
  synchronisation ;
- la **saisie** : aujourd'hui deux écrans indépendants ; unifier impose de
  choisir un point de saisie unique et de migrer l'autre.

## Options pour le fondateur

1. **Statu quo + alerte (livré).** On garde deux champs, on alerte à chaque
   divergence au run de virement. Zéro migration, zéro risque sur les virements.
   *Recommandé à ce stade.*
2. **Source unique RH.** `DossierEmploye.rib` devient la référence ; `ProfilPaie`
   lit le RIB RH (ou ne le stocke plus). Impose une migration de données et une
   revue des écrans de saisie paie.
3. **Source unique paie.** L'inverse. Même coût, choix inverse.

Toute bascule vers 2 ou 3 attend un GO explicite de Reda.

## Suivi technique (hors périmètre ARC25, à noter)

La notification est émise via `notifications.services.notify_many` avec la clé
d'événement `paie_rib_divergence`, en suivant le patron paie existant
(cf. `paie_bulletin_disponible` XPAI21, `paie_echeance_retard` XPAI6). Ces clés
paie ne sont PAS (encore) enregistrées dans `notifications.EventType`, donc la
ligne in-app n'est pas persistée tant que l'événement n'est pas déclaré. Ajouter
`EventType.PAIE_RIB_DIVERGENCE` (+ sa migration `AlterField` sur
`notification.event_type`) rendrait la notification in-app durable ; c'est un
suivi volontairement différé ici pour ne pas générer, dans un run multi-lane, une
migration `AlterField` sur la liste complète des choix (collision de fold quasi
certaine avec toute autre lane ajoutant un événement). À traiter en une passe
dédiée regroupant tous les événements paie non enregistrés.
