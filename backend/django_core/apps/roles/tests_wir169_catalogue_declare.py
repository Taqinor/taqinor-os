"""WIR169 — garde générique : tout code de permission DÉCLARÉ existe au catalogue.

Le bug corrigé n'est pas une politique mais un CÂBLAGE : un viewset pose
``read_permission = 'btp_voir'`` / ``write_permission = 'btp_gerer'`` et
personne n'enregistre ces codes dans ``roles.ALL_PERMISSIONS``. Comme
``DIRECTEUR_PERMISSIONS``/``ADMIN_PERMISSIONS`` DÉRIVENT du catalogue, aucun
rôle fin — Directeur compris — ne porte le code : ``has_erp_permission``
renvoie False et le module entier répond 403. Rien ne le signalait : ni
flake8, ni un test, ni un contrôle au démarrage.

Ce module ferme la classe de bug pour de bon. Il parcourt les URLs RÉELLEMENT
routées (``django.urls.get_resolver()``), lit sur chaque classe de vue les
attributs ``read_permission``/``write_permission`` (chaîne unique, ou tuple/
liste de codes comme ``apps.fpa.permissions.FPA_LECTURE``) et exige que chaque
code figure dans le catalogue. Le parcours est fait à l'EXÉCUTION et non par
lecture de source : il attrape donc aussi les codes posés via une constante
(``DOUANE_RESPONSABLE``, ``VEILLE_AO_VOIR``…), qu'un scan textuel de
``apps/*/views.py`` manquerait.

Aucune liste d'exceptions : un code déclaré mais non catalogué est TOUJOURS un
bug (403 silencieux pour tout le monde), jamais un cas toléré.
"""
from django.test import SimpleTestCase
from django.urls import URLPattern, URLResolver, get_resolver

from apps.roles.models import (
    ADMIN_PERMISSIONS,
    ALL_PERMISSIONS,
    DIRECTEUR_PERMISSIONS,
)

#: Les six codes que WIR169 enregistre (déclarés par des viewsets réels, mais
#: absents du catalogue jusqu'ici — le module répondait donc 403 à tout rôle
#: fin, Directeur inclus).
CODES_WIR169 = (
    'btp_voir', 'btp_gerer',
    'assurances_voir', 'assurances_gerer',
    'douane_responsable', 'transport_responsable',
)


def _iter_view_classes():
    """Chaque classe de vue atteignable depuis la racine d'URL, dédupliquée."""
    vues = {}

    def _walk(patterns):
        for entry in patterns:
            if isinstance(entry, URLResolver):
                _walk(entry.url_patterns)
            elif isinstance(entry, URLPattern):
                callback = entry.callback
                cls = (getattr(callback, 'cls', None)
                       or getattr(callback, 'view_class', None))
                if cls is not None:
                    vues[(cls.__module__, cls.__qualname__)] = cls

    _walk(get_resolver().url_patterns)
    return list(vues.values())


def _codes_declares(view_class):
    """Codes de permission déclarés sur ``view_class`` (chaîne OU tuple/liste)."""
    codes = []
    for attribut in ('read_permission', 'write_permission'):
        valeur = getattr(view_class, attribut, None)
        if valeur is None:
            continue
        if isinstance(valeur, str):
            codes.append(valeur)
        elif isinstance(valeur, (tuple, list, set, frozenset)):
            codes.extend(c for c in valeur if isinstance(c, str))
    return codes


def collecter_codes_declares():
    """``{code: [noms de vues qui le déclarent]}`` sur toutes les URLs routées."""
    trouves = {}
    for view_class in _iter_view_classes():
        for code in _codes_declares(view_class):
            trouves.setdefault(code, []).append(view_class.__name__)
    return trouves


class CatalogueCouvreLesCodesDeclaresTests(SimpleTestCase):
    """La garde générique : zéro code déclaré hors catalogue."""

    def test_le_scan_trouve_bien_des_codes(self):
        """Anti-faux-vert : une garde qui ne collecte rien passerait toujours."""
        trouves = collecter_codes_declares()
        self.assertTrue(
            trouves,
            "Aucun read_permission/write_permission trouvé : le parcours "
            "d'URLs est cassé, la garde ne vérifierait plus rien.")
        # Témoin : un code que l'on sait déclaré par un viewset routé.
        self.assertIn('btp_voir', trouves)

    def test_tout_code_declare_existe_au_catalogue(self):
        catalogue = set(ALL_PERMISSIONS)
        manquants = {
            code: sorted(set(vues))
            for code, vues in collecter_codes_declares().items()
            if code not in catalogue
        }
        self.assertEqual(
            manquants, {},
            "Codes de permission déclarés par un viewset mais ABSENTS de "
            "roles.ALL_PERMISSIONS : aucun rôle fin (Directeur inclus) ne peut "
            "les porter, l'endpoint répond 403 à tout le monde. Ajoutez-les au "
            "catalogue (et aux presets adéquats).")


class CodesWir169Tests(SimpleTestCase):
    """Les six codes de WIR169 sont catalogués et hérités par la direction."""

    def test_codes_au_catalogue(self):
        for code in CODES_WIR169:
            self.assertIn(code, ALL_PERMISSIONS, code)

    def test_directeur_et_admin_les_portent_par_heritage(self):
        for code in CODES_WIR169:
            self.assertIn(code, DIRECTEUR_PERMISSIONS, code)
            self.assertIn(code, ADMIN_PERMISSIONS, code)

    def test_catalogue_sans_doublon(self):
        self.assertEqual(
            len(ALL_PERMISSIONS), len(set(ALL_PERMISSIONS)),
            "ALL_PERMISSIONS contient un code en double.")
