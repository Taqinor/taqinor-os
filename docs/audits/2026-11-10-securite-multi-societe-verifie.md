# Vérifie APFS — contre-visite de mi-parcours du parcours PF1 « sécurité / multi-société », 10/11/2026

Commande `loop audit` (10/11). L'audit de parcours PF1 (08/11, PR #1302) avait déposé APFS1-117 ; 20 tâches constructibles sur 31
sont cochées (64 %) depuis la fusion de la PR #1308 : la contre-visite de mi-parcours est due. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `3a9182b4e`. Branche de claim : `verifie-apfs-1011`.
- **Registre.** PF1 `securite-multi-societe`, groupe APFS, 20 tâches cochées sur 31 constructibles.
- **Échantillon (graine = SHA `3a9182b4e`).** Les 2 P0 cochées (APFS100, APFS101) + 6 tirées = **8 tâches** : APFS28, 43, 46, 60, 62,
  64, 100, 101.
- **Pile locale.** Checkout principal en retard de plus de 6 000 commits : aucune sonde rejouée ; verdicts par lecture des
  commits, du code sur `origin/main` et des tests nommés.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **7** | APFS28, 43, 46, 60, 62, 100, 101 |
| partiel | **1** | APFS64 (la garde d'étanchéité ne lit qu'une partie des vues et son critère est trop large) |
| non-fait / faux / régression | **0** | — |

Tiennent en particulier : les classeurs et les probabilités d'étape fermés au compte portail (APFS100), les réglages de gammes
(APFS101), la lecture bornée au droit du module avec ses octrois explicites (APFS28), le superutilisateur qui ne consent plus pour
une autre société ni pour lui-même (APFS60), la référence d'une autre société rendue comme une référence absente (APFS62), les
documents OCR d'autrui fermés sans le droit sur les prix d'achat (APFS46).

## 2. Tests nommés

Tous présents et comportementaux (code HTTP, message, donnée relue), sauf APFS43, qui teste la permission sur une vue factice
plutôt que par une requête réelle (verdicts exacts). Une assertion existante a été assouplie par APFS62 (« 400 » devenu
« différent de 200 »), compensée par un nouveau test d'égalité stricte avec la réponse d'une référence absente. Aucun test rejoué.

## 3. Sondes (dossier PF1, lues, non rejouées)

Les tâches APFS100, APFS60 et APFS62 annoncent une sonde rejouée comme preuve : aucune ne l'a été (pile locale en retard).

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-APFS-VER1-064 | APFS64 | S3 | la garde d'étanchéité entre sociétés n'ouvre que les fichiers nommés « vues » : 100 fonctions de vue sur 278 vivent dans 44 autres fichiers et ne sont jamais lues (comptage du rédacteur, reproductible) ; son critère accepte tout mot « company » dans n'importe quel appel ; aucune fuite trouvée dans les fichiers ouverts | STATIQUE (lecture) | APFS118, APFS119 |

Aucun écart S1-S2 : ni seconde lentille ni critique (METHODE §C.4).

## 5. Optionnel (non déposé)

- APFS43 : l'inventaire des gardes ignore en silence une vue dont le choix de permission dépend de la méthode HTTP (6 fichiers ;
  aucune n'y cache aujourd'hui la garde « responsable »).
- APFS62 : le correctif des champs « responsable » et « rôles autorisés » est lu dans le code, sans test de comportement.
- APFS46 : le service d'actions de l'assistant décide encore sur le rôle porté par le jeton ; Django reste la vraie porte.
- APFS101 : les comptes internes du test sont d'anciens comptes à rôle simple, pas les rôles système.
- APFS100 : d'autres vues d'analyse restent ouvertes à tout compte connecté ; elles relèvent de l'inventaire APFS1, encore ouvert.
- Acceptation : aucun enregistrement `docs/audits/acceptation/APFS/` ; aucune des huit tâches n'est couverte.

## 6. Couverture et suite

- **Couvert.** 8 tâches sur 20 cochées ; lecture du code, des commits et des tests.
- **Non couvert.** Les 12 autres tâches cochées ; aucune sonde rejouée ; aucun rejeu à deux comptes en direct ; l'exécution du
  test du service FastAPI en CI (APFS46) n'a pas été confirmée.
- **Statut.** Mi-parcours sans écart S1-S2 ; la contre-visite de clôture sera due à 95 %.

## 7. Coût

- 1 vérificateur + 1 rédacteur (opus, effort élevé) ≈ 0,4 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: APFS | pct: 64 | ecarts_s1_s2: 0 -->
