"""CALX39 — la porte HTTP de l'import d'un plan, éprouvée sur un VRAI DXF.

CE QUE CE FICHIER PROUVE
------------------------
``services/import_plan.py`` (CAL62) savait analyser un plan déposé, mais rien
ne l'appelait : ``PlanImporteCalage.jsx`` l'écrivait noir sur blanc, et le
contour devait lui arriver par une propriété que personne ne fournissait.
Cette tâche pose la porte ``POST calepinages/<pk>/importer-plan/``. Ici, sans
base de données :

1. la route EXISTE dans la table que DRF construira, en POST, gardée par
   ``PeutGererCalepinage``, et rattachée par ``views/rattachements.py`` ;
2. l'échantillon COMMITTÉ ``contract_samples/calepinage_import_plan.json``
   est, au caractère près, ce que la porte rend sur un DXF fabriqué par
   ``ezdxf`` — la bibliothèque que l'analyseur emploie, jamais un fichier
   binaire écrit à la main (qui « passe » ici et casse la CI) ;
3. AUCUNE échelle n'est devinée : l'unité est celle que le fichier DÉCLARE,
   ``echelle`` est toujours ``null`` et le motif le dit en français ;
4. chaque refus NOMME le champ fautif (``fichier`` ou ``calque``) avec le
   motif français — jamais un « non enregistré » générique, jamais un 500 ;
5. la porte n'ÉCRIT RIEN : aucun ``roof_layout`` n'est posé, et la source du
   module ne contient aucune écriture.

Run ::

    python manage.py test apps.calepinage.tests.test_calx39_import_plan -v 2
"""
from __future__ import annotations

import io
import json
import pathlib

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLON = (RACINE_APP / 'contract_samples'
               / 'calepinage_import_plan.json')
SOURCE_VUE = (RACINE_APP / 'views' / 'import_plan.py').read_text(
    encoding='utf-8')
SOURCE_RATTACHEMENTS = (RACINE_APP / 'views' / 'rattachements.py').read_text(
    encoding='utf-8')

#: L'enveloppe du plan d'essai, dans l'unité DU FICHIER (mètres déclarés).
CONTOUR = [(0.0, 0.0), (30.0, 0.0), (30.0, 18.0), (0.0, 18.0)]
CALQUE = 'ENVELOPPE'
CALQUE_COTES = 'COTES'
NOM_FICHIER = 'plan-toiture.dxf'

#: En-tête PNG, écrit en hexadécimal pour qu'aucune relecture d'encodage ne
#: le déforme : c'est une SIGNATURE de fichier, pas du texte.
ENTETE_PNG = bytes.fromhex('89504e470d0a1a0a')


def _contrat():
    return json.loads(ECHANTILLON.read_text(encoding='utf-8'))


def _dxf():
    """Un DXF RÉEL fabriqué en mémoire par ``ezdxf`` — jamais à la main.

    Un « DXF » tapé à la main passe le test qui l'a écrit et casse dès que la
    CI le donne au vrai analyseur : le fichier d'essai vient donc de la même
    bibliothèque que celle qui le relira.
    """
    import ezdxf

    doc = ezdxf.new('R2010')
    doc.header['$INSUNITS'] = 6  # mètres, DÉCLARÉS par le fichier
    doc.layers.add(CALQUE)
    doc.layers.add(CALQUE_COTES)
    doc.modelspace().add_lwpolyline(
        CONTOUR, close=True, dxfattribs={'layer': CALQUE})
    doc.modelspace().add_line((0, -2), (30, -2),
                              dxfattribs={'layer': CALQUE_COTES})
    flux = io.StringIO()
    doc.write(flux)
    return flux.getvalue().encode('utf-8')


class CalepinageNu:
    """Un calepinage NU : aucun document — donc aucune base de données."""

    pk = 1
    company = None
    roof_layout = None


class FausseRequete:
    """Le strict nécessaire d'une requête multipart : ``FILES`` et ``data``."""

    def __init__(self, fichier=None, **donnees):
        self.FILES = {'fichier': fichier} if fichier is not None else {}
        self.data = dict(donnees)


class FausseVue:
    def __init__(self, calepinage=None):
        self.calepinage = calepinage or CalepinageNu()

    def get_object(self):
        return self.calepinage


def _appeler(octets=None, *, nom=NOM_FICHIER, vue=None, **donnees):
    from apps.calepinage.views.import_plan import importer_plan

    octets = _dxf() if octets is None else octets
    fichier = SimpleUploadedFile(nom, octets, content_type='application/dxf')
    return importer_plan(vue or FausseVue(), FausseRequete(fichier, **donnees),
                         pk=1)


def _actions():
    from apps.calepinage import urls  # noqa: F401
    from apps.calepinage.views.calepinages import CalepinageViewSet

    return {methode.__name__: methode
            for methode in CalepinageViewSet.get_extra_actions()}


