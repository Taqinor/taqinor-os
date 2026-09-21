"""Configuration de l'app « einvoice » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class EinvoiceConfig(AppConfig):
    """Facturation électronique DGI — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.einvoice'
    label = 'einvoice'
    verbose_name = 'Facturation électronique DGI'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'einvoice',
        'sku': 'optional',
        'label': 'E-invoicing DGI',
        'icone': 'file-signature',
        'depends': [],
        'description': "Générateur de facture électronique au schéma DGI marocain (dry-run/réel derrière flag), scaffold de signature électronique et file d'attente de transmission Simpl inerte tant que la DGI n'a pas publié son API (Groupe NTMAR).",
        'categorie': 'Finance',
        'parked': True,
    }
