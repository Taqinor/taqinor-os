"""CALX6 — la porte ``export-csv`` SERT la série persistée, ou refuse en la nommant.

CE QUE CE FICHIER TIENT
-----------------------
``services/export_csv.py`` (CAL144) offre trois sorties — ``horaire``,
``mensuel``, ``ombrage`` — et ``views/export_csv.py`` les sert sur
``calepinages/<pk>/export-csv/?quoi=…``. Jusqu'à CALX6, cette porte n'avait
AUCUN consommateur : un export construit et injoignable n'existe pas. Le
panneau « Séries » l'appelle désormais, et ce fichier affirme les deux moitiés
du contrat que l'écran attend :

* **après une simulation**, ``?quoi=horaire`` rend un FICHIER non vide, avec
  son en-tête de provenance et ses sept colonnes historiques ;
* **sans simulation**, le refus est un 400 dont la clé NOMME le champ absent
  (``points``, ``mensuel``, ``shading12x24``) — c'est ce motif-là que l'écran
  affiche sous le bouton, jamais un « export impossible » générique.

LA SÉRIE N'EST PAS ÉCRITE ICI. Elle est persistée par la chaîne de pertes
(CALX193, ``resultat['serie_horaire']``) et sa forme est figée par
``contract_samples/calepinage_serie_horaire.json`` (CALX142). Ce test
l'INJECTE telle qu'elle est committée — patron de CALX70 : le document est
écrit à la main dans ``resultat``, sans base de données ni réseau. Le test
frontend (``atelier/PanneauSeries.test.jsx``) relit le MÊME fichier : les deux
moitiés ne peuvent pas diverger en silence.

Aucune base : la vue est appelée directement avec un ``self`` factice dont
``get_object()`` rend le calepinage d'essai (le bornage par société reste
l'affaire de ``get_queryset``, couvert par ``test_isolation_societe``).

Run :
    python manage.py test apps.calepinage.tests.test_calx6_serie_horaire -v2
"""
from __future__ import annotations

import copy
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.export_csv import EXPORTS
from apps.calepinage.views.export_csv import (
    document_exportable, export_csv_simulation,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
CONTRAT = json.loads((ECHANTILLONS / 'calepinage_serie_horaire.json')
                     .read_text(encoding='utf-8'))

#: L'agrégat mensuel et la matrice d'ombrage d'essai : des repères ASSUMÉS,
#: qui ne décrivent aucune installation réelle (D-CALX 7). Ce test vérifie la
#: porte et ses refus, jamais un chiffre de production.
MENSUEL = {'base': {'base_rayonnement': 'PVGIS-SARAH3',
                    'fenetre_annees': '2020-2020',
                    'loss_passee_pct': 7.25},
           'total': {'p50_kwh': 1234.5},
           'mensuel': [{'mois': 1, 'p50_kwh': 600.25},
                       {'mois': 2, 'p50_kwh': 634.25}]}
OMBRAGE = [[1.0] * 24 for _ in range(12)]


class _Calepinage:
    """Le strict minimum que la vue lit sur un pivot — aucun ORM."""

    def __init__(self, resultat=None, roof_layout=None, pk=7):
        self.pk = pk
        self.resultat = resultat
        self.roof_layout = roof_layout
        self.version_moteur = 'essai-calx6'


class _Vue:
    """Le ``self`` de l'action : seul ``get_object()`` est appelé."""

    def __init__(self, calepinage):
        self._calepinage = calepinage

    def get_object(self):
        return self._calepinage


class _Requete:
    """Le strict minimum que l'action lit sur la requête."""

    def __init__(self, **parametres):
        self.query_params = dict(parametres)


def _appeler(calepinage, **parametres):
    return export_csv_simulation(_Vue(calepinage), _Requete(**parametres),
                                 pk=calepinage.pk)


def _resultat_simule():
    """Le ``resultat`` d'un calepinage SIMULÉ, série committée comprise."""
    return {
        'serie_horaire': copy.deepcopy(
            CONTRAT['exemple']['serie_horaire']),
        'production': copy.deepcopy(MENSUEL),
        'pertes': [{'poste': 'soiling', 'pct': 2.0, 'source': 'societe'}],
    }


class SerieServieTest(SimpleTestCase):
    """Après une simulation, le fichier horaire sort — et il n'est pas vide."""

    def setUp(self):
        self.calepinage = _Calepinage(resultat=_resultat_simule(),
                                      roof_layout={'shading12x24': OMBRAGE})

    def test_le_fichier_horaire_est_servi_et_non_vide(self):
        reponse = _appeler(self.calepinage, quoi='horaire')

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.content,
                        "L'export horaire a rendu un fichier VIDE alors que "
                        'la série est persistée.')
        self.assertIn('attachment', reponse['Content-Disposition'])
        self.assertIn('calepinage-7-horaire.csv',
                      reponse['Content-Disposition'])

    def test_le_fichier_porte_les_points_de_la_serie_committee(self):
        texte = _appeler(self.calepinage,
                         quoi='horaire').content.decode('utf-8-sig')
        points = CONTRAT['exemple']['serie_horaire']['points']

        # Une ligne de tableau par point committé, en plus de l'en-tête de
        # provenance et de la ligne de titres.
        lignes = [ligne for ligne in texte.splitlines()
                  if ligne and ligne[0].isdigit()]
        self.assertEqual(len(lignes), len(points))
        # Le point de 13 h : ``p_w`` (watts) devient des kW à la française.
        midi = [point for point in points if point['heure'] == 13][0]
        attendu = f'{midi["p_w"] / 1000.0:.3f}'.replace('.', ',')
        self.assertIn(attendu, texte)

    def test_le_bloc_calx193_est_lu_par_sa_cle_points(self):
        """Le BLOC (CALX142/CALX193), pas une liste nue, est bien déplié."""
        document = document_exportable(self.calepinage)
        self.assertEqual(
            document['points'],
            CONTRAT['exemple']['serie_horaire']['points'])

    def test_les_trois_exports_sortent_sur_un_calepinage_simule(self):
        for quoi in EXPORTS:
            with self.subTest(quoi=quoi):
                reponse = _appeler(self.calepinage, quoi=quoi)
                self.assertEqual(reponse.status_code, 200, quoi)
                self.assertTrue(reponse.content, quoi)

    def test_aucun_prix_dans_le_fichier_servi(self):
        texte = _appeler(self.calepinage,
                         quoi='horaire').content.decode('utf-8-sig').lower()
        for interdit in ('prix', 'marge', 'mad', 'dh '):
            self.assertNotIn(interdit, texte)


