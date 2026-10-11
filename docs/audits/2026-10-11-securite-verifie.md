# Vérifie ASEC — contre-visite de clôture du groupe sécurité (X1), 11/10/2026

Commande `vérifie ASEC` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**49 tâches cochées sur 53** constructibles (**94 %**) ; la contre-visite (proche clôture, ≥ 50 %) est due, première du
groupe. 8ᵉ de la boucle (ordre par nombre de tâches cochées décroissant). Groupe SÉCURITÉ : vérificateurs attentifs à
l'étanchéité multi-société (404 pas 403), à l'auth et au verrou de connexion.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `0030d515b` (re-fetch en début d'itération). Branche de claim : `verifie-asec`.
- **Registre.** X1 `sécurité`, groupe ASEC, tâches réparties sur 13 plans (18 dans `PLAN_AUDIT_SECURITE.md`, reste chez les
  propriétaires des fichiers touchés).
- **Décisions gravées.** D-ASEC : verrou compte+IP ; compte verrouillé = même 401 qu'un faux mot de passe ;
  Commercial/Technicien gardent l'agenda ; Admin Ventes sans `users_gerer` ; prod en settings.prod, CORS par défaut.
- **Inventaire (déterministe).** 53 tâches ASEC, 49 `[x]`.
- **Échantillon (graine = SHA `0030d515b`).** Toutes les P0/S1 cochées (23) + 25 % du reste (6 sur 26). Total :
  **29 tâches** (le plus gros échantillon de la boucle, vu la densité de P0/S1).

## 1. Vérificateurs (29 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **28** | ASEC2, 3, 4, 6, 7, 9, 11, 12, 13, 19, 22, 26, 27, 28, 29, 30, 32, 33, 34, 35, 36, 37, 39, 41, 42, 43, 44, 46 |
| partiel | **1** | ASEC24 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1-S2 : 0.** Pas de critique Fable (réservée aux écarts S1 restants).

Points saillants des tâches jugées ok (étanchéité, auth) :

- **ASEC2/3/4 (gestion des comptes, verrou de connexion).** Garde de rang centralisée (`peut_gerer`) câblée sur tous les
  chemins d'écriture (avatar/reset/update/destroy) ; mot de passe sorti de l'update générique (action dédiée + révocation
  de sessions) ; un mauvais mot de passe lève bien `AuthenticationFailed` ET incrémente le compteur (le verrou FG22 était
  mort), verrou compte+IP, compte verrouillé = même 401. Tests comportementaux via l'URL réelle.
- **ASEC6/7 (étanchéité des FK).** Les FK `Activity.assigned_to`/`activity_type` et `assert_entite_assignable` vérifient
  l'appartenance société AVANT tout retour anticipé ; une référence étrangère = 400/404 « inexistant », jamais 403 ni fuite
  d'identité. ASEC7 fermait une faille S1 réelle (retour `ids is None` avant le contrôle société) — confirmée disparue.

## 2. Tests nommés

- Les 28 tâches jugées ok ont un test nommé **présent et comportemental** (rejeu à deux comptes, 404/400 pas 403, même 401,
  relecture en base). Non rejoués localement (lecture seule, sans pile) : raisonnés par lecture ; vert de la CI de `0030d515b`.

## 3. Sondes

Aucune sonde déposée : l'unique écart (ASEC24) est S3 (test manquant), la garde de sécurité sous-jacente étant saine. Les
clauses d'étanchéité/auth des tâches échantillonnées ont été jugées tenues par lecture du code de production.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Suite |
|---|---|---|---|---|---|
| ASEC54 | C-ASEC-VER-001 | ASEC24 | S3 | test déclaré `test_nombre_de_pages_inchange` jamais écrit (absent), et le test double `download_roof_image` au lieu du MinIO réel prescrit (leçon 5) ; la garde de sécurité `cle_toit_de_la_societe` est saine | tâche v3 déposée (`PLAN_AUDIT_MOTEUR.md`, propriétaire moteur) |

**Constats S1-S2 : 0.** La faille lecteur C-ASEC-008 (clé de toit étrangère) et la faille d'étanchéité C-ASEC-001/ASEC7
sont confirmées CORRIGÉES sur le code réel.

## 5. Optionnel (non déposé)

- Les notes de leçons sur des tâches ok (ASEC22/28/35) sont des observations des vérificateurs sans divergence
  comportementale ; non déposées.
- ASEC2 : la preuve en direct est reportée à ASEC21 (tâche d'acceptation du groupe, encore ouverte).

## 6. Couverture et non-couvert

- **Couvert.** 29 tâches sur 49 cochées (toutes les P0/S1 + 25 %). Commits, tests nommés, code de production.
- **Non couvert.** Les 20 autres tâches cochées ; aucun aller-retour en direct (lecture seule, sans pile).
- **Statut du registre.** Après ce dépôt : 49/53 cochées (94 %), contre-visite **sans écart S1-S2** (1 écart S3 déposé en
  tâche). La clôture stricte (≥ 95 %) et la sortie du cycle (deux contre-visites consécutives à zéro S1-S2) restent dues.

## 7. Coût

- 29 vérificateurs opus (effort élevé) : **≈ 2,50 M de jetons**, 544 appels d'outil, ≈ 39 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 29 verdicts (focus S1), vérification du test ASEC24, rédaction.

<!-- verifie | groupe: ASEC | pct: 94 | ecarts_s1_s2: 0 -->
