"""ACAL214 — les livrables lisent le résultat SERVI (chaîne RÉELLE).

Un calepinage fabriqué par les vrais écrivains (``enregistrer_entree`` +
``simuler_calepinage``, météo rejouée en ENTRÉE) ne porte NI ``pose`` NI
``electrique`` dans ``Calepinage.resultat`` : lire la colonne brute donnait
« pose.total_modules absente » sur toute la flotte. Ces essais exigent la
lecture du résultat servi (``rapport.resultat_du_rapport``) et jamais le
dictionnaire du contrat collé à la main.

Run :
    python manage.py test \
        apps.calepinage.tests.test_acal_resultat_servi_livrables -v2
"""
import copy

from django.test import SimpleTestCase

from apps.calepinage.services.note_calcul import (
    NoteRefusee, construire_note_calcul, motif_note_indisponible,
    rendre_note_calcul, resultat_servi_et_stocke,
)
from apps.calepinage.views.sorties import inventaire_des_sorties

from .acal_livrables_helpers import (
    calepinage_simule_reel, modifier_la_conception, patch_materiel,
)

SITE = {'ville': 'Casablanca', 'adresse': '', 'source': 'roof_point'}


class NoteDeCalculSurCalepinageReelTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pivot = calepinage_simule_reel()

    def test_le_stocke_ne_porte_ni_pose_ni_electrique(self):
        # Le défaut d'origine : la colonne brute n'a jamais ces deux blocs.
        self.assertNotIn('pose', self.pivot.resultat)
        self.assertNotIn('electrique', self.pivot.resultat)
        self.assertIn('simulation', self.pivot.resultat)

    def test_note_de_calcul_200_sur_calepinage_reel(self):
        with patch_materiel():
            octets = rendre_note_calcul(self.pivot, site=SITE, identite={},
                                        styles={})
        self.assertTrue(octets.startswith(b'%PDF'))

    def test_la_note_lit_pose_et_production_du_servi(self):
        with patch_materiel():
            servi, stocke = resultat_servi_et_stocke(self.pivot)
            note = construire_note_calcul(servi, stocke=stocke, site=SITE)
        self.assertEqual(note['pose']['total_modules'],
                         servi['pose']['total_modules'])
        self.assertTrue(note['pose']['total_modules'])
        self.assertEqual(note['production']['p50_kwh'],
                         servi['production']['total']['p50_kwh'])

    def test_lecture_pure_aucune_ecriture(self):
        avant = copy.deepcopy((self.pivot.resultat, self.pivot.roof_layout))
        with patch_materiel():
            rendre_note_calcul(self.pivot, site=SITE, identite={}, styles={})
            rendre_note_calcul(self.pivot, site=SITE, identite={}, styles={})
        self.assertEqual(avant, (self.pivot.resultat, self.pivot.roof_layout))

    def test_note_refuse_nommee_quand_simulation_perimee(self):
        perime = modifier_la_conception(calepinage_simule_reel())
        with patch_materiel(), self.assertRaises(NoteRefusee) as refus:
            rendre_note_calcul(perime, site=SITE, identite={}, styles={})
        self.assertEqual(refus.exception.champ, 'simulation')
        # Le motif SERVI, jamais un P50 d'un ancien toit.
        self.assertIn('simulation', str(refus.exception).lower())

    def test_inventaire_sorties_note_indisponible_si_lecture_stricte_refuse(
            self):
        perime = modifier_la_conception(calepinage_simule_reel())
        with patch_materiel():
            self.assertIsNone(motif_note_indisponible(self.pivot))
            motif = motif_note_indisponible(perime)
        self.assertTrue(motif)

    def test_inventaire_note_et_pack_disponibles_sur_calepinage_frais(self):
        class Inventorie:
            pk = 7
            titre = 't'
            layout_hash = 'a' * 64
            version_moteur = 'v'
            roof_image = ''

            def __init__(self, pivot):
                self.roof_layout = pivot.roof_layout
                self.resultat = pivot.resultat
                self.company = None

        with patch_materiel():
            sorties = {s['code']: s for s in inventaire_des_sorties(
                Inventorie(self.pivot))['sorties']}
        self.assertTrue(sorties['note_calcul_pdf']['disponible'])
        self.assertIsNone(sorties['note_calcul_pdf']['motif_indisponible'])
