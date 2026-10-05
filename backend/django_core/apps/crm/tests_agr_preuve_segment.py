"""AGR514 (D-AGR-10) — J4 « preuve » omise sans réalisation éligible.

Le gabarit après-devis garde ses 10 barreaux (jamais un axe segment, CAD124) ;
c'est la DONNÉE qui décide : `parametres.selectors.realisation_pour_lead`
(filtré par segment, AGR513) renvoie `None` → la touche `j4_preuve` est
écartée, le trou de `ordre` est gardé. Le lead porte « Décision à plusieurs »
pour que la touche dominicale (MRY4) soit comptée : 10 barreaux au complet.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile
from apps.parametres.models_realisations import Realisation
from apps.ventes.domain.cycle_vie import mark_devis_sent
from apps.ventes.models import Devis

User = get_user_model()


class _Base(TestCase):
    slug = 'agr514'
    type_installation = Lead.TypeInstallation.AGRICOLE

    def setUp(self):
        self.company = Company.objects.create(nom=self.slug, slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Exploitant', owner=self.acteur,
            telephone='+212661112233', ville='Agadir',
            type_installation=self.type_installation,
            tags='Décision à plusieurs')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client',
            email=f'{self.slug}@example.com')

    def _realisation(self, segment, ville='Agadir'):
        return Realisation.objects.create(
            company=self.company, titre=f'Chantier {segment}', ville=ville,
            mise_en_service=datetime.date(2026, 7, 1),
            puissance_kwc=Decimal('6'), segment=segment,
            url_page='https://taqinor.ma/realisations/x/')

    def _envoyer(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug}-1',
            client=self.client_obj, lead=self.lead, statut='brouillon',
            taux_tva=Decimal('20.00'))
        mark_devis_sent(devis=devis, user=self.acteur)
        return devis

    def _cles_planifiees(self):
        partition = calculer_echeances_cadence(
            self.lead, 'apres_devis', datetime.datetime.now(
                datetime.timezone.utc))
        return [g.template_cle for g, _e in partition]

    def _cles_creees(self):
        return list(self.lead.relance_etapes.filter(cadence='apres_devis')
                    .values_list('template_cle', flat=True))


class LeadAgricoleTests(_Base):
    slug = 'agr514-agri'

    def test_sans_realisation_agricole_pas_de_j4(self):
        # Une réalisation RÉSIDENTIELLE n'est jamais servie à un agricole.
        self._realisation('residentiel')
        self._envoyer()
        cles = self._cles_planifiees()
        self.assertEqual(len(cles), 9)
        self.assertNotIn('j4_preuve', cles)
        self.assertIn('dimanche_famille', cles)
        self.assertNotIn('j4_preuve', self._cles_creees())
        self.assertTrue(self._cles_creees())  # le suivi démarre bien

    def test_le_trou_de_numerotation_est_garde(self):
        self._envoyer()
        ordres = list(self.lead.relance_etapes.filter(
            cadence='apres_devis').values_list('ordre', flat=True))
        self.assertNotIn(4, ordres)
        self.assertIn(5, ordres)

    def test_avec_realisation_agricole_dix_touches_dont_j4(self):
        self._realisation('agricole')
        self._envoyer()
        cles = self._cles_planifiees()
        self.assertEqual(len(cles), 10)
        self.assertIn('j4_preuve', cles)
        self.assertIn('j4_preuve', self._cles_creees())


class LeadResidentielTests(_Base):
    slug = 'agr514-resi'
    type_installation = Lead.TypeInstallation.RESIDENTIEL

    def test_residentiel_avec_realisations_garde_ses_dix_touches(self):
        self._realisation('residentiel')
        self._realisation('agricole')  # jamais servie ; n'ôte rien
        self._envoyer()
        cles = self._cles_planifiees()
        self.assertEqual(len(cles), 10)
        self.assertIn('j4_preuve', cles)
