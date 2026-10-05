# Audit J6 « documents » — dossier d'évaluation (L2, 05/10/2026)

Unité **J6** du registre (`docs/audits/unites.yml`), groupe **ADOC**, niveau **L2** (défaut du registre ;
auto-pick go-deep confirmé : sortie client — portail, PDF de chantier, page publique — et multi-société,
mais ni moteur de devis ni chaîne argent possédés ⇒ L2, pas L3). Claim : branche `audit-J6` (`47dfd46c6`).
Méthode : `docs/audits/METHODE.md` v2. Sorties brutes (cartes, constats bruts, verdicts, JSON du run live) :
scratchpad de la session — seuls la commande, le SHA et un extrait court figurent ici.

## 0. Préconditions (phase 0)

- **SHA.** Lecture à `origin/main` `7e325e0ae` (05/10/2026). Pile locale : la checkout principale
  `C:\dev\taqinor-os` sur `main` `7e325e0ae` (montée dans `erp-agentique-django_core-1`).
- **Propriété.** `docs/ownership.yml` existe et PRIME : J6 = `apps/documents/**`, `apps/portail/**`,
  `ventes/selectors_portail.py`, `templates/pdf/document_*`, `api/{documents,ged,portail}Api*`,
  `features/{ged,portail}/**`, `pages/ged/**`, résiduel `apps/ged/**`. **`apps/web/src/pages/suivi/**`
  n'est PAS à J6** (propriétaire `web` → `docs/WEB_PLAN.md`) alors que `unites.yml` le revendique encore :
  le registre est corrigé dans cette PR (§9).
- **Apps parquées.** `python scripts/check_parked_apps.py` → « OK — aucune référence vers les 47 apps
  parquées ».
- **Dédoublonnage** : voir §4 (scout haiku, résultat au scratchpad `doc/dedupe.md`).

## 1. Charte (phase 1)

- **Système et frontière.** Possédé (ownership.yml) ci-dessus. `perimetre_lu` : sélecteurs lus par le
  portail (ventes, ged, installations, crm, sav, stock) ; couture `document_produit` (ventes / calepinage →
  `ged/receivers.py`) ; endpoint public `GET /api/django/ventes/suivi/<token>/` (QX34, J1b) consommé par la
  page `apps/web` `suivi/[token].astro` (propriétaire web). Contrats : `apps/portail/contract_samples/`
  (13 échantillons). Apps parquées exclues.
- **Objet.** Objectifs fondateur 1 (tout se corrige après coup), 2 (une fonction par geste), 3 (code
  propre), 4 (le client voit le bon chiffre). Contrat J6 (METHODE §D.6) : le client voit TOUJOURS la
  version en vigueur (« mis à jour le … »), rien hors de son périmètre (NTPRT14), même CGV que le PDF.
- **Personas réelles** (`roles/models.py` `CANONICAL_SYSTEM_ROLES`) : Administrateur, Commercial,
  Technicien responsable ; **client portail** (`ComptePortail`), partenaire et fournisseur portail
  (comptes externes). Aucun compte portail n'est seedé : le run live en crée un en local (couverture
  déclarée en §4).
- **Niveau** L2 ; **jeu de données** `demo` (société démo) + second locataire (C5).
- **Critères retenus** : C1, C2, C3, C4, C5, C6, C8, C9, C10, C11 (règle #4 : un devis montré au portail
  passe par `/proposal`), C13 ; C7 limité à « montant portail = montant facture/devis ». **Non retenus** :
  C12 (hors rejeu live), C14 (unité X6).
- **Sous-domaine** : support (GED, portail) ⇒ L2.
- **Étapes (identifiants stables).**
  P1 GED interne — P1.1 dépôt / classement (dossiers, tags, règles) · P1.2 versions et remplacement ·
  P1.3 navigateur / recherche · P1.4 ACL, partages, coffres · P1.5 approbation · P1.6 rétention, legal
  hold, corbeille, destruction · P1.7 numérisation / OCR / lots · P1.8 modèles de documents, tampons.
  P2 Signature et dépôt public — P2.1 demande de signature · P2.2 page publique (OTP) · P2.3 multi-
  signataires / champs · P2.4 dépôt public.
  P3 Documents de chantier (`apps/documents`) — P3.1 PV de réception · P3.2 bon de livraison · P3.3
  dossier de remise · P3.4 attestation.
  P4 Couture documents produits → GED — P4.1 `document_produit` (facture, calepinage) → classement ·
  P4.2 version en vigueur côté GED.
  P5 Portail client — P5.1 provisionnement / invitation / mot de passe · P5.2 tableau de bord · P5.3 mes
  devis (+ acceptation) · P5.4 mes factures (+ paiement) · P5.5 mes chantiers / jalons / photos · P5.6 mes
  documents · P5.7 livraisons / preuve · P5.8 demandes SAV / fil · P5.9 équipe · P5.10 export, recherche,
  consommation.
  P6 Portails externes — P6.1 partenaire (soumissions, commissions, ressources) · P6.2 fournisseur (BCF,
  factures, candidature, performance).
  P7 Administration portail (écrans ERP) — comptes, acceptations, paiements, documents client, jalons,
  demandes de ticket.
  P8 Suivi public — P8.1 `suivi/[token]` ← `ventes/suivi/<token>/`.
- **Non-objectifs.** Intérieur du moteur `/proposal` (D2/X4) ; PDF facture legacy (J5) ; studio toiture
  et livrables calepinage (D3, déjà audité) ; apps parquées.

## 2. Spécification (phase 2)

