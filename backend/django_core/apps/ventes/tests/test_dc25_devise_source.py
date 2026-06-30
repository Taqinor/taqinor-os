"""DC25 — UNE source devise + taux de change (FG52) pour devis/facture/UBL.

`selectors.devise_for` est l'unique résolveur : devise portée par le document →
devise par défaut de la société (CompanyProfile.devise_defaut) → « MAD ». L'export
UBL (dgi_export.build_ubl_xml) et le builder de devis le consomment, remplaçant
les `getattr(..., 'devise') or 'MAD'` épars. Aucune conversion de montant.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_dc25_devise_source -v 2
"""
from decimal import Decimal

from django.test import TestCase


def _make_company(slug, nom):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestDeviseFor(TestCase):
    def test_document_devise_wins(self):
        from apps.ventes.selectors import devise_for

        class Doc:
            devise = 'eur'
            taux_change = Decimal('0.092')
            company = None
        dev, taux = devise_for(Doc())
        self.assertEqual(dev, 'EUR')          # normalisée en majuscules
        self.assertEqual(taux, Decimal('0.092'))

    def test_falls_back_to_company_default(self):
        from apps.ventes.selectors import devise_for
        from apps.parametres.models import CompanyProfile
        company = _make_company('dc25-co', 'DC25 Co')
        prof = CompanyProfile.get(company=company)
        prof.devise_defaut = 'USD'
        prof.save()

        class Doc:
            devise = ''       # document sans devise → défaut société
            taux_change = None
            company = None
        Doc.company = company
        dev, taux = devise_for(Doc())
        self.assertEqual(dev, 'USD')
        self.assertEqual(taux, Decimal('1'))  # pas de taux → 1, aucune conversion

    def test_ultimate_fallback_mad(self):
        from apps.ventes.selectors import devise_for

        class Doc:
            devise = None
            taux_change = None
            company = None
        dev, taux = devise_for(Doc())
        self.assertEqual(dev, 'MAD')
        self.assertEqual(taux, Decimal('1'))


class TestUblUsesResolver(TestCase):
    def test_ubl_currency_from_company_default(self):
        from apps.crm.models import Client
        from apps.parametres.models import CompanyProfile
        from apps.ventes.models import Facture
        from apps.ventes.dgi.dgi_export import build_ubl_xml
        company = _make_company('dc25-ubl', 'DC25 UBL')
        prof = CompanyProfile.get(company=company)
        prof.devise_defaut = 'EUR'
        prof.nom = 'DC25 UBL'
        prof.ice = '001122334455667'
        prof.save()
        client = Client.objects.create(
            company=company, nom='X', prenom='Y', telephone='+212600000050')
        # Facture sans devise explicite → l'UBL doit prendre le défaut société.
        facture = Facture.objects.create(
            company=company, reference='FAC-DC25', client=client,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'), devise='')
        xml = build_ubl_xml(facture, profile=prof)
        self.assertIn('DocumentCurrencyCode', xml)
        self.assertIn('>EUR<', xml)
        self.assertNotIn('>MAD<', xml)

    def test_explicit_currency_arg_still_honored(self):
        from apps.crm.models import Client
        from apps.parametres.models import CompanyProfile
        from apps.ventes.models import Facture
        from apps.ventes.dgi.dgi_export import build_ubl_xml
        company = _make_company('dc25-ubl2', 'DC25 UBL2')
        prof = CompanyProfile.get(company=company)
        prof.nom = 'DC25 UBL2'
        prof.ice = '001122334455668'
        prof.save()
        client = Client.objects.create(
            company=company, nom='X', prenom='Y', telephone='+212600000051')
        facture = Facture.objects.create(
            company=company, reference='FAC-DC25-2', client=client,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))
        xml = build_ubl_xml(facture, profile=prof, currency='USD')
        self.assertIn('DocumentCurrencyCode', xml)
        self.assertIn('>USD<', xml)
