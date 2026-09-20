"""CAL233 — la structure du module est posée UNE fois, et elle tient.

Deux garanties, prouvées sans base de données :

1. ``apps/calepinage/services`` et ``apps/calepinage/views`` sont des PAQUETS
   (jamais des modules ``services.py`` / ``views.py``). Les deux formes ne
   peuvent pas coexister en Python : si une lane repose un module plat, ce
   test rougit AVANT que la collision n'arrive en fusion.

2. Le module n'expose QUE DEUX formes d'URL :
   ``/api/django/calepinage/calepinages/<pk>/…`` (sous-ressources en
   ``@action`` du routeur DRF) et ``/api/django/calepinage/parametres/``.
   Deux familles d'URL pour un même objet, c'est l'incident PACT10 par
   construction (écran « AO — Tableau de bord », 03/08/2026) : ce test
   échoue si une URL du module sort de ces deux formes.

Run :
    python manage.py test apps.calepinage.tests.test_structure_urls -v2
"""
import pathlib

from django.test import SimpleTestCase

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]

#: Motifs engendrés par ``DefaultRouter`` à la racine (api-root + suffixe de
#: format) : ils ne portent aucune ressource, donc ils sont hors contrat.
#: CAL16 — la troisième forme (``<drf_format_suffix:format>``) est celle que
#: DRF engendre RÉELLEMENT pour l'api-root dès qu'un viewset est enregistré :
#: elle est apparue au premier ``router.register`` (le routeur était vide quand
#: cette liste a été écrite). C'est la même route sans ressource que les deux
#: autres — jamais une seconde famille d'URL.
_RACINE_ROUTEUR = ('', r'\.(?P<format>[a-z0-9]+)/?',
                   '<drf_format_suffix:format>')


def _routes(patterns, prefixe=''):
    """Aplatit un ``urlpatterns`` en la liste des routes complètes."""
    routes = []
    for motif in patterns:
        chemin = prefixe + str(motif.pattern)
        enfants = getattr(motif, 'url_patterns', None)
        if enfants is not None:
            routes.extend(_routes(enfants, chemin))
        else:
            routes.append(chemin)
    return routes


class StructurePaquetsTest(SimpleTestCase):
    """``services/`` et ``views/`` sont des paquets, pas des modules plats."""

    def test_services_est_un_paquet(self):
        self.assertTrue((RACINE_APP / 'services' / '__init__.py').is_file())
        self.assertFalse(
            (RACINE_APP / 'services.py').exists(),
            "apps/calepinage/services.py réapparu : il ne peut pas coexister "
            "avec le paquet services/ (CAL233).")

    def test_views_est_un_paquet(self):
        self.assertTrue((RACINE_APP / 'views' / '__init__.py').is_file())
        self.assertFalse(
            (RACINE_APP / 'views.py').exists(),
            "apps/calepinage/views.py réapparu : il ne peut pas coexister "
            "avec le paquet views/ (CAL233).")

    def test_pas_de_viewsets_plat(self):
        """Un second foyer de vues (``viewsets.py``) rouvrirait l'ambiguïté."""
        self.assertFalse(
            (RACINE_APP / 'viewsets.py').exists(),
            "apps/calepinage/viewsets.py : les vues du module vivent dans le "
            "paquet views/ (CAL233), nulle part ailleurs.")

    def test_reexport_nomme_le_sous_module_manquant(self):
        """Un nom inconnu échoue en NOMMANT les sous-modules connus."""
        from apps.calepinage import services

        with self.assertRaises(AttributeError) as capture:
            services.fonction_qui_nexiste_pas
        self.assertIn('creation', str(capture.exception))


class FormeUrlUniqueTest(SimpleTestCase):
    """Toute URL du module tient dans les DEUX formes admises."""

    def test_deux_formes_seulement(self):
        from apps.calepinage import urls
        from apps.calepinage.views import PREFIXES_URL_AUTORISES

        hors_contrat = []
        for route in _routes(urls.urlpatterns):
            if route in _RACINE_ROUTEUR:
                continue
            premier = route.lstrip('^').split('/', 1)[0]
            if premier not in PREFIXES_URL_AUTORISES:
                hors_contrat.append(route)

        self.assertEqual(
            hors_contrat, [],
            "URL(s) hors des deux formes admises "
            f"({' / '.join(PREFIXES_URL_AUTORISES)}) : {hors_contrat}. "
            "Une sous-ressource s'expose en @action du viewset pivot, jamais "
            "en nouvelle famille d'URL (CAL233).")

    def test_les_prefixes_sont_les_bons(self):
        """L'objet métier a UNE forme d'URL ; le moteur n'est pas l'objet.

        CAL22 — ``moteur`` rejoint la liste : c'est un CALCUL SANS ÉTAT (sans
        identifiant, n'appartenant à aucun calepinage), dont le chemin est figé
        depuis le jour 1 par ``contract_samples/moteur_calculer.json``. La
        règle protège le calepinage lui-même, qui reste servi sous
        ``calepinages/<pk>/…`` et nulle part ailleurs.
        """
        from apps.calepinage.views import PREFIXES_URL_AUTORISES

        self.assertEqual(PREFIXES_URL_AUTORISES,
                         ('calepinages', 'moteur', 'parametres'))
        self.assertNotIn(
            'calepinage', PREFIXES_URL_AUTORISES,
            "Aucun second préfixe ne doit servir l'objet métier lui-même.")
