# Arrivée des leads — runbook (MRY0)

Ce document répond à UNE question : *« un prospect a rempli le formulaire, pourquoi n'est-il pas
dans l'ERP ? »*. Il liste les cinq chemins d'entrée, ce qui peut les casser, et le geste exact
qui les répare.

Incident fondateur du 03/09/2026 (« lead AZIZ ») : lead Meta créé à 11:04:04 UTC, présent dans
Odoo 11 s plus tard, absent de l'ERP jusqu'à 22:53 UTC — parce que le webhook temps réel était
muet et que seul le pull quotidien de 07:25 pouvait le faire entrer. Cause réelle : l'app
« Taqinor Ads Engine » n'était pas autorisée dans le **Gestionnaire d'accès aux prospects** de la
Page (Meta : *« App does not have leads permission »*). Réparé le 04/09 à 00:52 ; les filets
décrits ici existent pour que ce silence ne dure plus jamais 46 h.

## 1. Les cinq chemins d'entrée

| Chemin | Code | Déclencheur | Latence nominale |
| --- | --- | --- | --- |
| Webhook Meta Lead Ads | `apps/crm/webhooks.py::meta_lead_ads_webhook` | POST de Meta | quelques secondes |
| Pull Meta — filet 15 min | `adsengine.pull_meta_leads_recent` | beat `*/15` (fenêtre 48 h) | ≤ 15 min |
| Pull Meta — passe complète | `adsengine.pull_meta_leads` | beat 07:25 (fenêtre 90 j) | ≤ 24 h |
| Miroir Odoo → ERP | `crm.sync_odoo_leads` | beat `*/30` | ≤ 30 min |
| Site web / saisie manuelle | `apps/crm/webhooks.py` (site) / `LeadViewSet` | immédiat | immédiat |

Les deux pulls Meta et le webhook **convergent** sur le même lead (idempotence par `leadgen_id`) :
un lead n'est jamais dupliqué, quel que soit le nombre de chemins qui le voient.

La ligne « création » du chatter nomme désormais le chemin emprunté
(« Lead créé via Meta Lead Ads (webhook) » / « … (pull) ») et `Lead.date_creation` porte
l'heure Meta RÉELLE, pas l'heure du beat — c'est cette date que lisent le SLA, le KPI
« premier contact » et les notifications.

## 2. Variables d'environnement

