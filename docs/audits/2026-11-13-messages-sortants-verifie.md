# Vérifie AMSG — contre-visite de mi-parcours du parcours PF8 « messages sortants », 13/11/2026

Commande `loop audit` (13/11). L'audit de parcours PF8 (11/11) avait déposé les tâches AMSG. Première contre-visite du
groupe, due à mi-parcours (29 tâches cochées sur 38 constructibles). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `bbe833192`. Branche de claim : `verifie-pf-1311`.
- **Registre.** PF8 `messages-sortants`, groupe AMSG, 29 tâches cochées sur 38 constructibles (76 %).
- **Échantillon.** Sur précision du fondateur (13/11 : pousser le parallélisme), les **29 tâches cochées** sont relues, pas
  seulement le tirage : AMSG7, 8, 9, 17, 33, 34, 35, 38, 39, 40, 41, 42, 43, 45, 65, 66, 67, 69, 70, 71, 74, 75, 76, 77, 78,
  79, 80, 81, 82. Aucune tâche P0 / S1 n'est cochée.
- **Méthode.** Lecture des commits, du code sur `origin/main` et des tests nommés ; deux rejeux hôte ; gardes hôte
  `check_garde_contact.py` et `check_beat_active_companies.py` vertes. Aucune pile, aucun test Django lancé, aucune
  production consultée. Chaque écart ci-dessous a été relu une seconde fois dans le code avant d'être retenu.

## 1. Vérificateurs (3 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **23** | AMSG7, 8, 9, 17, 33, 34, 40, 41, 42, 45, 65, 67, 70, 71, 74, 75, 76, 77, 78, 79, 80, 81, 82 |
| partiel | **5** | AMSG35, 38, 39, 66, 69 |
| régression | **1** | AMSG43 (latente) |
| non-fait / faux / déjà-présent | **0** | — |

Toutes les tâches cochées sont arrivées par la PR #1377 (vague 13, merge queue, contrôles requis verts).

## 2. Tests nommés

Vingt-huit tests nommés sur vingt-neuf existent et sont comportementaux : vraie route ou vraie tâche planifiée, état relu
en base (journal d'e-mail, notification, échéance d'automatisation, marqueur de rappel) ; les simulations ne portent que
sur un canal de sortie ou un rendu PDF, jamais sur la règle testée. Le test promis par AMSG38 (route de la fiche lead sur
une version remplacée, devis refusé ou expiré) **n'a jamais été écrit** : seul un ancien test de l'envoi par e-mail d'un
devis refusé a été réaligné. Le test d'AMSG34 est un test d'écran ; il n'a pas été rejoué ici.

## 3. Sondes et preuve en direct

- Les constats des 29 tâches cochées sont tous STATIQUE : aucune sonde à rejouer. Les douze sondes du dossier PF8 couvrent
  des tâches encore bloquées sur leur preuve en direct (code livré le 12/11), hors de cette contre-visite.
- **Rejeu hôte du rappel avant échéance** (AMSG43) : le prédicat de fenêtre, joué jour par jour avec le beat du lundi au
  vendredi, perd des échéances. Délai réglé à 1 jour : les échéances du dimanche et du lundi ne reçoivent plus aucun
  rappel ; à 2 jours : celles du lundi ; à 3 et 5 jours (défaut) : aucune perte. Avant AMSG43 (beat tous les jours) : aucune
  perte. La correction proposée (borne haute = veille du prochain passage + délai) a été rejouée : aucune perte.
