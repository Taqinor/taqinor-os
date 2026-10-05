"""ACAL309 - GET dossiers-reglementaires/ sert packs_france pour la France.

La vue est appelee directement (get_object doublé) : l'agregat et le pack sont
ceux des services reels, ici doubles aux deux seams documentes.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services.reglementaire import (
    GENRES_FRANCE, MESSAGE_GENRE_SANS_GABARIT,
)
from apps.calepinage.views import reglementaire as vue

CAL = SimpleNamespace(pk=1)


def _appel(pays, packs):
    agregat = {'calepinage': 1, 'pays': pays, 'gabarits_deposes': 0,
               'message_aucun_gabarit': None, 'dossiers': []}
    with mock.patch.object(vue, 'dossiers_du_calepinage',
                           return_value=agregat), \
            mock.patch.object(vue, 'packs_france',
                              return_value={'packs': packs}) as pf:
        reponse = vue.dossiers_reglementaires(
            SimpleNamespace(get_object=lambda: CAL), None)
    return reponse.data, pf


def _packs():
    return [{'genre': g, 'libelle': lib, 'gabarit_depose': False,
             'message': MESSAGE_GENRE_SANS_GABARIT % lib, 'dossiers': []}
            for g, lib in GENRES_FRANCE]


class PacksFranceTest(SimpleTestCase):
    def test_trois_packs_servis_avec_avancement(self):
        donnees, pf = _appel('fr', _packs())
        self.assertEqual([p['genre'] for p in donnees['packs_france']],
                         [g for g, _l in GENRES_FRANCE])
        pf.assert_called_once()

    def test_genre_sans_gabarit_message_nomme(self):
        donnees, _pf = _appel('fr', _packs())
        for pack in donnees['packs_france']:
            self.assertFalse(pack['gabarit_depose'])
            self.assertIn(pack['libelle'], pack['message'])

    def test_societe_hors_france_sans_cle(self):
        donnees, pf = _appel('ma', _packs())
        self.assertNotIn('packs_france', donnees)
        pf.assert_not_called()
