"""ADOC131 (D-ADOC-4) — le lien public d'un devis accepté vit jusqu'à la
réception du chantier + 90 jours, et se révoque.

Rejoue la sonde #112 (ttl_jours=30, chantier en cours, J+31 → 404, aucun champ
de révocation) : à J+31 le suivi répond désormais 200 ; à la réception
(``core.events.chantier_receptionne``, émis par la VRAIE transition de statut
du chantier) l'échéance devient réception + 90 jours ; la révocation coupe le
suivi ET la proposition (même jeton). Horloge figée (freezegun), aucune source
mockée — seuls les effets d'entrée-sortie de l'acceptation (PDF scellé,
courriels) sont neutralisés.

Test-du-test : retirer la branche ``suivi_prolonge_le`` de
``ShareLink.is_valid`` ⇒ ``test_lien_vivant_apres_30_jours_chantier_en_cours``
échoue ; ignorer ``revoque_le`` ⇒ ``test_revocation_coupe_suivi_et_proposition``
échoue.
"""
import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.services import (
    changer_statut_chantier, create_installation_from_devis,
)
from apps.ventes.domain.cycle_vie import accept_devis
from apps.ventes.models import Devis, ShareLink
from authentication.models import Company

User = get_user_model()

T0 = datetime.datetime(2026, 8, 1, 10, 0, 0)


def _jour(n):
    return (T0 + datetime.timedelta(days=n)).strftime('%Y-%m-%d %H:%M:%S')


