# `apps/crm/contract_samples/` — les contrats PACT10 du CRM

La doctrine complète (pourquoi ce dossier existe, la règle « le contrat part le
premier et atterrit SEUL sur `main` », le format d'un échantillon) est écrite
une seule fois, dans **`apps/ventes/contract_samples/README.md`**. Ce fichier-ci
ne la répète pas : il dit ce que porte le dossier du CRM et les deux points où
ce dossier s'écarte du cas nominal.

## Ce que le dossier contient

| Fichier | Ce qu'il apparie |
| --- | --- |
| `lead_ref_lookup.json` | la relève de référence courte du site (WREF2-L3) |
| `questionnaire_lead.json` | le questionnaire rempli par le client depuis son lien |
| `questionnaire_lien_mint.json` | la frappe du lien de questionnaire |
| `visite_externe.json` | la trace de visite anonyme envoyée par le site |
| `tunnel_webhook_keys.json` | **le registre du tunnel ↔ la lecture du webhook** (QJR229) |

## Écart 1 — un échantillon peut ne PAS décrire une réponse

`tunnel_webhook_keys.json` documente un **corps de requête** et la table
« clé émise par le site → champ `crm.Lead` », pas la réponse d'un endpoint. Il
porte donc `"forme_serveur": "partielle"` (vocabulaire de
`scripts/check_api_shapes.py`, QJR228) et son `endpoint` est le proxy du site
(`POST /api/capture-lead`), qu'aucune vue Django ne sert : la garde de forme ne
compare rien dessus — même situation que
`apps/ventes/contract_samples/ligne_fiche_mapping.json`.

Ce n'est pas un trou : la garde de conformité de ce fichier est
**`scripts/check_lead_webhook_parite.py`** (QJR230), qui compare
`apps/crm/webhooks.py::_map_payload_to_fields` à la table du contrat et rougit
en nommant la clé non traitée.

## Écart 2 — la moitié d'en face vit dans `apps/web`, en TypeScript

Le registre qui décide des noms de clés est
`apps/web/src/lib/tunnel/champs.ts`. Aucun outil de ce dépôt ne lit le
TypeScript : c'est précisément pourquoi la table doit être **publiée ici, en
JSON**, et pourquoi les clés y sont **dérivées** du registre (la commande
d'extraction est écrite dans `notes.regeneration` de l'échantillon), jamais
recopiées à la main.

**Une clé délibérément ignorée par le CRM s'écrit dans le contrat, avec sa
raison — jamais par omission.** Trois clés du registre sont dans ce cas
aujourd'hui (`consent`, `eventId`, `website_url`), plus une lue par la vue sans
colonne d'accueil (`idempotencyKey`). Une omission silencieuse est exactement
le mode de panne que ce dossier existe pour fermer : une clé qui survit à toute
la chaîne web et se perd sans trace à l'arrivée.
