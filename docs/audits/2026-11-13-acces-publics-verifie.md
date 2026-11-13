# Vérifie APUB — contre-visite de mi-parcours du parcours PF5 « accès publics », 13/11/2026

Commande `loop audit` (13/11). L'audit de parcours PF5 (11/11, PR #1363) avait déposé les tâches APUB. Première contre-visite
du groupe, due à mi-parcours (18 tâches cochées sur 24 constructibles). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `bbe833192`. Branche de claim : `verifie-pf-1311`.
- **Registre.** PF5 `acces-publics`, groupe APUB, 18 tâches cochées sur 24 constructibles (75 %).
- **Échantillon.** Sur précision du fondateur (13/11 : pousser le parallélisme), les **18 tâches cochées** sont relues, pas
  seulement le tirage de 8 : APUB2 (la seule P0), 30, 31, 32, 34, 36, 37, 38, 42, 43, 47, 48, 50, 51, 53, 56, 70, 72.
- **Méthode.** Lecture des commits, du code sur `origin/main` et des tests nommés ; sondes hôte rejouées. Aucune pile, aucun
  test Django lancé, aucune production consultée.

## 1. Vérificateurs (2 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **18** | APUB2, 30, 31, 32, 34, 36, 37, 38, 42, 43, 47, 48, 50, 51, 53, 56, 70, 72 |
| partiel / non-fait / faux / régression / déjà-présent | **0** | — |

## 2. Tests nommés

Les dix-huit tests nommés existent et sont comportementaux : vrais appels HTTP, état relu en base, aucune simulation de la
règle testée (seul le stockage de fichiers est simulé dans le test d'APUB47). Le correctif de CI d'APUB53 n'affaiblit pas son
test. Pour APUB2, c'est l'assertion « le lien n'est plus actif » qui attraperait un retrait du correctif ; le 404 final du
même test ne prouve rien, le fichier étant absent du stockage simulé (voir §5).

## 3. Sondes et preuve en direct

- **APUB2 (P0).** Preuve hôte rejouée sur les vrais corps de fonction : avant la coupure le téléchargement rend 200 ; un
  Commercial responsable reçoit 403 sans écriture ; un Directeur coupe le lien (deux fois, même résultat) ; après la coupure
  404 ; autre société 404.
- **Sonde 037 du dossier PF5.** Telle quelle, elle plante sur l'arbre actuel (un import déplacé par APUB70). Rejouée par un
  harnais qui laisse la sonde inchangée : ne reproduit plus (jeton refusé, accès au compte fermé dans les trois états).
- **Sonde 001 du dossier PF5.** Elle affiche encore « reproduit » : faux positif sur sa partie historique (elle ne voit pas
  la garde posée dans la vue de l'historique, tâche APUB1 hors de cette contre-visite) ; sa partie stockage ne reproduit plus.
- Les sondes 003, 005, 008 et 010 du dossier plantent à l'extraction depuis les correctifs ; elles couvrent d'autres tâches.
- **Preuve en direct.** Les dix-huit tâches sont « API seulement » : aucune n'est due. Il n'existe pas d'enregistrement
  d'acceptation du groupe.

## 4. Écarts retenus

Aucun sur les tâches cochées.

## 5. Optionnel (non déposé)

- Rafraîchir les sondes 001, 003, 005, 008, 010 et 037 du dossier PF5, qui ne tournent plus telles quelles.
- Le 404 final du test d'APUB2 ne prouve rien ; durcissement possible.
- APUB31 compte une consultation avant de refuser une facture brouillon ou annulée.
- APUB37 ne plafonne pas une durée finie mais énorme.
- Les webhooks du CRM lisent encore le premier saut de l'en-tête d'adresse relayée (lecteur historique gelé par sa garde).
- Les deux routes d'APUB51 partagent le même seau de limitation de débit.
- Un commentaire périmé des réglages de base parle encore de l'ancienne garde administrateur.
- Le point « non vérifié » d'APUB48 (collecteur de production) n'a pas été vérifié ici.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 18 tâches cochées : code, commits, tests nommés, jumeaux, appelants.
- **Non couvert.** Aucun test Django lancé (la preuve des tests est la CI de `main`) ; aucun rejeu navigateur ; les 6 tâches
  ouvertes, dont APUB1.
- **Statut.** Zéro écart S1-S2 sur les tâches cochées. La contre-visite de clôture reste due à 95 %.

## 7. Coût

- 2 vérificateurs (opus, effort élevé) ≈ 0,4 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: APUB | pct: 75 | ecarts_s1_s2: 0 -->
