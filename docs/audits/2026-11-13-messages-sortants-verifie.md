# Vérifie AMSG — contre-visite de mi-parcours du parcours PF8 « messages sortants », 13/11/2026

Commande `loop audit` (13/11). L'audit de parcours PF8 (11/11) avait déposé les tâches AMSG. Ce compte rendu réunit les
**deux passes du même jour** (la seconde remplace le fichier canonique ; git garde la première) :

- **Première passe (journée)** : contre-visite de mi-parcours, due à 29 tâches cochées sur 38 constructibles. Les 29
  tâches cochées sont relues. Huit écarts S3 déposés (AMSG84-91).
- **Seconde passe (soir)**, lancée **par anticipation, à la demande du fondateur** : les **26 tâches livrées** par la vague
  13 (PR #1377) mais encore bloquées sur leur preuve en direct sont relues de la même façon. Un écart S2 et trois écarts
  S3 déposés (AMSG92-95).

Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** Première passe : `origin/main` = `bbe833192`. Seconde passe : `origin/main` = `d64fa1e4e` (après `git fetch`).
  Branche de claim de la première passe : `verifie-pf-1311`.
- **Registre.** PF8 `messages-sortants`, groupe AMSG, 29 tâches cochées sur 38 constructibles (76 %) au déclenchement.
- **Échantillon, première passe.** Sur précision du fondateur (13/11 : pousser le parallélisme), les **29 tâches cochées**
  sont relues, pas seulement le tirage : AMSG7, 8, 9, 17, 33, 34, 35, 38, 39, 40, 41, 42, 43, 45, 65, 66, 67, 69, 70, 71, 74,
  75, 76, 77, 78, 79, 80, 81, 82. Aucune tâche P0 / S1 n'est cochée.
- **Échantillon, seconde passe.** Les **26 tâches livrées** en attente de preuve en direct : AMSG1, 2, 4, 5, 6, 11, 12, 13,
  14, 15, 16, 27, 28, 29, 31, 32, 37, 56, 57, 58, 59, 60, 61, 63, 64, 68.
- **Méthode.** Lecture des commits, du code sur `origin/main` et des tests nommés ; rejeux hôte ; gardes hôte
  `check_garde_contact.py` et `check_beat_active_companies.py` vertes (première passe). Aucune pile, aucun test Django
  lancé, aucune production consultée. Chaque écart ci-dessous a été relu une seconde fois dans le code avant d'être retenu.

## 1. Vérificateurs

Première passe : 3 lots, opus, effort élevé, frais, même répertoire. Seconde passe : 1 vérificateur frais (opus, effort
élevé) qui n'a pas lu la première passe, puis relecture du rédacteur dans le code.

| Passe | Verdict | Nombre | Tâches |
|---|---|---|---|
| 1 | ok | **23** | AMSG7, 8, 9, 17, 33, 34, 40, 41, 42, 45, 65, 67, 70, 71, 74, 75, 76, 77, 78, 79, 80, 81, 82 |
| 1 | partiel | **5** | AMSG35, 38, 39, 66, 69 |
| 1 | régression | **1** | AMSG43 (latente) |
| 2 | ok | **23** | AMSG1, 2, 4, 5, 6, 11, 12, 13, 14, 15, 16, 27, 28, 29, 31, 32, 37, 56, 59, 60, 61, 63, 64 |
| 2 | partiel | **3** | AMSG57, 58, 68 |
| 1 et 2 | non-fait / faux / déjà-présent | **0** | — |

Toutes ces tâches sont arrivées par la PR #1377 (vague 13, merge queue, contrôles requis verts) ; deux correctifs CI de
la même PR touchent AMSG29 (backend e-mail réel jugé sous l'enveloppe) et AMSG57 (refus en 409).

## 2. Tests nommés

- **Première passe.** Vingt-huit tests nommés sur vingt-neuf existent et sont comportementaux : vraie route ou vraie tâche
  planifiée, état relu en base (journal d'e-mail, notification, échéance d'automatisation, marqueur de rappel) ; les
  simulations ne portent que sur un canal de sortie ou un rendu PDF, jamais sur la règle testée. Le test promis par AMSG38
  (route de la fiche lead sur une version remplacée, devis refusé ou expiré) **n'a jamais été écrit** : seul un ancien test
  de l'envoi par e-mail d'un devis refusé a été réaligné. Le test d'AMSG34 est un test d'écran ; il n'a pas été rejoué ici.
- **Seconde passe.** Les 26 tests nommés existent et sont comportementaux (API réelle ou vraie tâche, état relu, témoin).
  Un trou : AMSG57 n'est vérifié qu'au niveau du service (`assertRaises`) ; ni le code HTTP de `repondre-email` ni
  « première réponse non posée » ne sont vérifiés par un test de route (écart C-AMSG-VER2-104).

## 3. Sondes et preuve en direct

- **Première passe.** Les constats des 29 tâches cochées sont tous STATIQUE : aucune sonde à rejouer.
  - **Rejeu hôte du rappel avant échéance** (AMSG43) : le prédicat de fenêtre, joué jour par jour avec le beat du lundi au
    vendredi, perd des échéances. Délai réglé à 1 jour : les échéances du dimanche et du lundi ne reçoivent plus aucun
    rappel ; à 2 jours : celles du lundi ; à 3 et 5 jours (défaut) : aucune perte. Avant AMSG43 (beat tous les jours) :
    aucune perte. La correction proposée (borne haute = veille du prochain passage + délai) a été rejouée : aucune perte.
  - **Rejeu hôte de la règle d'omission** (AMSG67) : découpage de phrase arabe et retour à la ligne conformes.
- **Seconde passe, sonde nouvelle** `docs/audits/sondes/AMSG/C-AMSG-VER2-101.py` (hôte, sans Django ni réseau), jouée le
  13/11 : **repro: True**. Elle exécute la vraie vue « Mon équipe » (`create`), le vrai `inviter_membre_portail` et le vrai
  `_envoyer_invitation_portail`, avec la vraie chaîne qui décide si l'e-mail part. Clé posée et backend console (la
  production) : l'envoi rend False, `send_mail` n'est pas appelé, la vue répond 201 sans aucune clé qui le dise. Témoin
  avec un backend qui envoie : l'envoi rend True et un e-mail part, ce qui prouve que la chaîne réelle est traversée. Lu
  dans l'écran : `inviter` affiche « Invitation envoyée. » sans lire la réponse.
- **Preuve en direct.** Le même soir, deux rejeux d'acceptation sur runner ont été enregistrés PASS
  (`docs/audits/acceptation/AMSG/2026-11-13-f409ca823.md` et `docs/audits/acceptation/AMSG/2026-11-13-cb69bf89b.md`) : ils
  couvrent 24 des 26 tâches de la seconde passe. AMSG57 et AMSG68 y ont été écartés pour les mêmes défauts que ceux
  retenus ici (409 au lieu du 400 écrit ; erreur seulement en toast). La couverture d'AMSG58 porte sur `provisionner-acces`
  (conforme) ; l'invitation d'équipe n'y était pas rejouée.

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
| C-AMSG-VER2-101 | AMSG58 | **S2** | appelant oublié : `inviter_membre_portail` jette le « non envoyé » ; la vue « Mon équipe » répond 201 sans le dire et l'écran du portail client affiche « Invitation envoyée. » alors que rien ne part (backend console de la prod) ; l'invitation est morte sans que le client le sache | `docs/audits/sondes/AMSG/C-AMSG-VER2-101.py` | AMSG92 |
| C-AMSG-VER2-102 | AMSG58 | S3 | jumeau resté sans tâche : `provisionner-acces` partenaire (côté crm) répond toujours « mot de passe temporaire envoyé par email » sans lire le résultat de l'envoi (API seulement) | lecture | AMSG93 |
| C-AMSG-VER2-103 | AMSG68 | S3 | l'écran Automatisations n'affiche pas le refus sous le champ : `addRule` ne lit que `detail` et dit « Ajout impossible. » ; le motif n'apparaît que dans le toast global (latent : 0 règle) | lecture | AMSG94 |
| C-AMSG-VER2-104 | AMSG57 | S3 | le refus de `repondre-email` sans e-mail opérationnel (409) et la première réponse non posée ne sont vérifiés par aucun test de route | lecture | AMSG95 |

Gravités rejugées.
- Première passe : aucune n'est S1-S2. Pour C-AMSG-VER1-101, le constat d'origine était S3 (lead perdu, un seul en
  production), l'opposition reste bloquée sur cette route et il faut un geste délibéré du vendeur ; S3 maintenu.
- Seconde passe : **C-AMSG-VER2-101 reste S2**. C'est le client lui-même qui lit un faux « envoyée », la production est en
  backend console (cas réel, pas latent) et le collègue invité ne reçoit jamais de lien, puisque le jeton n'est servi
  nulle part. La clause « fini quand » d'AMSG58 est tenue (l'envoi rend False) ; l'écart porte sur l'appelant et l'écran.
  C-AMSG-VER2-102 est S3 : le texte trompeur ne s'adresse qu'à l'administrateur interne, et aucun écran n'appelle cette
  route. La tâche AMSG93 touche le portail et la vue crm : elle va dans le plan transverse, en un seul commit.

