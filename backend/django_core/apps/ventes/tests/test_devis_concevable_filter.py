"""QJR636 — ``GET /ventes/devis/?concevable=1`` : les devis qu'on peut
calepiner, lus dans la table de modifiabilité (geste CALEPINAGE), bornés à la
société, jamais limités à la première page côté client.

Run :
    python manage.py test apps.ventes.tests.test_devis_concevable_filter -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.selectors import contexte_conception_devis, devis_concevables
from authentication.models import Company

User = get_user_model()


class DevisConcevableFilterTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Conc A', slug='conc-a-636')
        self.autre = Company.objects.create(nom='Conc B', slug='conc-b-636')
        self.user = User.objects.create_user(
            username='conc636', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_a = Client.objects.create(company=self.company, nom='CA')
        self.client_b = Client.objects.create(company=self.autre, nom='CB')
        self.n = 0
        self.brouillon = self._devis(statut=Devis.Statut.BROUILLON)
        for _ in range(55):
            self._devis(statut=Devis.Statut.ACCEPTE)
        self.envoye = self._devis(statut=Devis.Statut.ENVOYE)
        self.agricole = self._devis(
            statut=Devis.Statut.BROUILLON,
            mode_installation=Devis.ModeInstallation.AGRICOLE)
        self.multi = self._devis(statut=Devis.Statut.BROUILLON)
        self.multi.lignes.create(
            designation='Panneau villa 2', quantite=Decimal('1'),
            prix_unitaire=Decimal('100'), groupe_index=1)
        self.etranger = self._devis(statut=Devis.Statut.BROUILLON,
                                    company=self.autre, client=self.client_b)

    def _devis(self, *, company=None, client=None, **extra):
        self.n += 1
        return Devis.objects.create(
            company=company or self.company, client=client or self.client_a,
            reference=f'DEV-QJR636-{self.n}', created_by=self.user, **extra)

    def test_filtre_serveur_rend_exactement_brouillon_et_envoye(self):
        resp = self.api.get('/api/django/ventes/devis/',
                            {'concevable': '1', 'page_size': 100})
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertEqual(sorted(r['id'] for r in rows),
                         sorted([self.brouillon.id, self.envoye.id]))

    def test_sans_le_parametre_la_liste_est_inchangee(self):
        resp = self.api.get('/api/django/ventes/devis/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.data['count'], 2)

    def test_presence_equivaut_a_design_context_modifiable(self):
        concevables = set(devis_concevables(
            Devis.objects.filter(company=self.company)).values_list(
                'id', flat=True))
        un_accepte = Devis.objects.filter(
            company=self.company, statut=Devis.Statut.ACCEPTE).first()
        for devis in (self.brouillon, self.envoye, self.agricole, self.multi,
                      un_accepte):
            contexte = contexte_conception_devis(devis, self.company)
            self.assertEqual(devis.id in concevables, contexte['modifiable'],
                             devis.reference)
