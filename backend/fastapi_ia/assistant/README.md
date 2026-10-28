# Manuel et manifeste de l'assistant des commerciaux

Dossier lu par `app/services/sql_agent_service.py::_charger_docs_assistant`
(AIC5). Les deux fichiers ci-dessous sont produits par AIC50 et voyagent dans
l'image `fastapi_ia` (`COPY . /app/`). Les tests pointent un dossier factice via
la variable `ASSISTANT_DOCS_DIR`.

| Fichier | Rôle |
|---|---|
| `manuel.md` | « Comment on fait X dans TAQINOR » : texte libre en français. Absent ⇒ l'assistant répond comme avant et l'événement porte `manuel_present=false`. |
| `capacites.yml` | Manifeste de ce que l'assistant sait faire, ne sait PAS faire, et des questions suggérées par écran. |

Les deux entrent, avec la politique « contenu non fiable », dans le prompt
SYSTÈME, marqué `cache_control` éphémère 1 h sous le fournisseur `claude`. Le
bloc est REFUSÉ (ignoré, erreur journalisée) au-delà d'environ 60 000 tokens :
le manuel doit rester un manuel. Ni nom de client, ni téléphone, ni prix
d'achat dans ces fichiers (D7).

## Format de `capacites.yml` (contrat partagé AIC5 ↔ AIC9 ↔ AIC50)

```yaml
fait:            # liste de capacités, une phrase chacune
  - "Lire les leads, devis, factures et chantiers de ta société"
ne_fait_pas:     # ce que l'ERP ne fait PAS : l'assistant le dit et appelle report_gap
  - "Envoyer un e-mail ou un WhatsApp à la place du commercial"
droits:          # rôle -> ce qui est permis (texte)
  normal: "lecture + actions internes de son périmètre"
  admin: "tout, dont l'export et les statistiques"
suggestions:     # préfixe de route -> exactement trois questions (AIC9)
  /crm/leads:
    - "Quels leads dois-je relancer aujourd'hui ?"
    - "Résume ce lead en trois lignes."
    - "Quel devis ai-je envoyé à ce lead ?"
```

Clés inconnues ignorées ; un YAML illisible laisse le texte brut dans le
prompt (journalisé) et aucune suggestion n'est servie.
