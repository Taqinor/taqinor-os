"""ACAL245 - date et auteur du releve par ligne de pose reelle.

Essais PURS sur le code reel (comparer, _ligne_du_contrat, _valider_saisie) :
la date est servie par ligne, facultative en correction d'un pan deja releve,
refusee a la premiere saisie, et figee avec son auteur dans le bloc des ecarts.
"""
import datetime

from django.test import SimpleTestCase

from apps.calepinage.services import asbuilt as service

AUTEUR = {'id': 3, 'nom_complet': 'Chef de chantier'}
PREVUS = [{'pan': 'P', 'modules': 12}]
SAISIE = {'pan': 'P', 'modules_poses': 12, 'ecarts_position': '',
          'releve_le': datetime.date(2026, 9, 1), 'releve_par': AUTEUR}


def lignes(saisies):
    ecarts = service._agreger(1, service.SOURCE_VARIANTE,
                              service.comparer(PREVUS, saisies))
    return service._forme_contrat(ecarts, None)['lignes']


class PoseReelleTest(SimpleTestCase):
    def test_get_sert_releve_le_et_releve_par_par_ligne(self):
        ligne = lignes([SAISIE])[0]
        self.assertEqual(ligne['releve_le'], '2026-09-01')
        self.assertEqual(ligne['releve_par'], AUTEUR)

    def test_pan_non_releve_sans_date_ni_auteur(self):
        ligne = lignes([])[0]
        self.assertIsNone(ligne['releve_le'])
        self.assertIsNone(ligne['releve_par'])

    def test_correction_du_texte_conserve_la_date_et_l_auteur(self):
        corps = {'pan': 'P', 'modules_poses': 12, 'ecarts_position': 'x'}
        saisie = service._valider_saisie(corps, ['P'], deja_releves={'P'})
        # Pas de date fournie : None = ne rien reecrire (ni date, ni auteur).
        self.assertIsNone(saisie['releve_le'])
        fournie = service._valider_saisie(
            dict(corps, releve_le='2026-09-05'), ['P'], deja_releves={'P'})
        self.assertEqual(fournie['releve_le'], datetime.date(2026, 9, 5))

    def test_premiere_saisie_sans_date_refusee_sous_releve_le(self):
        with self.assertRaises(service.PoseRefusee) as refus:
            service._valider_saisie({'pan': 'P', 'modules_poses': 12}, ['P'])
        self.assertEqual(refus.exception.champ, 'releve_le')

    def test_version_figee_garde_date_et_auteur(self):
        bloc = lignes([SAISIE])
        meme = lignes([dict(SAISIE)])
        self.assertEqual(bloc, meme)
        self.assertEqual(bloc[0]['releve_par'], AUTEUR)
        self.assertEqual(bloc[0]['releve_le'], '2026-09-01')