| Variable | Rôle | Sans elle |
| --- | --- | --- |
| `META_LEAD_ADS_APP_SECRET` | vérifie la signature `X-Hub-Signature-256` | webhook **refusé** (403, fail-closed) |
| `META_LEAD_ADS_VERIFY_TOKEN` | poignée de main GET de souscription | souscription Meta impossible |
| `META_LEAD_ADS_ACCESS_TOKEN` | jeton system-user (prioritaire sur l'écran Connexion) | repli sur la `MetaConnection` |
| `META_LEAD_ADS_COMPANY_ID` | société cible du webhook | repli bruyant (journalisé) |
| `ODOO_SYNC_URL` / `ODOO_SYNC_API_KEY` | miroir Odoo (JSON-2, **lecture seule**) | tâche `crm.sync_odoo_leads` no-op |
| `ODOO_SYNC_COMPANY_SLUG` | société cible du miroir Odoo | tâche no-op (jamais de slug en dur) |
| `ODOO_SYNC_ALIGN` | `0` ⇒ `--no-align` (pipeline ERP non aligné sur Odoo) | alignement actif |

## 3. Diagnostiquer le webhook temps réel

```bash
python manage.py meta_webhook_status --company taqinor
```

La commande (et la tuile « Webhook leads temps réel » de *Publicité → Connexion*) affiche les
trois causes possibles **dans l'ordre** :

1. **App non souscrite au champ `leadgen`** — `GET /{app_id}/subscriptions`. Réparation : App
   Dashboard → Webhooks → objet *Page* → champ `leadgen` → callback
   `https://api.taqinor.ma/api/django/crm/webhooks/meta-lead-ads/`.
2. **Page non abonnée à l'app** — `GET /{page_id}/subscribed_apps`. Lisible seulement avec un
   jeton portant `pages_manage_metadata` ; sans cette permission Meta répond `(#200)` et la
   commande le dit. Réparation : `python manage.py meta_webhook_status --subscribe` ou le bouton
   « Abonner la Page » de l'écran Connexion.
3. **App absente du Gestionnaire d'accès aux prospects** — *aucune API publique ne lit cette
   liste*. Détectée par le SYMPTÔME : câblage complet mais aucun `MetaLeadMirror` d'origine
   `webhook` depuis plus de 7 jours. Réparation (geste manuel, 1 min) :
   **Meta Business Suite → Paramètres → Intégrations → Accès aux prospects → CRM →
   « Affecter le CRM » → l'app**.

### Obtenir un jeton avec `pages_manage_metadata`

Business Manager → Utilisateurs système → le system user des jetons → *Attribuer des actifs* →
Page « Taqinor Solutions » → *Gérer la Page* (contrôle total) ; puis *Générer un jeton* en cochant
`pages_manage_metadata` **en plus** des scopes actuels (`leads_retrieval`, `pages_show_list`,
`pages_read_engagement`, `pages_manage_ads`, `ads_read`, `ads_management`, `business_management`,
`read_insights`). Coller le jeton dans l'écran Connexion **et** dans `META_LEAD_ADS_ACCESS_TOKEN`
du `.env` serveur (l'env prime), puis redémarrer `django_core` + `celery_*`.

### Test de bout en bout

Meta → **Lead Ads Testing Tool** → formulaire *TAQINOR FORM-4.0* → *Créer un lead*. Attendu en
moins de 60 s :

```bash
docker logs --since 5m django_core | grep meta_lead_ads_webhook
# → « meta_lead_ads_webhook: token Lead Ads via env »
```

et, côté base, un `Lead` avec `external_id=<leadgen_id>` plus un `MetaLeadMirror` dont
`origine='webhook'`.

Si la tuile est verte et que rien n'arrive : App Dashboard → mode **Live** et version du champ
(v25.0) ; consigner ici ce qui a été trouvé.

## 4. Alerte « webhook muet »

Quand le filet 15 min **crée** un lead dont l'heure Meta a plus de 20 minutes, une notification
`lead_rattrape` (« Lead Meta rattrapé après N min — webhook à vérifier ») part vers la direction,
au plus une par heure. Recevoir cette alerte = exécuter la section 3.
Zéro alerte quand le webhook fonctionne : le pull ne crée alors plus rien.

## 5. Commandes de secours

```bash
# Rejouer le miroir Odoo à blanc (aucune écriture) :
python manage.py sync_odoo_leads --company taqinor --dry-run

# Rapatrier sans toucher au pipeline ERP (jour où Meryem travaille dans l'ERP) :
python manage.py sync_odoo_leads --company taqinor --no-align

# Vérifier que les beats tournent :
docker logs --since 1h celery_beat | grep -E "pull-meta-leads-recent|sync-odoo-leads"
```

Un `sync_odoo_leads --dry-run` lancé juste après une passe réelle doit afficher
**0 créé / 0 déplacé**. Les leads de TEST Meta (« Test Lead », « dummy data ») sont ignorés et
comptés à part : supprimés de l'ERP, ils n'y reviennent plus.

## 6. Ce qui n'est JAMAIS fait ici

* Aucune écriture Odoo hors `push_odoo_stages` (allowlist `odoo_sync._WRITE_ALLOWED`) — et
  toujours par l'API JSON-2, jamais en SQL (règle #1).
* Aucun jeton n'est journalisé : on journalise la **source** (`env` / `connexion`).
* Aucune campagne n'est créée ni activée par ces chemins.
