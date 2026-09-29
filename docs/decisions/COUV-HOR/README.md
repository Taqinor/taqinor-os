# COUV-HOR — donut de couverture fausse, repli 1,20 MAD/kWh, et audit QA (29–30/09/2026)

Dossier de passation : tout ce qui a été trouvé, décidé, livré et corrigé en prod,
plus ce qui reste ouvert. Lisible depuis n'importe quel poste / compte Claude
(`git pull`, puis ce fichier).

---

## 1. L'incident

- **Signalé par le fondateur** sur DEV-202609-0113 (Khalid, Mohammedia) : page 1 du PDF,
  « **28 % couverture** » à côté de « **−37 %** sur votre facture ». Réalité : **37 %**.
- **Cause 1 — la donut recalculait** `production × taux ÷ etude_params.conso_annuelle`
  (`residential/renderer.py`, `synthese_economies`) au lieu de lire la couverture que le
  moteur horaire avait déjà calculée (`etude_horaire.annuel.couverture_*` = 0,3705).
- **Cause 2 — `conso_annuelle` valait factures ÷ 1,20 MAD/kWh.** Le lead n'avait pas de
  distributeur (depuis CAD167 le SRM est déduit de la ville **côté serveur seulement**),
  `autoQuote.js` passait `undefined` à `consoAnnuelleDepuisFactures` → `resolveTranches` sans
  table → prix plat `FALLBACK_KWH_PRICE` 1,20. 198 000 MAD ÷ 1,20 = 165 000 kWh au lieu de
  123 024 kWh (moteur horaire).
- **Cause 3 — l'écran réécrivait la valeur fausse** à chaque réouverture (`?edit=`) : la conso
  stockée revenait en « kWh tapés », passait avant la dérivation des factures, et était
  estampillée `'onee'` (dérive ×12 en plus : 110 000 → 110 004).
- **Ampleur en prod (29/09)** : 134 devis résidentiels avec une donut ≠ moteur horaire
  (38 envoyés), depuis ~20/08. 11 devis envoyés imprimaient aussi une « facture actuelle »
  ~40 % trop haute (modèle « factures » alimenté par la conso ÷ 1,20).

## 2. Livré — PR Taqinor/taqinor-os#738 (mergée le 30/09, commit `62542682`)

| Commit | Contenu |
|---|---|
| `f834e376` | La donut lit le moteur horaire (pricing → builder → renderer), clés `couverture_*` publiées seulement pour une colonne chiffrée à l'heure (empreinte PDF des autres devis inchangée) ; `couverture_avec` masquée côté public si `avec_ok` faux ; conso résidentielle du devis auto au barème national. |
| `df9e1e1b` | `DevisGenerator` : une conso stockée qui descend des factures (barème ou ÷ 1,20) est re-dérivée ; une vraie saisie repart exacte ; distributeur estampillé seulement s'il est choisi, déjà stocké, ou a servi au calcul. `solar.consoDescendDesFactures`. |
| `a8aeb16c` | Miroir CAD167 : `solar.resolveTranches` et `pricing._table_tarifaire` résolvent un distributeur NOMMÉ (SRM, « autre ») sur la grille nationale ; sans distributeur, le repli étiqueté reste (`test_cad167`). Grille société appliquée à tout distributeur ; libellé SRM/Amendis/national au lieu de « saisi pour ce devis ». |
| `b5e7f95e`, `e0878fca` | Garde PACT159 (formulation de commentaires) et empreinte CODEMAP. |

Tests ajoutés, tous vérifiés **en échec sur l'ancien code** : `test_quote_engine_builder`
(`test_couv_hor_*`), `test_cad167_distributeur_srm`, `DevisGeneratorConsoRouverte.test.jsx`
(écran réel rendu en édition), `autoQuote.balayageCI.test.jsx`, `autoQuote.facturesReelles.test.mjs`
(exécute désormais le vrai bloc, plus une copie), `solar.test.mjs`.

## 3. Décisions du fondateur (29–30/09)

