# `contract_samples/` — PACT10 : le contrat part EN PREMIER, et il est PARTAGÉ

## Pourquoi ce dossier existe

Le 03/08/2026, l'écran « Appels d'offres — Tableau de bord » a planté en
production. Zéro clé sur six ne concordait entre l'écran et le serveur. Les
**deux** suites de tests étaient vertes et se contredisaient : le test frontend
mockait l'inverse exact de ce que le test backend affirmait. Chacun testait sa
propre hypothèse ; personne ne testait le lien.

Ce n'est pas une négligence. `scripts/plan_lanes.py` force les lanes à être
disjointes en fichiers — c'est ce qui permet à 8 agents de travailler sans
conflit. Or un contrat front↔back ne partage **aucun fichier par construction**
(`urls.py` d'un côté, `frontend/src/api/*.js` de l'autre). La règle qui protège
des conflits de fusion garantit mécaniquement que les deux moitiés d'un contrat
travaillent en aveugle l'une de l'autre. L'en-tête de `frontend/src/api/aoApi.js`
le disait en toutes lettres : « ce fichier PUBLIE le contrat que le backend
enregistre ensuite » — une obligation adressée à une lane parallèle qui ne l'a
jamais reçue. Personne n'a menti ; **l'obligation n'avait aucun porteur.**

Ce dossier EST le porteur. Un fichier, versionné, que les deux moitiés lisent.

## La règle

> Dès qu'une fonctionnalité a une moitié front et une moitié back, **une tâche
> de contrat part la première et atterrit SEULE sur `main`**. Les deux lanes
> branchent ensuite depuis un `main` qui le contient déjà.

Cette tâche de contrat dépose ici **un exemple de réponse JSON par endpoint
agrégé** — pas une description, un exemple exécutable.

## Le format

Un fichier `<nom_endpoint>.json` par endpoint agrégé :

```json
{
  "endpoint": "GET /api/django/ventes/devis/<int:pk>/…",
  "pourquoi": "une phrase : à quoi sert cet agrégat",
  "exemple": { "…": "une réponse complète et réaliste" },
  "exemple_vide": { "…": "facultatif : un AUTRE ÉTAT du serveur" }
}
```

- `endpoint` — verbe + chemin **exact**, tel qu'il est enregistré. C'est la clé
  d'appariement : `scripts/check_api_shapes.py` retrouve la vue qui sert ce
  chemin et compare l'exemple au dictionnaire RÉELLEMENT renvoyé.
- `exemple` — une réponse complète. Les valeurs sont illustratives ; ce sont les
  **clés et leurs natures** qui font le contrat.
- `exemple_*` — variantes facultatives décrivant un autre **état** du serveur
  (société vide, liste sans résultat…). Jamais une autre **forme** : les clés
  restent celles du contrat.

## Ce qui rend le fichier digne de confiance

`scripts/check_api_shapes.py` **échoue** si l'exemple et le serveur divergent :
une clé en trop, une clé manquante, une nature incompatible. L'exemple ne peut
donc pas pourrir dans son coin — si le serveur change de forme, l'exemple doit
changer, et le test frontend qui l'importe casse tout seul. C'est exactement le
lien qui manquait : **sans réunion et sans discipline humaine.**

Un contrat déposé AVANT que l'endpoint existe (le cas le plus fréquent ici :
la tâche de contrat part avant les deux lanes qui construisent front et back)
n'est pas encore vérifiable statiquement — la garde ne rougit jamais sur un
doute, elle vérifie dès que la vue existe et devient lisible.

Côté frontend, un test n'écrit plus son `PAYLOAD` à la main : il importe cet
exemple (`frontend/src/test/fixtures/`). Un mock écrit à la main est une
DEUXIÈME source de vérité — c'est elle qu'il faut supprimer.
