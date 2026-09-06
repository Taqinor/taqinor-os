"""AUD413 — le miroir ``/api/v1/`` ne contourne NI le gating de modules NI
celui d'ÉDITION.

ÉTAT RÉEL LU AVANT D'ÉCRIRE (le constat d'origine n'est plus reproductible) :

  · volet MODULE — SOL7 a déjà étendu ``core.permissions._module_key_for_path``
    aux DEUX racines (``_API_ROOTS = ('api/django/', 'api/v1/')``,
    ``core/permissions.py``), et ``core/tests/test_sol7_miroir_v1_gate.py``
    épingle la parité du helper ET le 404 d'un ``ModuleToggle`` éteint sur le
    miroir. Rien à re-corriger de ce côté ;
  · volet LICENCE — SOL9 compose le plan de licence DANS
    ``feature_flags.module_actif`` (``acces_module_autorise`` en ET), point
    d'entrée UNIQUE du ``DisabledModuleMiddleware`` : un module hors plan suit
    donc exactement le même chemin de 404 que le miroir garde déjà ;
  · volet ÉDITION — c'est celui que ce module gèle. ``erp_agentique/urls.py``
    ne parque pas une app en la retirant d'un préfixe : ``_si_active()`` la
    retire de la liste ``_APP_URLS``, et cette liste UNIQUE est montée deux
    fois. La garantie qui compte n'est donc pas « les sept verticaux solaires
    sont absents » (vide de sens en édition ``full``, celle de la CI) mais :
    **quelle que soit l'édition, les deux montages exposent EXACTEMENT le même
    ensemble de routes**. Une future app montée à la main sous ``api/django/``
    seulement — ou, pire, sous ``api/v1/`` seulement, hors ``_APP_URLS`` et
    donc hors ``_si_active`` — rendrait ce test rouge immédiatement.

Ce test est un GEL de non-régression : il doit rester vert en édition ``full``
comme en édition ``solar``, sans jamais dépendre de la liste des apps parquées.

Lancer :
    docker compose exec django_core python manage.py test \
        core.tests.test_aud413_edition_miroir_v1 -v 2
"""
from django.test import SimpleTestCase
from django.urls import get_resolver

from core import permissions

RACINE_HISTORIQUE = 'api/django/'
RACINE_MIROIR = 'api/v1/'


def _resolveur_de_racine(racine):
    """Le resolver monté SOUS ``racine`` dans l'urlconf réellement chargé."""
    for motif in get_resolver().url_patterns:
        if not hasattr(motif, 'url_patterns'):
            continue
        if str(getattr(motif.pattern, '_route', '')) == racine:
            return motif
    return None


def _modules_montes(resolver):
    """Noms des modules d'urls inclus DIRECTEMENT sous ce resolver."""
    noms = set()
    for motif in getattr(resolver, 'url_patterns', []):
        cible = getattr(motif, 'urlconf_name', None)
        nom = getattr(cible, '__name__', None)
        if nom:
            noms.add(nom)
    return noms


def _segments_montes(resolver):
    """Premiers segments de route exposés DIRECTEMENT sous ce resolver."""
    segments = set()
    for motif in getattr(resolver, 'url_patterns', []):
        route = str(getattr(motif.pattern, '_route', ''))
        segments.add(route.split('/', 1)[0])
    return segments


class LesDeuxMontagesExposentLeMemePlan(SimpleTestCase):
    """Le volet ÉDITION d'AUD413 : rien ne peut être parqué d'un seul côté."""

    def setUp(self):
        self.historique = _resolveur_de_racine(RACINE_HISTORIQUE)
        self.miroir = _resolveur_de_racine(RACINE_MIROIR)

    def test_les_deux_racines_sont_bien_montees(self):
        self.assertIsNotNone(
            self.historique, "la racine historique api/django/ a disparu.")
        self.assertIsNotNone(
            self.miroir,
            "le miroir api/v1/ a disparu : si le montage est retiré, retirer "
            "aussi 'api/v1/' de core.permissions._API_ROOTS.")

    def test_meme_liste_de_modules_sous_les_deux_racines(self):
        """``_si_active`` filtre la liste PARTAGÉE : le parking d'édition vaut
        donc pour les deux préfixes, ou pour aucun."""
        self.assertEqual(
            _modules_montes(self.historique), _modules_montes(self.miroir),
            "un module d'urls n'est monté que sous UNE des deux racines : le "
            "gating d'édition/module serait contournable par l'autre.")

    def test_memes_segments_de_route_sous_les_deux_racines(self):
        self.assertEqual(
            _segments_montes(self.historique), _segments_montes(self.miroir),
            'les deux montages doivent exposer exactement les mêmes segments.')

    def test_chaque_segment_monte_est_gardable_sous_les_deux_prefixes(self):
        """Parité du helper de gating SUR LES SEGMENTS RÉELLEMENT MONTÉS.

        SOL7 épingle la parité sur une liste écrite à la main ; ici elle est
        rejouée sur l'arbre d'urls vivant, donc toute app ajoutée demain à
        ``_APP_URLS`` est couverte sans toucher au test.
        """
        for segment in sorted(_segments_montes(self.historique)):
            if not segment:
                continue
            with self.subTest(segment=segment):
                self.assertEqual(
                    permissions._module_key_for_path(
                        f'/{RACINE_HISTORIQUE}{segment}/x/'),
                    permissions._module_key_for_path(
                        f'/{RACINE_MIROIR}{segment}/x/'))


class LeGatingDEditionPasseParLeMemePointDEntree(SimpleTestCase):
    """Volets MODULE et LICENCE : un seul chemin de décision, déjà gardé."""

    def test_les_deux_racines_internes_sont_declarees(self):
        self.assertEqual(
            permissions._API_ROOTS, (RACINE_HISTORIQUE, RACINE_MIROIR))

    def test_le_middleware_decide_par_le_helper_a_deux_racines(self):
        """Le 404 de module/licence est posé APRÈS ``_module_key_for_path`` —
        donc pour les deux préfixes à la fois. On le vérifie en neutralisant
        le helper : sans clé, aucune requête n'est bloquée."""
        vues = []

        def suivante(requete):
            vues.append(requete.path)
            return 'servi'

        middleware = permissions.DisabledModuleMiddleware(suivante)
        original = permissions._module_key_for_path
        try:
            permissions._module_key_for_path = lambda chemin: None
            from django.test import RequestFactory
            requete = RequestFactory().get('/api/v1/stock/produits/')
            self.assertEqual(middleware(requete), 'servi')
        finally:
            permissions._module_key_for_path = original
        self.assertEqual(vues, ['/api/v1/stock/produits/'])

    def test_la_licence_est_composee_dans_le_point_d_entree_unique(self):
        """SOL9 — ``module_actif`` (appelé par le middleware) compose le plan
        de licence ; le miroir hérite donc du gating d'édition sans code
        supplémentaire."""
        import inspect

        from core import feature_flags
        source = inspect.getsource(feature_flags.module_actif)
        self.assertIn(
            'acces_module_autorise', source,
            "module_actif ne compose plus le plan de licence : le gating "
            "d'édition ne suivrait plus le miroir api/v1/.")
