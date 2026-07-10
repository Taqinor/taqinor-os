"""SCA28 — thème neutre + modèles brandés par défaut seedés à l'inscription.

Vérifie que :
  * un signup neuf obtient un ``TenantTheme`` NEUTRE (présent, sans couleur/logo
    imposés) + les ``BrandedTemplate`` par défaut (signature e-mail) ;
  * le seed est idempotent (double exécution : ni doublon, ni écrasement d'une
    valeur déjà personnalisée) ;
  * les lignes seedées sont CONSOMMÉES sans étape manuelle — SCA24 lit le thème,
    SCA25 rend la signature d'email STRICTEMENT à l'identique du repli neutre
    (« L'équipe {nom} », jamais « TAQINOR ») ;
  * le hook ``branding`` est bien enregistré dans le registre core.signup_hooks.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory


class SignupBrandingSeedRegistryTest(TenantAPITestCase):
    def test_hook_branding_enregistre(self):
        from core.signup_hooks import registered_hooks
        self.assertIn('branding', registered_hooks())

    def test_signup_neuf_obtient_theme_neutre_et_modeles(self):
        api = APIClient()
        r = api.post('/api/django/auth/register-company/', {
            'company_nom': 'Neutre SARL',
            'username': 'boss-neutre',
            'password': 'motdepasse123',
            'email': 'boss@neutre.ma',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)

        from authentication.models import Company
        from core.models import BrandedTemplate, TenantTheme
        from core.selectors import EMAIL_SIGNATURE_CODE
        company = Company.objects.get(nom='Neutre SARL')

        # Thème présent ET neutre (aucun branding imposé au nouveau tenant).
        theme = TenantTheme.objects.filter(company=company).first()
        self.assertIsNotNone(theme, 'le thème doit être seedé au signup')
        self.assertEqual(theme.couleur_primaire, '')
        self.assertEqual(theme.couleur_secondaire, '')
        self.assertEqual(theme.logo_url, '')
        self.assertEqual(theme.domaine, '')
        self.assertEqual(theme.nom_affichage, '')

        # Modèle brandé « signature e-mail » présent, actif, sans nom en dur.
        sig = BrandedTemplate.objects.filter(
            company=company, kind=BrandedTemplate.KIND_EMAIL,
            code=EMAIL_SIGNATURE_CODE).first()
        self.assertIsNotNone(sig, 'la signature e-mail doit être seedée')
        self.assertTrue(sig.actif)
        self.assertNotIn('TAQINOR', sig.corps)
        # Corps 100 % placeholders (aucun nom de société littéral).
        self.assertIn('{{ nom_societe }}', sig.corps)

    def test_seed_idempotent_pas_de_doublon(self):
        company = CompanyFactory(nom='Rejoue', slug='rejoue-sca28')
        from core.models import BrandedTemplate, TenantTheme
        from core.services import seed_tenant_branding

        seed_tenant_branding(company)
        n_theme = TenantTheme.objects.filter(company=company).count()
        n_tpl = BrandedTemplate.objects.filter(company=company).count()
        self.assertEqual(n_theme, 1)
        self.assertGreaterEqual(n_tpl, 1)

        # Deuxième passage : aucun doublon.
        res = seed_tenant_branding(company)
        self.assertEqual(res['templates_crees'], 0)
        self.assertEqual(
            TenantTheme.objects.filter(company=company).count(), n_theme)
        self.assertEqual(
            BrandedTemplate.objects.filter(company=company).count(), n_tpl)

    def test_seed_ne_remplace_pas_une_personnalisation(self):
        """Un thème/modèle déjà personnalisé n'est jamais écrasé par le seed."""
        company = CompanyFactory(nom='Perso', slug='perso-sca28')
        from core.models import BrandedTemplate, TenantTheme
        from core.selectors import EMAIL_SIGNATURE_CODE
        from core.services import seed_tenant_branding

        TenantTheme.objects.create(
            company=company, couleur_primaire='#ff0000', logo_url='logo.png')
        BrandedTemplate.objects.create(
            company=company, kind=BrandedTemplate.KIND_EMAIL,
            code=EMAIL_SIGNATURE_CODE, nom='Ma signature',
            corps='Bien à vous,\n{{ nom_societe }}')

        seed_tenant_branding(company)

        theme = TenantTheme.objects.get(company=company)
        self.assertEqual(theme.couleur_primaire, '#ff0000')
        self.assertEqual(theme.logo_url, 'logo.png')
        sig = BrandedTemplate.objects.get(
            company=company, kind=BrandedTemplate.KIND_EMAIL,
            code=EMAIL_SIGNATURE_CODE)
        self.assertEqual(sig.corps, 'Bien à vous,\n{{ nom_societe }}')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SeededSignatureRendersNeutralTest(TestCase):
    """La signature seedée est CONSOMMÉE par SCA25 à l'identique du repli neutre.

    Le corps ``L'équipe {{ nom_societe }}`` rendu par
    ``core.selectors.resolve_email_signature`` doit donner « L'équipe {nom} » —
    strictement le repli neutre historique — pour un tenant nommé « ACME ».
    """

    @classmethod
    def setUpTestData(cls):
        from authentication.models import Company
        cls.company = Company.objects.get_or_create(
            slug='sca28-acme', defaults={'nom': 'ACME Énergie'})[0]

    def test_signature_seedee_rend_le_repli_neutre(self):
        from core.services import seed_tenant_branding
        from core.selectors import resolve_email_signature

        # Sans seed : repli neutre « L'équipe ACME Énergie ».
        avant = resolve_email_signature(self.company, 'ACME Énergie')
        self.assertEqual(avant, "L'équipe ACME Énergie")

        # Après seed : la signature seedée rend EXACTEMENT la même chaîne.
        seed_tenant_branding(self.company)
        apres = resolve_email_signature(self.company, 'ACME Énergie')
        self.assertEqual(apres, "L'équipe ACME Énergie")
        self.assertNotIn('TAQINOR', apres)
