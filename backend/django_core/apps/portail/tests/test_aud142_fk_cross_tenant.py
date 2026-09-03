"""Tests AUD142 — les FK cross-app des 5 ressources portail refusent l'id
d'une AUTRE société.

Défaut d'origine : ``devis_id``, ``facture_id``, ``client_id``, ``lead_id`` et
``chantier_id`` étaient de simples ``IntegerField(min_value=0)`` — aucun
``validate_*``, aucun queryset borné. Les ``perform_create`` ne posaient que
``company=request.user.company`` (SEUL ``ComptePortailClientViewSet``
vérifiait l'appartenance), et les FK portent ``db_constraint=False`` : la base
ne vérifiait ni existence ni tenant. Un Responsable de la société A créait donc
une ligne de paiement portail pointant sur la facture de la société B, et le
client de A voyait apparaître le montant d'un tiers.

Note de drain : AUD140 a fermé ENTIÈREMENT l'écriture ERP sur deux des cinq
ressources (acceptation de devis, paiement de facture) — leur POST répond 405,
ce qui satisfait « jamais 201 » plus fortement qu'un 400. Les validateurs y
sont malgré tout posés (défense en profondeur) et exercés ici AU NIVEAU
SERIALIZER, pour qu'une réouverture future de ces surfaces naisse gardée.

Ces tests étaient ROUGES avant le correctif (201 sur les cinq).

Run :
    python manage.py test apps.portail.tests.test_aud142_fk_cross_tenant -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from apps.compta.serializers import (
    AcceptationDevisPortailSerializer,
    DemandeTicketPortailSerializer,
    DocumentClientPortailSerializer,
    JalonChantierPortailSerializer,
    PaiementFacturePortailSerializer,
)
from apps.crm.models import Client, Lead
from apps.facturation.models import Facture
from apps.installations.models import Installation
from apps.portail.models import (
    DemandeTicketPortail,
    DocumentClientPortail,
    JalonChantierPortail,
)
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD142-{n}',
        email=f'aud142-{company.id}-{n}@example.invalid')


def make_responsable(company, username):
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role_legacy='responsable')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def contexte(user):
    """Contexte serializer minimal portant l'utilisateur (donc sa société)."""
    request = APIRequestFactory().post('/')
    request.user = user
    return {'request': request}


