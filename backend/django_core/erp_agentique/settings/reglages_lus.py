"""Réglages LUS par le code (`getattr(settings, 'X', repli)`) puis DÉCLARÉS ici (ADEP20, ENF15).

C-ADEP-004 : une clé lue mais affectée dans aucun fichier de réglages n'a aucun effet quand on la
pose dans l'environnement ou dans un fichier de réglages d'instance. Chaque clé ci-dessous porte
EXACTEMENT la valeur de repli de son lecteur (`tests` : `core.tests.test_adep_reglages_securite`) :
l'absence de variable d'environnement garde le comportement d'avant la déclaration.

Importé par `base.py` (`from .reglages_lus import *`) : `dev.py` et `prod.py` en héritent.
"""
import os

# apps.notifications.sweeps (_sweep_hot_leads) : seuils du filet « lead chaud non contacté ».
HOT_LEAD_SCORE_THRESHOLD = 60
HOT_LEAD_MINUTES_OUVREES = 30
# Défauts de reporting.calendar et core (bi_cache, ai, tenant_ratelimit) ; None = repli du module.
ICS_TOKEN_MAX_AGE_DAYS, BI_WIDGET_CACHE_TTL, AI_GUARD_MAX_CHARS, AI_TOXIC_TERMS, TENANT_TASK_RATE_LIMITS = (
    180, 300, 6000, None, None
)

# apps.adsengine.tasks (PUB102, PUB104) : alerte EOL de la version Graph API, rollup des snapshots.
ADSENGINE_GRAPH_EOL_ALERT_MONTHS = 4
ADSENGINE_ROLLUP_AFTER_MONTHS = 13
# apps.identity.anomaly : repli historique de GEOIP_PATH (base GeoLite2 City). Vide = géolocalisation inerte.
GEOIP2_CITY_DB = os.environ.get('GEOIP2_CITY_DB', '')
# apps.publicapi : durée de vie (s) du jeton OAuth client_credentials ; seuil d'échecs consécutifs
# (0 = désactivé) et fenêtre (heures) de la coupure automatique d'un webhook.
PUBLIC_API_OAUTH_TOKEN_TTL = 3600
WEBHOOK_AUTO_DISABLE_THRESHOLD = int(os.environ.get('WEBHOOK_AUTO_DISABLE_THRESHOLD') or 20)
WEBHOOK_AUTO_DISABLE_WINDOW_HOURS = int(os.environ.get('WEBHOOK_AUTO_DISABLE_WINDOW_HOURS') or 24)
# authentication.password_policy : plancher plateforme de verrou de connexion (ASEC4, décision
# fondateur 07/10 : 10 échecs consécutifs, 15 minutes, couple compte+IP) — valeurs fixes, jamais d'env.
LOGIN_PLANCHER_ECHECS = 10
LOGIN_PLANCHER_VERROU_MINUTES = 15
# apps.ventes : cadence des relances de devis envoyé (jours après l'envoi), Reply-To des e-mails
# (vide = pas de Reply-To), seuil de lignes au-delà duquel un export part en tâche, numéros de compte
# CGNC surchargés (global puis par slug de société ; {} = défauts CGNC).
DEVIS_NUDGE_DAYS = [2, 5, 10]
INBOUND_REPLY_EMAIL = os.environ.get('INBOUND_REPLY_EMAIL', '')
VENTES_EXPORT_ASYNC_ROW_THRESHOLD = int(os.environ.get('VENTES_EXPORT_ASYNC_ROW_THRESHOLD') or 2000)
VENTES_COMPTA_ACCOUNT_CODES = {}
VENTES_COMPTA_ACCOUNT_CODES_BY_COMPANY = {}
