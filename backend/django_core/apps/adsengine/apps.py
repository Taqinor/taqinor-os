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

    # ODX21 — registre de modules (doit correspondre à la clé du
    # frontend features/adsengine/module.config.jsx). Satellite OFF par défaut.
    module_manifest = {
        'key': 'adsengine',
        'label': 'Publicité',
        'icone': 'megaphone',
        'depends': [],
        'installable': False,
        'description': "Moteur publicitaire Meta Ads autonome (propose→approuve→"
                       "applique, campagnes toujours PAUSED, off par défaut).",
        'categorie': 'Commercial',
    }

    def ready(self):
        # ADSENG32 — câble l'émetteur CAPI CRM-stage (Conversion Leads), SÉPARÉ
        # de l'émetteur signature QJ9 : un récepteur pre_save/post_save sur
        # crm.Lead (sender résolu via apps.get_model, jamais un import des
        # modèles crm) émet un événement sur chaque transition d'étape STAGES.py.
        from . import capi_crm
        capi_crm.connect()

        # ADSDEEP17 — abonne le récepteur domaine ``meta_lead_captured`` (le
        # webhook CRM existant l'émet) pour matérialiser un MetaLeadMirror sans
        # que ``adsengine`` importe ``apps.crm``.
        from . import receivers
        receivers.connect()
