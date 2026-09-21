"""ARC14 — registre data-driven des modules customfieldables.

Couvre : (1) non-régression des clés natives historiques (elles résolvent
toujours vers le bon modèle et leurs données existantes restent lisibles) ;
(2) l'API du registre lui-même (register/is_registered/get_model).

SOLMVP20 — les clés natives ``document``/``employe`` (apps PARQUÉES GED/RH)
et les pilotes ``contrats.contrat``/``flotte.vehicule`` (apps PARQUÉES,
Groupe SOLMVP) ont été retirés du registre et de cette couverture.
"""
from django.test import TestCase

from apps.customfields import registry
from apps.customfields.models import CustomFieldDef
from apps.customfields.serializers import _module_model
from authentication.models import Company


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestNativeModulesNonRegression(TestCase):
    """Les clés natives historiques GARDÉES (Module.LEAD..FOURNISSEUR)
    résolvent toujours vers le même modèle après le passage au registre — le
    comportement de ``_module_model`` est inchangé pour les appelants
    existants.

    SOLMVP20 — ``document``/``employe`` restent dans ``Module.values``
    (catalogue historique) mais ne sont plus enregistrées (apps GED/RH
    PARQUÉES) : exclues explicitement, jamais itérées en aveugle sur
    ``Module.values``."""

    def test_all_native_keys_registered(self):
        for key in ('lead', 'client', 'produit', 'devis', 'installation',
                    'ticket', 'fournisseur'):
            self.assertTrue(
                registry.is_registered(key),
                f'Clé native « {key} » absente du registre.')

    def test_native_keys_resolve_to_expected_models(self):
        from apps.crm.models import Client, Lead
        from apps.installations.models import Installation
        from apps.sav.models import Ticket
        from apps.stock.models import Fournisseur, Produit
        from apps.ventes.models import Devis

        expected = {
            'lead': Lead,
            'client': Client,
            'produit': Produit,
            'devis': Devis,
            'installation': Installation,
            'ticket': Ticket,
            'fournisseur': Fournisseur,
        }
        for key, model in expected.items():
            self.assertIs(_module_model(key), model,
                          f'Module « {key} » ne résout plus vers {model}.')

    def test_existing_lead_custom_data_still_readable(self):
        """Une définition + donnée custom_data posée sur un module natif
        (lead) reste lisible/validée à l'identique après ARC14."""
        from apps.crm.models import Lead
        from apps.customfields.serializers import validate_custom_data

        company = make_company('arc14-native', 'ARC14 Native Co')
        CustomFieldDef.objects.create(
            company=company, module='lead', code='budget',
            libelle='Budget', type='number', obligatoire=False)
        lead = Lead.objects.create(
            company=company, nom='Lead existant',
            custom_data={'budget': 42000})
        lead.refresh_from_db()
        self.assertEqual(lead.custom_data.get('budget'), 42000)
        # Re-validation via le même chemin que l'API (non-régression du
        # comportement de validation, pas seulement de la lecture brute).
        clean = validate_custom_data('lead', company, {'budget': 42000})
        self.assertEqual(clean.get('budget'), 42000)


class TestRegistryApi(TestCase):
    """Comportement de base du registre lui-même."""

    def test_unknown_module_returns_none(self):
        self.assertIsNone(registry.get_model('module_inexistant_xyz'))
        self.assertFalse(registry.is_registered('module_inexistant_xyz'))

    def test_register_is_idempotent_for_same_target(self):
        registry.register('_arc14_test_key', 'crm', 'Lead')
        registry.register('_arc14_test_key', 'crm', 'Lead')  # no-op, no raise
        self.assertTrue(registry.is_registered('_arc14_test_key'))

    def test_register_conflicting_target_raises(self):
        registry.register('_arc14_conflict_key', 'crm', 'Lead')
        with self.assertRaises(ValueError):
            registry.register('_arc14_conflict_key', 'crm', 'Client')
