"""CALX317 — le rapport d'ombrage autonome.

Ce qui est prouvé ici, en essais PURS (``unittest``, sans base) — le résultat
de simulation est INJECTÉ (``construire_rapport_ombrage(..., resultat=...)``)
pour ne jamais dépendre du pipeline complet ``resultat_calepinage`` :

* sans conception (``roof_layout`` vide/absent) : refus nommant
  ``roof_layout`` ;
* sans matrice 12×24 (absente ou incomplète) : refus nommant
  ``shading12x24``, avec le MÊME motif que ``export_csv._export_ombrage``
  (``:270-273``) — jamais un second texte ;
* 2 pans → 2 blocs (kWc, modules, azimut, inclinaison, accès solaire,
  TOF/TSRF, méthode) ;
* TOF/TSRF absents sur un pan ⇒ ``bloc['tof']``/``bloc['tsrf']`` restent
  ``None`` — AUCUNE valeur n'est imprimée à leur place (le rendu HTML publie
  « — » et le motif d'omission, jamais un chiffre inventé) ;
* deux pans dont l'accès solaire vient de méthodes différentes (l'un MESURÉ
  via ``solarAccess.values``, l'autre CALCULÉ via ``resultat['ombrage']``)
  ⇒ refus nommant ``methode_acces`` ;
* l'en-tête du rendu HTML NOMME la méthode de chaque bloc ;
* AUCUN montant (D5) — une clé de coût dans ``resultat`` fait refuser (même
  pare-feu que le rapport d'étude, ``verifier_etancheite``), et le motif
  reste ``RapportOmbrageRefuse`` (celui que la vue attrape), jamais
  l'exception interne du pare-feu.

Ce qui exige l'ORM/DB (le viewset HTTP, ``rendre_rapport_ombrage`` via
``core.pdf.render_pdf``) est écrit mais NON EXÉCUTÉ localement — CI validera.

Run (essais purs) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx317_rapport_ombrage.py -q
"""
from __future__ import annotations

import unittest

from apps.calepinage.services import rapport_ombrage
from apps.calepinage.services.rapport import RapportRefuse

MATRICE_12X24 = [[0.6] * 24 for _ in range(12)]


class FauxCalepinage:
    def __init__(self, *, roof_layout=None, pk=1, company=None,
                 titre='Toit d’essai'):
        self.pk = pk
        self.roof_layout = roof_layout
        self.company = company
        self.titre = titre
        self.client_id = None
        self.lead_id = None
        self.devis = None


def _resultat(pans, *, ombrage_par_pan=(), production_par_pan=(),
              electrique=None):
    return {
        'hash_entree': 'a' * 64,
        'version_moteur': 'calepinage-1.0.0',
        'calcule_le': '',
        'pose': {'pans': list(pans)},
        'ombrage': {'par_pan': list(ombrage_par_pan)},
        'production': {'par_pan': list(production_par_pan)},
        'electrique': electrique or {},
    }


PANS_DEUX = [
    {'pan': 'PAN-A', 'modules': 8, 'kwc': 5.76, 'azimut_deg': 180.0,
     'inclinaison_deg': 15.0},
    {'pan': 'PAN-B', 'modules': 6, 'kwc': 4.32, 'azimut_deg': 90.0,
     'inclinaison_deg': 20.0},
]


class ConstruireSansConceptionTest(unittest.TestCase):
    def test_refuse_sans_roof_layout(self):
        for vide in (None, {}):
            calepinage = FauxCalepinage(roof_layout=vide)
            with self.assertRaises(rapport_ombrage.RapportOmbrageRefuse) \
                    as capture:
                rapport_ombrage.construire_rapport_ombrage(calepinage)
            self.assertEqual(capture.exception.champ, 'roof_layout')


class ConstruireSansMatriceTest(unittest.TestCase):
    def test_refuse_sans_matrice_12x24_meme_motif_que_export_csv(self):
        for matrice_invalide in (None, [], [[0.1] * 24] * 11,
                                 [[0.1] * 23] * 12):
            calepinage = FauxCalepinage(
                roof_layout={'shading12x24': matrice_invalide, 'zones': []})
            with self.assertRaises(rapport_ombrage.RapportOmbrageRefuse) \
                    as capture:
                rapport_ombrage.construire_rapport_ombrage(calepinage)
            self.assertEqual(capture.exception.champ, 'shading12x24')
            self.assertEqual(str(capture.exception),
                             rapport_ombrage.MOTIF_SANS_MATRICE)