## 5. Optionnel (non déposé) et points pour le fondateur

- **Clause d'AMSG57 à réaligner (pas de tâche de code).** La ligne du plan d'AMSG57 dit que `repondre-email` « répond
  400 » ; c'est une erreur d'écriture. Le 409 est voulu : un e-mail non opérationnel est un refus d'état, pas un corps
  invalide (convention ENF11, correctif CI de la PR #1377). L'étape PF8.5-AMSG57 de la spec d'acceptation AMSG (branche
  d'acceptation, pas encore sur `main`) attend aussi 400 et doit passer à 409.
- **AMSG68, pour décision.** Le serveur refuse désormais une règle « Envoyer un email » sans corps même quand la société a
  un modèle d'e-mail enregistré, que l'envoi savait utiliser. C'est conforme au texte de la tâche, mais cela ferme un
  chemin qui marchait. Le brouillon IA du même écran a le même défaut d'affichage (motif lu seulement dans `detail`).
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
- AMSG28, 57, 59, 61 : l'envoi des devis, des identifiants du portail fournisseur et des réponses SAV ignore le nombre de
  messages remis ; sous l'enveloppe, un message entièrement filtré se dit « envoyé ». AMSG56 et AMSG58 le lisent.
- Un même état (« e-mail non opérationnel ») est refusé en 502 sur les devis, en 409 sur les factures et le SAV.
- AMSG57 : le docstring de `repondre_email` dit encore que l'envoi « retombe sur le backend console » et que le fil est
  journalisé dans tous les cas ; la remise du brouillon WhatsApp recopie la création de tâche de l'automatisation.
- AMSG64 : la liste blanche du front garde « à corriger » pour AMSG1 et AMSG2 alors que leurs gardes serveur sont
  livrées ; indexée par fonction, elle ne rougit pas un appel ajouté dans une fonction déjà listée.
- AMSG60 : les téléphones semés ont la forme d'un vrai mobile marocain ; un numéro hors plan serait plus sûr.
- AMSG2, 4, 6 : rôle de test construit à la main (AMSG2) ; ni le journal de destruction du lead (AMSG4) ni l'absence de
  touche après-devis (AMSG6) ne sont vérifiés.

## 6. Couverture et sortie de cycle

- **Couvert.** Première passe : les 29 tâches cochées (code, commits, tests nommés, jumeaux, appelants). Seconde passe :
  les 26 tâches livrées en attente de preuve en direct, même grille, plus une sonde hôte rejouée.
- **Non couvert.** Aucun test Django lancé (la preuve des tests est la CI de `main`) ; aucun rejeu navigateur par cette
  contre-visite (les rejeux d'acceptation du soir sont cités, pas refaits) ; la règle « STOP étendu à toutes les fiches aux
  mêmes coordonnées » dans la garde de contact, lue par AMSG1 et AMSG2, n'a pas été revérifiée ; les tâches encore
  ouvertes (dont l'heure 08:30, AMSG44, AMSG72, AMSG73).
- **Statut.** Un écart S2 (C-AMSG-VER2-101, AMSG92) et onze écarts S3 déposés en tout (AMSG84-91, AMSG93-95). Le groupe
  ne peut pas devenir « vérifié » avant la contre-visite d'AMSG92 une fois cochée ; la contre-visite de clôture reste due
  à 95 %.

## 7. Coût

- Première passe : 3 vérificateurs (opus, effort élevé) ≈ 0,6 M de jetons ; aucun appel Fable.
- Seconde passe : 1 vérificateur (opus, effort élevé) + 1 rédacteur ; jetons non relevés (≈ 0,6 M estimés à 22 k par
  tâche) ; aucun appel Fable.

<!-- verifie | groupe: AMSG | pct: 76 | ecarts_s1_s2: 1 -->