**Scénarios H×H (joués en direct à L2)** — stimulus → réponse → mesure :
S-A version en vigueur : un devis/facture déjà visible au portail est corrigé côté ERP → le portail et le
document téléchargé montrent la nouvelle version et sa date (parité écran ERP = JSON portail = PDF).
S-B étanchéité : client portail A demande les objets du client B (même société) et d'une autre société
(identifiants substitués) → 404, jamais 403 ni donnée. S-C `prix_achat` / marge jamais dans un JSON
portail, une page à jeton ou un PDF de chantier. S-D GED aller-retour : déposer → renommer / reclasser /
nouvelle version → rouvrir ⇒ identique, chatter old→new. S-E signature publique : demande → OTP → signé →
document final versionné, lien rejoué refusé. S-F document de chantier (PV / BL) régénéré après correction
du chantier ⇒ reflète la correction. S-G suivi public : jeton valide / révoqué / d'une autre société.

**Saisie → consommateurs.**

| Saisie | Écrite par | Lue par |
|---|---|---|
| fichier / version GED | navigateur GED, `document_produit`, dépôt public, signature | navigateur, recherche, portail « mes documents », partages, rétention |
| document client portail (`DocumentClientPortail`) | admin portail | portail client |
| devis / facture / BC (ventes) | ventes | portail mes devis / factures (via `selectors_portail`), PDF |
| jalons chantier portail | admin portail / installations | portail mes chantiers, suivi public |
| identité client (nom, e-mail) | crm / ventes | compte portail, invitation, PDF chantier |
| CGV (`parametres`) | paramètres | PDF devis, portail (acceptation) |

**Chaîne documentaire 1:N.** client 1-N comptes portail ; devis 1-N révisions (V2) → portail montre la
version en vigueur ; facture 1-N paiements portail ; chantier 1-N jalons / photos / PV / BL ; document GED
1-N versions ; demande de signature 1-N signataires.

**Seuils.** S1-S2 ⇒ tâche ; S3 ⇒ tâche si effort ≤ M ; S4, style, durcissement hypothétique ⇒ liste
OPTIONNELLE. Chiffre client / multi-société : toujours correctness, CONFIRMÉ seulement sur preuve exécutée.

**Détecteurs prévus (4-a).** `check_parked_apps`, `check_services_appeles`, `check_ecrans_atteignables`,
`rapport_backend_sombre`, `check_api_shapes`, `check_api_contract`, `check_openapi_shapes`,
`check_tests_source_regex`, `check_invariants`, `core/event_coverage.py` (abonnés/émetteurs ged/portail),
`lint-imports`, `makemigrations --check --dry-run` (conteneur), `audit_coherence` (aucune règle J6 attendue).

**Décisions fondateur (AskUserQuestion, 05/10/2026), gravées pour le groupe ADOC.**
D-ADOC-1 : brancher les six surfaces portail servies sans écran (mes documents, demandes SAV, mon équipe,
contrats de maintenance, consommation, recherche / export) — jamais les retirer. D-ADOC-2 : un document
client régénéré = NOUVELLE VERSION du même document GED, historique gardé ; le portail montre la version en
vigueur avec sa date. D-ADOC-3 : source unique de l'avancement client = jalons synchronisés du chantier
(CHT11) ; la saisie manuelle devient une correction tracée ; le suivi public lit la même source. D-ADOC-4 : à
l'acceptation, le lien public de suivi est prolongé jusqu'à réception du chantier + 90 jours, révocable.

## 3. Plan des lanes (phase 3)

| Ronde | Lanes (modèle / effort) | Travail |
|---|---|---|
| Scouts | détecteurs, dédoublonnage (haiku / low) | `doc/detecteurs.txt`, `doc/dedupe.md` |
| R2 | 9 lanes : GEDCYC cycle de vie GED (sonnet/medium) · GEDACC accès et conservation (opus/high) · SIGN signature et dépôt public (opus/high) · CHANT documents de chantier (sonnet/medium) · COUTURE `document_produit` → GED (sonnet/medium) · PCLIENT portail client (opus/high) · PEXT portails externes + administration (opus/high) · PFRONT écrans portail (sonnet/medium) · SUIVI suivi public (sonnet/medium) | 113 constats jugés + 32 optionnels |
| R3 | réfuteurs frais opus/high : 2 lentilles (code ; frères + déjà-corrigé) sur S1/S2, 1 lentille sur S3 — 151 verdicts | 2 réfutés |
| Porte empirique | 9 rédacteurs de sondes (sonnet/medium) ; exécution par l'orchestrateur seul, chaque sonde dans une transaction ANNULÉE (`docker exec … manage.py shell`) + 23 commandes grep front | 63 sondes, 60 reproduites |
| Live | orchestrateur : Playwright (portail client) + 3 sondes HTTP (étanchéité, confinement, documents chantier) | §4 |
| Tâches | 3 rédacteurs (opus/high), relecture bloquante de l'orchestrateur contre §C.2 | groupe ADOC |

Fable : **aucun appel** (lot L2 sans moteur ni argent possédé ; la revue opus + la porte empirique suffisent,
CLAUDE.md « a small batch … does NOT get a Fable pass » appliqué par analogie).

## 4. Manifeste de couverture (phase 4)

- **Lanes R2 (9).** Fichiers lus / non lus par lane au scratchpad (`doc/wf1.json`, champs `lus` / `non_lus`).
  Principaux non lus : `ged/services.py` 2656-4130 (signature, lu par SIGN seulement) et 6090-6149 ;
  `ged/views.py` 2080-2480 en diagonale par GEDCYC (couvert par GEDACC) ; tests des apps lus par noms ;
  `portail/branding.py`, `portail/pdf_commissions.py` ; `templates/pdf/bon_livraison.html` (ZSTK4) ;
  `ventes/public/lecture_views.py`.