class DeuxPansDeuxBlocsTest(unittest.TestCase):
    def test_deux_pans_donnent_deux_blocs(self):
        roof_layout = {
            'shading12x24': MATRICE_12X24,
            'zones': [
                {'id': 'PAN-A', 'label': 'PAN-A',
                 'geometry': {'solarAccess': {
                     'values': [90.0, 95.0, 100.0]}}},
                {'id': 'PAN-B', 'label': 'PAN-B',
                 'geometry': {'solarAccess': {
                     'values': [80.0, 70.0]}}},
            ],
        }
        calepinage = FauxCalepinage(roof_layout=roof_layout)
        resultat = _resultat(
            PANS_DEUX,
            ombrage_par_pan=[
                {'pan': 'PAN-A', 'acces_solaire_moyen_pct': 95.0,
                 'motif_omission': ''},
                {'pan': 'PAN-B', 'acces_solaire_moyen_pct': 75.0,
                 'motif_omission': ''},
            ],
            production_par_pan=[
                {'pan': 'PAN-A', 'tof': 0.97, 'tsrf': 0.94},
                {'pan': 'PAN-B', 'tof': 0.9, 'tsrf': 0.85},
            ])
        rapport = rapport_ombrage.construire_rapport_ombrage(
            calepinage, resultat=resultat, etat={})

        self.assertEqual(len(rapport['blocs']), 2)
        pans_vus = {b['pan'] for b in rapport['blocs']}
        self.assertEqual(pans_vus, {'PAN-A', 'PAN-B'})
        bloc_a = next(b for b in rapport['blocs'] if b['pan'] == 'PAN-A')
        self.assertEqual(bloc_a['kwc'], 5.76)
        self.assertEqual(bloc_a['modules'], 8)
        self.assertEqual(bloc_a['azimut_deg'], 180.0)
        self.assertEqual(bloc_a['inclinaison_deg'], 15.0)
        self.assertEqual(bloc_a['tof'], 0.97)
        self.assertEqual(bloc_a['tsrf'], 0.94)
        # Les DEUX pans sont MESURÉS ici (solarAccess.values présent pour
        # les deux) : une seule méthode, aucun refus.
        self.assertEqual(bloc_a['methode_acces'], 'mesure')
        self.assertEqual(rapport['methode_acces'], 'mesure')

    def test_tof_tsrf_absents_ne_publient_aucune_valeur(self):
        roof_layout = {
            'shading12x24': MATRICE_12X24,
            'zones': [{'id': 'PAN-A', 'label': 'PAN-A',
                      'geometry': {'solarAccess': {'values': [90.0]}}}],
        }
        calepinage = FauxCalepinage(roof_layout=roof_layout)
        ligne_ombrage = {
            'pan': 'PAN-A', 'acces_solaire_moyen_pct': 90.0,
            'motif_omission': 'PVGIS injoignable pour ce pan.'}
        resultat = _resultat(
            [PANS_DEUX[0]],
            ombrage_par_pan=[ligne_ombrage],
            production_par_pan=[{'pan': 'PAN-A', 'tof': None,
                                 'tsrf': None}])
        rapport = rapport_ombrage.construire_rapport_ombrage(
            calepinage, resultat=resultat, etat={})
        bloc = rapport['blocs'][0]
        self.assertIsNone(bloc['tof'])
        self.assertIsNone(bloc['tsrf'])
        self.assertEqual(bloc['motif_omission_tof'],
                         'PVGIS injoignable pour ce pan.')

        html = rapport_ombrage._table_blocs(rapport['blocs'], 'fr')
        self.assertIn('PVGIS injoignable pour ce pan.', html)
        self.assertNotIn('>None<', html)


class MethodesIncompatiblesTest(unittest.TestCase):
    def test_refuse_deux_methodes_qui_ne_se_comparent_pas(self):
        # PAN-A : MESURÉ (solarAccess.values présent). PAN-B : rien dans le
        # document -> repli sur le CALCUL (resultat['ombrage']).
        roof_layout = {
            'shading12x24': MATRICE_12X24,
            'zones': [{'id': 'PAN-A', 'label': 'PAN-A',
                      'geometry': {'solarAccess': {'values': [90.0]}}}],
        }
        calepinage = FauxCalepinage(roof_layout=roof_layout)
        resultat = _resultat(
            PANS_DEUX,
            ombrage_par_pan=[
                {'pan': 'PAN-A', 'acces_solaire_moyen_pct': 90.0,
                 'motif_omission': ''},
                {'pan': 'PAN-B', 'acces_solaire_moyen_pct': 60.0,
                 'motif_omission': ''},
            ])
        with self.assertRaises(rapport_ombrage.RapportOmbrageRefuse) \
                as capture:
            rapport_ombrage.construire_rapport_ombrage(
                calepinage, resultat=resultat, etat={})
        self.assertEqual(capture.exception.champ, 'methode_acces')
        message = str(capture.exception)
        self.assertIn('méthodes', message.lower())


