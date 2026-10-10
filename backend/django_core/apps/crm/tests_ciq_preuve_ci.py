"""CIQ515 — un devis commercial ENVOYÉ sans réalisation pro : le suivi après
devis ne porte pas la touche `j4_preuve` (jamais une villa montrée à un pro).
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.crm.cadence_plan import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile
from apps.parametres.models_realisations import Realisation
from apps.ventes.domain.envoi import mark_devis_sent
from apps.ventes.models import Devis

User = get_user_model()


class PreuveCITests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ciq515', slug='ciq515-co')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='ciq515-u', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Hôtel', owner=self.acteur,
            telephone='+212661115150', ville='Casablanca',
            type_installation=Lead.TypeInstallation.COMMERCIAL,
            tags='Décision à plusieurs')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Hôtel', email='ciq515c@example.com')

    def _realisation(self, segment):
        return Realisation.objects.create(
            company=self.company, titre=f'Chantier {segment}',
            ville='Casablanca', mise_en_service=datetime.date(2026, 7, 1),
            puissance_kwc=Decimal('30'), segment=segment,
            url_page=f'https://taqinor.ma/realisations/ciq515-{segment}/')

    def _cles_apres_envoi(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-CIQ515-20',
            client=self.client_obj, lead=self.lead, statut='brouillon',
            taux_tva=Decimal('20.00'))
        mark_devis_sent(devis=devis, user=self.acteur)
        partition = calculer_echeances_cadence(
            self.lead, 'apres_devis',
            datetime.datetime.now(datetime.timezone.utc))
        return [g.template_cle for g, _e in partition]

    def test_devis_commercial_sans_realisation_pro_pas_de_j4(self):
        self._realisation('residentiel')  # une villa n'est jamais servie
        cles = self._cles_apres_envoi()
        self.assertTrue(cles)  # le suivi démarre bien
        self.assertNotIn('j4_preuve', cles)