- **Détecteurs exécutés** à `7e325e0ae`, tous verts : `check_parked_apps`, `check_services_appeles` (474
  fonctions, 166 dettes gelées), `check_ecrans_atteignables` (540 écrans, 10 dettes), `check_api_shapes` (303
  endpoints + 424 ressources ; **aucun** contrat J6 hors des 13 échantillons portail), `check_api_contract`
  (1 956 appels résolus), `check_openapi_shapes`, `check_tests_source_regex`, `check_invariants` (19),
  `lint-imports` (17 contrats tenus), `makemigrations --check` ged/portail/documents (aucun changement).
  `rapport_backend_sombre.py` (non bloquant) : 879 ressources, **264 « sans écran par oubli »** dont les six
  surfaces portail de C-ADOC-050. Tous verts alors que 60 défauts se reproduisent : aucune garde n'attrape
  ces classes (d'où les gardes M3).
- **Non exécutés** : `tests/test_tenant_sweep.py` (DB de test hors porte orchestrateur ; C5 couvert par les
  sondes inter-sociétés), `audit_coherence` (aucune règle J6 : la commande ne couvre que ventes/crm),
  `scripts/audit_couplage.py` (n'existe pas), calibration des réfuteurs (§7).
- **Run live (orchestrateur, pile locale `7e325e0ae`).** Compte portail client provisionné en local
  (`client-294`, société 2) + client B (même société) + client C (société 6). Sondes : 13 endpoints × 3
  comptes, aucune clé interne (`prix_achat`, marge, notes) dans les JSON ; IDOR A → B et A → C = 404 sur 6
  détails ; compte portail sur 6 endpoints internes = 403 ; documents de chantier société 6 depuis société 2 =
  404 ; GED société 6 depuis société 2 = 404 sur 17 actions (sonde #GEDX, contrôle positif OK). Playwright :
  connexion → tableau de bord → devis (`/proposal` 200, PDF 362 Ko, « Document mis à jour le » affiché) →
  chantiers (détail, jalons, photos) → factures. Capture
  `docs/qa-explorer/captures/2026-10-05/adoc-portail-accueil.jpg`. Incident d'environnement : gunicorn local
  bloqué (504 partout, autre session lourde sur la machine) → redémarrage du seul conteneur web + nginx.
  **Non joués** : portails fournisseur / partenaire en écran (bloqués par C-ADOC-061), page publique de
  signature et `apps/web` suivi en écran (non servie par le nginx local), rejeu indépendant Chrome DevTools
  (les candidats live sont prouvés par sonde HTTP rejouable).
- **Migration en attente** sur la pile locale (`adsengine`, autre session) : non appliquée, hors J6.

## 5. Registre des constats (phase 4 → 6)

145 constats bruts (113 jugés + 32 optionnels) → 66 constats par cause racine. Format §C.1 complet au scratchpad (`doc/constats_final.json` : ouvreur, preuve exécutée, verdicts). « Confiance » = résultat de la sonde exécutée (porte empirique) ; PLAUSIBLE = l'oracle est le test rouge de la tâche. Priorité fixée par l'orchestrateur : S1 confirmé P0, S2 confirmé P1, S3 confirmé P2, plausible un cran plus bas.

| Constat | Étape | Crit. | Grav. | Confiance | Prio. | Titre | Tâches |
|---|---|---|---|---|---|---|---|
| C-ADOC-001 | P2.4 | C5 | S1 | CONFIRMÉ (sonde) | P0 | FK des serializers GED non bornées à la société : lien de dépôt public, exigence, annotation, planification acceptent un objet d'une autre société ; u | ADOC1, ADOC36, ADOC170 |
| C-ADOC-002 | P1.2 | C5 | S2 | CONFIRMÉ (sonde) | P1 | Versions : liste, aperçu et export annoté contournent coffre-fort, ACL et corbeille (le document répond 404, ses octets 200) | ADOC3, ADOC37 |
| C-ADOC-003 | P1.6 | C6 | S1 | CONFIRMÉ (sonde) | P0 | Supprimer un dossier ou une armoire détruit en cascade les documents archivés légalement ou sous legal hold (204, document et archivage disparus) | ADOC2 |
| C-ADOC-004 | P1.4 | C5 | S2 | CONFIRMÉ (sonde) | P1 | Confidentialité non héritée / échec ouvert : scinder-fusionner produit des documents hors coffre, supprimer un coffre rend ses documents visibles de t | ADOC4 |
| C-ADOC-005 | P1.4 | C5 | S2 | CONFIRMÉ (sonde) | P1 | Niveaux ACL jamais appliqués aux écritures (lecteur ACL renomme et supprime) ; un responsable exclu s'octroie lui-même l'accès ; arbre des dossiers no | ADOC5 |
| C-ADOC-006 | P1.4 | C8 | S2 | CONFIRMÉ (sonde) | P1 | Liens publics : jetons listés à tout rôle interne, lien créable sur un document invisible, lien révoqué réactivable par PATCH, document en corbeille t | ADOC6, ADOC37 |
| C-ADOC-007 | P1.6 | C6 | S2 | CONFIRMÉ (sonde) | P1 | Disposition : chemin de destruction définitive moins gardé que « purger » (tout rôle d'écriture détruit un document non échu) | ADOC7 |
| C-ADOC-008 | P1.5 | C7 | S3 | CONFIRMÉ (sonde) | P2 | Approbation : le demandeur s'auto-approuve et parcourt seul la chaîne ; cycle-vie saute la décision ; approbation non liée à une version | ADOC14 |
| C-ADOC-009 | P1.7 | C6 | S2 | CONFIRMÉ (sonde) | P1 | HTML importé (import-masse, office) servi inline sur l'origine ERP par l'aperçu et le lien public : XSS stocké | ADOC8 |
| C-ADOC-010 | P1.7 | C5 | S2 | CONFIRMÉ (sonde) | P1 | File de validation OCR ouverte à tout rôle : écrit dans custom_data d'un document archivé légalement | ADOC9 |
| C-ADOC-011 | P1.8 | C8 | S2 | CONFIRMÉ (sonde) | P1 | Caviardage : zone hors page ignorée en silence, la copie « (caviardé) » contient encore le texte | ADOC11 |
| C-ADOC-012 | P1.1 | C7 | S2 | CONFIRMÉ (sonde) | P1 | Checklist de pièces : une exigence jamais fournie s'affiche « Présente » | ADOC12 |
| C-ADOC-013 | P1.8 | C2 | S2 | CONFIRMÉ (sonde) | P1 | Générer depuis un modèle : l'écran envoie un contexte vide et le serveur renvoie le même document | ADOC13 |
| C-ADOC-014 | P4.2 | C2 | S2 | CONFIRMÉ (sonde) | P1 | Document régénéré (facture via document_produit) : la GED ne crée jamais de nouvelle version et reste figée sur l'ancien rendu, même sur un document e | ADOC61, ADOC62 |
| C-ADOC-015 | P4.1 | C10 | S3 | CONFIRMÉ (sonde) | P2 | Seule la facture émet document_produit : avoir, note de débit, bordereau de remise jamais archivés en GED | ADOC74, ADOC75 |
| C-ADOC-016 | P1.3 | C13 | S2 | CONFIRMÉ (sonde) | P1 | Listes lues sur la page 1 seulement (50 lignes) : navigateur GED et 6 écrans d'administration portail | ADOC30, ADOC31, ADOC32, ADOC38 |
| C-ADOC-017 | P1.2 | C2 | S2 | CONFIRMÉ (sonde) | P1 | Aucun geste « nouvelle version » ni « renommer » dans la GED ; POST /ged/versions/ exige un file_key | ADOC18, ADOC20 |
| C-ADOC-018 | P1.2 | C5 | S2 | CONFIRMÉ (sonde) | P1 | POST /ged/versions/ dédoublonne par checksum tous documents confondus : renvoie la version d'un AUTRE document (coffre compris) avec son file_key | ADOC10 |
| C-ADOC-019 | P1.3 | C5 | S3 | CONFIRMÉ (sonde) | P2 | Favoris et vues partagées ignorent visibilité et propriété | ADOC15, ADOC37 |
| C-ADOC-020 | P1.6 | C13 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Exceptions métier GED non traduites en 4xx (doublon armoire/tampon, document archivé, PDF sur non-PDF, disposition, restauration) → 500 | ADOC22 |
| C-ADOC-021 | P1.1 | C2 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Chatter GED : aucun journal old→new pour renommage, déplacement, assignation, tags, corbeille | ADOC19 |
| C-ADOC-022 | P1.2 | C9 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Versions modifiables par PUT/PATCH, restauration qui ignore le check-out, comparateur qui lit le niveau Document | ADOC17 |
| C-ADOC-023 | P1.1 | C6 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Empreinte jamais calculée aux dépôts écran ; quota appliqué sur 4 routes avec taille client ; dépôt public hors quota | ADOC23 |
| C-ADOC-024 | P1.1 | C3 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | PATCH parent/cabinet d'un dossier contourne move_folder (chemin périmé, cycles) | ADOC21 |
| C-ADOC-025 | P1.3 | C10 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Écrans GED qui lisent des champs absents ou périmés (vue enregistrée, « vundefined », étoile favori) | ADOC33, ADOC34, ADOC35 |
| C-ADOC-026 | P1.3 | C10 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Recherche GED : résultats non cliquables ; documents des autres apps absents du plein-texte | ADOC24, ADOC33 |
| C-ADOC-027 | P1.7 | C4 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Fonctions GED inertes ou sans appelant (alias e-mail, lot séparé, classer-après-vente, office-sauvegarder, OCR qui annonce « effectué ») | ADOC25, ADOC26, ADOC27, ADOC28, ADOC39 |
| C-ADOC-028 | P1.4 | C5 | S3 | CONFIRMÉ (sonde) | P2 | Partager avec un client ou un partenaire cache le document aux employés internes non-admin | ADOC16, ADOC37 |
| C-ADOC-029 | P1.6 | C7 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Suppression définitive et certificat de destruction laissent le fichier dans MinIO | ADOC29 |
| C-ADOC-030 | P2.1 | C10 | S2 | CONFIRMÉ (sonde) | P1 | Signataires jamais joints : lien multi relatif vers la mauvaise route (404), signataire mono jamais notifié | ADOC63, ADOC81 |
| C-ADOC-031 | P2.2 | C5 | S2 | CONFIRMÉ (sonde) | P1 | OTP de signature contournable : signer sans demander de code est accepté | ADOC64 |
| C-ADOC-032 | P2.3 | C3 | S2 | CONFIRMÉ (sonde) | P1 | Deux chemins de signature : l'individuelle jette tracé/IP/UA/hash/champs requis ; IP de preuve = REMOTE_ADDR | ADOC65, ADOC66, ADOC79, ADOC81 |
| C-ADOC-033 | P2.2 | C13 | S2 | CONFIRMÉ (sonde) | P1 | Page publique de signature : document jamais affiché (appels authentifiés → 401) | ADOC67 |
| C-ADOC-034 | P2.3 | C9 | S2 | CONFIRMÉ (sonde) | P1 | Document signé jamais figé : champs et versions modifiables après signature, PDF signé recalculé | ADOC68 |
| C-ADOC-035 | P2.3 | C6 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Cérémonie : état global et rôle non vérifiés ; creer-multi écrit des destinataires bruts | ADOC76 |
| C-ADOC-036 | P3.2 | C1 | S1 | CONFIRMÉ (sonde) | P0 | PV, BL et dossier de remise listent TOUTES les lignes du devis (option batterie non retenue, optionnelles) au lieu de la nomenclature vendue | ADOC60 |
| C-ADOC-037 | P3.4 | C5 | S2 | CONFIRMÉ (sonde) | P1 | Les 4 documents de chantier ignorent la portée des rôles restreints | ADOC69, ADOC80 |
| C-ADOC-038 | P3.1 | C9 | S2 | CONFIRMÉ (sonde) | P1 | PV signé et attestation régénérés depuis l'état courant (même mention « Signé le … — empreinte », attestation datée du téléchargement) | ADOC70, ADOC71 |
| C-ADOC-039 | P3.4 | C6 | S2 | CONFIRMÉ (sonde) | P1 | Attestation « achevés et conformes » produite pour un chantier signé, annulé ou non conforme | ADOC72, ADOC73, ADOC80 |
| C-ADOC-040 | P3.4 | C10 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Attestation de fin de travaux inatteignable depuis la fiche chantier | ADOC73 |
| C-ADOC-041 | P3.3 | C1 | S3 | CONFIRMÉ (sonde) | P2 | Équipements remplacés/HS/rebut imprimés « posés » au dossier de remise | ADOC77 |
| C-ADOC-042 | P3.1 | C6 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Signature client du PV non validée (toute chaîne → « signé », injectée dans <img src>) | ADOC78 |
| C-ADOC-043 | P5.3 | C10 | S2 | CONFIRMÉ (sonde) | P1 | Devis à deux options impossible à accepter au portail (option jamais envoyée → 400) | ADOC110, ADOC113, ADOC114 |
| C-ADOC-044 | P5.9 | C5 | S2 | CONFIRMÉ (sonde) | P1 | Réactivation qui ressuscite les membres révoqués en écriture ; rôle par défaut permissif | ADOC115 |
| C-ADOC-045 | P5.10 | C3 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Export « mes données » sans filigrane (jumeau de télécharger) | ADOC142 |
| C-ADOC-046 | P5.2 | C1 | S3 | CONFIRMÉ (sonde) | P2 | Tableau de bord : versions remplacées comptées en « devis en attente » | ADOC125, ADOC148 |
| C-ADOC-047 | P5.5 | C13 | S3 | CONFIRMÉ (sonde) | P2 | Détail d'un chantier annulé au portail → 500 | ADOC126, ADOC148 |
| C-ADOC-048 | P5.3 | C6 | S3 | CONFIRMÉ (sonde) | P2 | Ré-acceptation portail d'un devis déjà accepté : fausse preuve d'e-signature | ADOC127 |
| C-ADOC-049 | P5.9 | C10 | S2 | CONFIRMÉ (sonde) | P1 | Lien d'invitation d'équipe mort (SITE_URL Astro + route inexistante) | ADOC111, ADOC116, ADOC117 |
| C-ADOC-050 | P5.6 | C4 | S3 | CONFIRMÉ (sonde) | P2 | Six surfaces client servies sans écran ; file « Demandes de ticket » jamais alimentée | ADOC111, ADOC117, ADOC134, ADOC135, ADOC136, ADOC137, ADOC138, ADOC139, ADOC140, ADOC141, ADOC147, ADOC149 |
| C-ADOC-051 | P5.1 | C6 | S3 | CONFIRMÉ (sonde) | P2 | Invitation : mot de passe sans validateurs | ADOC111, ADOC122 |
| C-ADOC-052 | P5.1 | C8 | S3 | CONFIRMÉ (sonde) | P2 | Client sans e-mail : « mot de passe envoyé par email » alors que rien n'est envoyé | ADOC123, ADOC124 |
| C-ADOC-053 | P7 | C5 | S2 | CONFIRMÉ (sonde) | P1 | prendre_en_charge accepte un ticket d'une autre société ; valeur non numérique → 500 | ADOC118 |
| C-ADOC-054 | P7 | C2 | S3 | CONFIRMÉ (sonde) | P2 | Demande SAV prise en charge non re-liable | ADOC118 |
| C-ADOC-055 | P7 | C13 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Rapprochement paiement portail non atomique | ADOC143 |
| C-ADOC-056 | P6.2 | C6 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Candidature fournisseur : champs non bornés → 500 | ADOC144 |
| C-ADOC-057 | P6.1 | C3 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Anti-doublon partenaire limité à l'e-mail | ADOC145 |
| C-ADOC-058 | P6.1 | C8 | S3 | CONFIRMÉ (sonde) | P2 | Ressources partenaires : document obsolète/archivé encore servi | ADOC128, ADOC148 |
| C-ADOC-059 | P8.1 | C3 | S3 | PLAUSIBLE (oracle = test rouge) | P3 | Trois timelines de chantier sans parité (jalons manuels, synchro CHT11, suivi public) | ADOC121, ADOC129, ADOC171 |
| C-ADOC-060 | P7 | C2 | S3 | CONFIRMÉ (sonde) | P2 | Jalons client : aucun geste d'édition à l'écran | ADOC129 |
| C-ADOC-061 | P6 | C13 | S2 | CONFIRMÉ (sonde) | P1 | Portails fournisseur et partenaire bloqués au premier login (aucun écran de changement de mot de passe) | ADOC119 |
| C-ADOC-062 | P5.2 | C13 | S2 | CONFIRMÉ (sonde) | P1 | Shell global : composants internes montés pour un compte portail (messages-accueil 403 → toast à chaque page, dialogue « Bienvenue chez Taqinor ») | ADOC120, ADOC146 |
| C-ADOC-063 | P8.1 | C1 | S2 | CONFIRMÉ (sonde) | P1 | Suivi public : « Installation : Fait » dès la signature ; étapes cochées sur lignes annulées | ADOC112, ADOC121, ADOC132, ADOC171 |
| C-ADOC-064 | P8.1 | C1 | S3 | CONFIRMÉ (sonde) | P2 | Suivi public : « Mis à jour le » = date de la requête | ADOC112, ADOC130, ADOC132, ADOC171 |
| C-ADOC-065 | P8.1 | C10 | S3 | CONFIRMÉ (sonde) | P2 | Lien de suivi mort après 30 jours (aucune prolongation à l'acceptation) | ADOC131, ADOC171 |
| C-ADOC-066 | P8.1 | C13 | S3 | CONFIRMÉ (sonde) | P2 | Suivi public sous OTP : aucun écran de saisie du code | ADOC133 |

## 6. Constats OPTIONNELS (hors tâches — S4, style, durcissement hypothétique)

- GEDCYC (S4) — update_search_vector n'indexe ni les tags ni la référence DOC-… (contrairement à sa docstring)
- GEDCYC (S4) — file_key libre sur POST /ged/versions/ et clés de stockage GED sans préfixe société (SCA42)
- GEDCYC (S4) — Entrées non typées/bornées dans les vues GED → 500 (nom > 255, ids non numériques, lots)
- GEDCYC (S4) — Modèles de documents : Template() sur du HTML de modèle et WeasyPrint sans url_fetcher restreint
- GEDCYC (S4) — assembler-photos : images illisibles/tronquées ou trop lourdes → 500, plafond 10 Mo atteint seulement sur le PDF final
- GEDCYC (S4) — Tampon apposé invisible à la lecture (couche séparée non superposée à l'aperçu, au partage ni au ZIP)
- GEDCYC (S4) — Règles (dossier, approbation, ACL métadonnée) : condition_group validé à la création seulement
- GEDCYC (S4) — Libellés/fuites mineurs de l'écran : « Archiver » pour un check-in, URL d'aperçu jamais révoquées
- GEDACC (S4) — documents_visible_to_user évalue l'ACL document par document en Python à chaque liste dès qu'une seule ACL existe
- GEDACC (S4) — Ajouter une version : jumeaux incohérents face au legal hold (Office et fusion refusent, POST /versions/ et l'upload acceptent)
- GEDACC (S4) — La purge ou la destruction d'un document efface aussi son journal d'accès « append-only »
- SIGN (S4) — Réglages de signature sans effet : peut_changer_signataire, auto_remplir, lecture_seule, options/mode_saisie des types de champ
- SIGN (S3) — Ré-émission du code OTP illimitée (coût SMS) et remise à zéro des essais
- SIGN (S4) — Double POST concurrent de signature : pas de verrou, les preuves de la 1re signature peuvent être écrasées
- CHANT (S3) — Le dossier de remise imprime un instantané du pack CH4 (pièces, « dossier complet ») sans sa date de génération
- CHANT (S4) — Couverture arabe partielle et mélange de langues : seul le BL est traduit ; « à » français dans le gabarit AR ; _photos_count masque les erreurs
- COUTURE (S3) — Routage : dossier_cible réduit à '/' ou vide après jetons => folder None, IntegrityError avalée par le récepteur, document perdu sans trace utile
- COUTURE (S4) — Routage : store_attachment appelé sans company= (clé de stockage plate non préfixée société, contrairement à SCA42 et à publier_documents_meryem)
- PCLIENT (S4) — « Mes documents » montre un document GED obsolète ou archivé comme s'il était en vigueur, daté de sa création et non de sa dernière version
- PCLIENT (S3) — Acceptation d'invitation d'équipe : aucun contrôle de robustesse du mot de passe côté serveur
- PCLIENT (S4) — Identifiants non numériques dans l'URL ou ?chantier= → 500 au lieu de 404
- PCLIENT (S4) — Bouton « Accepter » affiché sur un devis refusé ou expiré (409 au clic)
- PEXT (S3) — Le client d'un ComptePortailClient reste modifiable par PATCH après création : le jeton et les invitations basculent sur un autre client
- PEXT (S3) — Acceptation d'invitation sans verrou : deux POST concurrents sur le même jeton créent deux comptes, dont un sans invitation (donc admin et écriture)
- PEXT (S4) — « Copier le lien d'accès » copie une URL générique sans jeton ; « Régénérer » annonce que « l'ancien lien ne fonctionne plus » alors que ce lien est inchangé
- PEXT (S3) — Rapprocher un paiement portail sans verrou : un double clic peut créer deux encaissements ventes pour une seule intention
- PFRONT (S4) — Bouton « Accepter » affiché sur les devis refusés ou expirés
- PFRONT (S4) — Colonnes admin Client et Chantier affichées en identifiant brut (#id)
- PFRONT (S4) — Tableau de bord fournisseur : `livraisons_annoncees` servi mais jamais affiché, commentaire périmé
- PFRONT (S4) — Écrans fournisseur et partenaire sans contrat committé ni test (PACT10)
- SUIVI (S4) — Contrat du suivi public non partagé : aucun contract_sample, interface TS écrite à la main, champ 'date' polymorphe (date ou statut)
- SUIVI (S4) — suivi_path() est du code mort (aucun appelant) et un commentaire de test dit que personne n'émet le lien
- PFRONT (S4, réfuteur) — « Total du relevé » partenaire inclut les commissions annulées sans sous-total (#108).
- CHANT (S4, réfuteur) — deux générateurs de bon de livraison pour un même chantier (#75) ; COUTURE (S4) — publication Meryem sans `--company` (#82), recherche par référence qui ignore la corbeille (#81, absorbé dans C-ADOC-014).
- GEDCYC — `documents_visible_to_user` itère tous les documents de la société dès qu'une ACL existe (#27, C14 non retenu : unité X6).

## 7. Vérification adversariale (phase 5)

- **Réfuteurs** (opus/high, contexte frais, 151 verdicts) : 2 réfutations. #78 « documents routés jamais
  partagés au portail » : mécanique exacte, mais rien n'exige qu'un document routé atteigne le portail
  (choix délibéré : partage explicite par ACL client) → non-défaut. #86 « galerie chantier = toutes les
  images » : aucun chemin produit n'attache une image interne sans phase à un chantier → non reproductible.
  Les réfuteurs ne sont **pas calibrés** (corpus QJR5 non rejoué) : « confirmé » signifie ici « sonde
  exécutée », jamais « un second agent est d'accord ».
- **Porte empirique** : 63 sondes, 60 reproduites. **#73 réfuté par l'exécution** : l'heure du PV est
  imprimée en heure locale — le Maroc est à GMT depuis le 20/09/2026 (WEB_PLAN « Heure légale »), donc UTC
  = heure locale. **#99** (candidature fournisseur, champs non bornés) : la sonde a cassé la transaction
  (erreur de base, compatible avec le constat) sans verdict propre → PLAUSIBLE (C-ADOC-056).
- **Déjà corrigé sur main** : aucun constat (lentille 2 sur tous les S1/S2 ; `git log -S`).
- **Lentille frères** : les classes FK non bornée, liste lue page 1, IP hors primitive, endpoint interne
  appelé par un compte portail, surface servie sans écran reçoivent chacune une garde M3 (ADOC36, ADOC37,
  ADOC38, ADOC79, ADOC80, ADOC81, ADOC146, ADOC147, ADOC148).

## 8. Non-risques consignés (valides tant que l'hypothèse tient)

- **GEDCYC** — Isolement société de la lecture de documents : DocumentViewSet.get_queryset passe par documents_visible_to_user (filtre company_id) donc un document d'une autre société renvoie 404 (hypothèse : request.user.company_id non nul ; un superuser plateforme sans société voit tout par conception TenantMixin).
- **GEDCYC** — company forcée côté serveur dans perform_create de Cabinet/Folder/Document/Tag/Coffre/ModeleDocument/Routage/QuotaStockage (jamais lue du corps) ; Folder/Document/Coffre/Tag/Lien/Favori ont une validation de société explicite dans leurs serializers.
- **GEDCYC** — Dossier cible de televerser, scan-lot, assembler-photos, import-masse, deposer-lot-scans-separe et deplacer résolu par Folder.objects.filter(company=request.user.company) : 404 si autre société (hypothèse : id entier).
- **GEDACC** — Inter-locataires (« 404 jamais 403 ») : tous les viewsets de la surface héritent de TenantMixin (core/mixins.py:141-145, company_qs). get_object sur un id d'une autre société renvoie 404. Les créations forcent company côté serveur (perform_create, ou company=document.company dans les services). Les actions qui prennent un id du 
- **GEDACC** — Lien public : résolu à partir du jeton seul (services.py:1691-1705). Révoqué ou inconnu → 404 indistinct ; expiré ou quota atteint → 410 ; mot de passe haché (make_password) vérifié → 403. Le quota est consommé atomiquement AVANT de servir (views.py:3879-3882). Throttle IP+jeton (views.py:3801-3819) et X-Robots-Tag noindex. Hypo
- **GEDACC** — Legal hold, chemins couverts : DELETE document → corbeille gardée (views.py:514-524, services.py:2181-2182) ; opération par lot « corbeille » (services.py:5048-5050, gardes par élément) ; purger → Document.delete() (models.py:703-704) ; purge automatique (services.py:2325, filet l.2331) restreinte à active_companies et à apply e
- **SIGN** — Entropie des jetons (signature, signataire, dépôt) : secrets.token_urlsafe(32) ≈ 256 bits, unique, non éditable (models.py:1163-1169, 1727-1729, 1969-1971, 2486-2488) — l'énumération est infaisable même sans throttle inter-jetons.
- **SIGN** — Rejeu après signature (jeton de demande XGED1) : resolve_signature_publique renvoie DEJA_TRAITEE → 410 dès que statut != en_attente (services.py:2837-2838) ; idem signataire déjà signé/refusé → 410 (views.py:4290-4294). Vrai hors course concurrente (voir constat optionnel).
- **SIGN** — Révocation/expiration : annulation émetteur et expires_at dépassé → 410 (services.py:2835-2836, views.py:4286-4289) ; dépôt révoqué → 404, expiré/quota → 410 (services.py:4389-4392) ; sweep quotidien expirer_demandes_echues planifié (tasks.py:47-61, celery.py:61).
- **CHANT** — Isolation inter-société : views.py:20-29 passe par get_company_object (core/selectors.py:24-64) ; un pk d'une autre société renvoie 404 indistinct ; test_documents.py:131-175 le vérifie (hypothèse : request.user.company_id renseigné ; un utilisateur sans société et non superuser obtient .none() donc 404).
- **CHANT** — prix_achat/marge : grep de builders.py et des 5 gabarits document_* ne trouve que des commentaires ; _composants et _equipements_poses sont des whitelists champ par champ (hypothèse : Produit n'est jamais sérialisé en bloc).
- **CHANT** — Date « Document généré le » : erp_agentique/jinja2.py (AUD308) évalue now à chaque rendu ; l'heure est locale au process (hypothèse : TZ = Africa/Casablanca, Django fixe TZ sur POSIX depuis settings.TIME_ZONE).
- **COUTURE** — Tâches Celery ged : toutes (purge corbeille, relances signature, intégrité archives, notif émetteurs, relances demandes, planifications, poll mail, migrer_pieces_jointes) itèrent via authentication.selectors.active_companies() et isolent l'échec par société (tasks.py:52,78,107,132,163,188,216 ; services.py:2365) ; vrai sous l'hy
- **COUTURE** — document_produit a un abonné vivant (ged/receivers.py, dispatch_uid posé, câblé par GedConfig.ready apps.py:61-65) ET un émetteur réel (ventes/utils/pdf.py:342) ; il n'est ni dans les réserves 'sans abonné' de event_coverage ni dans NO_STATIC_EMITTER (event_coverage.py:116,363) et le payload du catalogue correspond aux kwargs ré
- **COUTURE** — Pas de doublon à la régénération pour la facture : l'idempotence source+reference empêche la création d'un second Document (services.py:5889-5896) ; le problème est l'absence de version, pas le doublon.
- **PCLIENT** — C5 étanchéité : chaque lecture portail client exige (société, client_id) dérivés du compte connecté (_scope, views_client.py:47-60) — devis/factures (selectors_portail.py:50-53, 89-92, 112-114, 149-152), chantiers/photos (installations/selectors.py:2995-2997, 3011-3013), livraisons/preuve (2147-2148, 2207-2210), fil SAV (sav/sel
- **PCLIENT** — C5 /proposal : get_queryset portail borne client_id=scope et exclut BROUILLON (ventes/views/devis.py:376-390) + has_object_permission (roles/permissions.py:284-292) ; méthodes non sûres refusées (269).
- **PCLIENT** — C5 création : company et client_id forcés depuis le compte dans create SAV (views_client.py:1018-1021), dépôt de document (1489-1495, lead_id retiré), paiement (678-682), invitation (1310-1312) — jamais lus du corps ; le chantier d'un ticket étranger est ignoré (1012-1016).
- **PEXT** — Viewsets admin portail (ComptePortail, Acceptations, Paiements, DocumentsClient, Jalons, DemandesTicket) : TenantMixin.get_queryset scope par request.user.company et perform_create/perform_update forcent company (core/mixins.py:141-159). Un id d'une autre société renvoie 404 par get_object. Hypothèse : company_qs filtre company 
- **PEXT** — Un compte portail (client/partenaire/fournisseur) ne franchit pas les viewsets admin : IsResponsableOrAdmin s'appuie sur is_responsable, et _role_grants_write ignore les permissions 'portail_*' (authentication/models.py:461-468). Les rôles portail n'ont que 'portail_*_acces' (roles/models.py:1276-1278). Hypothèse : personne n'aj
- **PEXT** — Séparation des portées : IsPortalClientUser/FournisseurUser/PartenaireUser exigent la portée EXACTE et un id de rattachement non nul (roles/permissions.py:202-232). Un fournisseur n'atteint pas mes-soumissions et un partenaire n'atteint pas mes-bons-commande. Les sélecteurs prennent (request.user.company, portal_scope_id) et jam
- **PFRONT** — Le lien « Voir le devis (PDF) » (PortailClientDevis.jsx:134) emprunte bien /ventes/devis/<id>/proposal/ (règle #4) : l'authentification est par cookie (axios.js withCredentials), donc la navigation par <a href> porte la session ; garde IsInternalWriterOrPortalClientOwner (roles/permissions.py:235-300) limitée à la portée client,
- **PFRONT** — La date « Document mis à jour le » est affichée (PortailClientDevis.jsx:118-122) à partir de mis_a_jour_le, servi par selectors_portail.py:66 depuis etude_params.resync_apres_envoi et testé contre le contrat committé (PortailClientDevisMisAJour.test.jsx). Hypothèse : le marqueur resync_apres_envoi est posé par la correction aprè
- **PFRONT** — La liste portail n'expose pas les brouillons et filtre is_active=True (selectors_portail.py:50-52) : le client voit la version en vigueur, pas une version remplacée.
- **SUIVI** — Jeton / multi-société : le suivi est borné à UN ShareLink => UN devis d'une seule société (selectors.py:682-687) ; aucune donnée d'une autre société ne peut sortir (hypothèse : le jeton secrets.token_urlsafe(32) reste imprévisible, models.py _default_share_token) ; jeton invalide/expiré/sans devis => 404 générique via _not_found
- **SUIVI** — C8 données exposées : le payload ne contient que reference, generated_at, milestones[{key,label,done,date}] (selectors.py:756-760) ; aucun prix, prix_achat, marge, nom ou montant (hypothèse : la liste fermée du dict reste telle quelle ; test_qx34_suivi.test_no_prix_achat_in_payload le garde).
- **SUIVI** — Lecture pure : devis_milestones ne mute rien (pas de stamp de vue, chatter ni notification) et suivi_public est GET AllowAny avec PublicLinkRateThrottle par IP+jeton (public_views.py:1630-1632 ; noyau.py:60-66).

## 9. Conclusion (phase 6)

- **Couverture.** 9 surfaces sur 9 lues (fichiers non lus listés §4) ; 11 détecteurs exécutés sur le code + 3 gardes de plan (`check_taches_cablage`, `check_plan_taches_mixtes`, `check_ownership`, verts après correction), 3 non
  exécutés (§4) ; 66 constats, dont 49 CONFIRMÉS par exécution (3 S1, 29 S2, 17 S3) et 17 PLAUSIBLES ;
  scénarios live S-A, S-B, S-C joués en direct (portail client, Playwright + HTTP), S-D, S-E, S-F, S-G joués
  par sondes HTTP en transaction annulée ; **non joués en écran** : portails fournisseur / partenaire,
  signature publique, `/suivi` d'apps/web.
- **Ce qui tient** (non-risques §8) : l'étanchéité inter-sociétés en LECTURE du portail, de la GED et des
  documents de chantier (404 partout, rejouée) ; aucun `prix_achat` côté client ; `/proposal` seul chemin
  du devis client (règle #4) ; « Document mis à jour le » sur Mes devis.
- **Ce qui ne tient pas** : les ÉCRITURES ne sont pas bornées comme les lectures (FK des serializers GED,
  ticket SAV d'une autre société, dépôt public rangé chez une autre société) ; la conservation légale cède à
  une cascade ; la confidentialité GED (coffre, ACL) est contournée par les versions et ne se transmet pas ;
  les documents de chantier imprimés au client listent du matériel non vendu et se régénèrent sous une
  signature ; la signature électronique ne figera pas ce qui a été signé ; un tiers du portail (écrans
  fournisseur / partenaire, devis à deux options, invitation d'équipe, six surfaces) est inutilisable.
- **Registre corrigé** (`docs/audits/unites.yml`) : J6 → `audité` ; `apps/web/src/pages/suivi/**` retiré
  de `possede` de J6 (propriétaire `web` selon `docs/ownership.yml`, qui prime) ; `possede` aligné sur
  ownership.yml (`ventes/selectors_portail.py`, `templates/pdf/document_*`).
- **Coût.** Scouts 2 (haiku/low) ; lanes 9 (5 opus/high, 4 sonnet/medium) ; réfuteurs 151 (opus/high) ;
  rédacteurs de sondes 9 (sonnet/medium) ; rédacteurs de tâches 3 (opus/high) — 176 agents ≈ 22,3 M jetons
  sous-agents ; Fable : aucun. Exécution des sondes et run live : orchestrateur.
