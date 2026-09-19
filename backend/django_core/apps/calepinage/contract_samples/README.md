# `contract_samples/` du module Calepinage — PACT10 : le contrat part EN PREMIER

## Pourquoi ce dossier existe AVANT l'application

`apps/calepinage/` n'a encore ni `models.py`, ni `views/`, ni migration. Ce
dossier, lui, existe déjà — et ce n'est pas un oubli d'ordre, c'est l'ordre.

Le 03/08/2026, l'écran « Appels d'offres — Tableau de bord » a planté en
production avec **zéro clé sur six** concordante entre l'écran et le serveur,
les deux suites de tests vertes et se contredisant. La cause racine n'est pas
une négligence : `scripts/plan_lanes.py` FORCE les lanes à être disjointes en
fichiers — c'est ce qui permet à huit agents de travailler sans conflit. Or un
contrat front↔back ne partage **aucun fichier par construction** (`views/` d'un
côté, `frontend/src/api/*.js` de l'autre). La règle qui protège des conflits de
fusion garantit donc mécaniquement que les deux moitiés d'un contrat
travaillent en aveugle l'une de l'autre. L'obligation existait ; elle n'avait
aucun **porteur**.

Ce dossier EST ce porteur, et il l'est dès maintenant : le module Calepinage
est construit par une vingtaine de lanes file-disjointes (`backend/calepinage-*`,
`frontend/calepinage`, `web/roofpro`). Poser le contrat en même temps que la
vue qui le sert ne préviendrait rien — la lane d'en face aurait déjà inventé sa
forme. Les échantillons de ce dossier atterrissent donc **SEULS sur `main`**,
avant toute lane productrice, et les deux moitiés branchent ensuite depuis un
`main` qui les contient déjà.

Le patron est `apps/ao/contract_samples/` — lisez son README, il porte le récit
complet de l'incident. Ce dossier-ci n'en est pas une copie : il ajoute ce que
le module Calepinage a de particulier, ci-dessous.

## La règle

> Dès qu'une fonctionnalité du module a une moitié front et une moitié back,
> **une tâche de contrat part la première et atterrit SEULE sur `main`**.

Un échantillon dépose **un exemple de réponse JSON par endpoint agrégé** — pas
une description, un exemple exécutable.

## Le format

Un fichier `<nom_endpoint>.json` par endpoint agrégé :

```json
{
  "endpoint": "GET /api/django/calepinage/calepinages/<int:pk>/",
  "pourquoi": "ce que cet agrégat sert, et pourquoi il part seul",
  "exemple": { "…": "une réponse complète et réaliste" },
  "exemple_vide": { "…": "facultatif : un AUTRE ÉTAT du serveur" }
}
```

- `endpoint` — verbe + chemin **exact**, tel qu'il sera enregistré. C'est la
  clé d'appariement : `scripts/check_api_shapes.py` retrouve la vue qui sert ce
  chemin et compare l'exemple au dictionnaire RÉELLEMENT renvoyé. Tant que la
  vue n'existe pas, la garde s'abstient (« un doute ne rougit JAMAIS ») ; le
  jour où elle naît, une divergence rougit **sans qu'aucune ligne d'ici ne
  change**. C'est pour cela que le chemin doit être écrit juste dès le premier
  jour.
- `exemple` — une réponse complète. Les valeurs sont illustratives ; ce sont
  les **clés et leurs natures** qui font le contrat.
- `exemple_*` — variantes facultatives décrivant un autre **état** du serveur
  (calepinage neuf, société sans gabarit…). Jamais une autre **forme** : les
  clés restent celles du contrat.

## Les quatre règles propres à ce module

1. **Une seule forme d'URL** — `/api/django/calepinage/calepinages/<pk>/…`
   (routeur DRF, sous-ressources en `@action`) ; les réglages société vivent
   sous `/api/django/calepinage/parametres/`. Un échantillon qui écrit une
   autre forme fige une route qui ne sera jamais servie.
2. **Le client est `crm.Client`** — `ventes.Client` n'existe pas et
   `Devis.client` pointe déjà `'crm.Client'`. Les échantillons nomment donc
   `client` et `lead` (`crm.Lead`), jamais un tiers modèle.
3. **Une grandeur non mesurée vaut `null`, jamais `0`** — c'est la discipline
   déjà tenue par `apps/ao/calepinage_io.marges_vers_json` : `Marges` rend
   `0.0` aussi bien pour « au ras » que pour « rien de ce type n'existe dans ce
   plan ». Publier ce zéro ferait lire « marge nulle » là où **rien n'a été
   mesuré**. Chaque `exemple_vide` de ce dossier garde donc TOUTES ses clés
   avec des valeurs nulles — jamais des zéros, jamais une clé absente (un écran
   qui reçoit parfois 4 clés et parfois 5 finit par tester l'absence de clé au
   lieu de l'absence de données, et c'est là qu'il casse).
4. **Aucun chiffre client inventé** — les valeurs des exemples sont des
   PLACEHOLDERS assumés (identifiants à un chiffre, empreintes visiblement
   factices, libellés « d'essai »). Aucun prix d'achat, aucune marge, aucun
   chiffre d'affaires ne figure dans un échantillon : `Produit.prix_achat`
   alimente un indicateur GÉNÉRATEUR et ne doit apparaître dans aucune sortie
   destinée au client.

## Le cas particulier : `roof_layout_v2.schema.json`

Ce dossier porte aussi un **schéma JSON** (et non un échantillon de réponse) :
`roof_layout_v2.schema.json` fige le document `roof_layout` que le constructeur
du site sérialise (`apps/web/src/scripts/roofPro11/prefill.ts`) et que le
backend consomme sans le valider nulle part. Il vit ici pour la même raison que
les échantillons — sept tâches du groupe CAL l'étendent depuis des lanes
file-disjointes — mais il porte, en plus de son vocabulaire JSON Schema, les
clés `endpoint` / `pourquoi` / `exemple` du format ci-dessus : c'est la
condition pour que `check_api_shapes.py` le lise sans le prendre pour un
échantillon cassé. Les mots-clés inconnus étant ignorés par tout validateur
JSON Schema, le document reste un schéma valide et utilisable tel quel.

## Ce qui rend un fichier d'ici digne de confiance

`scripts/check_api_shapes.py` **échoue** si l'exemple et le serveur divergent :
une clé en trop, une clé manquante, une nature incompatible. L'exemple ne peut
donc pas pourrir dans son coin. Côté frontend, un test n'écrit plus son
`PAYLOAD` à la main (PACT13) : il importe cet exemple via
`frontend/src/test/fixtures/`. Un mock écrit à la main est une DEUXIÈME source
de vérité — c'est elle qu'il faut supprimer.