class RouteImporterPlanTest(SimpleTestCase):
    """La porte existe, en écriture gardée, et elle est rattachée."""

    def test_l_action_est_enregistree_en_post(self):
        actions = _actions()
        chemins = {methode.url_path for methode in actions.values()}
        self.assertIn(
            'importer-plan', chemins,
            "L'URL « calepinages/<pk>/importer-plan/ » n'est pas enregistrée "
            "(CALX39) : l'import de views/import_plan.py doit s'exécuter "
            "AVANT router.register, par views/rattachements.py.")
        action = actions['importer_plan']
        self.assertEqual(set(action.mapping), {'post'})
        self.assertEqual(
            [garde.__name__
             for garde in action.kwargs['permission_classes']],
            ['PeutGererCalepinage'])
        self.assertEqual(action.url_name, 'importer-plan')

    def test_le_rattachement_passe_par_la_liste_append_only(self):
        from apps.calepinage.views import rattachements

        self.assertIn('import_plan', rattachements.MODULES_RATTACHES)
        self.assertIn('from . import import_plan', SOURCE_RATTACHEMENTS)
        self.assertNotIn(
            'import_plan', (RACINE_APP / 'urls.py').read_text(
                encoding='utf-8'),
            "urls.py n'est PAS rouvert pour une action neuve (D-CALX 13).")

    def test_l_action_accepte_le_multipart(self):
        parsers = _actions()['importer_plan'].kwargs['parser_classes']
        self.assertIn('MultiPartParser',
                      [parser.__name__ for parser in parsers])


class ContratImportPlanTest(SimpleTestCase):
    """L'échantillon committé EST ce que la porte rend."""

    def test_l_exemple_est_la_reponse_reelle_avec_calque(self):
        reponse = _appeler(calque=CALQUE)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data, _contrat()['exemple'])

    def test_l_exemple_sans_calque_est_la_reponse_reelle(self):
        reponse = _appeler()
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data, _contrat()['exemple_sans_calque'])

    def test_les_calques_disponibles_sont_rendus(self):
        exemple = _contrat()['exemple_sans_calque']
        noms = [calque['nom'] for calque in exemple['calques']]
        self.assertIn(CALQUE, noms)
        self.assertIn(CALQUE_COTES, noms)
        self.assertIsNone(exemple['contour'],
                          "Sans calque choisi, aucun contour n'est proposé : "
                          "en choisir un d'office serait deviner l'enveloppe.")

    def test_le_contour_est_celui_du_fichier(self):
        exemple = _contrat()['exemple']
        self.assertEqual([tuple(point) for point in exemple['contour']],
                         CONTOUR)
        self.assertEqual(exemple['cotes_hors_tout'],
                         {'largeur': 30.0, 'hauteur': 18.0, 'sommets': 4})


class AucuneEchelleDevineeTest(SimpleTestCase):
    """L'unité est déclarée par le fichier ; l'échelle ne l'est jamais."""

    def test_l_echelle_est_toujours_nulle_et_le_motif_est_dit(self):
        for etat in ('exemple', 'exemple_sans_calque'):
            donnees = _contrat()[etat]
            self.assertIsNone(donnees['echelle'],
                              f"{etat} : une échelle servie serait une "
                              "estimation — la calibration la donne.")
            self.assertTrue(donnees['motif_echelle'].strip())

    def test_un_fichier_sans_unite_declaree_rend_inconnu(self):
        import ezdxf

        doc = ezdxf.new('R2010')
        # 0 = « sans unité » dans la table DXF : le fichier ne déclare RIEN,
        # et le serveur ne comble pas ce vide (``unite='inconnu'``).
        doc.header['$INSUNITS'] = 0
        doc.layers.add(CALQUE)
        doc.modelspace().add_lwpolyline(
            CONTOUR, close=True, dxfattribs={'layer': CALQUE})
        flux = io.StringIO()
        doc.write(flux)

        reponse = _appeler(flux.getvalue().encode('utf-8'))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['unite'], 'inconnu')
        self.assertIsNone(reponse.data['echelle'])


class RefusNommesTest(SimpleTestCase):
    """Chaque refus NOMME le champ fautif, en français."""

    def test_sans_fichier_le_champ_fichier_est_nomme(self):
        from apps.calepinage.views.import_plan import importer_plan

        reponse = importer_plan(FausseVue(), FausseRequete(), pk=1)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('fichier', reponse.data)

    def test_un_fichier_vide_est_refuse_en_nommant_le_champ(self):
        reponse = _appeler(b'')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, _contrat()['refus_fichier_vide'])

    def test_une_image_est_refusee_sans_contour_devine(self):
        # Le format est jugé sur le CONTENU : un « .dxf » renommé depuis un
        # PNG est un cas réel d'atelier.
        reponse = _appeler(ENTETE_PNG + b'0' * 64, nom='plan.dxf')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, _contrat()['refus_fichier_image'])

    def test_un_calque_inconnu_liste_les_calques_disponibles(self):
        reponse = _appeler(calque='ENVELOPE')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(reponse.data, _contrat()['refus_calque'])
        self.assertIn(CALQUE, reponse.data['calque'])

    def test_un_dxf_illisible_est_refuse_et_jamais_un_500(self):
        reponse = _appeler(b'ce fichier n est pas un plan' * 10)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('fichier', reponse.data)
        self.assertTrue(str(reponse.data['fichier']).strip())


class AucuneEcritureTest(SimpleTestCase):
    """La porte LIT un fichier et rend un contour : elle n'écrit rien."""

    def test_aucun_roof_layout_n_est_pose(self):
        vue = FausseVue()
        reponse = _appeler(vue=vue, calque=CALQUE)
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(vue.calepinage.roof_layout,
                          "La porte a posé un roof_layout : l'enregistrement "
                          "reste le geste de l'utilisateur (POST layout/).")
        self.assertIs(reponse.data['enregistre'], False)

    def test_la_source_de_la_vue_n_ecrit_rien(self):
        for interdit in ('.save(', 'objects.create(', 'objects.update(',
                         'roof_layout ='):
            self.assertNotIn(
                interdit, SOURCE_VUE,
                f"« {interdit} » dans views/import_plan.py : cette porte est "
                "une LECTURE, aucun document ne s'y écrit.")
