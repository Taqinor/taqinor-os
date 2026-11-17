---
name: cadence-clarte-1711
description: 16-17/11/2026 — audit de clarté des cadences de suivi et étude L3 « liste froide / leads jamais oubliés » : décisions du fondateur, faits mesurés en prod, ce qui est livré, ce qui reste ouvert
metadata:
  type: project
---

Séance du 16-17/11/2026 (PR Taqinor/taqinor-os#1440). Reda a essayé les cadences et les trouve « pas claires, toujours beaucoup de possibilités, pas toujours pertinentes » ; Meryem ne comprenait pas l'étape « Pièces reçues ? ».

## Décisions du fondateur (ne pas re-demander)

- **Dernier réveil sans réponse (16/11)** : le lead part au Froid et RIEN n'est posé ; un suivi de devis pas allé au bout reprend comme avant. Avant, hors Froid, le moteur posait « Préparer et envoyer le devis » à quelqu'un de jamais joint.
- **« Pièces reçues ? » refondue (16/11)** : libellé « Relancer le client pour ses pièces (factures, schéma) », sa propre question et ses réponses, un message prêt (`relance_pieces`).
- **Panneau de réponses simplifié (17/11)** : un seul « Pas joint » (précision facultative), un seul « Plus tard… », le reste sous « Autre réponse » ; réponses filtrées par contexte ; « Ne plus me contacter » porte un avertissement d'opposition légale. Les clés serveur ne changent pas.
- **Douze corrections de textes approuvées telles quelles (17/11)** : uniquement des phrases déjà validées, recombinées ou raccourcies ; seuls mots nouveaux : « comme convenu » et « pour fixer la date de la visite technique ». Darija à formuler par un locuteur natif : `repondeur` (nouvelle phrase FR), `appel_rappel_convenu`, `appel_planifier_visite`.
- **Bouton « Déléguer mes dossiers » (17/11)** : Reda veut confier ses dossiers à Meryem. (La liste des leads avait déjà « Réassigner » en lot.)
- **Liste froide dans l'ERP, tirée par la commerciale (17/11)** : carte « Liste froide » du cockpit, « selon sa charge » — jamais des étapes datées poussées. Lot et plafond = **10** appels ouverts (« make it 10 »), 2 tentatives par dossier.
- **Nettoyage appliqué en prod le 17/11 sur « oui » de Reda** : liste 1 (réveils aveugles : 48 dossiers, 90 étapes annulées) et liste 2 (441 contacts Odoo froids archivés, étiquette `archive_odoo`, « Restaurer » les rouvre). Liste 3 (37 rebonds à remettre au Froid) NON appliquée : attend son oui ; tant qu'elle ne l'est pas, 42 dossiers de la liste 1 restent vivants sans étape (37 sans responsable, 5 à Meryem). Fiches de test (21) et 101 oppositions : toujours à revoir par Reda.
- **Réponses du 17/11 après l'audit final** : (1) un dossier rouvert dont le client n'a JAMAIS répondu (dé-perdu, opposition levée, archive restaurée, fusion) reçoit « Décider la suite », jamais « Préparer et envoyer le devis » ; (2) « c'est un appel commercial » n'est PAS ajouté aux appels 3 et 5 — pour Reda, un client qui a rempli le formulaire a demandé à être appelé, ce n'est pas un appel commercial ; tranché le même jour : la mention est RETIRÉE de l'appel d'ouverture des leads du formulaire (`appel_ouverture` de base, site et Meta), gardée sur les autres origines, les réveils et la liste froide ; (3) libellés d'étapes renommés (« 2e appel — laisser un message vocal », « Appel de réveil à 1 mois »…) ; (4) les trois anciens guides PDF (Guide, Protocole, Carte : six appels / quatorze jours) sont retirés de la bibliothèque jusqu'à réécriture.
- **Pas de PR ni de push tant qu'un changement de la séance est ouvert**, sauf feu vert explicite (donné le 17/11 pour ce lot).

## Faits mesurés en prod (lecture seule, 17/11) — ne pas re-dériver

- 1 188 leads ; Froid 728 (712 vivants) : 703 sans raison de parcage, 441 sans propriétaire (imports Odoo), 251 Meta, 14 joints ET chiffrés. « Jamais joint dans l'ERP » ≠ jamais appelé (beaucoup l'ont été dans Odoo).
- 549 des 551 leads sans propriétaire viennent de l'import Odoo (`source=odoo_import_test`), qui n'a jamais posé d'`owner`. Tous les leads natifs en ont un.
- 68 leads vivants sans étape ni standby futur (63 imports Odoo, 5 natifs en Nouveau) ; 207 perdus/archivés/opposés encore dans une étape vive ; 108 étapes en retard (52 sur des leads sans propriétaire, 40 sur ceux de Reda, 8 sur ceux de Meryem).
- **101 leads « Ne plus me contacter »**, tous posés en 75 jours par une personne (Meryem 99, Asmaa 2) via la réponse d'une étape ; 74 sur « Préparer et envoyer le devis », surtout après deux réveils sans réponse. Lecture (inférence, Meryem non interrogée) : la réponse servait à faire disparaître une tâche sans objet. Lever un drapeau = geste par lead, sur preuve datée, jamais en lot.
- Les réparations du 01/11 (D-CADV-8/9) n'ont jamais été appliquées : commandes manuelles `--apply`, 0 étiquette `archive_odoo`.
- L'auditeur nocturne tourne (04:15) mais EXCLUT les imports Odoo, n'a ni écran ni API, et ne notifie les admins qu'une fois par violation (445 ouvertes).
- Capacité : Meryem 726 étapes closes en 28 j, Asmaa 159 (≈ 221/semaine) — aucune marge pour travailler la liste froide en volume.

