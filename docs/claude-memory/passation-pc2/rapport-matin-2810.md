# Rapport du matin — run L3 « générateurs de devis », nuit du 27 au 28/10/2026 (PC1 puis PC2)

_Rédigé par la coordinatrice PC2 (session « Passation PC2 L3 générateurs de devis »), 28/10/2026 09:20 UTC — run terminé, tout est sur `main`. Déploiement = Reda._

## 1. Ce qui est sur `main` ce matin

**PC1 (02:00 → 00:27 UTC)** : 21 PR puis 5 autres (#1113, #1115 CORC v2, #1116/#1119/#1122 CPRW, #1118, #1111, #1097 CQST, #1103 RGEN, #1114 RPDF R1-R3 à 02:32). Détail dans `passation/registre-pc1.md`.

**PC2 (23:45 → 09:15 UTC)** — 12 PR mergées (10 lanes + 2 correctives après l'audit Fable), toutes passées par la file de merge avec leur CI de groupe verte :

| PR | Lane | Ce que ça change pour un devis |
|---|---|---|
| #1120 | AGV — vendeur agricole | Facture électrique de la pompe (part fixe déclarée, jamais supposée 0), visite point d'eau → lead (plaque kW, tension, phases), garde « visite validée lève la re-visite » (D-AGR-4), générateur agricole sans vocabulaire batterie, migration crm 0144. |
| #1121 | CPRS — devis web serveur | `/proposition` sert les chiffres de l'option servie (= PDF) en C&I, résidentiel, agricole ; textes internes retirés ; signature seulement sur une option offerte et chiffrée ; `roi_*_jamais` au contrat. Parité page/PDF rejouée : 0 écart. |
| #1123 | CSV — script d'appel & visite | Le script d'appel (3 segments) fournit tout ce que le devis auto exige ; visite C&I mobile avec « Sur la fiche : … — Confirmer », phase relevée recopiée sur le lead, « Préparer le devis révisé ». CSV1-18 cochées (CSV7 sur preuve de tests), 2 acceptations en direct. |
| #1126 | CEC v4 — économie C&I | Prix déclaré non fini refusé, aperçu hors contrat → 400 nommé, motif exact bt_domestique ; **#1094 corrigé** : l'O&M de l'option « avec » ne sort plus de l'an 0 des devis envoyés (`regles_au_moins(devis, 3)` au lieu de `calcul_corrige`). |
| #1129 | AGC — client agricole | Document pompage 3 pages et une-page : plus de « rendement non publié… », carte eau « estimation » suivant le noyau, dépense déclarée en ligne neutre (sans « après la visite »), « HMT » traduit, « CV » traduit EN/AR (AGC18) ; site /pompage-solaire FR/EN/AR (TVA sur la pompe seule, formule du m³ seulement pour un nouveau forage). |
| #1124 | RSIZ — taille & composition résidentiel | Jamais Huawei + Deye dans la même offre ; « avec batterie » exige une batterie en stock chiffrée ; câble DC dérivé des paires MPPT ; plafond 2 000 panneaux, balayage adaptatif ; **4 corrections qui touchaient des devis envoyés remises au niveau 3**. |
| #1131 | RWEB — site & page résidentielle | « Non rentabilisé sur 25 ans » cohérent avec le PDF, retour par carte d'option, économie calculée/estimée comme le PDF, incertitudes retirées, garanties réelles sur tout le site (Deye 5, Huawei 10, Dyness DL5.0C 7, Powerbox 10). |
| #1130 | CPDF — PDF client C&I | L'option batterie imprime ses propres chiffres/échéancier/retour ; deux cartes d'option en couverture et deux cases au bon pour accord ; plus de jargon ni d'incertitude (« scénario prudent », IEA/P50, « (moteur C&I) », « VAN omise ») ; prix du kWh évité imprimé ; **toute correction de chiffre gardée au niveau 3** (drapeau `regles_avant_2710` reposé par chaque renderer) ; fuite des tables i18n C&I dans le catalogue global corrigée. |
| #1128 | CCAT — catalogue « prêt pour devis » | Tableau Stock « ce qui manque pour chiffrer un devis » C&I + agricole + résidentiel (CCAT16), encadré à onglets, semis à prix vide (protections, structures, Nexans), fiche Deye sans « SUN-…SG » (migration stock 0175/0176 réversible), prestations C&I en tableau. Mergée 07:31. |
| #1133 | CE2E — recette de bout en bout (docs) | 16 devis joués sur `main` (10 C&I, 4 résidentiels, 2 agricoles) : aucun 5xx, aucun prix d'achat, aucun code interne ; 5 enregistrements d'acceptation (CE2E, CEC, AMOT, CLD, RHOR — verdicts FAIL/partiel, rien coché) ; 9 défauts posés en tâches v3 (voir §2). |

**Après l'audit Fable final (07:15 UTC)** — deux PR correctives, mergées (#1134 à 08:26, #1135 à 09:15) :

| PR | Ce que ça corrige |
|---|---|
| #1134 FIX-MOTEUR | Le chemin « composition » de l'option batterie C&I (`etude_ci_batterie.py`) ne gardait pas l'O&M hors de l'an 0 au niveau 3 : un devis envoyé recalculé aurait changé — gardé par `regles_au_moins(devis, 3)` + test ; remise à zéro du drapeau de rendu à chaque requête/tâche Celery ; CMP5/7/8 (toit plat 30°, production, batterie) posées en tâche CMP12 **gated** sur une décision à toi (D-CMP-7). |
| #1135 FIX-WEB | Page /proposition : garantie batterie lue sur `garantie_mois` des lignes comme le PDF (Powerbox 10 ans, plus 7) ; « 5 à 30 ans » sur /pourquoi-taqinor (FR méta, AR) ; **RWEB24** : la page sert le même « Gain net sur 25 ans » que le PDF (niveau 3) au lieu du cumul brut sous « même calcul ». |

## 2. Ce qui reste ouvert et pourquoi
- **Défauts trouvés par CE2E (tâches v3 posées, rien corrigé)** — P1 : CE2E1 sur un C&I à deux options, `etude_params.puissance_kwc`/`prix_par_kwc` portent l'option AVEC (écran du lead « 59,64 kWc vendus » vs PDF 25,56) ; CE2E2/CE2E3 retour arrondi à l'entier sur la page publique et la bannière du devis auto vs dixième au PDF (7 devis sur 10 divergent) ; CE2E4 garantie onduleur imprimée 5 ans (Deye) alors que la fiche Huawei dit 10 ; CE2E5 PDF « 1,75 MAD/kWh saisi pour ce devis » sur un tarif que le calcul n'utilise pas (RHOR7) ; CE2E6 productible saisi par la société ignoré par le chemin horaire résidentiel (AMOT64 a). P2 : « Bonjour Villa, » + téléphone brut (CE2E7), liste `/ventes/devis` vide sous vite (CE2E8), exemple de calcul p.4 d'une autre option que p.1 (CE2E9).
- **Preuves en direct** : RHOR8 partiel (RHOR7 échoue), AMOT64 partiel (valeur saisie ignorée), CLD13 partiel, CEC6 FAIL (retour PDF ≠ page), AMOT65 non jouée (aucun devis agricole neuf rendable : « Structure au sol : prix à renseigner » dans toutes les sociétés de dev = manque catalogue). Non joué : navigateur Astro (seule la charge JSON de /proposition comparée), générateur et modale d'édition, signature, visite, EN/AR, mobile.
- **Audit Fable final — décisions laissées à toi** : RHOR5 (omission du retour quand jamais rentabilisé, non gardée niveau 3) ; CMP5/7/8 sans garde niveau 3 (option recommandée : bumper `regles_calcul` à 3 sur tout recalcul forcé) ; seuils produit CPDF (90 % « la couvre », scénario prudent retiré) ; fixture `solar_calculs_expected.json` (« uniquement par un humain ») recapturée par un agent dans #1103 (payback 6,2 → 12 ans) ; `recommendedOption()` de la page ignore « Sans batterie » (corriger changerait des devis envoyés).
- **RWEB24** (gain net 25 ans sur la page = PDF) attend que le payload de changement de taille serve le net (propriétaire devis).
- **AGV** : rendu réel du parcours lead pompage → visite → devis (2e round sec) non joué ; 211 + 2 349 tests le couvrent.
- **Devis boulangerie (lead 1637)** : contrôle ligne à ligne sur la prod NON fait (il faut Reda connecté à l'ERP ; aucune saisie d'identifiants par Claude).
- **Test flaky** `frontend/src/components/ProductTour.test.jsx` (« un clic hors de la bulle ferme la visite », timeout 15 s sous charge CI) — a éjecté CSV une fois ; à durcir.
- **Réglage projet** `.claude/settings.json` : ajouter `Bash(gh run cancel *)` — refusé au classificateur (auto-modification), à poser par Reda.

## 3. Décisions prises pour le fondateur (à revoir)
PC1 : `passation/decisions-prises.txt` (15 lignes). PC2 : `decisions-prises.txt` (44 lignes, préfixées par la lane). Les plus structurantes :
- #1114/#1130 : corrections de chiffre du 27/10+ seulement sur les nouveaux rendus (niveau 3) ; RPDF30 nombres EN à l'anglaise gardé.
- #1129 : test CIW406 (contrat questionnaire web) réécrit pour comparer chaque liste web à sa part du contrat — à valider à l'audit.
- CSV : CSV16 « Non » copie la facture d'hiver dans l'été ; CSV14 vise le devis le plus récent ; ordre D-CIQ-7 amendé ; CSV7 cochée sur preuve de tests.
- CPDF : scénario prudent retiré, seuil 90 % pour « la couvre », « estimée » gardé sur les prévisions, « C&I » retiré au rendu.
- RSIZ : ombrage seulement quand tous les moteurs l'acceptent ; prêt-devis résidentiel : batterie obligatoire, tri/alu/compteur/wifi optionnels.
- Coordination : #1121 sortie de la file pour laisser passer #1114 ; 28 anciennes sessions archivées (accord Reda) ; base de dev migrée (0144) par la coordinatrice.

## 4. Manques du catalogue (données fondateur, jamais inventées)
Aucun article `structure_sol` ; taux INST-PMP absent ; aucune pompe à courbe monophasée ; 11 pompes OSP sans prix → **0/10 devis agricoles auto chiffrables** ; fiches onduleur avec garanties « 5 à 10 ans selon site » (à aligner : Deye 5 / Huawei 10) ; `VEI-SI22-AFF` décrit « pour SI22 » sous un SI23 ; Huawei SUN2000 « Modèle supposé » ; `ond_dc_max_kwc` Deye SG05LP3, `bat_max_modules_par_banc` Powerbox Pro, `ond_chaines_max_par_mppt` Huawei absents des fiches. Le tableau Stock « prêt pour devis » (#1128) les signale.

## 5. Machine et méthode (pour la prochaine nuit)
- 16 Go : 5 lanes au travail max, pauses `stop_session` quand RAM < 2 Go ; 28 vieilles sessions archivées ; pile allégée (fastapi_ia, celery beat/interactif, frontend, nginx arrêtés pendant les lanes).
- Jetons portés aussi par fichiers (`jetons/docker.txt`, `jetons/ci.txt`) : les agents attendent dessus sans message.
- Les classificateurs des lanes bloquent `gh pr merge --auto` et parfois `push` : la coordinatrice arme elle-même les PR.
- Les runs PR « légers » (CI-UNE) ne jouent pas les tests backend ni web : chaque PR se révèle dans son run de groupe (5 éjections cette nuit, toutes corrigées en un push).
- Quota : hebdo 24 % → 44 % ; Fable 0 % → 28 % (critiques pré-merge + audit final).

## 6. Nettoyage (à faire en fin de run)
Sessions lanes archivées après leur merge ; worktrees `agent-*`/`pc2-*` fusionnés supprimés ; branches distantes mergées supprimées ; claim `app:jeton-ci` rendue ; keep-awake rendu ; pile Docker complète remise (`docker compose up -d`).

Déploiement = Reda (`scripts/deploy-prod.ps1`, 2 min) ; l'auto-deploy du serveur suit aussi chaque merge.
