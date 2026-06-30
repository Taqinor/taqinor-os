"""DC1 — l'identité société (RC/ICE/RIB/banque/adresse/tél/nom) du moteur de
devis premium vient de CompanyProfile, plus codée en dur.

- Sans profil renseigné → repli STRICT sur les littéraux historiques Taqinor
  (PDF byte-identique, pas de régression).
- Profil renseigné → le moteur expose les coordonnées de CETTE société et plus
  jamais le RIB Taqinor (correctif multi-tenant + fuite RIB).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_dc1_company_identity -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.tests.test_quote_engine import (
    make_company, make_user, make_client, make_devis,
)
from apps.ventes.utils.company_settings import entreprise_for, ENTREPRISE_DEFAULTS


class TestEntrepriseFor(TestCase):
    def test_no_company_returns_historical_defaults(self):
        ent = entreprise_for(None)
        self.assertEqual(ent['rc'], '691213')
        self.assertEqual(ent['ice'], '003799642000067')
        self.assertEqual(ent['banque'], 'Saham Bank')
        self.assertEqual(ent['nom'], 'TAQINOR')
        # aucune valeur n'est None — les renderers peuvent l'utiliser tel quel
        self.assertTrue(all(v is not None for v in ent.values()))

    def test_blank_profile_falls_back_to_literals(self):
        """Une société sans champ d'identité renseigné garde EXACTEMENT les
        valeurs historiques → PDF inchangé."""
        company = make_company()
        ent = entreprise_for(company)
        for key, default in ENTREPRISE_DEFAULTS.items():
            self.assertEqual(ent[key], default, f'{key} doit rester le défaut')

    def test_populated_profile_overrides_each_field(self):
        from authentication.models import Company
        from apps.parametres.models import CompanyProfile
        company = Company.objects.create(slug='other-co', nom='Énergie Sud SARL')
        prof = CompanyProfile.get(company=company)
        prof.nom = 'Énergie Sud SARL'
        prof.rc = '123456'
        prof.ice = '999888777666555'
        prof.rib = '011 111 0001111111111111 22'
        prof.banque = 'CIH Bank'
        prof.adresse = '12 Avenue Hassan II, Agadir'
        prof.telephone = '+212 5 28 00 00 00'
        prof.email = 'contact@energiesud.ma'
        prof.save()

        ent = entreprise_for(company)
        self.assertEqual(ent['nom'], 'Énergie Sud SARL')
        self.assertEqual(ent['raison_sociale'], 'Énergie Sud SARL')
        self.assertEqual(ent['rc'], '123456')
        self.assertEqual(ent['ice'], '999888777666555')
        self.assertEqual(ent['rib'], '011 111 0001111111111111 22')
        self.assertEqual(ent['banque'], 'CIH Bank')
        # plus jamais le RIB / RC Taqinor pour une autre société
        self.assertNotIn('691213', ent.values())
        self.assertNotEqual(ent['rib'], ENTREPRISE_DEFAULTS['rib'])


class TestBuildQuoteDataEntreprise(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_entreprise_injected_into_quote_data(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ], reference='DEV-DC1-0001')
        data = build_quote_data(devis)
        self.assertIn('entreprise', data)
        ent = data['entreprise']
        # JSON-sérialisable (cette donnée transite par l'endpoint proposal)
        self.assertIsInstance(ent, dict)
        self.assertEqual(ent['rc'], '691213')
        self.assertEqual(ent['ice'], '003799642000067')

    def test_other_company_quote_carries_its_own_identity(self):
        from authentication.models import Company
        from apps.parametres.models import CompanyProfile
        from apps.ventes.quote_engine import build_quote_data
        company = Company.objects.create(slug='dc1-co', nom='Soleil Atlas')
        prof = CompanyProfile.get(company=company)
        prof.rc = '654321'
        prof.banque = 'Bank Of Africa'
        prof.save()
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.create_user(
            username='dc1u', password='x', role_legacy='responsable',
            company=company)
        from apps.crm.models import Client
        cl = Client.objects.create(
            company=company, nom='X', prenom='Y', email='x@y.z',
            telephone='+212600000001', adresse='Marrakech')
        devis = make_devis(company, u, cl, [
            ('Panneau mono 450W', '8', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ], reference='DEV-DC1-0002')
        ent = build_quote_data(devis)['entreprise']
        self.assertEqual(ent['rc'], '654321')
        self.assertEqual(ent['banque'], 'Bank Of Africa')
        self.assertEqual(ent['rib'], ENTREPRISE_DEFAULTS['rib'])  # non renseigné → défaut

    def test_taux_tva_unaffected(self):
        # garde-fou : l'injection identité ne touche pas les autres clés
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ], reference='DEV-DC1-0003')
        data = build_quote_data(devis)
        self.assertEqual(Decimal(str(data['taux_tva'])), Decimal('20'))
