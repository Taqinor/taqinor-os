"""CAL128 — les contraintes onduleur BLOQUANTES remontent jusqu'au plan.

Trois cas, et la frontière entre les deux premiers est la leçon de l'incident
DEV-202608-0016 :

* **bloquant** — l'Isc cumulé d'une entrée dépasse le courant de
  court-circuit PUBLIÉ par la fiche : le montage sort de ce que le
  constructeur garantit, le dossier ne se publie pas ;
* **alerte** — l'Imp cumulé dépasse le courant d'entrée admissible : ça
  s'installe, ça écrête, ça produit moins. Ce n'est pas un blocage ;
* **fiche muette** — aucun verdict. Ni faux vert, ni faux rouge : le silence,
  avec la liste de ce qui manque.

Run :
    python manage.py test apps.calepinage.tests.test_elec_bloquants_onduleur -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    PublicationBloquee, evaluation_electrique, garde_publication,
)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 1, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 20.0, 'phases': 3,
}


class _Calepinage:
    """Le strict minimum lu par le service — aucun ORM, aucune base."""

    pk = 7
    statut = 'brouillon'

    def __init__(self, modules):
        self.roof_layout = {'version': 2, 'zones': [
            {'label': 'PAN-A', 'geometry': {
                'count': modules, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}}]}
        self.resultat = {'entree_electrique': {
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0}}
        self.company = None


def _materiel(**onduleur):
    return {
        'module': MODULE, 'onduleur': dict(ONDULEUR, **onduleur),
        'optimiseur': None,
        'designations': {'module': 'Module d essai',
                         'onduleur': 'Onduleur d essai', 'optimiseur': ''},
        'absents': (),
    }


class VerdictBloquantTest(SimpleTestCase):
    """Isc publié dépassé : bloquant, et le message NOMME tout."""

    def test_isc_cumule_au_dessus_du_publie_bloque(self):
        # 24 modules sur UNE entrée MPPT → 2 chaînes en parallèle,
        # Isc cumulé 36,8 A face aux 26 A publiés par la fiche.
        evaluation = evaluation_electrique(
            _Calepinage(24), materiel=_materiel(isc_max_mppt_a=26.0))

        self.assertEqual(evaluation['verdict'], 'bloquant')
        self.assertFalse(evaluation['publiable'])
        message = evaluation['bloquants'][0]
        self.assertIn('Isc', message)
        self.assertIn('MPPT 1', message)
        self.assertIn('PAN-A', message)
        self.assertIn('CH1, CH2', message)
        self.assertIn('Onduleur d essai', message)

    def test_la_publication_est_refusee_et_le_refus_porte_les_bloquants(self):
        calepinage = _Calepinage(24)

        with self.assertRaises(PublicationBloquee) as capture:
            garde_publication_materiel(calepinage,
                                       _materiel(isc_max_mppt_a=26.0))

        self.assertTrue(capture.exception.bloquants)
        self.assertIn('Isc', capture.exception.bloquants[0])
        # Le statut n'est PAS touché : la garde refuse, elle ne rétrograde pas.
        self.assertEqual(calepinage.statut, 'brouillon')


def garde_publication_materiel(calepinage, materiel):
    """``garde_publication`` avec matériel injecté (aucune base de données).

    La garde de production lit le matériel par le sélecteur du stock ; ici on
    lui donne les mêmes blocs de fiche, pour tester la RÈGLE sans base.
    """
    evaluation = evaluation_electrique(calepinage, materiel=materiel)
    if evaluation['publiable']:
        return evaluation
    raise PublicationBloquee(
        'Publication refusée', bloquants=(evaluation['bloquants']
                                          or evaluation['manquantes']))


class VerdictAlerteTest(SimpleTestCase):
    """Imp dépassé : ça écrête, ça ne bloque pas."""

    def test_imp_cumule_alerte_mais_ne_bloque_pas(self):
        evaluation = evaluation_electrique(
            _Calepinage(24),
            materiel=_materiel(i_max_mppt_a=20.0, isc_max_mppt_a=45.0))

        self.assertEqual(evaluation['verdict'], 'alerte')
        self.assertTrue(evaluation['publiable'])
        self.assertEqual(evaluation['bloquants'], [])
        self.assertIn('ÉCRÊTAGE', '\n'.join(evaluation['alertes']))

    def test_champ_conforme(self):
        evaluation = evaluation_electrique(
            _Calepinage(12), materiel=_materiel(isc_max_mppt_a=45.0))

        self.assertEqual(evaluation['verdict'], 'conforme')
        self.assertTrue(evaluation['publiable'])
        self.assertEqual(evaluation['alertes'], [])


class FicheMuetteTest(SimpleTestCase):
    """Fiche incomplète ⇒ SILENCE, jamais un faux vert."""

    def test_onduleur_sans_tension_maximale_ne_rend_aucun_verdict(self):
        materiel = _materiel()
        materiel['onduleur'] = {cle: valeur
                                for cle, valeur in materiel['onduleur'].items()
                                if cle != 'v_max_abs'}

        evaluation = evaluation_electrique(_Calepinage(24),
                                           materiel=materiel)

        self.assertEqual(evaluation['verdict'], 'indetermine')
        self.assertFalse(evaluation['publiable'])
        self.assertEqual(evaluation['bloquants'], [])
        self.assertEqual(evaluation['alertes'], [])
        self.assertIn('onduleur : tension DC maximale absolue',
                      evaluation['manquantes'])

    def test_materiel_non_designe_ne_rend_aucun_verdict(self):
        vide = {'module': {}, 'onduleur': {}, 'optimiseur': None,
                'designations': {'module': '', 'onduleur': '',
                                 'optimiseur': ''},
                'absents': ('module PV non désigné',
                            'onduleur non désigné')}

        evaluation = evaluation_electrique(_Calepinage(24), materiel=vide)

        self.assertEqual(evaluation['verdict'], 'indetermine')
        self.assertIn('module PV non désigné', evaluation['manquantes'])

    def test_une_publication_indeterminee_est_refusee_en_le_disant(self):
        # Aucun matériel injecté : la garde de PRODUCTION résout le matériel
        # elle-même, ne trouve aucune désignation et refuse en le disant.
        with self.assertRaises(PublicationBloquee) as capture:
            garde_publication(_Calepinage(24))

        self.assertIn('module PV non désigné', capture.exception.bloquants)
        self.assertIn('Complétez les fiches techniques',
                      str(capture.exception))


class EvaluationAChaudTest(SimpleTestCase):
    """L'évaluation à chaud lit le dessin EN COURS et n'écrit rien."""

    def test_le_layout_du_corps_remplace_celui_enregistre(self):
        calepinage = _Calepinage(12)
        chaud = {'version': 2, 'zones': [
            {'label': 'PAN-A', 'geometry': {'count': 24, 'azimuthDeg': 180.0,
                                            'tiltDeg': 15.0}}]}

        evaluation = evaluation_electrique(
            calepinage, layout=chaud,
            materiel=_materiel(isc_max_mppt_a=26.0))

        self.assertEqual(evaluation['verdict'], 'bloquant')
        # Le document enregistré n'a pas bougé : c'est une évaluation.
        self.assertEqual(
            calepinage.roof_layout['zones'][0]['geometry']['count'], 12)
