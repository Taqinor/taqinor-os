"""ADEV9 (C-ADEV-003) — une installation révisée compte UNE fois.

Un devis V1 ENVOYÉ révisé en V2 ENVOYÉE garde sa V1 (``is_active=False``,
statut ``envoye`` inchangé). Tous les lecteurs agrégés possédés par
ventes-devis passent par ``selectors.devis_en_jeu`` : tableau de bord
(``envoyes``, ``valeur_pipeline``), KPI kWc conçus, sélecteurs ventes
(relances). Un devis jamais révisé compte comme avant.

Test-du-test : retirer le filtre de ``devis_en_jeu`` ⇒ les trois tests échouent.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev9_devis_en_jeu -v 2
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import Devis
from apps.ventes.tests.test_l_niv_niveau import (
    make_client, make_company, make_devis, make_user,
)

URL = '/api/django/ventes/dashboard/'


class DevisEnJeuTests(TestCase):

    def setUp(self):
        self.company = make_company('adev9')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        layout = {'result': {'kwc': 5.5}}
        self.v1 = make_devis(self.company, self.user, self.client_obj,
                             'DEV-ADEV9-0001', roof_layout=layout)
        self.v2 = make_devis(self.company, self.user, self.client_obj,
                             'DEV-ADEV9-0001-V2', roof_layout=layout)
        maintenant = timezone.now()
        Devis.objects.filter(pk=self.v1.pk).update(
            is_active=False, superseded_by=self.v2, date_envoi=maintenant)
        Devis.objects.filter(pk=self.v2.pk).update(
            version=2, version_parent=self.v1, date_envoi=maintenant)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _dashboard(self):
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        return r.data['devis']

    def test_dashboard_compte_une_fois(self):
        devis = self._dashboard()
        self.assertEqual(devis['envoyes'], 1)
        self.assertEqual(devis['total'], 1)
        ttc_v2 = Decimal(str(Devis.objects.get(pk=self.v2.pk).total_ttc))
        self.assertEqual(Decimal(devis['valeur_pipeline']),
                         ttc_v2.quantize(Decimal('0.01')))
        # Lecture pure : deux lectures identiques.
        self.assertEqual(self._dashboard(), devis)

    def test_devis_sans_revision_compte_comme_avant(self):
        make_devis(self.company, self.user, self.client_obj, 'DEV-ADEV9-0002')
        self.assertEqual(self._dashboard()['envoyes'], 2)

    def test_kwc_concus_sans_v1(self):
        from apps.ventes.reports import kpi_ventes
        tuiles = {t['id']: t['valeur'] for t in kpi_ventes(self.company)}
        self.assertEqual(tuiles['ventes_kwc_concus'], 5.5)

    def test_selectors_ventes_sans_v1(self):
        from apps.ventes.selectors import (
            devis_en_jeu, devis_envoyes_en_attente, devis_envoyes_periode)
        self.assertEqual(
            [d.pk for d in devis_envoyes_periode(self.company)], [self.v2.pk])
        self.assertEqual(
            [d.pk for d in devis_envoyes_en_attente(self.company)],
            [self.v2.pk])
        self.assertEqual(
            list(devis_en_jeu(Devis.objects.filter(company=self.company))
                 .values_list('pk', flat=True)), [self.v2.pk])
