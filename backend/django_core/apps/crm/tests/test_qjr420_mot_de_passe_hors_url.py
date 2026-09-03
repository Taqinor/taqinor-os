"""QJR420 (QJR4-06) — le mot de passe d'une salle de vente quitte l'URL.

CE QUE LE ROUGE PROUVAIT. ``apps/crm/public_views.py`` lisait ::

    mot_de_passe = request.query_params.get('mot_de_passe') or ''
    if not mot_de_passe and request.data:
        mot_de_passe = request.data.get('mot_de_passe', '')

Un SECRET dans la chaîne de requête atterrit dans les **journaux d'accès du
serveur**, l'**historique du navigateur** et l'en-tête **Referer** envoyé à
tout tiers que la page contacte. Le corps n'était consulté qu'à défaut.

CORRECTIF : le mot de passe se transmet **UNIQUEMENT dans le corps d'un POST**.
La lecture depuis la chaîne de requête est **SUPPRIMÉE**, pas laissée en repli
— règle permanente 2 : un repli qui accepte encore le secret en clair dans
l'URL ne corrige rien. L'écran qui l'envoie
(``frontend/src/pages/crm/salle-vente/PublicSalleVentePage.jsx``) suit dans le
MÊME commit.
"""
import ast
from pathlib import Path

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from apps.crm.models import Client, SalleVente


_MOT_DE_PASSE = 'secret-qjr420'


class MotDePasseHorsUrlTests(TestCase):

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='qjr420', defaults={'nom': 'QJR420'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR420')
        self.salle = SalleVente.objects.create(
            company=self.company, client=self.client_obj,
            titre='Salle protégée QJR420')
        self.salle.set_password(_MOT_DE_PASSE)
        self.salle.save(update_fields=['password_hash'])
        self.anon = APIClient()

    def _url(self):
        return '/api/django/crm/salle-vente/%s/' % self.salle.token

    def test_le_mot_de_passe_dans_l_url_n_est_plus_lu(self):
        """ROUGE avant QJR420 : cette requête réussissait (200)."""
        reponse = self.anon.get(
            self._url(), {'mot_de_passe': _MOT_DE_PASSE})
        self.assertEqual(reponse.status_code, 403)

    def test_le_mot_de_passe_dans_l_url_d_un_post_n_est_pas_lu_non_plus(self):
        """Aucun repli : même sur un POST, la chaîne de requête ne décide rien."""
        reponse = self.anon.post(
            '%s?mot_de_passe=%s' % (self._url(), _MOT_DE_PASSE),
            {}, format='json')
        self.assertEqual(reponse.status_code, 403)

    def test_le_mot_de_passe_dans_le_corps_d_un_post_reussit(self):
        reponse = self.anon.post(
            self._url(), {'mot_de_passe': _MOT_DE_PASSE}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['titre'], 'Salle protégée QJR420')

    def test_un_mauvais_mot_de_passe_reste_refuse(self):
        reponse = self.anon.post(
            self._url(), {'mot_de_passe': 'pas-le-bon'}, format='json')
        self.assertEqual(reponse.status_code, 403)

    def test_un_corps_sans_mot_de_passe_est_refuse(self):
        self.assertEqual(
            self.anon.post(self._url(), {}, format='json').status_code, 403)

    def test_un_mot_de_passe_non_textuel_ne_fait_pas_planter(self):
        """Entrée hostile : jamais un 500 sur un endpoint public."""
        for valeur in (5, None, {'a': 1}, [1]):
            with self.subTest(valeur=valeur):
                reponse = self.anon.post(
                    self._url(), {'mot_de_passe': valeur}, format='json')
                self.assertEqual(reponse.status_code, 403)

    def test_une_salle_sans_mot_de_passe_reste_lisible_en_get(self):
        """Le cas courant ne bouge pas : aucun mot de passe ⇒ GET inchangé."""
        libre = SalleVente.objects.create(
            company=self.company, client=self.client_obj, titre='Salle libre')
        reponse = self.anon.get(
            '/api/django/crm/salle-vente/%s/' % libre.token)
        self.assertEqual(reponse.status_code, 200, reponse.data)


class AucuneLectureDeSecretEnQueryTests(TestCase):
    """Troisième test du `Done` : la preuve structurelle."""

    def test_aucun_query_params_ne_lit_un_secret_dans_ce_fichier(self):
        from apps.crm import public_views

        arbre = ast.parse(
            Path(public_views.__file__).read_text(encoding='utf-8'))
        fautifs = []
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Attribute)
                    and noeud.func.attr == 'get'):
                continue
            cible = ast.unparse(noeud.func.value)
            if 'query_params' not in cible and 'GET' not in cible:
                continue
            for argument in noeud.args:
                if (isinstance(argument, ast.Constant)
                        and isinstance(argument.value, str)
                        and 'mot_de_passe' in argument.value):
                    fautifs.append('ligne %d : %s' % (noeud.lineno, cible))
        self.assertEqual(
            fautifs, [],
            'un secret est encore lu dans la chaîne de requête : %r'
            % (fautifs,))

    def test_l_ecran_envoie_le_mot_de_passe_en_corps_de_post(self):
        """Second test du `Done`, moitié écran : ``PublicSalleVentePage.jsx``
        ne met plus le secret dans ``params``."""
        # …/backend/django_core/apps/crm/tests/<ce fichier> → racine du dépôt.
        racine = Path(__file__).resolve().parents[5]
        ecran = (racine / 'frontend' / 'src' / 'pages' / 'crm'
                 / 'salle-vente' / 'PublicSalleVentePage.jsx')
        source = ecran.read_text(encoding='utf-8')
        self.assertIn('api.post(`/crm/salle-vente/${token}/`', source)
        self.assertNotIn('params: pwd', source)
