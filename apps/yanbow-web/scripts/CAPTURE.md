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
