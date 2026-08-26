# `contract_samples/` — PACT10 : le contrat part EN PREMIER, et il est PARTAGÉ

Dossier créé par WIR275 (patron `apps/ao/contract_samples/`). Voir
`apps/ao/contract_samples/README.md` pour l'historique complet de l'incident
du 03/08/2026 qui a fait naître ce mécanisme — même règle ici, sans la
répéter mot pour mot.

## La règle

> Dès qu'une fonctionnalité a une moitié front et une moitié back, **une tâche
> de contrat part la première et atterrit SEULE sur `main`**. Les deux lanes
> branchent ensuite depuis un `main` qui le contient déjà.

## Le format

Un fichier `<nom_endpoint>.json` par endpoint AGRÉGÉ (jamais une simple liste
CRUD paginée — celle-ci est déjà couverte par le contrat de sérialiseur,
PACT177) :

```json
{
  "endpoint": "POST /api/django/qhse/decisions-reunion/<int:pk>/creer-capa/",
  "pourquoi": "une phrase : à quoi sert cet agrégat",
  "exemple": { "…": "une réponse complète et réaliste" }
}
```

- `endpoint` — verbe + chemin **exact**, tel qu'il est enregistré. C'est la
  clé d'appariement : `scripts/check_api_shapes.py` retrouve la vue qui sert
  ce chemin et compare l'exemple au dictionnaire RÉELLEMENT renvoyé (silence
  si la forme n'est pas certaine statiquement — un doute ne rougit jamais).
- `exemple` — une réponse complète. Les valeurs sont illustratives ; ce sont
  les **clés et leurs natures** qui font le contrat.

Côté frontend, un test n'écrit plus son `PAYLOAD` à la main pour ces
endpoints : il importe cet exemple
(`frontend/src/test/fixtures/contractSamples.js` →
`reponseContrat('qhse', '<nom_endpoint>')`).
