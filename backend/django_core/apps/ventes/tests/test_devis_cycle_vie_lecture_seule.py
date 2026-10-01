"""QJR541 (Groupe QJR5) — le statut et les champs de CYCLE DE VIE d'un devis
sont en LECTURE SEULE au PATCH/POST du corps.

``statut``, ``date_envoi``, ``date_acceptation``, ``accepte_par_nom``,
``date_refus``, ``motif_refus``, ``option_acceptee``, ``superseded_by``,
``version_parent`` et ``version`` sont dans ``read_only_fields`` : DRF les
IGNORE (200, jamais un 400). Un envoi passe par ses portes dédiées (lien,
courriel, WhatsApp — ``mark_devis_sent``), une acceptation par ``/accepter/`` ;
le funnel CRM avance par les événements ``devis_sent`` / ``devis_accepted``,
plus par un ``avancer_stage_pour_devis`` direct de la vue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.crm.stages import NEW
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class TestDevisCycleVieLectureSeule(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='QJR541 Co', slug='qjr541-co')
        cls.user = User.objects.create_user(
            username='qjr541_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client', prenom='QJR541',
            email='qjr541@example.com', telephone='+212600005410')

    def setUp(self):
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, num, statut, **extra):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{5410 + num * 10}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            **extra)

    def _patch(self, devis, corps):
        return self.api.patch(
            f'/api/django/ventes/devis/{devis.id}/', corps, format='json')

    def test_patch_brouillon_sur_envoye_ignore_note_ecrite(self):
        devis = self._devis(1, Devis.Statut.ENVOYE)
        r = self._patch(devis, {'statut': 'brouillon', 'note': 'x'})
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.note, 'x')

    def test_patch_envoye_sur_brouillon_reste_brouillon(self):
        devis = self._devis(2, Devis.Statut.BROUILLON)
        r = self._patch(devis, {'statut': 'envoye'})
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertIsNone(devis.date_envoi)

    def test_patch_option_acceptee_inchangee(self):
        devis = self._devis(3, Devis.Statut.ENVOYE)
        avant = devis.option_acceptee
        r = self._patch(devis, {'option_acceptee': 'avec_batterie',
                                'accepte_par_nom': 'Pirate',
                                'motif_refus': 'x', 'version': 9})
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.option_acceptee, avant)
        self.assertNotEqual(devis.accepte_par_nom, 'Pirate')
        self.assertNotEqual(devis.version, 9)

    def test_post_envoye_cree_un_brouillon_sans_avancer_le_lead(self):
        lead = Lead.objects.create(company=self.company, nom='Lead QJR541')
        self.assertEqual(lead.stage, NEW)
        r = self.api.post('/api/django/ventes/devis/', {
            'statut': 'envoye', 'lead': lead.id, 'client': self.client_obj.id,
            'taux_tva': '20',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        devis = Devis.objects.get(pk=r.data['id'])
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertIsNone(devis.date_envoi)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, NEW)

    def test_is_active_reste_ecrivable(self):
        devis = self._devis(4, Devis.Statut.BROUILLON)
        r = self._patch(devis, {'is_active': False})
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertFalse(devis.is_active)
