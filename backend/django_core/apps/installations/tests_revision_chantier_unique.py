"""QJR559 — accepter la V2 d'un devis signé RÉUTILISE son chantier.

ROUGE AVANT : ``create_installation_from_devis`` ne dédupliquait que sur CE
devis ; accepter la révision (D-QJR5-2) créait un SECOND chantier. Désormais
le chantier de la version remplacée est RATTACHÉ à la V2 (note de trace,
nomenclature gelée intacte).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_revision_chantier_unique"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.installations.models import Installation, InstallationActivity
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class RevisionChantierUnique(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr559-inst', defaults={'nom': 'QJR559 Inst'})
        self.user = User.objects.create_user(
            username='qjr559_inst', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR559',
            email='qjr559-inst@example.invalid')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead QJR559', stage='QUOTE_SENT',
            type_installation='residentiel')
        self.v1 = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-5591',
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')

    def _accepter(self, devis):
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')

    def test_accepter_la_v2_rattache_le_chantier_de_la_v1(self):
        self._accepter(self.v1)
        chantier = Installation.objects.get(devis=self.v1)
        bom_avant = chantier.bom

        v2 = reviser_devis(self.v1, user=self.user)
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE)
        v2.refresh_from_db()
        self._accepter(v2)

        chantiers = Installation.objects.filter(company=self.company)
        self.assertEqual(chantiers.count(), 1)
        chantier.refresh_from_db()
        self.assertEqual(chantier.devis_id, v2.pk)
        self.assertEqual(chantier.bom, bom_avant)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=chantier, body__contains=v2.reference).exists())

    def test_un_devis_sans_lien_de_revision_garde_son_propre_chantier(self):
        self._accepter(self.v1)
        autre = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-5592',
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        self._accepter(autre)
        self.assertEqual(
            Installation.objects.filter(company=self.company).count(), 2)