## Étude L3 (liste froide, leads jamais oubliés) — conclusions vérifiées

- Les meilleurs outils (Pipedrive, Close, Sierra, ServiceTitan, Outreach) ne réparent rien automatiquement : une courte liste d'exceptions tenue à zéro + une alerte au manager ; une tâche future ne masque pas un dossier qui stagne ; tout vivier a un propriétaire nommé.
- Aucun taux de réactivation mesuré de façon indépendante par âge de lead (solaire, services à domicile) : les tableaux « aged leads » sont du marketing fournisseur, à ne pas citer.
- Maroc, à ne PAS écrire dans un message : « le prix de l'électricité augmente » (02/04/2026 : hausses non répercutées sur les consommateurs) ; un prix de rachat du surplus pour les ménages (aucun tarif basse tension fixé). Pompage : le guide FDA 2024 porte une aide pilote de 30 % plafonnée à 30 000 DH/projet (remplacement du butane) — ouverture actuelle non établie.
- WhatsApp : l'opt-in doit nommer l'entreprise, y compris pour l'application Business ; un formulaire Meta n'est pas un opt-in documenté (D-CADV-11 inchangée).

## Ordre recommandé (accepté pour l'étape 1 ; le reste attend Reda)

1. Livrer les correctifs du moteur (ce lot). 2. Nettoyage sur listes validées par Reda, AVANT toute attribution (archive des contacts Odoo froids, 207 dossiers morts hors des étapes vives, réveils aveugles, téléphones). 3. Revue des 101 oppositions sur preuve. 4. Passation des dossiers de Reda à Meryem après le nettoyage, étapes re-datées. 5. Une liste du lundi à deux règles (lead vivant sans étape ; étape en retard de plus de 2 jours ouvrés). 6. Appeler seulement les joints-et-chiffrés, avec un élément nouveau. À ne pas construire maintenant : écran de travail de la liste froide, échelles d'escalade, plafonds d'étape, job d'archive à 12 mois.

## Audit final du 17/11 — deux faits vérifiés en prod (les autres constats : rapport de séance)

- Les 5 comptes actifs ont un prénom VIDE (le login porte le prénom). Depuis ACVI54 (« jamais le login dans un message »), toute phrase portant `{conseiller}` est omise : le premier WhatsApp part sans « Bonjour…, je suis … de TAQINOR », le script d'ouverture sans « c'est un appel commercial », la confirmation de visite sans la ligne STOP. Prénoms renseignés en prod le 17/11 (sur « oui » de Reda) et rendu re-vérifié ; un nouveau compte sans prénom rouvre le défaut.
- Gabarits de prod = gabarits du code, sauf l'heure de l'après-devis ordres 1, 2 et 6 (vide en prod → la touche part à l'heure d'envoi du devis au lieu de 9 h 30 / 18 h) : migration de données à écrire.

## Ouvert

- Un code de raison honnête pour le stock jamais travaillé (`parquer_lead` refuse « injoignable » sous 5 appels tracés) : libellé à choisir par Reda.
- Pas encore construit : « Classer le dossier » (perdu + motif) sur chaque étape ; une question propre pour les neuf étapes qui tombent sur « Où en est ce dossier ? » ; l'étape agricole « relevé du point d'eau » qui réutilise la question de la visite.
- Les étapes de message montrent six réponses + « Autre réponse » (cinq annoncées).
- Phrase à trancher : `appel_ouverture_telephone` (« Suite à notre échange au sujet du solaire. » seule est un fragment à l'oral).
