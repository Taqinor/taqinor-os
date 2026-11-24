# Dossier contractuel — état du chantier L5 (à lire EN PREMIER pour reprendre)

Dernière écriture : 24/11/2026 par la session du poste fixe · branche `claude/erp-lead-contracts-e2fdab`.
**Prochaine action unique** : la PR Taqinor/taqinor-os#1539 est SORTIE de la file de fusion le 25/11 (tête
`350f91e7c8`) : la CI complète de la file (lots de tests, fuzz de l'API — que la CI de la PR ne joue pas) a trouvé
22 rouges dus à ce travail, listés ci-dessous. RIEN n'est mergé ; la fusion automatique est désarmée. Corriger les
cinq causes, pousser, vérifier par `gh workflow` / la file, puis re-mettre en file SUR DEMANDE de Reda. Quota
hebdomadaire à 99 % le 25/11 : reprise après la remise à zéro du 28/11.

### Rouges de la file de fusion (run 45342555496) — à corriger avant toute re-mise en file
1. **Règle n° 4 — une app importe le moteur de devis.** `apps/ventes/tests/test_cal195_schema_unifilaire.py`
   (`test_aucune_app_n_importe_le_moteur_de_devis`) refuse `contrats/rendu/style.py` (import de
   `apps.ventes.quote_engine…theme.font_face_css`) ; même défaut probable pour `rendu/composants.py` (import de
   `quote_engine.logo`). Correctif : ne plus IMPORTER le moteur — lire les fichiers de police par leur chemin (ou les
   poser dans `apps/documents`), et traiter le logo sans `quote_engine.logo` (logo de la société tel quel sur une
   pastille claire de l'en-tête).
2. **Garde de classe des routes de `documents`.** `apps/documents/tests/test_adoc_garde_classe_endpoints.py`
   (`test_toutes_les_routes_documents_portee_et_etat`) : une vingtaine d'écarts — `chantiers/<pk>/contrats/` rend 200
   sur un chantier annulé (409 attendu) ; les routes d'action (`emettre`, `rouvrir`, `signer`, `marquer-signe`) rendent
   405 là où la garde attend 404 ; `modele` rend 403 là où elle attend 404. Lire la garde, puis soit aligner les
   routes (portée → 404 avant méthode et droit ; chantier annulé → 409 ou exception documentée), soit déclarer les
   nouvelles routes dans le registre de la garde avec leur règle.
3. **Montants des tranches (bug réel, introduit par S2-C1).** `test_contrats_dossier.MontantsTests.
   test_montants_acompte_regle` (10 sous-tests, fr et ar, quatre actes) : attendu `16560 / 33120 / 5520`, obtenu
   `16560 / 16560 / 5520` quand l'acompte est réglé ; et `ArticlesGabaritsTests.
   test_paiement_corrige_suit_l_echeancier_de_la_vente` : après passage de la vente à 40 / 50 / 10, la liste imprime
   30 % et 50 %. `tranches_convenues` ne doit PAS dériver des `cible_cumul_ttc` de `plan_facturation` (elles ne sont
   pas cumulatives dans tous les états) : calculer chaque tranche depuis l'échéancier figé du devis
   (`ventes.utils.echeancier.tranches_normalisees` : % ou montant) appliqué au prix convenu, la dernière prenant le
   reste au centime.
4. **Fuzz de l'API — « Response violates schema »** sur les neuf routes (`documents/chantiers/{id}/contrats/` et
   `documents/actes/{id}/…`, GET / PATCH / POST / pdf) : les réponses réelles ne respectent pas les schémas déclarés
   (`serializers_contrats.py` : valeurs nulles, énumérations, chaînes décimales, formes d'erreur 400 / 404 / 409 non
   déclarées, PDF binaire). Rejouer en local : job `api-fuzz-pr` (voir `.github/workflows/ci.yml`).
5. **Hors de ce travail** : `e2e/calepinage-parcours.spec.js:693` (ACAL987) a échoué une fois dans la file
   (délai dépassé sur un onglet du calepinage) — à laisser, sauf s'il se répète.
Leçon de méthode : la CI d'une PR ne joue ni les lots complets ni le fuzz ; avant de mettre une PR à routes neuves en
file, lancer ces jobs à la main ou lire les gardes de classe de l'app (`test_adoc_garde_classe_endpoints`,
`test_cal195…`).

## Demande et cadre
- Demande de Reda, mot pour mot (24/11/2026) : « i want you make ERP create 4 contract for each lead signed was we
  create the chantier, and those 4 contrat will be 1 : starting contract to send first, and contains the payments
  details that are in devis final and that can be changed, and of course contains a mention of our warranties, that
  also we can change. the second contract is the one of materiel delivered, to home, showing the part that need to be
  payed at this stage, and have 2 versions ready one with the remaining and the other that suppose the client payed
  his full 90%. the third is work complete properly that the client should sign after i finish the work, and that my
  lawyer told me i should have to protect myself if they dont pay at the end. and finall the finall contract when i
  get fully payed and that mentions our warenties and also advices on how they should change their consumption
  behaviour. i want you to go l5 in this and produce the best conract in terms of content and specially pretiness. »
- Niveau L5 (nommé par Reda) · régime **MIXTE** lu sur `origin/main@854d2adfe` (promesses servies 1,5 / 6 :
  `docs/contrats/conception.md` § 1).
- Coût : quota hebdomadaire lu à 82 % au départ (Fable 74 %), remise à zéro le 28/11 ; formule L4
  `k = min(3, floor((90 − 82 − 10) / 21)) = 0` → **cette session = tour 0 + construction + vérification finale** ; les
  tours de relecteurs commencent après le 28/11. Mesuré : tour 0 (4 éclaireurs + conception + maquettes réelles) =
  2 points « tous modèles », 4 points Fable.
- Poste mesuré : 8 cœurs, 42 Go de disque libre, pile `erp-agentique` en marche (non touchée), WebKit installé
  (`ms-playwright/webkit-2311`, `-2388`) → 2 lanes d'écriture au plus, 1 agent à navigateur.

## Contrat de sortie (écrit avant tout relecteur ; un seuil se resserre, ne se relâche jamais)
Périmètre fermé : les quatre actes (PDF), l'onglet « Contrats » de la fiche chantier, l'éditeur d'un acte, la
signature sur place. Hors périmètre signalé : signature par lien, version arabe, page publique, fiche lead.
Références nommées : le devis premium (`/proposal`, même famille visuelle), l'ancien procès-verbal de réception
(`document_pv_reception.html`, pour les paires avant / après), les règles de `juridique.md` § Mise en page.

| id | Critère | Seuil | Mesure |
|---|---|---|---|
| K1 | constats S1-S2 ouverts | 0 | registre des tours |
| K2 | tout montant imprimé = celui de la vente (`plan_facturation`, `solde_devis`) | au centime, 4 actes × 2 variantes | test serveur |
| K3 | pagination sur les données de référence | contrat ≤ 7 p., PV ≤ 2 p., clôture ≤ 4 p. | test serveur (rendu réel) |
| K4 | prix d'achat, marge | 0 occurrence dans le contenu et le texte des PDF | test serveur |
| K5 | parcours : acceptation → 5 brouillons → modifier → émettre → signer → PDF signé en GED ; dés-acceptation → annulés ; ré-acceptation → rétablis | 100 % ; L5 : 3 essais verts | tests serveur + spec e2e |
| K6 | envoyer le premier contrat depuis la fiche chantier | ≤ 4 gestes | relecteur |
| K7 | beauté par paires (ancien PV ↔ nouveau ; devis ↔ contrat) | ≥ 4 paires sur 5 préférées ou à égalité, 2 relecteurs aveugles | tours L5 |
| K8 | contraste du texte ; lisibilité en noir et blanc | ≥ 4,5:1 ; aucun état porté par la seule couleur | mesure sur le rendu en niveaux de gris |
| K9 | toute référence de loi citée dans `textes.py` figure dans `juridique.md` § 2 au niveau P | 100 % | test (grep) |
| K10 | les quatre documents existants | fichiers intacts, tests verts | `git diff` de la liste « à ne pas changer » |
| K11 | critique adverse du diff serveur | 0 bloquant (isolation société, perte de données, argent) | avant chaque merge |

## Déroulé
- [x] Tour 0 — éclaireurs (flux chantier et paiements, moteur PDF et écrans, droit marocain, mise en page de
      contrats), conception, contrat d'API, moteur de rendu et textes par défaut, PDF réels tirés et regardés
      (contrat 6 p., PV 2 p., clôture 4 p.). Décision de Reda en cours de route : pas de rétractation à domicile.
- [x] Construction — trois lanes pliées sur la branche (tête `57ce4b8135`) : **serveur** (modèles
      `ActeContractuel` / `ModeleActe`, contenu fr / ar, cycle de vie, récepteurs, API, commande `apercu_actes`,
      tests), **écran** (onglet « Contrats », éditeur par section, signature sur place et sur papier, bascule
      français / arabe), **arabe** (`textes_ar.py`, table de libellés, rendu de droite à gauche ; sortie française
      identique avant / après). Groupe CTC coché dans `docs/PLAN.md`, carte du code et empreintes à jour.
      Exécuté : rendu réel des cinq actes en français (6 / 2 / 2 / 2 / 4 pages) et en arabe (6 / 2 / 2 / 2 / 3),
      `test_contrats_rendu` 5/5 et `test_contrats_arabe` 10/10 dans un conteneur hors réseau, vitest de l'écran
      22/22, gardes hôte `backend-lint-fast` et les huit gardes de `stage-names` rejouées vertes.
      **Écrit mais PAS encore exécuté** : `test_contrats_dossier.py` et `test_contrats_api.py` (base de test
      nécessaire — la CI les joue).
- [ ] CI de la PR #1539 — première tête complète poussée le 24/11 ; rouges à corriger avant la suite.
- [ ] Vérification finale (jamais sautée, rien ne merge sans elle) — (1) un rejeu sur l'écran réel : accepter un
      devis → cinq brouillons → modifier → émettre → signer → PDF signé en GED, en français et en arabe, à 390 px
      et à 1440 px ; (2) une critique adverse neuve du diff serveur `git diff 854d2adfe..HEAD -- backend/`
      (isolation société, argent, perte de données, récepteur d'acceptation) ; (3) une relecture neuve de la
      traduction arabe contre le français (retraduction). Puis le premier merge par la file.
- [ ] Tours de relecteurs (après le 28/11) — fonction / simplicité / beauté × téléphone / bureau, K1 à K11.
- [ ] Seconde vague — signature par lien (cérémonie GED existante), version arabe, raccourci depuis la fiche lead.
- [ ] Étage « vraie vie » — Reda : deploy, un vrai chantier, relecture d'un juriste (`juridique.md` § 4).

## Décisions de Reda (24/11) — recopiées dans `docs/claude-memory/contrats-chantier-decisions.md`
Pas de rétractation à domicile ; date limite 30 jours ; pas de pénalité chiffrée ; signataire nommé ; version arabe
dans cette vague. Choix pris seul : `conception.md` § 8.

## Quota et points de contrôle
| Point | Quota hebdo (tous modèles / Fable) | Décision |
|---|---|---|
| départ | 82 % / 74 % | tour 0 + construction |
| fin du tour 0 (4 éclaireurs, conception, PDF réels) | 84 % / 78 % | lancer les lanes |
| lanes en cours (écran pliée) | 87 % / 82 % | continuer |
| trois lanes pliées, tête poussée | **90 % / 85 %** | **ligne d'arrêt de la méthode atteinte** : état écrit, arrêt ; la suite sur décision de Reda ou après la remise à zéro du 28/11 |

Mesuré (à recaler) : tour 0 ≈ 2 points, construction à trois lanes (deux opus, une sonnet) + orchestration ≈ 6
points. Régime MIXTE annoncé : tenu.

## Instrument de revue (pile privée `ctr`)
Conteneurs `ctr-django` (127.0.0.1:8017), `ctr-redis`, `ctr-minio`, réseau `ctr-net`, base `ctr` dans le Postgres
partagé (créée vide, migration complète lancée le 24/11 — à finir par `migrate` : la migration `documents.0001`
est arrivée après son démarrage). Contrôle du tour 0 : « instrument sur » le 24/11 (seule exception : `GPG_KEY`,
empreinte publique posée par l'image Python). Front compilé une fois (`frontend/dist`), jonction
`frontend/node_modules` posée dans ce worktree (à retirer par `cmd /c rmdir`, jamais `rm -rf`). Scripts :
scratchpad de la session, dossier `instrument/` (`lancer.sh`, `controle.sh`) — à réécrire depuis le gabarit si le
scratchpad a été vidé. **À démonter si la reprise n'est pas immédiate** : `docker rm -f ctr-django ctr-redis
ctr-minio`, `docker network rm ctr-net`, `DROP DATABASE ctr`.

## Où sont les choses
- Spécification : `docs/contrats/conception.md` · droit : `docs/contrats/juridique.md` · contrat d'API :
  `backend/django_core/apps/documents/contract_samples/{dossier_contractuel,acte_contractuel}.json`.
- Tirage des PDF d'exemple (sans base, conteneur jetable, hors réseau) : scripts du tour 0 dans le scratchpad de la
  session — à promouvoir en commande `manage.py` par la lane serveur (`apercu_actes`).

## Revue 1 et contre-vérifications (24-25/11/2026) — détail : `docs/contrats/revue-1.md`
- Cinq relecteurs neufs avant le premier merge (code serveur, écran, contenu français, traduction arabe par
  retraduction, impression de 31 pages) → 4 lanes de correction (S 14 points, T 21, R 11, F 9), toutes pliées.
- Contre-vérification du serveur par un relecteur neuf : 13 points sur 14 « ok », S1 « partiel » (option et
  article dans le même enregistrement) → mécanisme refait par alignement du texte corrigé sur son gabarit
  (lane S2), module `contrats/gabarits.py`.
- Contre-vérification des phrases arabes nouvelles : aucun écart de sens, trois retouches de langue appliquées.
- Premier rejeu sur ÉCRAN RÉEL (pile privée, bureau et 390 px) : dix constats, dont trois S1 que ni les tests ni la
  lecture du code n'avaient vus (échéancier faux quand une facture d'acompte existe, brouillon de quitus trompeur,
  garantie du contrat ignorée au certificat) → corrigés (lanes S2 et F), règles C13 à C17 de `conception.md` § 8.
- CI entièrement verte sur `43cf846595` (dont les tests serveur à base de données) ; tête complète poussée :
  `d6e459643f`.
- Quota hebdomadaire au 25/11 : 97 % tous modèles, 91 % Fable (Reda a dit de continuer au-delà de 90 %).
- Restent pour le tour suivant (non bloquants) : en-tête de l'aperçu dans `InstallationDetail.jsx` (référence du
  chantier à côté de celle de l'acte), liste des cas « peut attendre » des rapports de relecteurs, relecture de
  l'arabe par un arabophone, les douze points de `juridique.md` § 4, signature par lien.

## Contre-vérification sur écran réel et clôture de la session (25/11/2026)
- Second relecteur neuf sur la pile privée (tête `d6e459643f`) : C1, C3, C4, C5, C7 à C10 « ok » ; parcours complet
  rejoué jusqu'au quitus sur un chantier neuf (contrat signé sur place à 390 px, paiements saisis, variante « 90 %
  réglés » émise une fois l'encaissement enregistré, réception signée, quitus émis et lu en français et en arabe :
  somme reçue, tableau des paiements, garanties avec dates de fin, page de conseils). C2 « partiel » (le chapeau du
  brouillon de clôture disait encore « votre installation est payée ») et un constat neuf (réserve de propriété
  décochée au contrat mais affirmée par la livraison et la réception) → corrigés par une dernière lane, couverts par
  des tests (clôture non soldée sans aucune phrase de paiement ; option lue sur le contrat par les trois autres
  actes), NON rejoués sur écran réel (quota).
- `main` fusionné dans la branche (seul conflit : la carte du code). Tête finale `244cf0702f` : 29 tests de rendu et
  d'arabe, 43 tests purs du dossier, 48 tests de l'écran, toutes les gardes hôte vertes.

## Restes (tour 2, aucun n'est bloquant)
- Écran : la case « Réserve de propriété » reste visible sur la livraison et la réception (le serveur l'ignore, la
  valeur vient du contrat) ; l'en-tête de l'aperçu (`InstallationDetail.jsx`) montre la référence du chantier à côté
  de celle de l'acte ; l'éditeur renvoie vers « l'échéancier du devis » alors qu'aucun écran ne modifie l'échéancier
  d'un devis accepté (la route existe) ; nom accessible « Constat N coché » même quand la case est vide.
- Rendu arabe : point final d'une phrase française placé à gauche ; « درهم.، » dans la livraison ; « Paiement » et
  « Virement » laissés en français dans le tableau des paiements du quitus.
- Serveur : `_garde_signature` ne revérifie pas les paiements de la variante « tranche réglée » si un paiement est
  supprimé après l'émission ; date de signature papier antérieure à l'émission acceptée.
- Hors périmètre, vu en passant (ventes) : après une facture d'acompte, le dialogue « Facturer… » propose la tranche
  suivante à « 96,00 MAD » et ne laisse que « Totalité », refusée en 409 ; une facture libre liée au bon de commande
  n'est pas comptée dans « Réglé ».
- Données de démonstration : « Installation » et « Transport » rangés en accessoires par `seed_demo`.
- À faire par Reda : déployer ; saisir son nom et sa qualité dans le modèle du contrat ; faire relire l'arabe par un
  arabophone et les douze points de `juridique.md` § 4 par un juriste avant un usage réel.
