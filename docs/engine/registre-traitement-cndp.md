# Registre de traitement CNDP — moteur publicitaire (adsengine)

> PUB100. Registre des données à caractère personnel traitées par le moteur
> publicitaire, leurs finalités, la base légale, les durées de conservation et
> les mesures de purge/effacement. Conforme à l'esprit de la loi 09-08 (CNDP) :
> minimisation, durée de conservation bornée, droit à l'oubli propagé.

## 1. Traitements et données concernées

| Traitement | Modèle | Données personnelles | Finalité | Base légale |
|---|---|---|---|---|
| Leads publicitaires (Lead Ads) | `adsengine.MetaLeadMirror` | `phone_key` (téléphone NORMALISÉ, jamais en clair), `crm_lead_id` (référence) | Attribution d'un lead à une annonce/campagne | Intérêt légitime (mesure de performance pub) |
| Conversations CTWA (Click-to-WhatsApp) | `adsengine.CtwaReferral` | `phone_key` (normalisé), `ctwa_clid`, `crm_lead_id` | Attribution d'une conversation entrante à une annonce | Intérêt légitime |
| Ventilations de performance | `adsengine.InsightBreakdown` | Aucune donnée personnelle directe (agrégats âge×genre/placement/région/horaire) | Analyse de diffusion | Intérêt légitime |
| Événements CAPI hashés (uploads) | boucle CAPI (`capi_*`) | Identifiants HASHÉS (SHA-256) avant envoi à Meta | Conversion API / mesure | Consentement + intérêt légitime |

Principe de minimisation : le téléphone n'est **jamais** stocké en clair dans
les miroirs — seule la clé normalisée QW10 (`crm.selectors.normalize_phone_key`)
est conservée, et uniquement pour le rapprochement avec un lead CRM.

## 2. Durées de conservation (fenêtres de rétention)

Configurables par réglage Django (défauts prudents ci-dessous). Une fenêtre
`≤ 0` désactive explicitement la purge (conservation illimitée assumée).

| Réglage | Défaut | Modèle purgé | Champ de date |
|---|---|---|---|
| `ADSENGINE_LEAD_MIRROR_RETENTION_DAYS` | 400 j (~13 mois) | `MetaLeadMirror` | `created_at` |
| `ADSENGINE_CTWA_RETENTION_DAYS` | 400 j | `CtwaReferral` | `created_at` |
| `ADSENGINE_BREAKDOWN_RETENTION_DAYS` | 400 j | `InsightBreakdown` | `date` |

## 3. Purge automatique

Tâche Celery `adsengine.purge_expired_mirrors` (beat quotidien 03:40, queue
`scheduled`). Supprime les lignes plus anciennes que la fenêtre configurée,
toutes sociétés confondues (politique d'entreprise). **Idempotente** : une
seconde exécution ne trouve plus rien à purger. La purge est une **suppression
définitive** (droit à l'oubli / minimisation) — ce n'est PAS un soft-delete
réversible : c'est la finalité CNDP. Elle est tracée dans le log applicatif
(compte supprimé par miroir).

## 4. Droit à l'oubli — propagation de l'effacement

Quand un lead CRM est effacé, l'ERP émet l'événement domaine
`core.events.lead_erased` (`company`, `crm_lead_id`, `phone_key`). Le moteur
publicitaire y réagit dans `adsengine.receivers.on_lead_erased` (best-effort,
jamais bloquant) : il **anonymise** les miroirs (`MetaLeadMirror`,
`CtwaReferral`) qui référençaient ce lead — `phone_key` effacé et `crm_lead_id`
détaché — tout en conservant l'agrégat d'attribution par annonce (chiffre
dépersonnalisé). Le rapprochement se fait par `crm_lead_id` **ou** `phone_key`
(les deux clés de jointure QW10).

> Note d'intégration : l'ÉMISSION de `lead_erased` appartient au chemin de
> suppression de lead côté `apps.crm` (hors périmètre de la lane adsengine) ;
> adsengine ne fait qu'en être ABONNÉ, sans jamais importer `apps.crm`.