class EnTeteNommeLaMethodeTest(unittest.TestCase):
    def test_html_nomme_la_methode_de_chaque_bloc(self):
        roof_layout = {
            'shading12x24': MATRICE_12X24,
            'zones': [{'id': 'PAN-A', 'label': 'PAN-A',
                      'geometry': {'solarAccess': {'values': [90.0]}}}],
        }
        calepinage = FauxCalepinage(roof_layout=roof_layout)
        ligne_ombrage = {'pan': 'PAN-A', 'acces_solaire_moyen_pct': 90.0,
                         'motif_omission': ''}
        resultat = _resultat(
            [PANS_DEUX[0]],
            ombrage_par_pan=[ligne_ombrage],
            production_par_pan=[{'pan': 'PAN-A', 'tof': 0.9, 'tsrf': 0.8}])
        rapport = rapport_ombrage.construire_rapport_ombrage(
            calepinage, resultat=resultat, etat={})
        html = rapport_ombrage._table_blocs(rapport['blocs'], 'fr')
        self.assertIn(
            rapport_ombrage.LIBELLE_METHODE_ACCES['mesure'], html)


class AucunMontantTest(unittest.TestCase):
    def test_refuse_une_cle_de_cout_en_rapportOmbrageRefuse(self):
        roof_layout = {'shading12x24': MATRICE_12X24, 'zones': []}
        calepinage = FauxCalepinage(roof_layout=roof_layout)
        resultat = _resultat(PANS_DEUX)
        resultat['prix_achat'] = 100  # clé de coût INTERDITE (D5)
        with self.assertRaises(rapport_ombrage.RapportOmbrageRefuse):
            rapport_ombrage.construire_rapport_ombrage(
                calepinage, resultat=resultat, etat={})
        # Le pare-feu lève d'abord RapportRefuse : confirmons qu'il est
        # bien RÉELLEMENT levé ici (pas un texte inventé), puis TRADUIT.
        with self.assertRaises(RapportRefuse):
            from apps.calepinage.services.rapport import verifier_etancheite

            verifier_etancheite(resultat)


class ChaineLaPlusFaibleTest(unittest.TestCase):
    def test_chaine_la_plus_faible_apparait_sur_son_pan(self):
        roof_layout = {
            'shading12x24': MATRICE_12X24,
            'zones': [{'id': 'PAN-A', 'label': 'PAN-A',
                      'geometry': {'solarAccess': {'values': [62.0, 98.0]}}}],
        }
        calepinage = FauxCalepinage(roof_layout=roof_layout)
        chaine = {'chaine': 2, 'pan': 'PAN-A', 'module': 'PAN-A#1',
                  'acces_solaire': 0.62, 'raison': 'module le plus ombré'}
        ligne_ombrage = {'pan': 'PAN-A', 'acces_solaire_moyen_pct': 80.0,
                         'motif_omission': ''}
        resultat = _resultat(
            [PANS_DEUX[0]],
            ombrage_par_pan=[ligne_ombrage],
            production_par_pan=[{'pan': 'PAN-A', 'tof': 0.9, 'tsrf': 0.8}],
            electrique={'chaine_la_plus_faible': chaine})
        rapport = rapport_ombrage.construire_rapport_ombrage(
            calepinage, resultat=resultat, etat={})
        self.assertEqual(rapport['blocs'][0]['chaine_la_plus_faible'],
                         chaine)


class AvertissementSansCourseDuSoleilTest(unittest.TestCase):
    def test_avertit_sans_inventer_le_diagramme_calx118(self):
        roof_layout = {'shading12x24': MATRICE_12X24, 'zones': []}
        calepinage = FauxCalepinage(roof_layout=roof_layout)
        resultat = _resultat(PANS_DEUX)
        rapport = rapport_ombrage.construire_rapport_ombrage(
            calepinage, resultat=resultat, etat={})
        self.assertIn(rapport_ombrage.AVERTISSEMENT_SANS_COURSE_SOLEIL,
                      rapport['avertissements'])


# ── ORM/DB/MinIO/HTTP — écrits, NON EXÉCUTÉS localement (CI validera) ──────

class RapportOmbragePdfDbTest(unittest.TestCase):
    """Marqueur : ``rendre_rapport_ombrage`` (``core.pdf.render_pdf``) et la
    route ``GET rapport-ombrage.pdf/`` (tenant, ``PeutVoirCalepinage``, 400
    ``shading12x24`` nommé) exigent une base + WeasyPrint — CI validera."""

    @unittest.skip('ORM/WeasyPrint/HTTP — CI validera (non exécuté '
                   'localement)')
    def test_pdf_deux_pans_deux_blocs(self):
        raise NotImplementedError
