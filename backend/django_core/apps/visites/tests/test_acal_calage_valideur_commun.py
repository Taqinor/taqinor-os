"""ACAL202 — le calage de la visite passe par LE validateur unique du noyau.

``core.calepinage.calage.valider_quatre_coins`` est partagé avec le calage des
photos de site du calepinage : la visite refuse les MÊMES quadrilatères
dégénérés (coins confondus, alignés, croisés), en nommant ``texture_calage``.

Run :
    python manage.py test apps.visites.tests.test_acal_calage_valideur_commun -v2
"""
from apps.visites.tests.test_visite_assemblage import AssemblageBase

COINS = [[33.5731, -7.5898], [33.5732, -7.5898],
         [33.5732, -7.5897], [33.5731, -7.5897]]
IDENTIQUES = [[33.5731, -7.5898]] * 4
COLINEAIRES = [[33.5731, -7.5898], [33.5732, -7.5898],
               [33.5733, -7.5898], [33.5734, -7.5898]]
CROISES = [COINS[0], COINS[2], COINS[1], COINS[3]]


class CalageVisiteValideurCommunTest(AssemblageBase):

    def _url(self):
        return f'/api/django/visites/visites/{self.visite_id}/calage/'

    def test_visite_refuse_le_meme_calage_degenere(self):
        for nom, coins in (('identiques', IDENTIQUES),
                           ('colineaires', COLINEAIRES),
                           ('croises', CROISES)):
            with self.subTest(nom):
                resp = self.api.patch(
                    self._url(), {'texture_calage': {'coins': coins}},
                    format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertIn('texture_calage', resp.data['erreurs'])
        self.assertIsNone(self.visite().texture_calage)

    def test_visite_accepte_un_quadrilatere_convexe(self):
        resp = self.api.patch(self._url(),
                              {'texture_calage': {'coins': COINS}},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.visite().texture_calage, {'coins': COINS})

    def test_le_validateur_n_est_plus_recopie_dans_visites(self):
        import inspect

        from apps.visites import views

        source = inspect.getsource(views.VisiteTerrainViewSet.calage)
        self.assertIn('valider_quatre_coins', source)
        self.assertNotIn('len(coins) != 4', source)
