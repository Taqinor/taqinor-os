from django.apps import AppConfig


class AdsengineConfig(AppConfig):
    """ENG1 — Moteur publicitaire Meta Ads intégré à l'ERP.

    App satellite (comme ``apps.monitoring`` / ``apps.flotte``) : multi-société,
    additive, scopée société côté serveur. Elle pilote les campagnes Meta DEPUIS
    l'ERP via une boucle propose→approuve→applique persistée ; toute création de
    campagne/adset/ad naît TOUJOURS ``PAUSED`` (extension de la règle #3, codée
    en dur dans ``meta_client``). Sans clé/token configuré, tout no-ope.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.adsengine'
    verbose_name = 'Moteur publicitaire (Meta Ads)'
