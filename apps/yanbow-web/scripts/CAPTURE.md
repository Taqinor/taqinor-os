# Captures d'écran produit (YBW41, D-YBW-10)

Vrais écrans de l'ERP, **données fictives**, sur la **pile locale** seulement.
Jamais la production, jamais une vraie société, jamais un écran de veille
(D-YBW-7), jamais un montant ni une devise (D-YBW-8).

## 1. Préparer la société jetable (une fois, sur la pile locale)

Pile : `docker compose up` à la racine du dépôt (ERP sur `http://localhost`).
Rien n'est modifié dans les commandes de seed des autres plans.

1. Dans l'admin Django local (`http://localhost/api/django/admin/` par défaut, ou la valeur de `DJANGO_ADMIN_URL`), créer une
   société **neuve** (slug `yanbow-demo-capture`, `est_demo` coché) et la
   nommer exactement **`YanBow — démo`** (raison sociale ET nom du profil
   société). Ne jamais renommer une société existante.
2. Créer un utilisateur administrateur rattaché à CETTE société, avec un mot de
   passe de test généré pour l'occasion (jamais un mot de passe réel, jamais
   écrit dans le dépôt).
3. Thème de la société (`TenantTheme`) : nom affiché `YanBow — démo`, logo =
   `src/brand/` (pack YanBow, tel quel). Les couleurs du shell restent celles de
   l'ERP : on recadre donc sur la zone utile, jamais sur le chrome.
4. Saisir à la main, dans l'interface de CETTE société, des données
   manifestement fictives (noms de type « Projet Exemple », villes françaises
   génériques, aucune personne réelle) :
   - quelques prospects répartis sur les étapes du pipeline ;
   - un calepinage avec une toiture dessinée (vue 3D) et ses dossiers
     réglementaires (déclaration préalable, Enedis, Consuel) ;
   - un devis dont la proposition PDF est générée ;
   - côté Publicité : des campagnes (créées en pause), une proposition en
     attente d'approbation, les règles / garde-fous.

## 2. Lancer les captures

```sh
cd apps/yanbow-web
CAPTURE_ERP_URL=http://localhost \
CAPTURE_IDENTIFIANT=<utilisateur de test> \
CAPTURE_MOT_DE_PASSE=<mot de passe de test> \
CAPTURE_ID_CALEPINAGE=<id du calepinage fictif> \
CAPTURE_IMAGE_PROPOSITION=<png d'une page de la proposition, zone SANS montant> \
node scripts/capture-product-screens.mjs            # ou --ecran <id> (répétable)
```

Le script :

- s'arrête avant d'ouvrir un navigateur si l'adresse n'est pas locale, et à la
  première navigation hors pile locale ;
- refuse de continuer si la société affichée n'est pas `YanBow — démo` ;
- capture chaque écran à 1440 et 390 px, recadré sur la zone utile (`main`) ;
- contrôle le TEXTE de la zone avant d'écrire : nom de l'entreprise
  d'installation, devise (€, EUR, MAD, DH), prix d'achat, marge, veille → écran
  refusé, rien écrit ;
- écrit AVIF + WebP dans `src/assets/product/` et leurs dimensions dans
  `captures.json`.

La proposition PDF ne se rend pas dans un navigateur sans tête : fournir un PNG
d'une page **recadrée hors de toute zone de montant** (`CAPTURE_IMAGE_PROPOSITION`) ;
le script le convertit ; son texte n'est pas contrôlable automatiquement
(`controle_texte: "revue-seule"`), la revue zoomée fait foi.

## 3. Revue zoomée (obligatoire, consignée)

Ouvrir chaque image à 200 % et vérifier : aucun nom réel, aucun « TAQINOR »,
aucune devise ni montant, aucun prix d'achat ni marge, aucune veille, aucune
personne. Puis écrire dans `captures.json`, champ `revue` de chaque capture :
`AAAA-MM-JJ <qui> : zoom 200 %, conforme`. `tests/productScreens.test.ts` refuse
toute capture dont la revue est vide, dont un fichier manque ou dont les
dimensions ne correspondent pas ; `capturesPubliables()` n'expose jamais une
capture non revue.

