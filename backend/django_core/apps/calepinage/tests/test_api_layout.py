"""CAL18 — l'action ``layout`` (GET/POST) du calepinage.

Ce qui est prouvé ici :

* le POST accepte le layout NU et les deux enveloppes (``layout`` /
  ``roof_layout``) — les mêmes que côté ventes et côté AO ;
* renvoyer le MÊME document répond ``{"inchange": true}`` et n'ajoute AUCUNE
  version ; un document modifié en ajoute exactement une ;
* aucun statut n'est écrit (règle #4) : le calepinage reste où il est ;
* un corps vide est refusé 400 avec un message français nommant le champ ;
* un calepinage d'une AUTRE société est introuvable (404), jamais interdit ;
* sans ``calepinage_gerer``, le POST répond 403 (la lecture, elle, suffit au
  GET).

Run :
    python manage.py test apps.calepinage.tests.test_api_layout -v2
"""
from apps.calepinage.models import Calepinage, CalepinageVersion

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {'schema_version': 2, 'result': {'panels': 12}, 'zones': [{'id': 1}]}
LAYOUT_2 = {'schema_version': 2, 'result': {'panels': 14}, 'zones': [{'id': 1}]}


def url_layout(pk):
    return f'{url_detail(pk)}layout/'


class ActionLayoutTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=42, titre='Chez la voisine')

    def _versions(self):
        return CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()

    def test_get_rend_la_conception_et_son_empreinte(self):
        reponse = self.api.get(url_layout(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.data['roof_layout'])
        self.assertIsNone(reponse.data['layout_hash'])

    def test_post_nu_enregistre_et_historise(self):
        reponse = self.api.post(url_layout(self.calepinage.pk), LAYOUT,
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(reponse.data['inchange'])
        self.assertIsNotNone(reponse.data['version'])
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_layout, LAYOUT)
        self.assertEqual(len(self.calepinage.layout_hash), 64)
        self.assertEqual(self._versions(), 1)

    def test_post_enveloppes_acceptees(self):
        for enveloppe in ('layout', 'roof_layout'):
            with self.subTest(enveloppe=enveloppe):
                reponse = self.api.post(url_layout(self.calepinage.pk),
                                        {enveloppe: LAYOUT}, format='json')
                self.assertEqual(reponse.status_code, 200, reponse.data)
                self.calepinage.refresh_from_db()
                self.assertEqual(self.calepinage.roof_layout, LAYOUT)

    def test_renvoi_a_l_identique_est_inchange(self):
        self.api.post(url_layout(self.calepinage.pk), LAYOUT, format='json')
        reponse = self.api.post(url_layout(self.calepinage.pk), LAYOUT,
                                format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data['inchange'])
        self.assertIsNone(reponse.data['version'])
        self.assertEqual(self._versions(), 1)

    def test_layout_modifie_ajoute_une_version(self):
        self.api.post(url_layout(self.calepinage.pk), LAYOUT, format='json')
        self.api.post(url_layout(self.calepinage.pk), LAYOUT_2, format='json')
        self.assertEqual(self._versions(), 2)

    def test_aucun_statut_n_est_ecrit(self):
        avant = self.calepinage.statut
        self.api.post(url_layout(self.calepinage.pk), LAYOUT, format='json')
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.statut, avant)

    def test_corps_vide_refuse_en_francais(self):
        reponse = self.api.post(url_layout(self.calepinage.pk), {},
                                format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('roof_layout', reponse.data)

    def test_autre_societe_introuvable(self):
        reponse = self.api.post(url_layout(self.etranger.pk), LAYOUT,
                                format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_d_ecriture_403(self):
        reponse = self.api_sans.post(url_layout(self.calepinage.pk), LAYOUT,
                                     format='json')
        self.assertEqual(reponse.status_code, 403)
