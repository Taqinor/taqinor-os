"""QJR559 — accepter la V2 d'un devis signé ne crée jamais un second contrat
d'entretien.

ROUGE AVANT : ``creer_contrat_depuis_devis_accepte`` dédupliquait sur le
marqueur ``[devis:<pk>]`` de CE devis seulement ; la révision acceptée
(D-QJR5-2) créait un second ``ContratMaintenance``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.sav.tests_revision_contrat_unique"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance
from apps.stock.models import Produit
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class RevisionContratUnique(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr559-sav', defaults={'nom': 'QJR559 Sav'})
        self.user = User.objects.create_user(
            username='qjr559_sav', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR559',
            email='qjr559-sav@example.invalid')
        self.recurrent = Produit.objects.create(
            company=self.company, nom='Monitoring annuel', sku='MON-QJR559',
            prix_achat=0, prix_vente=1200, est_recurrent=True)
        self.v1 = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-5593',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=self.v1, produit=self.recurrent,
            designation='Monitoring annuel', quantite=1,
            prix_unitaire=Decimal('1200'), taux_tva=Decimal('20'))

    def _accepter(self, devis):
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')

    def test_la_v2_acceptee_ne_cree_pas_de_second_contrat(self):
        self._accepter(self.v1)
        self.assertEqual(ContratMaintenance.objects.filter(
            client=self.client_obj).count(), 1)

        v2 = reviser_devis(self.v1, user=self.user)
        self.assertTrue(v2.lignes.exists())
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE)
        v2.refresh_from_db()
        self._accepter(v2)

        self.assertEqual(ContratMaintenance.objects.filter(
            client=self.client_obj).count(), 1)