1. **Garder le moteur horaire** comme source ; plus jamais 1,20 MAD/kWh quand le tarif est connu.
2. **Balayage C&I du devis auto : « conso seulement »** — la conso suit le barème national,
   le MODÈLE d'économie reste celui d'avant. Mesuré sur les 61 leads C&I de prod : 0 devis ne
   change. La « bascule complète » (modèle deux-factures à 60 % d'autoconso) aurait fait passer
   le lead 42 de 135 à 125 kWc et plafonné les gros C&I vers 125 kWc. **Question ouverte** :
   le modèle « factures » applique `AUTOCONSO_SANS` = 0,60 (résidentiel) et ignore les 80 %
   de consommation diurne C&I.
3. **Réparer les données de prod** sur tous les devis touchés, y compris envoyés, et fournir
   la liste des envoyés dont les chiffres changent (pour renvoi).

## 4. Actions en prod (via Django, jamais SQL ; statut, lignes, totaux intouchés)

- **DEV-202609-0113** (29/09) : `conso_annuelle` 165 000 → 123 024 via
  `domain.etude_schema.ecrire`, PDF régénéré (`cle_pdf_a_jour`) → donut **37 %**, prix et
  économies identiques (seule `conso_annuelle_kwh` changeait dans les données du PDF).
- **128 devis** (30/09, après merge) : 84 brouillons, 35 envoyés, 9 expirés ; `conso_annuelle`
  ← consommation du moteur horaire (5 sans bloc : inversion serveur `serie_kwh_depuis_mad`).
  Re-scan : **0** devis restant avec la signature ÷ 1,20. Aucun devis accepté touché.
  Les PDF stockés se régénèrent au prochain téléchargement/envoi (PVFRESH).
- **Les 12 devis ENVOYÉS dont les chiffres imprimés ont changé — à renvoyer aux clients :**

| Devis | Conso (kWh/an) | Facture actuelle (MAD/an) | Économie sans batterie | Économie option 2 | Payback sans / option 2 (ans) | Tarif retenu |
|---|---|---|---|---|---|---|
| DEV-202609-0055 | 13 000 → 8 731 | 22 425 → **15 612** | 6 265 → **7 712** | 17 392 → **15 133** | 7,1 → **5,8** / 5,1 → **5,9** | 1,5958 |
| DEV-202609-0062 | 15 000 → 10 228 | 25 616 → **18 001** | 7 308 → **8 768** | 11 264 → **13 368** | 5,8 → **4,8** / 5,2 → **4,4** | 1,5958 |
| DEV-202609-0063 | 15 000 → 10 228 | 25 616 → **18 001** | 6 265 → **6 384** | 10 221 → **11 655** | 6,4 → **6,3** / 5,5 → **4,8** | 1,5958 |
| DEV-202609-0068 | 14 000 → 9 475 | 24 020 → **16 799** | 7 215 → **8 665** | 11 158 → **13 339** | 6,7 → **5,5** / 6,5 → **5,4** | 1,5958 |
| DEV-202609-0071 | 22 500 → 15 867 | 37 585 → **27 000** | 10 441 | 19 398 → **21 625** | 5,3 / 5,2 → **4,6** | 1,5958 |
| DEV-202609-0077 | 20 500 → 14 363 | 34 393 → **24 600** | 10 440 → **10 441** | 22 386 → **23 776** | 5,3 / 5,2 → **4,9** | 1,5958 |
| DEV-202609-0087 | 8 007 → 5 592 | — | 5 354 | 7 336 | 4,2 / 7,3 | 1,5958 → **1,3817** |
| DEV-202609-0088 | 12 000 → 7 972 | 20 829 → **14 401** | 6 265 → **7 702** | 11 680 → **12 271** | 7,1 → **5,8** / 5,9 → **5,6** | 1,5958 |
| DEV-202609-0098 | 12 500 → 8 356 | 21 627 → **15 014** | 5 220 → **6 672** | 11 687 → **12 208** | 6,9 → **5,4** / 4,7 → **4,5** | 1,5958 |
| DEV-202609-0107 | 20 000 → 13 987 | 33 595 → **24 000** | 8 352 | 18 353 → **20 536** | 5,3 / 5,3 → **4,8** | 1,5958 |
| DEV-202609-0109 | 15 000 → 10 228 | 25 616 → **18 001** | 6 265 → **6 384** | 11 264 → **13 368** | 6,2 → **6,0** / 5,1 → **4,3** | 1,5958 |
| DEV-202609-0111 | 26 000 → 18 499 | 43 170 → **31 200** | 14 467 | 26 303 → **28 314** | 4,7 / 4,9 → **4,5** | 1,5958 |

Les 23 autres devis envoyés corrigés ne changent que la donut.

## 5. Ouvert

- [ ] **Renvoyer les 12 devis ci-dessus** aux clients (fondateur).
- [ ] **Bug trouvé par l'audit, NON corrigé par #738** — `apps/ventes/domain/etudes.py`
  `rafraichir_etude_horaire_devis` (~206-225) compte les panneaux des DEUX variantes : sur un
  devis à deux options de tailles différentes, l'étude horaire est calculée pour
  kWc_sans + kWc_avec (DEV-202609-0055 : 10,65 = 4,26 + 6,39), le moteur la rejette
  (garde 2 %) et retombe en silence sur les modèles « factures »/« estimation ».
  **60 blocs sur 145 en prod (15 devis envoyés).** Lancé dans une session séparée le 30/09
  (tâche « Fix hourly study kWc summed across both options ») ; ensuite recalculer les blocs
  périmés (commande dry-run d'abord, accord fondateur).
- [ ] Question C&I 60 % / 80 % (§3.2).
- [ ] Résidu connu : l'écran inverse les factures en énergie seule (`kwhFromBill`), le moteur
  horaire en facture complète (`bareme.kwh_depuis_facture_mad`) — ~1 % d'écart (122 007 vs
  123 024 kWh). Sans effet sur la donut depuis #738.

## 6. Audit QA — peut-on détecter ce type d'erreur automatiquement ? OUI.

**Constat.** Toute la QA actuelle (≈100 gardes `scripts/check_*.py`, 134 contrats, snapshots
PDF, explorateur QA, error-autopilot, Sentry) vérifie des **déclarations** (code contre code,
clés, types, chemins d'écriture) ou des **plantages**. Un chiffre faux mais plausible n'en
déclenche aucune.

**Comment les 30 bugs de la même famille (10/07 → 29/09) ont été trouvés :**
9 (30 %) par le fondateur sur un vrai devis ; 18 (60 %) par des audits IA ponctuels demandés ;
3 (10 %) par de l'automatisation permanente, toutes dans les 48 dernières heures ;
**0 par la CI**, **0 par la supervision prod**.

**Pourquoi celui-ci a échappé.** Chaque test vérifiait un maillon isolé avec des entrées
choisies à la main — jamais deux sources de la même consommation en même temps. Le test
autoQuote rejouait une COPIE du code (et était exempté de la garde anti-copie), avec le cas
exact « lead sans distributeur » qui n'assertait que `conso > 0` ; deux tests épinglaient
÷ 1,20 comme comportement voulu ; PVCOV comparait PDF et page web qui appellent la même
fonction (verts même si elle est fausse).

**Prototype d'auditeur exécuté en lecture seule sur la prod** (310 devis en **15 s**, code
d'avant #738) — `docs/decisions/COUV-HOR/auditeur_coherence_prototype.py` :

| Règle | Signalés | Remarque |
|---|---|---|
| I4 conso stockée = factures réelles ÷ 1,20 (±12 kWh) | 129 (35 envoyés) | ~0 faux positif, aucune génération de PDF requise |
| I2 donut vs « −N % » (gros comptes en tranche haute : ils doivent être proches) | 35 / 40 contrôlables | physique pure, indépendant du moteur |
| I5 « facture actuelle » imprimée vs somme des vraies factures (±10 %) | 60 (11 envoyés) | le document se contredit lui-même |
| I7 bloc horaire calculé pour un autre kWc (repli silencieux) | 60 (15 envoyés) | → bug §5 |
| I10 total du graphe mensuel vs économie de la carte option | 18 (3 envoyés) | deux chiffres de la même page |
| I1 donut vs couverture du moteur | 80 | devient une garde de non-régression après #738 |
| I3 conso stockée vs conso moteur (±10 %) | 125 | bruyant tant que le résidu JS ~1 % existe |
| I11 « −N % » page 1 vs bloc méthode | 97 | NE PAS utiliser : compare deux options différentes |

**Recommandations, par valeur :**
1. **(M) Auditeur nocturne lecture seule** sur la prod (`apps/ventes/coherence/regles.py` +
   commande `audit_coherence_devis` + tâche beat), alerte seulement sur les NOUVELLES
   violations. Règles indépendantes à privilégier : I4, I2, I5, I7, I10.
2. **(S) Étendre l'e2e existant** `frontend/e2e/devis.spec.js` (il crée déjà un lead sans
   distributeur à chaque PR) : comparer donut / −N % / facture entre écran, PDF et proposition.
3. **(M) Contrôle au rendu** : en prod, journaliser + estampiller `pdf_render_meta` ; bloquer
   l'ENVOI (pas la génération) ; en test, échouer (`COHERENCE_STRICT`).
4. **(M) Pas de repli silencieux** : une valeur estimée garde un drapeau de qualité en
   stockage (`etude_params['_qualite']`), + garde CI sur l'écriture de valeurs issues d'un repli.
5. **(M) Tests de propriétés** (Hypothesis, déjà épinglé) sur `build_quote_data` avec leads
   générés (sans distributeur, facture d'hiver seule, bloc périmé, options divergentes).
6. (M) Parité énergie : comparer, pour un même lead, la conso dérivée par l'écran et celle du
   moteur horaire — PAS fonction JS contre fonction Python (les deux font ÷ 1,20 sans distributeur).
7. (L) Rejouer un corpus anonymisé de vrais devis sur les PR du moteur (jamais dans git, loi 09-08).
8. (S) Explorateur QA + `seed_demo` capables d'atteindre ce chemin ; (S) error-autopilot
   réellement planifié ; (M) signal nocturne PDF/visuel exploitable ; (S) mutation testing
   sur les maths imprimées (indicatif).

**Correctifs rapides relevés par l'audit (rapportés par les agents, à vérifier) :**
Sentry apparemment **non armé en prod** (DSN vide, module absent du conteneur) ;
error-autopilot **sans planification** (n'a pas tourné pendant toute la fenêtre du bug) ;
alerte hebdo `controle_integrite` envoyée à 7 personnes, lue 3 fois sur 75 ;
nuit PDF/visuel rouge 39 nuits sur 40 ; retirer `autoQuote.facturesReelles.test.mjs` de la
liste blanche de `check_tests_source_regex.py` (il exécute désormais le vrai code).

**À ne pas faire :** compter sur les snapshots pixel (28 % vs 37 % passe sous le seuil de 2 %) ;
écrire des tests de parité entre surfaces qui appellent la même fonction ; épingler un repli
comme « comportement voulu » sans prouver que le drapeau d'estimation survit jusqu'à
l'impression ; faire planter la génération PDF en prod ; laisser l'auditeur écrire/réparer ;
envoyer les alertes dans un canal que personne ne lit.

**Réserves du critique :** « aurait sonné dès le 21/08 » est estimé sur les données
d'aujourd'hui (pas un vrai rejeu historique) ; les comptages mêlent deux bugs (donut et bloc
horaire périmé) ; la précision « ~0 faux positif » n'a pas été vérifiée sur un échantillon relu.

## 7. Reprendre depuis un autre poste

- Code : `git pull` ; tout le correctif est sur `main` (#738).
- Lecture prod (accord fondateur, lecture seule) : un script Python, puis
  `scp -i ~/.ssh/taqinor_hetzner <script> root@178.105.192.116:/tmp/` et
  `docker exec erp-agentique-django_core-1 sh -c "python manage.py shell < /tmp/<script>"`,
  toujours dans `transaction.atomic()` + `set_rollback(True)`. La clé SSH n'est pas dans le dépôt.
- Auditeur : `docs/decisions/COUV-HOR/auditeur_coherence_prototype.py` (même procédure ;
  ~15 s pour 310 devis ; sortie `AUDIT_JSON`).
- Déploiement : Claude s'arrête au merge (CLAUDE.md) ; l'auto-deploy du serveur suit.
