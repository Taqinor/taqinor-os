"""QAH4 — l'administration Django de ``publicapi`` est bornée à la société.

LE TROU. ``ApiKeyAdmin`` et ``WebhookDeliveryAdmin`` héritaient d'un
``admin.ModelAdmin`` nu : un superutilisateur RATTACHÉ À UNE SOCIÉTÉ listait les
clés d'API (libellé, préfixe) et les livraisons de webhooks (URL cible, charge
utile, statut de réponse) de TOUTES les sociétés. La garde transverse AUD417
(``tests/test_aud417_admin_scoping_transverse.py``) le signalait — mais le
paquet racine ``tests/`` n'est collecté par aucun shard CI, elle ne tournait
donc jamais. Ce test-ci vit DANS l'app : ``scripts/ci_shard.py`` le découvre.

Cadrage honnête (même adjudication qu'AUD185/AUD417) : défense en profondeur
sur la console d'administration (superutilisateur), pas une fuite d'API.
Sans base : il vérifie la classe et la clause ``WHERE`` construite.
"""
from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase

from core.admin_scoping import CompanyScopedAdminMixin

from .models import ApiKey, Webhook, WebhookDelivery


class _Utilisateur:
    """Utilisateur minimal (aucune requête base) pour sonder le filtrage."""

    is_authenticated = True
    is_active = True
    is_staff = True
    is_superuser = True

    def __init__(self, company_id=None):
        self.company_id = company_id
        self.company = None


def _requete(company_id):
    requete = RequestFactory().get('/admin/')
    requete.user = _Utilisateur(company_id=company_id)
    return requete


class Qah4PublicapiAdminScopeTests(SimpleTestCase):

    def test_les_trois_admins_portent_le_mixin_partage(self):
        for model in (ApiKey, Webhook, WebhookDelivery):
            with self.subTest(modele=model.__name__):
                self.assertIsInstance(admin.site._registry[model],
                                      CompanyScopedAdminMixin)

    def test_un_compte_de_societe_ne_voit_que_sa_societe(self):
        """Le WHERE gagne une clause société dès que le compte en a une."""
        for model in (ApiKey, WebhookDelivery):
            with self.subTest(modele=model.__name__):
                adm = admin.site._registry[model]
                avec = adm.get_queryset(_requete(company_id=42))
                sans = adm.get_queryset(_requete(company_id=None))
                self.assertGreater(len(avec.query.where.children),
                                   len(sans.query.where.children))

    def test_un_operateur_plateforme_garde_la_vue_complete(self):
        """Compte sans société : aucun filtre, comportement historique."""
        for model in (ApiKey, WebhookDelivery):
            with self.subTest(modele=model.__name__):
                adm = admin.site._registry[model]
                sans = adm.get_queryset(_requete(company_id=None))
                base = model._default_manager.get_queryset()
                self.assertEqual(len(sans.query.where.children),
                                 len(base.query.where.children))