class RefusQuiNommeLeChampTest(SimpleTestCase):
    """Sans simulation, le 400 nomme le champ — jamais un fichier de zéros."""

    def test_serie_absente_le_refus_nomme_points(self):
        reponse = _appeler(_Calepinage(resultat={}), quoi='horaire')

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('points', reponse.data)
        self.assertIn('simulation', reponse.data['points'][0].lower())
        self.assertEqual(list(reponse.data['exports_disponibles']),
                         list(EXPORTS))

    def test_serie_vide_du_contrat_refusee_de_la_meme_facon(self):
        """L'état « posé, jamais simulé » du contrat : points = []."""
        vide = copy.deepcopy(CONTRAT['exemple_vide']['serie_horaire'])
        reponse = _appeler(_Calepinage(resultat={'serie_horaire': vide}),
                           quoi='horaire')

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('points', reponse.data)

    def test_mensuel_absent_le_refus_nomme_mensuel(self):
        reponse = _appeler(_Calepinage(resultat={}), quoi='mensuel')

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('mensuel', reponse.data)

    def test_ombrage_absent_le_refus_nomme_la_matrice(self):
        reponse = _appeler(_Calepinage(resultat=_resultat_simule()),
                           quoi='ombrage')

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('shading12x24', reponse.data)

    def test_export_inconnu_refuse_en_listant_les_exports(self):
        reponse = _appeler(_Calepinage(resultat=_resultat_simule()),
                           quoi='trimestriel')

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('quoi', reponse.data)
        self.assertEqual(list(reponse.data['exports_disponibles']),
                         list(EXPORTS))

    def test_sans_parametre_quoi_la_serie_horaire_est_demandee(self):
        """Le défaut du serveur reste ``horaire`` — le panneau s'y fie."""
        reponse = _appeler(_Calepinage(resultat={}))

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('points', reponse.data)


class ContratPartageTest(SimpleTestCase):
    """L'échantillon committé est celui que les deux moitiés relisent."""

    def test_l_echantillon_decrit_la_porte_appelee_par_l_ecran(self):
        self.assertTrue(CONTRAT['endpoint'].startswith('GET '))
        self.assertTrue(CONTRAT['endpoint'].rstrip('/').endswith('export-csv'))

    def test_les_sept_colonnes_historiques_sont_au_contrat(self):
        colonnes = CONTRAT['exemple']['serie_horaire']['colonnes']
        for attendue in ('annee', 'mois', 'jour', 'heure', 'p_w', 'gi_w_m2',
                         't2m_c'):
            self.assertIn(attendue, colonnes)

    def test_les_trois_exports_offerts_sont_ceux_du_service(self):
        self.assertEqual(list(EXPORTS), ['horaire', 'mensuel', 'ombrage'])
