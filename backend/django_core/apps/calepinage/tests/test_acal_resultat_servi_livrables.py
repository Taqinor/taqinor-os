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
from html import escape
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services.note_calcul import (
    NoteRefusee, construire_note_calcul, motif_note_indisponible,
    rendre_note_calcul, resultat_servi_et_stocke,
)
from apps.calepinage.services.documents.presentation_compacte import (
    MOTIF_SANS_RESULTAT, html_de_presentation_compacte,
)
from apps.calepinage.services import export_tableur
from apps.calepinage.services.planche import (
    MENTION_NON_CHAINE, rendre_plan_pose_svg,
)
from apps.calepinage.views.sorties import inventaire_des_sorties

from .acal_livrables_helpers import (
    LAYOUT_PLANCHE_SIMULABLE, LAYOUT_SIMULABLE, PivotSansBase,
    calepinage_simule_reel,
    modifier_la_conception, patch_materiel,
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


class PresentationCompacteSurResultatServiTest(SimpleTestCase):
    """ACAL215 — la page 2 lit la production SERVIE, jamais la colonne brute."""

    def test_presentation_n_imprime_aucune_production_quand_simulation_perimee(
            self):
        perime = modifier_la_conception(calepinage_simule_reel())
        with patch_materiel():
            servi, _stocke = resultat_servi_et_stocke(perime)
            html = html_de_presentation_compacte(perime)
        # On compare le TEXTE produit (jamais une valeur numérique).
        self.assertNotIn('presentation-mensuelle', html)
        self.assertNotIn('Production P50 (kWh)', html)
        self.assertIn(escape(servi['motif'][:30]), html)

    def test_presentation_sans_simulation_garde_le_motif_sans_resultat(self):
        jamais = PivotSansBase(copy.deepcopy(LAYOUT_SIMULABLE))
        with patch_materiel():
            html = html_de_presentation_compacte(jamais)
        self.assertNotIn('presentation-mensuelle', html)
        # Le motif est échappé par la mise en page : on compare son début.
        self.assertIn(MOTIF_SANS_RESULTAT[:30], html)

    def test_presentation_pied_porte_l_empreinte_de_la_simulation_fraiche(
            self):
        pivot = calepinage_simule_reel()
        with patch_materiel():
            servi, _stocke = resultat_servi_et_stocke(pivot)
            html = html_de_presentation_compacte(pivot)
        self.assertIn('presentation-mensuelle', html)
        self.assertTrue(servi['hash_entree'])
        self.assertIn(servi['hash_entree'][:12], html)


class PlanDePoseEtClasseurSurResultatServiTest(SimpleTestCase):
    """ACAL216 — bandeau Chaînes et feuilles Chaînes/Nomenclature du servi."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pivot = calepinage_simule_reel(LAYOUT_PLANCHE_SIMULABLE)

    def _tables(self, pivot):
        with patch_materiel(), mock.patch.object(
                export_tableur, '_table_fixation', return_value=None):
            return export_tableur._tables_du_calepinage(pivot)

    def test_plan_de_pose_porte_les_chaines_du_calepinage_reel(self):
        with patch_materiel():
            from apps.calepinage import selectors

            servi = selectors.resultat_servi(self.pivot)
            svg = rendre_plan_pose_svg(self.pivot)
        self.assertNotIn('electrique', self.pivot.resultat)
        self.assertIn('Chaînes : %s' % servi['electrique']['chainage']
                      ['chaines'], svg)
        self.assertIn('Onduleur', svg)

    def test_plan_de_pose_non_chaine_le_dit_sans_erreur(self):
        jamais = PivotSansBase(copy.deepcopy(LAYOUT_PLANCHE_SIMULABLE))
        with patch_materiel():
            svg = rendre_plan_pose_svg(jamais)
        self.assertIn(MENTION_NON_CHAINE, svg)

    def test_classeur_chaines_et_nomenclature_remplis(self):
        with patch_materiel():
            from apps.calepinage import selectors

            servi = selectors.resultat_servi(self.pivot)
        tables = {titre: (entetes, lignes)
                  for titre, entetes, lignes in self._tables(self.pivot)}
        chaines = dict((ligne[0], ligne[1])
                       for ligne in tables['Chaînes'][1])
        self.assertEqual(chaines['Nombre de chaînes'],
                         servi['electrique']['chainage']['chaines'])
        modules = [ligne for ligne in tables['Nomenclature'][1]
                   if ligne[0].startswith('Module photovoltaïque')]
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0][1], servi['pose']['total_modules'])

    def test_deux_exports_successifs_donnent_les_memes_tables(self):
        self.assertEqual(self._tables(self.pivot), self._tables(self.pivot))