class FkCrossTenantPortailTests(TestCase):
    def setUp(self):
        self.a = make_company('aud142-co-a', 'AUD142 Société A')
        self.b = make_company('aud142-co-b', 'AUD142 Société B')
        self.user_a = make_responsable(self.a, 'aud142-resp-a')
        self.api = auth(self.user_a)

        # Objets appartenant à la société B — jamais atteignables depuis A.
        self.client_b = make_client_crm(self.b, 'Beta')
        self.lead_b = Lead.objects.create(company=self.b, nom='Lead Beta')
        self.chantier_b = Installation.objects.create(
            company=self.b, reference='CHT-AUD142-B')
        self.devis_b = Devis.objects.create(
            company=self.b, reference='DEV-AUD142-B', client=self.client_b,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))
        self.facture_b = Facture.objects.create(
            company=self.b, reference='FAC-AUD142-B', client=self.client_b)

        # Les mêmes objets, côté A — le témoin « ça passe quand c'est à moi ».
        self.client_a = make_client_crm(self.a, 'Alpha')
        self.chantier_a = Installation.objects.create(
            company=self.a, reference='CHT-AUD142-A')

    # ── Les 3 ressources encore écrivables : 400, jamais 201 ────────────────

    def test_document_client_dun_autre_tenant_refuse(self):
        """ROUGE avant AUD142 : 201."""
        res = self.api.post('/api/django/portail/documents-client-portail/', {
            'client_id': self.client_b.id, 'type_document': 'facture_onee',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.content)
        self.assertFalse(DocumentClientPortail.objects.filter(
            client_id=self.client_b.id).exists())

    def test_document_lead_dun_autre_tenant_refuse(self):
        res = self.api.post('/api/django/portail/documents-client-portail/', {
            'client_id': self.client_a.id, 'lead_id': self.lead_b.id,
        }, format='json')
        self.assertEqual(res.status_code, 400, res.content)

    def test_jalon_chantier_dun_autre_tenant_refuse(self):
        """ROUGE avant AUD142 : 201."""
        res = self.api.post('/api/django/portail/jalons-chantier-portail/', {
            'chantier_id': self.chantier_b.id, 'libelle': 'Installation',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.content)
        self.assertFalse(JalonChantierPortail.objects.filter(
            chantier_id=self.chantier_b.id).exists())

    def test_demande_ticket_dun_autre_tenant_refusee(self):
        """ROUGE avant AUD142 : 201."""
        res = self.api.post('/api/django/portail/demandes-ticket-portail/', {
            'client_id': self.client_b.id, 'sujet': 'Onduleur',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.content)
        self.assertFalse(DemandeTicketPortail.objects.filter(
            client_id=self.client_b.id).exists())

    def test_demande_ticket_chantier_dun_autre_tenant_refusee(self):
        res = self.api.post('/api/django/portail/demandes-ticket-portail/', {
            'client_id': self.client_a.id, 'sujet': 'Onduleur',
            'chantier_id': self.chantier_b.id,
        }, format='json')
        self.assertEqual(res.status_code, 400, res.content)

    def test_les_objets_de_ma_societe_passent_toujours(self):
        res = self.api.post('/api/django/portail/demandes-ticket-portail/', {
            'client_id': self.client_a.id, 'sujet': 'Onduleur',
            'chantier_id': self.chantier_a.id,
        }, format='json')
        self.assertEqual(res.status_code, 201, res.content)

    # ── Les 2 ressources fermées par AUD140 : 405 à l'API, garde au ────────
    #    niveau serializer (défense en profondeur)

    def test_acceptation_et_paiement_ne_sont_plus_creables_du_tout(self):
        for chemin, corps in (
            ('acceptations-devis-portail',
             {'devis_id': self.devis_b.id, 'nom_signataire': 'X'}),
            ('paiements-facture-portail',
             {'facture_id': self.facture_b.id, 'montant': '1.00'}),
        ):
            with self.subTest(chemin=chemin):
                res = self.api.post(
                    f'/api/django/portail/{chemin}/', corps, format='json')
                self.assertEqual(res.status_code, 405, res.content)

    def test_le_serializer_acceptation_refuse_un_devis_dun_autre_tenant(self):
        ser = AcceptationDevisPortailSerializer(
            data={'devis_id': self.devis_b.id, 'nom_signataire': 'X'},
            context=contexte(self.user_a))
        self.assertFalse(ser.is_valid())
        self.assertIn('devis_id', ser.errors)

    def test_le_serializer_paiement_refuse_une_facture_dun_autre_tenant(self):
        ser = PaiementFacturePortailSerializer(
            data={'facture_id': self.facture_b.id, 'montant': '1.00'},
            context=contexte(self.user_a))
        self.assertFalse(ser.is_valid())
        self.assertIn('facture_id', ser.errors)

    # ── Les cinq serializers, en un seul balayage ───────────────────────────

    def test_les_cinq_serializers_refusent_lid_dun_autre_tenant(self):
        cas = (
            (AcceptationDevisPortailSerializer,
             {'devis_id': self.devis_b.id, 'nom_signataire': 'X'}, 'devis_id'),
            (PaiementFacturePortailSerializer,
             {'facture_id': self.facture_b.id, 'montant': '1.00'},
             'facture_id'),
            (DocumentClientPortailSerializer,
             {'client_id': self.client_b.id}, 'client_id'),
            (JalonChantierPortailSerializer,
             {'chantier_id': self.chantier_b.id, 'libelle': 'X'},
             'chantier_id'),
            (DemandeTicketPortailSerializer,
             {'client_id': self.client_b.id, 'sujet': 'X'}, 'client_id'),
        )
        for classe, donnees, champ in cas:
            with self.subTest(serializer=classe.__name__):
                ser = classe(data=donnees, context=contexte(self.user_a))
                self.assertFalse(ser.is_valid())
                self.assertIn(champ, ser.errors)

    def test_un_id_inexistant_est_refuse_comme_un_id_dun_autre_tenant(self):
        """Aucun oracle : « d'une autre société » et « inexistant » se
        confondent dans le même message."""
        ser = DocumentClientPortailSerializer(
            data={'client_id': 987654321}, context=contexte(self.user_a))
        self.assertFalse(ser.is_valid())
        self.assertIn('client_id', ser.errors)
