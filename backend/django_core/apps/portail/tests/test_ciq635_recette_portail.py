"""CIQ635 — portail client : la recette et les réserves de SON chantier (lecture
seule), le sous-objet ``vue_portail`` du contrat ``recette_ci.json``.

Run :
    python manage.py test apps.portail.tests.test_ciq635_recette_portail
"""
import datetime
import json
import pathlib

from django.test import TestCase
from rest_framework.test import APIClient

from apps.installations.models import (
    CommissioningRecord, Installation, Reserve,
)
from apps.portail.tests.test_ntprt14_mes_chantiers import (
    make_client, make_company, make_portal_user,
)
from authentication.models import CustomUser

APPS = pathlib.Path(__file__).resolve().parents[2]


def _json(app, nom):
    return json.loads((APPS / app / 'contract_samples' / f'{nom}.json')
                      .read_text(encoding='utf-8'))


DETAIL = _json('portail', 'mes_chantiers_detail')['exemple']
VUE = _json('installations', 'recette_ci')['exemple']['vue_portail']


class RecetteCIPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('ciq635-co', 'CIQ635 Société')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-CIQ635-1',
            client=self.client_a, site_ville='Casablanca',
            type_installation='industriel',
            puissance_installee_kwc=100,
            date_reception=datetime.date(2026, 10, 13))
        self.record = CommissioningRecord.objects.create(
            company=self.company, installation=self.chantier,
            date_essai=datetime.date(2026, 10, 12), resultat='reserves',
            technicien='Technicien interne', irradiation_kwh_m2=5,
            energie_mesuree_kwh=405)
        Reserve.objects.create(
            company=self.company, installation=self.chantier,
            description='Étiquette de repérage manquante',
            date_echeance=datetime.date(2026, 10, 26))
        user = make_portal_user(
            self.company, 'ciq635-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=user)

    def _get(self, chantier):
        return self.api.get(
            f'/api/django/portail/mes-chantiers/{chantier.id}/')

    def test_le_client_voit_resultat_pr_reserves_et_dates(self):
        res = self._get(self.chantier)
        self.assertEqual(res.status_code, 200, res.data)
        vue = res.data['recette_ci']
        self.assertEqual(vue['resultat'], 'reserves')
        self.assertEqual(vue['date'], '2026-10-12')
        self.assertEqual(vue['pr'], 0.81)
        self.assertEqual(vue['pr_libelle'], "à titre d'information")
        self.assertEqual(vue['reserves_ouvertes'], [{
            'description': 'Étiquette de repérage manquante',
            'date_echeance': '2026-10-26'}])
        self.assertEqual(vue['date_reception_provisoire'], '2026-10-13')
        self.assertIsNone(vue['date_reception_definitive'])

    def test_reserve_levee_n_est_plus_listee(self):
        Reserve.objects.update(statut='resolue')
        vue = self._get(self.chantier).data['recette_ci']
        self.assertEqual(vue['reserves_ouvertes'], [])

    def test_jamais_instrument_technicien_ni_prix(self):
        vue = self._get(self.chantier).data['recette_ci']
        texte = json.dumps(vue)
        for interdit in ('instrument', 'technicien', 'prix', 'prix_achat'):
            self.assertNotIn(interdit, texte)
        self.assertNotIn('Technicien interne', texte)

    def test_chantier_d_un_autre_client_404(self):
        autre = Installation.objects.create(
            company=self.company, reference='CH-CIQ635-2',
            client=self.client_b, type_installation='industriel')
        CommissioningRecord.objects.create(
            company=self.company, installation=autre)
        self.assertEqual(self._get(autre).status_code, 404)

    def test_pas_de_fiche_null(self):
        sans = Installation.objects.create(
            company=self.company, reference='CH-CIQ635-3',
            client=self.client_a, type_installation='industriel')
        res = self._get(sans)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data['recette_ci'])

    def test_les_deux_exemples_committes_sont_affirmes(self):
        res = self._get(self.chantier)
        self.assertEqual(set(res.data['recette_ci']), set(VUE))
        self.assertEqual(DETAIL['recette_ci'], VUE)
        self.assertIn('recette_pompage', DETAIL)
        # Même jeu de clés que l'exemple du détail (hors jalons/recette).
        self.assertEqual(set(res.data), set(DETAIL))
