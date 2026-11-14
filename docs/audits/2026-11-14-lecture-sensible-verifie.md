<!-- verifie | groupe: ALEC | pct: 96 | ecarts_s1_s2: 3 -->

# Vérifie ALEC — contre-visite de clôture du parcours PF6 « lecture des données sensibles », 14/11/2026

Commande `vérifie ALEC` (14/11), due au titre de la CLÔTURE : le groupe a franchi 95 % de tâches constructibles cochées.
Deuxième contre-visite du groupe, après celle du 13/11 (deux écarts S2, un S3). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `a12f40f821`. Branche de travail : `verifie-cloture-1411`, à jour de `origin/main`.
- **Registre.** PF6 `lecture-sensible`, groupe ALEC : `audit_registre.py --du` (garde d'acceptation neutralisée, §C.4.5 f)
  compte 31 tâches cochées sur 32 constructibles (96 %), « vérifie dû, clôture ». La seule tâche constructible ouverte est
  ALEC40 (rejeu des sondes par l'orchestrateur). Douze tâches sont « code livré, preuve en direct due » et ne comptent pas :
  ALEC5, 6, 16, 18, 22, 23, 24, 28, 29, 41, 42, 43.
- **Cochées depuis le 13/11.** 24 tâches : les 23 tâches livrées que la contre-visite du 13/11 avait relues (ALEC1, 2, 3, 4,
  7 à 15, 19, 20, 21, 25, 26, 27, 36 à 39), cochées depuis sur leurs enregistrements d'acceptation, et ALEC44 (tâche d'écart
  du 13/11).
- **Échantillon.** Pas de tirage : relecture complète de ALEC44 ; des 7 tâches cochées jamais relues (ALEC17, ALEC30 à
  ALEC35) ; des trois tâches d'écart S2 du 13/11 (ALEC41, 42, 43), code livré, pour dire si les écarts d'origine sont
  fermés (§C.4.6) ; recherche de régression sur les 23 tâches déjà relues (fichiers produits modifiés depuis `d64fa1e4e4`).
- **Méthode.** Lecture des commits, du code de la branche, des tests nommés, des appelants et des jumeaux ; codes des rôles
  livrés lus dans le registre exécuté hors Django. Sondes du dossier rejouées sur l'hôte. Aucune pile, aucun conteneur,
  aucune base, aucun test Django ou FastAPI lancé, aucune production consultée.

## 1. Vérificateurs (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **10** | ALEC17, 30, 31, 33, 34, 35, 41, 42, 43, 44 |
| partiel | **1** | ALEC32 (S3, jumeau des leads non traité) |
| non-fait / faux / régression / déjà-présent | **0** | — |
| sans régression (déjà relues le 13/11) | **23** | ALEC1, 2, 3, 4, 7 à 15, 19, 20, 21, 25, 26, 27, 36 à 39 |

- **ALEC41 — fermé.** Les cinq tables rejoignent la liste des tables à propriétaire. Le test nommé prend les codes du
  Commercial et du Directeur dans le registre livré ; le mutant « retirer `ventes_lignefacture` » le fait échouer.
- **ALEC42 — fermé.** Les deux lectures passent de « tout rôle interne » au droit du module GED. Le test nommé joue le
  Commercial terrain livré sur les quatre routes (refus) contre le Commercial et le Directeur.
- **ALEC43 — fermé.** Une aide unique lit `can_view_client_pii` ; les deux rendus remettent à `null` e-mail, téléphone,
  adresse IP et navigateur (clés gardées), le détail imbriqué passe le contexte. Le test joue l'Admin RH livré et relit la base.
- **ALEC44 — ok.** Deux comptes aux codes du Commercial livré (portée « soi ») ; le mutant « retirer `scope_queryset` » est tué.
- **ALEC17, 30, 31, 33, 34, 35 — ok.** Code et tests conformes au texte ; les deux réponses de facture sans contexte
  signalées par ALEC33 passent maintenant la requête ; aucune route d'appel de `FactureSerializer` sans contexte ne reste.
- **ALEC32 — partiel.** La recherche des clients retire e-mail, téléphone et CIN sans le droit aux coordonnées ; la clause
  « Jumeaux » de la tâche nommait la recherche des leads (`LeadViewSet`, `search_fields` avec e-mail et téléphone), restée
  sur le filtre de recherche standard (constat 203).
- **Régression.** Les fichiers produits des 23 tâches modifiés depuis `d64fa1e4e4` ont été relus : droits d'écriture des
  entrepôts (ADRG41), réglage du négoce (ADRG38), à-faire des leads archivés (ASUP59), notifications GED (ACEL62 à 64),
  moteur natif du copilote (COP-B5, COP-B6). Le moteur natif reprend la lecture gardée et les droits de l'appelant
  (`_outils_sql`, `_droits_sql`) : aucune garde d'ALEC15 ou d'ALEC16 contournée.

## 2. Tests nommés

Les tests nommés des 11 tâches relues existent et sont comportementaux : vrais appels HTTP, rôles pris dans le registre
livré (Commercial, Commercial terrain, Admin RH, Directeur, Technicien), relecture de la base quand la tâche le demande.
ALEC42 tolère un code autre que 403 sur `pdf-signe/` pour les rôles autorisés (aucun PDF signé dans le jeu), ce qui suffit
au refus du module. Aucun test ALEC affaibli par un correctif de CI depuis le 13/11.

## 3. Sondes et preuve en direct

- **Sonde nouvelle 201, reproduit (`repro: true`).** Elle exécute le vrai corps de la garde module et portée de l'assistant
  SQL (parseur bouchonné, sqlglot absent de l'hôte) avec les codes réels : `SELECT phone_key, crm_lead_id FROM
  adsengine_metaleadmirror` passe pour le Commercial (portée « soi »), le Commercial terrain, l'Admin RH et l'Admin Ventes,
  alors que le témoin `crm_client` est refusé « portée » au Commercial et « module » au Commercial terrain. La garde des
  données personnelles ne connaît que `crm_client` ; `normalize_phone` exécutée rend le numéro entier (`661028028`).
  Aucun écran ne sert `phone_key`.
- **Sondes du 13/11.** La sonde 101 ne reproduit plus (ALEC41). La sonde 102 plante sur l'hôte depuis ATST13
  (`_role_grants_write` importe `authentication.permissions` par son nom) ; rejouée sans modification avec un bouchon de ce
  module : ne reproduit plus (Commercial terrain refusé sur les trois lectures ; son critère « `to_representation` cite
  `pii` » est périmé, le masque passant par `voit_les_coordonnees`, lu directement).
- **Sondes du dossier PF6.** Ne reproduisent plus : 004, 006, 011, 013, 014 ; avec le même bouchon : 005, 009, 018, 019,
  021, 022, 023, 024. La sonde 003 affiche encore « reproduit » : faux positif relu sur le code d'aujourd'hui (la liste
  sans cible exclut toute cible non déclarée hors palier administrateur, `pieces_visibles`, ce que le bouchon ignore).
  Plantent : 001, 002, 007, 008, 010, 012 (extraction) ; 016, 017, 020, 025 (même avec le bouchon).
- **Preuve en direct.** Pas rejouée ici (aucune pile). ALEC41, 42 et 43 restent « preuve en direct due ».

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ALEC-VER2-201 | ALEC16, ALEC41 | S2 | l'assistant SQL sert `phone_key` (numéro du lead Meta en clair) et `crm_lead_id` de toute la société : un Commercial à portée « soi » lit les numéros des leads des autres, un Commercial terrain ou un Admin RH sans droit aux coordonnées aussi | `docs/audits/sondes/ALEC/C-ALEC-VER2-201.py` | ALEC45 |
| C-ALEC-VER2-202 | ALEC16 | S3 | la garde du droit du module ignore le préfixe `adsengine_` : Commercial terrain, Admin RH et Admin Ventes, sans `adsengine_view`, lisent dépenses et budgets publicitaires | `docs/audits/sondes/ALEC/C-ALEC-VER2-201.py` (champ `insightsnapshot`) | ALEC46 |
| C-ALEC-VER2-203 | ALEC32 | S3 | la recherche des leads interroge encore e-mail et téléphone pour un rôle sans `client_pii_voir` (aucun rôle livré n'a `crm_voir` sans ce droit) | STATIQUE (lecture de `LeadViewSet`) | ALEC47 |

Écarts S1-S2 comptés au marqueur : 1 nouveau (201) et 2 d'origine dont les tâches ne sont pas cochées (C-ALEC-VER1-101,
ALEC41 ; C-ALEC-VER1-102, ALEC42 et ALEC43), fermés dans le code mais en attente de leur preuve en direct (§C.4.6).

## 5. Optionnel (non déposé)

- Le PDF signé (`pdf-signe/`) garde, dans sa page de preuve, les coordonnées des signataires ; il est réservé depuis ALEC42
  au droit GED et constitue la pièce légale : hors ALEC43.
- L'assistant SQL sert aussi à tout rôle `authentication_customuser` (noms et e-mails des collègues, secrets exclus) :
  annuaire interne, hors données client.
- Le journal des modifications d'un ticket SAV peut encore porter d'anciennes valeurs de `cout` (aucun écrivain depuis ASEC34).
- Rafraîchir les sondes du dossier PF6 qui plantent (bouchon `authentication.permissions` depuis ATST13) et la sonde 003
  (faux positif).

## 6. Couverture et sortie de cycle

- **Couvert.** ALEC44 et les 7 tâches cochées jamais relues ; contre-visite des trois tâches d'écart S2 ; recherche de
  régression sur les 23 tâches relues le 13/11 ; jumeaux de l'assistant SQL, des signatures, de la recherche et du coût SAV.
- **Non couvert.** Les tâches « code livré, preuve en direct due » ALEC5, 6, 22, 23, 24, 28, 29 (relecture complète non
  faite ; leurs sondes 004, 024 ne reproduisent plus) ; aucun test Django, FastAPI ou front lancé (preuve des tests = CI de
  `main`) ; aucun rejeu navigateur ; le comportement réel de sqlglot sur la requête de la sonde 201 n'est pas exécuté
  (garde des colonnes relue sur ses constantes).
- **Statut.** Un écart S2 nouveau et deux écarts S2 d'origine non encore cochés : le groupe reste « construit ». Le
  prochain `vérifie` contre-visite ALEC41 à ALEC47 une fois cochées.

## 7. Coût

- 1 vérificateur (opus, effort élevé) et 1 rédacteur ; aucun appel Fable.
