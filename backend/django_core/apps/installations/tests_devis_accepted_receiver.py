"""U6 — Auto-création du chantier à l'acceptation d'un devis (M6).

L'app ``installations`` s'abonne à l'événement métier ``core.events.devis_accepted``
(via ``apps/installations/receivers.py``, câblé par ``InstallationsConfig.ready``)
pour créer AUTOMATIQUEMENT le chantier correspondant — sans que ``ventes`` importe
``installations``. Ces tests couvrent :

  * create-once : émettre ``devis_accepted`` crée EXACTEMENT un chantier,
    atteignable dans la liste des chantiers ;
  * idempotence : ré-émettre l'événement (ou un devis déjà doté d'un chantier)
    ne crée AUCUN second chantier ;
  * end-to-end : POST .../accepter/ déclenche l'auto-création (preuve que
    l'abonnement ``ready()`` est bien en place) ;
  * multi-tenant : le chantier porte la société du devis, et la liste d'une
    société ne montre jamais le chantier d'une autre.

Run :
    docker compose exec django_core python manage.py test \
        apps.installations.tests_devis_accepted_receiver -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Installation
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestDevisAcceptedCreatesChantier(TestCase):
    def setUp(self):
        self.company = _make_company('u6-co', 'U6 Co')
        self.user = User.objects.create_user(
            username='u6_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = _auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='U6',
            email='u6@example.com', telephone='+212600000006')

    def _devis(self, num, statut=Devis.Statut.ENVOYE, lead=None):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, lead=lead, statut=statut,
            taux_tva=Decimal('20'), mode_installation='residentiel')

    def test_signal_creates_exactly_one_chantier(self):
        """Émettre ``devis_accepted`` crée un chantier atteignable dans la
        liste — preuve que l'abonnement (ready()) est câblé."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead U6', stage='QUOTE_SENT',
            type_installation='residentiel')
        devis = self._devis(num=1, statut=Devis.Statut.ACCEPTE, lead=lead)
        self.assertFalse(
            Installation.objects.filter(devis=devis).exists())

        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')

        chantiers = Installation.objects.filter(devis=devis,
                                                company=self.company)
        self.assertEqual(chantiers.count(), 1)
        inst = chantiers.first()
        self.assertEqual(inst.company_id, self.company.id)
        self.assertEqual(inst.client_id, self.client_obj.id)
        # Atteignable via la liste des chantiers de la société.
        self.assertIn(
            inst.id,
            list(Installation.objects.filter(company=self.company)
                 .values_list('id', flat=True)))

    def test_re_emitting_signal_does_not_duplicate(self):
        """Ré-émettre l'événement (re-acceptation) ne crée pas de doublon."""
        devis = self._devis(num=2, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='accepte')
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='accepte')
        self.assertEqual(
            Installation.objects.filter(devis=devis).count(), 1)

    def test_endpoint_accept_auto_creates_chantier(self):
        """Bout en bout : POST .../accepter/ déclenche l'auto-création."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead E2E', stage='QUOTE_SENT',
            type_installation='residentiel')
        devis = self._devis(num=3, lead=lead)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-10'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            Installation.objects.filter(devis=devis,
                                        company=self.company).count(), 1)

    def test_company_scoped_isolation(self):
        """Le chantier porte la société du devis ; une autre société ne le
        voit pas dans sa liste (multi-tenant)."""
        other_company = _make_company('u6-other', 'U6 Other')
        devis = self._devis(num=4, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')

        inst = Installation.objects.get(devis=devis)
        self.assertEqual(inst.company_id, self.company.id)
        # La liste de l'autre société ne contient pas ce chantier.
        self.assertFalse(
            Installation.objects.filter(company=other_company,
                                        devis=devis).exists())
