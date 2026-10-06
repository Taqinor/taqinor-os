"""AGR612 — portail client : la recette pompage de SON chantier (lecture
seule), le sous-objet ``vue_portail`` du contrat ``recette_pompage.json``.

Run :
    python manage.py test apps.portail.tests.test_agr612_recette_portail
"""
import json
import pathlib

from django.test import TestCase
from rest_framework.test import APIClient

from apps.installations.models import Installation, RecettePompage
from apps.portail.tests.test_ntprt14_mes_chantiers import (
    make_client, make_company, make_portal_user,
)
from authentication.models import CustomUser

APPS = pathlib.Path(__file__).resolve().parents[2]


def _exemple(app, nom):
    return json.loads((APPS / app / 'contract_samples' / f'{nom}.json')
                      .read_text(encoding='utf-8'))['exemple']


DETAIL = _exemple('portail', 'mes_chantiers_detail')
RECETTE = _exemple('installations', 'recette_pompage')['record']


class RecettePompagePortailTests(TestCase):
    def setUp(self):
        self.company = make_company('agr612-co', 'AGR612 Société')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-AGR612-1',
            client=self.client_a, site_ville='Taroudant',
            type_installation='agricole')
        self.recette = RecettePompage.objects.create(
            company=self.company, installation=self.chantier,
            date_essai='2026-11-18', hmt_mesuree_m=60.2,
            debit_mesure_m3h=17.0, instrument_id='DEB-ULTRA-02',
            commentaire_ecart='Forage colmaté.', resultat='conforme',
            promesse={'debit_hmt_m3h': 20.0, 'hmt_m': 60.0, 'm3_jour': None,
                      'heures_pompage': None, 'devis_reference': 'DEV-X',
                      'figee_le': '2026-11-02'})
        user = make_portal_user(
            self.company, 'agr612-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=user)

    def _get(self, chantier):
        return self.api.get(f'/api/django/portail/mes-chantiers/{chantier.id}/')

    def test_le_client_voit_sa_recette(self):
        res = self._get(self.chantier)
        self.assertEqual(res.status_code, 200, res.data)
        recette = res.data['recette_pompage']
        self.assertEqual(recette['debit_mesure_m3h'], 17.0)
        self.assertEqual(recette['debit_promis_m3h'], 20.0)
        self.assertEqual(recette['ecart_debit_pct'], -15.0)
        self.assertEqual(recette['commentaire_ecart'], 'Forage colmaté.')
        self.assertEqual(recette['resultat'], 'conforme')

    def test_jamais_l_instrument_le_technicien_ni_un_prix(self):
        recette = self._get(self.chantier).data['recette_pompage']
        for interdit in ('instrument_id', 'technicien', 'prix_achat',
                         'promesse', 'comparaison'):
            self.assertNotIn(interdit, recette)
        self.assertNotIn('DEB-ULTRA-02', json.dumps(recette))

    def test_chantier_d_un_autre_client_404(self):
        autre = Installation.objects.create(
            company=self.company, reference='CH-AGR612-2',
            client=self.client_b, type_installation='agricole')
        RecettePompage.objects.create(company=self.company,
                                      installation=autre)
        self.assertEqual(self._get(autre).status_code, 404)

    def test_pas_de_fiche_recette_null(self):
        self.recette.delete()
        res = self._get(self.chantier)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIsNone(res.data['recette_pompage'])

    def test_affirme_les_deux_exemples_commites(self):
        """La forme servie = ``vue_portail`` du contrat installations, et la
        clé additive est dans l'exemple portail committé."""
        res = self._get(self.chantier)
        self.assertEqual(set(res.data), set(DETAIL))
        self.assertEqual(set(res.data['recette_pompage']),
                         set(DETAIL['recette_pompage']))
        self.assertEqual(set(res.data['recette_pompage']),
                         set(RECETTE['vue_portail']))
