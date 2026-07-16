"""Tests YSERV4 — ``core.events.chantier_receptionne`` (émis par
``apps.installations`` au franchissement du chantier vers RECEPTIONNE) crée
idempotemment une ``EnqueteNPS`` pour le client (une par chantier, jamais de
doublon même en cas de ré-émission) et route l'envoi via ``envoyer_enquete_
nps`` (gated Brevo — no-op sans clé, comportement FG238 inchangé). ``apps.
installations`` n'est jamais importée par ``apps.compta`` : les instances
transitent par les arguments du signal, comme le reste de ce module."""
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.compta.models import EnqueteNPS
from apps.crm.models import Client
from core.events import chantier_receptionne

from apps.compta import receivers  # noqa: F401  (câblage ready())


def make_company(slug='yserv4-co', nom='YSERV4 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class _FakeInstallation:
    """Substitut léger : le récepteur ne lit que ``company``/``client_id``/
    ``id`` sur l'instance envoyée par le signal (jamais un import du modèle
    ``installations.Installation`` depuis ``apps.compta``)."""

    def __init__(self, company, client_id, installation_id=1):
        self.company = company
        self.client_id = client_id
        self.id = installation_id


class TestChantierReceptionneCreeEnqueteNPS(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YSERV4',
            email='yserv4@example.com', telephone='+212600000041')
        self.inst = _FakeInstallation(self.company, self.client_obj.id, 101)

    def test_signal_creates_one_enquete(self):
        chantier_receptionne.send(
            sender=object, installation=self.inst, user=None,
            ancien_statut='installe')
        qs = EnqueteNPS.objects.filter(
            company=self.company, chantier_id=self.inst.id)
        self.assertEqual(qs.count(), 1)
        enquete = qs.first()
        self.assertEqual(enquete.client_id, self.client_obj.id)

    def test_reemission_creates_no_duplicate(self):
        chantier_receptionne.send(
            sender=object, installation=self.inst, user=None,
            ancien_statut='installe')
        chantier_receptionne.send(
            sender=object, installation=self.inst, user=None,
            ancien_statut='installe')
        qs = EnqueteNPS.objects.filter(
            company=self.company, chantier_id=self.inst.id)
        self.assertEqual(qs.count(), 1)

    def test_no_send_without_brevo_key(self):
        chantier_receptionne.send(
            sender=object, installation=self.inst, user=None,
            ancien_statut='installe')
        enquete = EnqueteNPS.objects.get(
            company=self.company, chantier_id=self.inst.id)
        self.assertFalse(enquete.envoi_reel)
        self.assertEqual(enquete.statut, EnqueteNPS.Statut.ENVOYEE)

    @override_settings(BREVO_ENABLED=True, BREVO_API_KEY='test-key')
    def test_send_marks_envoi_reel_with_brevo_key(self):
        chantier_receptionne.send(
            sender=object, installation=self.inst, user=None,
            ancien_statut='installe')
        enquete = EnqueteNPS.objects.get(
            company=self.company, chantier_id=self.inst.id)
        self.assertTrue(enquete.envoi_reel)

    def test_no_client_id_is_noop(self):
        inst_sans_client = _FakeInstallation(self.company, None, 202)
        chantier_receptionne.send(
            sender=object, installation=inst_sans_client, user=None,
            ancien_statut='installe')
        self.assertEqual(
            EnqueteNPS.objects.filter(
                company=self.company, chantier_id=202).count(),
            0)


class TestChantierReceptionneMultiTenant(TestCase):
    def setUp(self):
        self.company_a = make_company(slug='yserv4-a', nom='YSERV4 A')
        self.company_b = make_company(slug='yserv4-b', nom='YSERV4 B')
        self.client_a = Client.objects.create(
            company=self.company_a, nom='Client', prenom='A',
            email='yserv4-a@example.com', telephone='+212600000042')
        self.client_b = Client.objects.create(
            company=self.company_b, nom='Client', prenom='B',
            email='yserv4-b@example.com', telephone='+212600000043')

    def test_enquete_scoped_to_its_own_company(self):
        inst_a = _FakeInstallation(self.company_a, self.client_a.id, 301)
        inst_b = _FakeInstallation(self.company_b, self.client_b.id, 301)
        chantier_receptionne.send(
            sender=object, installation=inst_a, user=None,
            ancien_statut='installe')
        chantier_receptionne.send(
            sender=object, installation=inst_b, user=None,
            ancien_statut='installe')
        self.assertEqual(
            EnqueteNPS.objects.filter(company=self.company_a).count(), 1)
        self.assertEqual(
            EnqueteNPS.objects.filter(company=self.company_b).count(), 1)
        enquete_a = EnqueteNPS.objects.get(company=self.company_a)
        self.assertEqual(enquete_a.client_id, self.client_a.id)