Écran refusé ou douteux → corriger les données fictives, relancer
`--ecran <id>` (l'entrée est remplacée, jamais dupliquée).

## 4. Passe du 2026-10-11 (lane YBW41) — état des écrans

Pile locale (`docker compose`, `http://localhost`). Société jetable `yanbow-demo-capture`
créée avec `seed_demo_company --slug yanbow-demo-capture` (Faker installé dans le conteneur
local), puis renommée « YanBow — démo » (société, profil société, `TenantTheme.nom_affichage`),
logo `src/brand/svg/yanbow-symbol-small-colour.svg` copié dans le conteneur frontend local et
référencé par `TenantTheme.logo_url = /yanbow-logo.svg`. Utilisateur de test jetable :
`yanbow_capture_admin` (administrateur de CETTE société ; mot de passe généré, non consigné).
Données fictives posées dans la base locale seulement : 42 leads « Exemple NN / Projet »
(coordonnées vidées, montants estimés vidés, devis détachés des leads pour qu'aucun montant ne
s'affiche), 16 clients « Client Exemple NN », 3 campagnes en pause, 3 propositions en attente.
Le script ferme les fenêtres d'accueil de l'ERP (`fermerAccueil`) avant de capturer.

| Écran | État |
|---|---|
| `crm-pipeline` (1440 + 390) | capturé, revu |
| `approbations` (1440 + 390) | capturé, revu |
| `garde-fous` (1440 + 390) | capturé, revu — montre le catalogue de règles ; l'écran « Connexion & garde-fous » (coupe-circuit) reste à capturer |
| `proposition-pdf` (1440 + 390) | capturé, revu — page 3, recadrée hors de tout montant (`/proposal` du devis fictif, rendu PDF vers PNG par PyMuPDF) |
| `calepinage-3d` | **à capturer** — la carte 3D est « indisponible » sans clé MapTiler côté serveur local ; aucune capture inventée |
| `packs-reglementaires` | **à capturer** — l'ERP ne fabrique aucun gabarit DP/Enedis/Consuel : il faut déposer les gabarits officiels (Réglages, Gabarits) dans la société fictive |
| `campagnes-en-pause` | **à capturer** — la colonne « Dépense » affiche « 0 MAD » (devise) ; le script refuse l'écran (contrôle du texte), c'est le comportement voulu |

### Revue des images (ouvertes une à une avec l'outil de lecture d'image)

- `crm-pipeline-1440` / `-390` : kanban Nouveau, Contacté, Devis envoyé, Relance, Signé ; cartes « Exemple NN Projet » ; ni montant, ni devise, ni nom réel, ni TAQINOR, ni prix d'achat/marge, ni veille. Le bord droit du kanban est coupé par le recadrage (colonne suivante partielle) : sans incidence.
- `approbations-1440` / `-390` : trois cartes (Mise en pause, Renommage, Création de campagne) avec Approuver/Rejeter ; textes en français sans montant ; rien d'interdit.
- `garde-fous-1440` / `-390` : « Règles & anomalies », gabarits désarmés (Stop-loss, Revive, Fatigue créative…), « Mise en pause proposée (approbation requise) » ; aucun chiffre monétaire ; rien d'interdit.
- `proposition-pdf-1440` / `-390` : « Pourquoi YanBow — démo », garanties (2/12/30/10 ans), conditions (échéancier en pourcentages, TVA 20 %), étapes ; aucun montant ni devise ; texte du recadrage extrait et contrôlé (aucune violation). Le 390 px est lisible mais très réduit (même page vue en petit).

Relecture faite à la résolution d'export (1200 px / 390 px), pas à 200 %. Pas d'OCR.
