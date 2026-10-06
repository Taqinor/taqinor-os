"""CIQ610 — chantier : niveau de tension et puissance souscrite, recopiés du
lead (colonnes CIQ1) à la création depuis le devis accepté.

Run :
    python manage.py test apps.installations.tests_ciq610_niveau_tension -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client, Lead
from apps.installations.models import Installation
from apps.installations.serializers import InstallationSerializer
from apps.ventes.models import Devis
from authentication.models import Company
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class NiveauTensionChantierTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ610', slug='ciq610-co')
        self.user = User.objects.create_user(
            username='ciq610_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Hôtel', prenom='CIQ610',
            email='ciq610@example.com')
        self._num = 0

    def _accepter(self, mode, **lead_kwargs):
        self._num += 10
        lead = Lead.objects.create(
            company=self.company, nom=f'Lead {self._num}',
            type_installation=mode, **lead_kwargs)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{self._num:04d}',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation=mode,
            etude_params={'puissance_kwc': 120})
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')
        return Installation.objects.get(devis=devis, company=self.company)

    def test_commercial_mt_mesure_en_visite(self):
        chantier = self._accepter(
            'commercial', tension_raccordement='mt',
            tension_source='mesure_visite',
            compteur_puissance_kva=Decimal('250'))
        self.assertEqual(chantier.type_installation, 'industriel')
        self.assertEqual(chantier.niveau_tension, 'mt')
        self.assertEqual(chantier.niveau_tension_source, 'mesure_visite')
        self.assertEqual(chantier.puissance_souscrite_kva, Decimal('250'))

    def test_niveau_declare(self):
        chantier = self._accepter(
            'industriel', tension_raccordement='bt', tension_source='facture')
        self.assertEqual(chantier.niveau_tension, 'bt')
        self.assertEqual(chantier.niveau_tension_source, 'declare')
        self.assertIsNone(chantier.puissance_souscrite_kva)

    def test_lead_sans_niveau_reste_null(self):
        chantier = self._accepter('commercial')
        self.assertIsNone(chantier.niveau_tension)
        self.assertIsNone(chantier.niveau_tension_source)
        self.assertIsNone(chantier.puissance_souscrite_kva)

    def test_ne_sait_pas_et_defaut_du_site_jamais_copies(self):
        for tension, source in (('ne_sait_pas', 'declare'),
                                ('bt', 'site_defaut_visible')):
            chantier = self._accepter(
                'commercial', tension_raccordement=tension,
                tension_source=source)
            self.assertIsNone(chantier.niveau_tension)
            self.assertIsNone(chantier.niveau_tension_source)

    def test_residentiel_identique(self):
        chantier = self._accepter(
            'residentiel', tension_raccordement='bt', tension_source='declare',
            compteur_puissance_kva=Decimal('9'))
        self.assertIsNone(chantier.niveau_tension)
        self.assertIsNone(chantier.niveau_tension_source)
        self.assertIsNone(chantier.puissance_souscrite_kva)

    def test_editable_sur_la_fiche(self):
        chantier = self._accepter('commercial')
        ser = InstallationSerializer(
            chantier, data={'niveau_tension': 'bt',
                            'puissance_souscrite_kva': '60'}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        chantier.refresh_from_db()
        self.assertEqual(chantier.niveau_tension, 'bt')
        self.assertEqual(
            InstallationSerializer(chantier).data['niveau_tension_display'],
            'Basse tension (BT)')