- **Rejeu hôte de la règle d'omission** (AMSG67) : découpage de phrase arabe et retour à la ligne conformes.
- **Preuve en direct.** Toutes les tâches cochées sont « latent » ou « API seulement » ; la tâche d'acceptation du groupe
  reste ouverte et aucun enregistrement d'acceptation AMSG n'existe.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AMSG-VER1-101 | AMSG35 | S3 | depuis la fiche lead, l'aperçu WhatsApp d'un devis de lead perdu ou archivé rend le lien et le message ; l'écran ouvre WhatsApp avant que l'enregistrement réponde 409 (l'opposé reste bloqué) | lecture | AMSG84 |
| C-AMSG-VER1-102 | AMSG38 | S3 | test promis jamais écrit ; l'aperçu WhatsApp côté ventes d'une version remplacée, d'un devis refusé ou expiré rend encore 200 avec le lien (API seulement) | lecture | AMSG85 |
| C-AMSG-VER1-103 | AMSG39 | S3 | le brouillon de relance de devis vise le téléphone de la fiche client, pas le contact du lead fixé par AMSG33 | lecture | AMSG86 |
| C-AMSG-VER1-104 | AMSG39 | S3 | le journal de la relance de devis écrit encore le numéro du client et le texte qui lui est destiné, lien compris | lecture | AMSG87 |
| C-AMSG-VER1-105 | AMSG43 | S3 | régression latente : avec le beat limité aux jours de semaine, un délai de rappel réglé à 1 ou 2 jours perd les échéances du dimanche et du lundi ; AMSG44 (heure 08:30) ne le couvre pas | rejeu hôte | AMSG88 |
| C-AMSG-VER1-106 | AMSG66 | S3 | Paramètres › E-mails propose un corps modifiable pour « Rappel de RDV (J-1) » que l'envoi ne lit jamais (seul le sujet l'est) | lecture | AMSG89 |
| C-AMSG-VER1-107 | AMSG69 | S3 | jumeau oublié côté SAV : lien client du ticket, étiquettes publiques et QR d'équipement bâtis sur l'hôte de l'employé (latent) | lecture | AMSG90 |
| C-AMSG-VER1-108 | AMSG77 | S3 | une boucle d'automatisation envoie à l'adresse de chaque élément sans lire le registre d'opposition ; AMSG3 ne couvre que les fiches lead (latent : 0 règle) | lecture | AMSG91 |

Gravités rejugées : aucune n'est S1-S2. Pour C-AMSG-VER1-101, le constat d'origine était S3 (lead perdu, un seul en
production), l'opposition reste bloquée sur cette route et il faut un geste délibéré du vendeur ; S3 maintenu. Aucune
sonde nouvelle n'est donc due.

## 5. Optionnel (non déposé)

- AMSG8 : une assertion du test dit encore qu'une demande de rappel lève l'opposition ; APUB39 (ouverte) la réalignera.
- AMSG9 : l'alerte « lead Meta sans premier contact » ne filtre pas les opposés ; aucun appelant aujourd'hui.
- AMSG33 : un WhatsApp de lead non normalisable ne retombe pas sur le téléphone valide du client.
- AMSG39 : le test n'affirme pas le nom de la société dans le texte.
- AMSG40 : le test appelle le journal fournisseur directement, pas l'action du bon de commande.
- AMSG45 : le code de signature est annoncé « envoyé » même quand l'enveloppe d'e-mail écarte le destinataire.
- AMSG69 : un second constructeur local de lien public subsiste dans le PDF d'intervention (servi au client lui-même).
- AMSG77 : un e-mail vers l'adresse d'un élément porte la mention d'opposition du lead déclencheur.
- AMSG80 : la ligne d'envoi de rapport garde un motif générique ; un e-mail de confirmation d'abonnement reste en échec
  silencieux ; le journal d'échec écrit l'adresse de l'abonné.
- AMSG81 : la notification au signataire suivant reste marquée « notifiée » sans lire le résultat de l'envoi.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 29 tâches cochées : code, commits, tests nommés, jumeaux, appelants.
- **Non couvert.** Aucun test Django lancé (la preuve des tests est la CI de `main`) ; aucun rejeu navigateur ; les tâches
  bloquées sur leur preuve en direct et les tâches ouvertes (dont l'heure 08:30, AMSG44, AMSG72, AMSG73).
- **Statut.** Zéro écart S1-S2 sur les tâches cochées ; huit écarts S3 déposés (AMSG84-91). La contre-visite de clôture
  reste due à 95 %.

## 7. Coût

- 3 vérificateurs (opus, effort élevé) ≈ 0,6 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: AMSG | pct: 76 | ecarts_s1_s2: 0 -->
