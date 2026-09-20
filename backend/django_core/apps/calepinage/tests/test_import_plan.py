"""CAL62 — importer un plan avec l'analyseur du module, jamais un second.

Ce que ce module VERROUILLE :

  1. **Un même DXF donne le MÊME contour** par la porte de l'analyseur
     (``apps.calepinage.analyse_plan.analyser_plan_importe``) et par le
     service du module (``apps.calepinage.services.import_plan``) — c'est la
     preuve qu'il n'y a qu'un analyseur, pas deux. SOLMVP15 : l'analyseur
     vivait chez le module d'appels d'offres, il a été rapatrié ici à la
     ligne près — ce test compare donc les deux MÊMES portes qu'avant.
  2. **Un PDF sans vectoriel est REFUSÉ** avec un message français qui nomme
     la cause (plan scanné), jamais un contour deviné depuis une image.
  3. **L'unité n'est jamais inventée** : celle que le DXF déclare, sinon
     ``'inconnu'`` — et ``'inconnu'`` pour un PDF (points typographiques).
  4. **Les refus nomment quoi corriger** : fichier vide, calque inexistant
     (avec la liste des calques disponibles).

Aucune base de données n'est touchée : tout est PUR (octets → dict).

Run :
    python manage.py test apps.calepinage.tests.test_import_plan -v2
"""
import io

from django.test import SimpleTestCase

from apps.calepinage.analyse_plan import analyser_plan_importe
from apps.calepinage.services import import_plan

#: Une enveloppe plausible de bâtiment, en MÈTRES dans le fichier.
CONTOUR = [(0.0, 0.0), (30.0, 0.0), (30.0, 18.0), (0.0, 18.0)]
CALQUE_ENVELOPPE = 'ENVELOPPE'


def _dxf(*, unites=6, calque=CALQUE_ENVELOPPE, contour=CONTOUR):
    """Un DXF RÉEL fabriqué en mémoire (ezdxf, déjà en production)."""
    import ezdxf

    doc = ezdxf.new('R2010')
    doc.header['$INSUNITS'] = unites
    doc.layers.add(calque)
    doc.modelspace().add_lwpolyline(
        contour, close=True, dxfattribs={'layer': calque})
    flux = io.StringIO()
    doc.write(flux)
    return flux.getvalue().encode('utf-8')


def _pdf(*, vectoriel):
    """Un PDF RÉEL : avec un rectangle tracé, ou seulement du texte (scan)."""
    import fitz

    document = fitz.open()
    page = document.new_page()
    if vectoriel:
        page.draw_rect(fitz.Rect(20, 30, 200, 150))
    else:
        page.insert_text((72, 72), 'Plan scanne sans trace vectoriel')
    octets = document.tobytes()
    document.close()
    return octets


class UnMemeDxfDonneUnMemeContour(SimpleTestCase):
    def test_la_porte_analyseur_et_le_module_rendent_le_meme_contour(self):
        octets = _dxf()

        par_analyseur = analyser_plan_importe(
            octets, nom_fichier='plan.dxf')
        par_module = import_plan.analyser_plan(octets, nom_fichier='plan.dxf')

        self.assertEqual(par_module, par_analyseur)
        self.assertEqual(
            import_plan.contour_du_calque(par_module, CALQUE_ENVELOPPE),
            import_plan.contour_du_calque(par_analyseur,
                                          CALQUE_ENVELOPPE))

    def test_le_contour_est_celui_du_fichier(self):
        analyse = import_plan.analyser_plan(_dxf())

        contour = import_plan.contour_du_calque(analyse, CALQUE_ENVELOPPE)

        self.assertEqual([tuple(p) for p in contour], CONTOUR)

    def test_le_format_et_l_unite_declaree_sont_rendus(self):
        analyse = import_plan.analyser_plan(_dxf(unites=6))

        self.assertEqual(analyse['format'], 'dxf')
        self.assertEqual(analyse['unite'], 'm')

    def test_une_unite_non_declaree_reste_inconnue(self):
        """Jamais devinée : un plan en mm lu « en m » est un plan faux."""
        analyse = import_plan.analyser_plan(_dxf(unites=0))

        self.assertEqual(analyse['unite'], 'inconnu')

    def test_les_cotes_hors_tout_derivent_du_contour(self):
        analyse = import_plan.analyser_plan(_dxf())
        contour = import_plan.contour_du_calque(analyse, CALQUE_ENVELOPPE)

        cotes = import_plan.cotes_hors_tout(contour)

        self.assertEqual(cotes['largeur'], 30.0)
        self.assertEqual(cotes['hauteur'], 18.0)
        self.assertEqual(cotes['sommets'], 4)

    def test_sans_contour_les_cotes_sont_nulles_jamais_zero(self):
        """Un ``0`` se lirait comme une mesure ; ``None`` dit « inconnu »."""
        self.assertEqual(import_plan.cotes_hors_tout([]),
                         {'largeur': None, 'hauteur': None, 'sommets': 0})


class UnPdfSansVectorielEstRefuse(SimpleTestCase):
    def test_le_message_nomme_la_cause(self):
        with self.assertRaises(import_plan.PlanIllisible) as refus:
            import_plan.analyser_plan(_pdf(vectoriel=False),
                                      nom_fichier='plan.pdf')

        message = str(refus.exception)
        self.assertIn('aucun tracé vectoriel', message)
        self.assertIn('SCANNÉ', message)
        self.assertEqual(refus.exception.champ, 'fichier')

    def test_un_pdf_vectoriel_passe_avec_une_unite_inconnue(self):
        analyse = import_plan.analyser_plan(_pdf(vectoriel=True),
                                            nom_fichier='plan.pdf')

        self.assertEqual(analyse['format'], 'pdf')
        self.assertEqual(analyse['unite'], 'inconnu')
        self.assertTrue(analyse['calques'])
        contour = import_plan.contour_du_calque(analyse,
                                                analyse['calques'][0]['nom'])
        self.assertGreaterEqual(len(contour), 2)

    def test_le_format_est_deduit_du_CONTENU_pas_de_l_extension(self):
        """Un PDF renommé « .dxf » est un cas réel d'atelier."""
        analyse = import_plan.analyser_plan(_pdf(vectoriel=True),
                                            nom_fichier='plan.dxf')

        self.assertEqual(analyse['format'], 'pdf')


class LesRefusDisentQuoiCorriger(SimpleTestCase):
    def test_un_fichier_vide(self):
        with self.assertRaises(import_plan.PlanIllisible) as refus:
            import_plan.analyser_plan(b'')
        self.assertIn('vide', str(refus.exception))

    def test_un_fichier_qui_n_est_ni_dxf_ni_pdf(self):
        with self.assertRaises(import_plan.PlanIllisible) as refus:
            import_plan.analyser_plan(b'ceci n\'est pas un plan')
        self.assertIn('DXF', str(refus.exception))

    def test_un_calque_inexistant_liste_les_calques_disponibles(self):
        analyse = import_plan.analyser_plan(_dxf())

        with self.assertRaises(import_plan.PlanIllisible) as refus:
            import_plan.contour_du_calque(analyse, 'TOITURE')

        message = str(refus.exception)
        self.assertIn('TOITURE', message)
        self.assertIn(CALQUE_ENVELOPPE, message)
        self.assertEqual(refus.exception.champ, 'calque')

    def test_un_fichier_trop_lourd(self):
        with self.assertRaises(import_plan.PlanIllisible) as refus:
            import_plan.analyser_plan(b'0' * (5 * 1024 * 1024 + 1))
        self.assertIn('5 Mo', str(refus.exception))
