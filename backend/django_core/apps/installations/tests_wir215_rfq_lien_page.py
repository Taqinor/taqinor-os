"""WIR215/XPUR21 — le lien RFQ envoyé au fournisseur mène à une PAGE.

Constat corrigé : ``_public_rfq_url`` produisait
``/api/django/public/installations/rfq/<token>/`` — le fournisseur qui ouvrait
le lien WhatsApp/email recevait du JSON brut, pas un formulaire. Le lien pointe
désormais vers la page publique ``/rfq/<token>``
(``frontend/src/pages/installations/RfqReponsePubliquePage.jsx``), qui consomme
ce même endpoint.

Run :
    python manage.py test apps.installations.tests_wir215_rfq_lien_page -v2
"""
import itertools
from urllib.parse import unquote

from django.test import TestCase, override_settings

from apps.installations.models import RFQ, RFQConsultation
from apps.installations.rfq_service import (
    _public_rfq_url, envoyer_consultation,
)

_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'wir215-co-{n}', defaults={'nom': f'WIR215 Co {n}'})
    return company


def make_user(company, role='responsable'):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=f'wir215-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_fournisseur(company, **kwargs):
    from apps.stock.models import Fournisseur
    kwargs.setdefault('nom', 'SolarImport')
    return Fournisseur.objects.create(company=company, **kwargs)


class TestLienRfqPointeVersLaPage(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.rfq = RFQ.objects.create(
            company=self.company, reference='RFQ-WIR215-1', objet='Panneaux',
            created_by=self.user)

    @override_settings(PUBLIC_BASE_URL='https://erp.example.ma')
    def test_url_publique_est_une_page_pas_un_endpoint_json(self):
        url = _public_rfq_url(None, 'JETON123')
        self.assertEqual(url, 'https://erp.example.ma/rfq/JETON123')
        self.assertNotIn('/api/django/', url)

    def test_url_publique_sans_base_reste_relative_a_la_page(self):
        url = _public_rfq_url(None, 'JETON123')
        self.assertEqual(url, '/rfq/JETON123')

    @override_settings(PUBLIC_BASE_URL='https://erp.example.ma')
    def test_message_whatsapp_porte_le_lien_de_page(self):
        fournisseur = make_fournisseur(self.company, telephone='0612345678')
        consultation = RFQConsultation.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=fournisseur)
        resultat = envoyer_consultation(consultation)
        self.assertTrue(resultat['whatsapp']['envoye'])
        # Le message est encodé dans l'URL wa.me : on le décode pour vérifier
        # que c'est bien la PAGE qui est transmise au fournisseur.
        message = unquote(resultat['whatsapp']['url'])
        self.assertIn(
            f'https://erp.example.ma/rfq/{consultation.token}', message)
        self.assertNotIn('/api/django/public/installations/rfq/', message)
