"""CALX7 — les DEUX exports du calepinage sont bien enregistrés.

LE DÉFAUT QUE CE FICHIER EMPÊCHE DE REVENIR
-------------------------------------------
``views/export_csv.py`` (CAL144, export de la SIMULATION : série horaire,
agrégat mensuel, matrice d'ombrage) rattache son action au viewset pivot par
affectation d'attribut de classe, parce que d'autres lanes travaillent sur
``views/calepinages.py``. Tant que cette action s'appelait ``export_csv``,
l'affectation ÉCRASAIT ``SortiesMixin.export_csv`` (CAL179, export TABLEUR :
modules, chaînes et nomenclature) : ``get_extra_actions()`` n'en voyait qu'UNE
seule et la route ``calepinages/<pk>/export.csv/`` n'était jamais enregistrée
— une capacité construite, testée au service, et injoignable par HTTP.

Rien dans la pile ne signale ce masquage : Python accepte l'écrasement, DRF
enregistre sans broncher ce qu'il trouve, et les tests de service continuent
de passer. Seule une lecture de ``get_extra_actions()`` le voit.

Essais PURS (ni base de données, ni réseau) : on n'interroge que la table des
actions que DRF construira, avant toute requête.

Run :
    python manage.py test apps.calepinage.tests.test_calx7_routage_exports -v2
"""
from django.test import SimpleTestCase


def _actions():
    """Les ``@action`` que le routeur DRF enregistrera, par nom de méthode.

    L'import de ``urls`` est ce qui exécute les rattachements par attribut de
    classe (``views/export_csv.py``, ``views/equipements.py``…) : sans lui, la
    table serait celle du viewset nu et le test ne prouverait rien.
    """
    from apps.calepinage import urls  # noqa: F401
    from apps.calepinage.views.calepinages import CalepinageViewSet

    return CalepinageViewSet, {methode.__name__: methode
                               for methode
                               in CalepinageViewSet.get_extra_actions()}


class DeuxExportsCsvEnregistresTest(SimpleTestCase):
    """Les deux CSV du module ont chacun leur route."""

    def test_les_deux_url_path_sont_enregistres(self):
        _viewset, actions = _actions()
        chemins = {methode.url_path for methode in actions.values()}
        for attendu in ('export.csv', 'export-csv'):
            self.assertIn(
                attendu, chemins,
                f"L'URL « calepinages/<pk>/{attendu}/ » n'est pas "
                "enregistrée : une @action en masque une autre sur le pivot "
                "(CALX7). Vérifier que le nom de la fonction, celui de "
                "l'attribut de classe et la clé du mapping DRF sont "
                "identiques ET distincts d'une action déjà portée par un "
                "mixin.")

    def test_chaque_export_est_sur_sa_propre_methode(self):
        _viewset, actions = _actions()
        self.assertIn('export_csv', actions,
                      "SortiesMixin.export_csv (export tableur CAL179) a "
                      "disparu de get_extra_actions() : quelque chose l'a de "
                      "nouveau écrasée (CALX7).")
        self.assertIn('export_csv_simulation', actions,
                      "L'export de simulation (CAL144) n'est plus rattaché "
                      "au viewset pivot.")
        self.assertEqual(actions['export_csv'].url_path, 'export.csv')
        self.assertEqual(actions['export_csv_simulation'].url_path,
                         'export-csv')

    def test_les_url_name_restent_reversibles_separement(self):
        """Deux actions ne peuvent pas partager un ``url_name``.

        ``reverse()`` ne rend que le DERNIER motif enregistré sous un nom
        donné : deux actions homonymes rendraient l'une des deux injoignable
        par son nom, ce qui est le même défaut déplacé d'un cran.
        """
        _viewset, actions = _actions()
        self.assertEqual(actions['export_csv'].url_name, 'export-csv')
        self.assertEqual(actions['export_csv_simulation'].url_name,
                         'export-csv-simulation')

    def test_les_deux_exports_restent_en_lecture_seule(self):
        _viewset, actions = _actions()
        for nom in ('export_csv', 'export_csv_simulation'):
            self.assertEqual(set(actions[nom].mapping), {'get'},
                             f"L'action « {nom} » n'est plus un simple "
                             "téléchargement.")
            self.assertEqual(
                [garde.__name__
                 for garde in actions[nom].kwargs['permission_classes']],
                ['PeutVoirCalepinage'])


class AucuneActionNEnMasqueUneAutreTest(SimpleTestCase):
    """La garde générale : le masquage ne peut pas revenir par ailleurs."""

    def test_le_nom_de_la_fonction_egale_le_nom_de_l_attribut(self):
        """DRF lit ``__name__`` — un alias serait ignoré en silence.

        ``get_extra_actions()`` renvoie les attributs de classe décorés, et le
        routeur reconstruit le mapping à partir du ``__name__`` de la
        fonction. Un rattachement du genre ``ViewSet.autre_nom = export_csv``
        (ou un décorateur qui ne recopie pas ``__name__``) enregistre donc une
        route qui appelle la mauvaise méthode, ou pas de route du tout.
        """
        viewset, actions = _actions()
        divergents = [nom for nom in actions
                      if getattr(getattr(viewset, nom), '__name__', None)
                      != nom]
        self.assertEqual(
            divergents, [],
            "Action(s) dont l'attribut de classe et le nom de fonction "
            f"divergent : {divergents}. DRF mappe par ``__name__`` : "
            "l'attribut doit porter EXACTEMENT le nom de la fonction.")

    def test_aucun_url_path_en_double(self):
        _viewset, actions = _actions()
        chemins = [methode.url_path for methode in actions.values()]
        doubles = sorted({chemin for chemin in chemins
                          if chemins.count(chemin) > 1})
        self.assertEqual(
            doubles, [],
            f"url_path servi(s) par deux actions : {doubles}. Le routeur "
            "enregistre les deux motifs, mais seul le premier répond.")

    def test_aucun_url_name_en_double(self):
        _viewset, actions = _actions()
        noms = [methode.url_name for methode in actions.values()]
        doubles = sorted({nom for nom in noms if noms.count(nom) > 1})
        self.assertEqual(
            doubles, [],
            f"url_name porté(s) par deux actions : {doubles}. ``reverse()`` "
            "ne rendrait que le dernier motif enregistré.")
