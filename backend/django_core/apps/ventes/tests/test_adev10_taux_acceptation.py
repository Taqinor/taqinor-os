"""ADEV10 (C-ADEV-058) — ``taux_acceptation_pct`` du tableau de bord sur les
devis ENVOYÉS DE LA PÉRIODE, jamais au-dessus de 100 %.

Sonde VB q5 : 4 devis acceptés, 1 envoyé encore ouvert ⇒ 400.0 (le
dénominateur était le STOCK d'envoyés ouverts). Désormais : acceptés parmi
les devis dont ``date_envoi`` tombe dans la période ÷ ces devis × 100 ; les
deux taux de conversion « depuis envoyé » suivent la même base ; ``envoyes``
(stock ouvert) reste servi tel quel.

Test-du-test : remettre ``n_envoyes`` comme dénominateur ⇒
``test_jamais_au_dessus_de_100`` échoue (400.0).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev10_taux_acceptation -v 2
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import Devis
from apps.ventes.tests.test_l_niv_niveau import (
    make_client, make_company, make_user,
)

URL = '/api/django/ventes/dashboard/'


class TauxAcceptationTests(TestCase):

    def setUp(self):
        self.company = make_company('adev10')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.n = 0

    def _devis(self, statut, date_envoi, par=None, en_jeu=True):
        self.n += 1
        d = Devis.objects.create(
            company=self.company, client=self.client_obj,
            created_by=par or self.user, reference=f'DEV-ADEV10-{self.n:04d}',
            statut=statut)
        Devis.objects.filter(pk=d.pk).update(
            date_envoi=date_envoi, is_active=en_jeu)
        return d

    def _devis_dashboard(self, **params):
        r = self.api.get(URL, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.data

    def test_jamais_au_dessus_de_100(self):
        maintenant = timezone.now()
        for _ in range(4):
            self._devis('accepte', maintenant)
        self._devis('envoye', maintenant)
        data = self._devis_dashboard()
        self.assertEqual(data['devis']['envoyes'], 1)  # stock ouvert inchangé
        self.assertEqual(data['devis']['taux_acceptation_pct'], 80.0)
        self.assertEqual(
            data['conversion']['devis_envoye_vers_accepte_pct'], 80.0)
        self.assertLessEqual(
            data['conversion']['devis_envoye_vers_facture_pct'] or 0, 100)

    def test_denominateur_envoyes_de_la_periode(self):
        aujourdhui = timezone.localdate()
        dans_periode = timezone.now()
        hors_periode = dans_periode - timedelta(days=90)
        self._devis('accepte', dans_periode)
        self._devis('envoye', dans_periode)
        self._devis('accepte', hors_periode)  # envoyé avant la période
        self._devis('accepte', None)  # jamais envoyé (accepté direct)
        debut = aujourdhui - timedelta(days=30)
        data = self._devis_dashboard(start=debut.isoformat(),
                                     end=aujourdhui.isoformat())
        self.assertEqual(data['devis']['taux_acceptation_pct'], 50.0)

    def test_aucun_envoi_dans_la_periode(self):
        self._devis('accepte', None)
        data = self._devis_dashboard()
        self.assertIsNone(data['devis']['taux_acceptation_pct'])

    def _scenario_aana59(self):
        """D-AANA-VER-1 : 6 envois, dont une V1 remplacée ⇒ base 5, 2 acceptés
        (+ un envoi hors période et un devis d'un autre commercial)."""
        autre = make_user(self.company, 'commercial')
        maintenant = timezone.now()
        self._devis('envoye', maintenant, en_jeu=False)  # V1 remplacée
        self._devis('accepte', maintenant)  # sa V2, acceptée
        self._devis('accepte', maintenant)
        self._devis('envoye', maintenant)
        self._devis('refuse', maintenant, par=autre)
        self._devis('envoye', maintenant, par=autre)
        self._devis('accepte', maintenant - timedelta(days=400))  # hors période
        return autre

    def test_effectifs_servis_reproduisent_le_taux(self):
        self._scenario_aana59()
        devis = self._devis_dashboard()['devis']
        self.assertEqual(devis['envoyes_periode'], 5)
        self.assertEqual(devis['acceptes_periode'], 2)
        self.assertEqual(devis['taux_acceptation_pct'], 40.0)
        self.assertEqual(
            self._devis_dashboard()['conversion']['devis_envoye_vers_accepte_pct'],
            40.0)

    def test_scope_mine(self):
        self._scenario_aana59()
        devis = self._devis_dashboard(mine=1)['devis']
        self.assertEqual(devis['envoyes_periode'], 3)  # 2 acceptés + 1 envoyé
        self.assertEqual(devis['acceptes_periode'], 2)
        self.assertEqual(devis['taux_acceptation_pct'], 66.7)

    def test_v1_acceptee_revisee_reste_acceptee(self):
        """AANA87 — « Réviser » une vente acceptée (V2 brouillon) laisse la V1
        envoyée ET acceptée (devis_signes_en_vigueur) : 1/2 = 50,0 %."""
        from apps.ventes.domain.revision import reviser_devis
        from apps.ventes.selectors import taux_acceptation_periode
        maintenant = timezone.now()
        jour = timezone.localdate()
        v1 = self._devis('accepte', maintenant)
        self._devis('envoye', maintenant)
        sans = taux_acceptation_periode(self.company, jour, jour)
        self.assertEqual((sans['envoyes'], sans['acceptes']), (2, 1))
        v2 = reviser_devis(Devis.objects.get(pk=v1.pk), user=self.user)
        self.assertNotEqual(v2.pk, v1.pk)
        res = taux_acceptation_periode(self.company, jour, jour)
        self.assertEqual(res, {'envoyes': 2, 'acceptes': 1, 'taux_pct': 50.0})
        # V2 acceptée ⇒ une seule vente (la V1 sort, la V2 envoyée compte).
        Devis.objects.filter(pk=v2.pk).update(
            statut='accepte', date_envoi=maintenant)
        res = taux_acceptation_periode(self.company, jour, jour)
        self.assertEqual(res, {'envoyes': 2, 'acceptes': 1, 'taux_pct': 50.0})