@patch('apps.ventes.domain.cycle_vie._send_acceptance_emails')
@patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
class SuiviProlongationTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ADOC131 Co')
        self.user = User.objects.create_user(
            username='adoc131', password='x', company=self.company,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADOC131',
            telephone='+212600000131')
        with freeze_time(_jour(0)):
            self.devis = Devis.objects.create(
                company=self.company, reference='DEV-202608-ADOC13101',
                client=self.client_obj, statut=Devis.Statut.ENVOYE,
                taux_tva=Decimal('20'))
            self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _accepter(self):
        with freeze_time(_jour(0)):
            accept_devis(devis=self.devis, user=self.user, nom='Client',
                         option=Devis.OptionAcceptee.SANS_BATTERIE)

    def _suivi(self, jour):
        with freeze_time(_jour(jour)):
            return self.api.get(
                f'/api/django/ventes/suivi/{self.link.token}/').status_code

    def _receptionner(self, jour):
        with freeze_time(_jour(5)):
            chantier, _ = create_installation_from_devis(
                self.devis, self.user, self.company)
        with freeze_time(_jour(jour)):
            changer_statut_chantier(
                chantier, 'receptionne', self.user, verifier_gates=False)
        return chantier

    def test_lien_vivant_apres_30_jours_chantier_en_cours(self, *_m):
        self._accepter()
        self.link.refresh_from_db()
        self.assertIsNotNone(self.link.suivi_prolonge_le)
        with freeze_time(_jour(5)):
            create_installation_from_devis(
                self.devis, self.user, self.company)
        self.assertEqual(self._suivi(31), 200)
        self.assertEqual(self._suivi(200), 200)

    def test_sans_acceptation_le_lien_expire_toujours_a_30_jours(self, *_m):
        self.assertEqual(self._suivi(29), 200)
        self.assertEqual(self._suivi(31), 404)

    def test_echeance_reception_plus_90_jours(self, *_m):
        self._accepter()
        chantier = self._receptionner(40)
        chantier.refresh_from_db()
        self.assertEqual(chantier.date_reception,
                         (T0 + datetime.timedelta(days=40)).date())
        self.link.refresh_from_db()
        self.assertIsNone(self.link.suivi_prolonge_le)
        self.assertEqual(self._suivi(129), 200)
        self.assertEqual(self._suivi(131), 404)

    def test_revocation_coupe_suivi_et_proposition(self, *_m):
        self._accepter()
        self.assertEqual(self._suivi(31), 200)
        self.api.force_authenticate(user=self.user)
        with freeze_time(_jour(32)):
            resp = self.api.post(
                f'/api/django/ventes/devis/{self.devis.id}/'
                'revoquer-lien-public/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['revoques'], 1)
        self.api.force_authenticate(user=None)
        # Persistance : la révocation est relue depuis la base.
        self.link.refresh_from_db()
        self.assertIsNotNone(self.link.revoque_le)
        self.assertEqual(self._suivi(32), 404)
        with freeze_time(_jour(32)):
            prop = self.api.get(
                f'/api/django/ventes/proposal/{self.link.token}/')
        self.assertEqual(prop.status_code, 404)
        # Un lien révoqué n'est jamais réutilisé : un nouveau jeton est créé.
        with freeze_time(_jour(33)):
            neuf = ShareLink.for_devis(self.devis)
        self.assertNotEqual(neuf.pk, self.link.pk)

    def test_revocation_autre_societe_404(self, *_m):
        self._accepter()
        autre = Company.objects.create(nom='ADOC131 Autre')
        intrus = User.objects.create_user(
            username='adoc131-intrus', password='x', company=autre,
            role_legacy='responsable')
        self.api.force_authenticate(user=intrus)
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/revoquer-lien-public/')
        self.assertEqual(resp.status_code, 404)
        self.link.refresh_from_db()
        self.assertIsNone(self.link.revoque_le)


class FinDeVieDuLienTests(TestCase):
    """ADEV97 — refus, remplacement par une nouvelle version, lead perdu :
    le lien public se révoque de lui-même (note au chatter) ; un devis
    ACCEPTÉ garde le sien (ADOC131)."""

    def setUp(self):
        from apps.crm.models import Lead
        self.company = Company.objects.create(nom='ADEV97 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV97')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='ADEV97')
        self.n = 0

    def _devis(self, statut=Devis.Statut.ENVOYE):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-202610-AD97{self.n:02d}',
            client=self.client_obj, lead=self.lead, statut=statut,
            taux_tva=Decimal('20'))
        return devis, ShareLink.for_devis(devis)

    def _revoque(self, link):
        link.refresh_from_db()
        return link.revoque_le is not None

    def test_devis_refuse_revoque_son_lien(self):
        from core.events import devis_refused
        from apps.ventes.models import DevisActivity
        devis, link = self._devis()
        devis_refused.send(sender=Devis, devis=devis, user=None,
                           motif_refus='prix')
        self.assertTrue(self._revoque(link))
        self.assertTrue(DevisActivity.objects.filter(
            devis=devis, body__contains='révoqué automatiquement').exists())
        self.assertEqual(self.api_get(link), 404)

    def test_version_remplacee_revoque_l_ancien_lien(self):
        from core.events import devis_revise
        v1, lien1 = self._devis()
        v2, lien2 = self._devis()
        devis_revise.send(sender=Devis, ancien=v1, nouveau=v2, user=None)
        self.assertTrue(self._revoque(lien1))
        self.assertFalse(self._revoque(lien2))

    def test_lead_perdu_revoque_les_liens_non_acceptes(self):
        envoye, lien_envoye = self._devis()
        accepte, lien_accepte = self._devis(Devis.Statut.ACCEPTE)
        self.lead.perdu = True
        self.lead.motif_perte = 'concurrent'
        self.lead.save(update_fields=['perdu', 'motif_perte'])
        self.assertTrue(self._revoque(lien_envoye))
        # ADOC131 — un accepté garde son lien (page en lecture + suivi).
        self.assertFalse(self._revoque(lien_accepte))

    def test_accepte_jamais_revoque_par_un_refus_ou_une_revision(self):
        from core.events import devis_refused, devis_revise
        accepte, lien = self._devis(Devis.Statut.ACCEPTE)
        autre, _ = self._devis()
        devis_refused.send(sender=Devis, devis=accepte, user=None,
                           motif_refus='')
        devis_revise.send(sender=Devis, ancien=accepte, nouveau=autre,
                          user=None)
        self.assertFalse(self._revoque(lien))

    @staticmethod
    def api_get(link):
        return APIClient().get(
            f'/api/django/ventes/proposal/{link.token}/').status_code
