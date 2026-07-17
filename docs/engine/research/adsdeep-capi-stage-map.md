# ADSDEEP29 — Table étape CRM → event_name Meta (Conversion Leads)

La boucle *Conversion Leads* renvoie à Meta « les étapes de votre CRM »
(dossier `adsdeep-leads-capi.md` §4). Cette table associe chaque étape canonique
du pipeline à un `event_name` du CRM Dataset Meta.

## Règle #2 — les CLÉS ne sont JAMAIS codées en dur

Les clés d'étape viennent de `STAGES.py` (racine du repo), lues côté `adsengine`
via `apps.crm.selectors.pipeline_stage_order()` — jamais une liste d'étapes
répétée dans le code. La fonction `apps.adsengine.capi_odoo.stage_event_map()`
construit la table à l'exécution ; un test grep-guard
(`test_no_hardcoded_stage_key_grep_guard`) échoue si un littéral d'étape apparaît
dans `capi_odoo.py`. Seules les VALEURS (le vocabulaire d'événements Meta)
appartiennent à ce module.

## La table

| Étape STAGES.py | `event_name` Meta        | Rôle dans la boucle                  |
|-----------------|--------------------------|--------------------------------------|
| `SIGNED`        | `signed_contract`        | Issue positive (émise par ADSDEEP27) |
| `COLD`          | `crm_lead_lost`          | Issue négative (« Perdu »)           |
| toute autre     | `crm_stage_<clé minusc.>`| Étape intermédiaire du funnel        |

`stage_event_map()` renvoie `{clé_STAGES: event_name}` pour TOUTES les étapes
canoniques. `event_name_for_stage(clé)` donne le nom d'une étape (ou `''`).

## Deux bornes hors table

`lead_received` (ADSDEEP28) n'est PAS une étape de pipeline : c'est la borne
AMONT émise pour chaque `MetaLeadMirror` (Meta exige au moins deux étapes par
`lead_id` — réception + issue). Elle vit hors de cette table, en constante
(`LEAD_RECEIVED_EVENT_NAME`), aux côtés de `SIGNED_EVENT_NAME`.

## Séparation des couches (règle #2 / #4)

Cette table décrit la couche PIPELINE (funnel STAGES.py) de l'intégration Meta
*Conversion Leads*. Elle reste distincte du statut DOCUMENT d'un devis
(`brouillon`/`envoye`/`accepte`…, règle #4, émetteur QJ9 `SignedQuote`) et de
l'émetteur de transition d'étape `capi_crm`/ADSENG32 — trois familles
d'événements CAPI qui ne fusionnent jamais.
