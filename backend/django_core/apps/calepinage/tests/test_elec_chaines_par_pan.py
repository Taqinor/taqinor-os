"""CAL124 — deux azimuts ne partagent JAMAIS une chaîne.

Le cas de référence est une toiture à TROIS pans sur un onduleur à DEUX
entrées MPPT : c'est là que la faute se produit (mélanger deux orientations en
série) et c'est là que le message doit NOMMER l'onduleur et le pan en trop.

Aucune base de données : le service prend un document de conception et deux
blocs de fiche technique (la forme rendue par
``apps.stock.selectors.specs_for_produit``), pas des enregistrements.

Les valeurs de fiche ci-dessous sont des VALEURS D'ESSAI, pas un produit du
catalogue : elles ne servent qu'à fermer la fenêtre de tension.

Run :
    python manage.py test apps.calepinage.tests.test_elec_chaines_par_pan -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import (
    concevoir_par_pan,
    groupes_electriques,
    pans_poses,
)
from apps.calepinage.services.electrique import temperatures_site

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}


def _layout(*comptes):
    """Un document v2 minimal : un pan par compte, azimuts TOUS différents."""
    azimuts = (180.0, 90.0, 270.0, 135.0)
    return {'version': 2, 'zones': [
        {'id': 'z%d' % rang, 'label': 'PAN-%d' % rang,
         'geometry': {'count': compte, 'azimuthDeg': azimuts[rang - 1],
                      'tiltDeg': 15.0}}
        for rang, compte in enumerate(comptes, start=1)]}


def _temperatures():
    return temperatures_site(
        saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0})


def _concevoir(layout, onduleur=None):
    return concevoir_par_pan(
        layout, module_specs=MODULE, onduleur_specs=onduleur or ONDULEUR,
        temperatures=_temperatures(), module_designation='Module d essai',
        onduleur_designation='Onduleur d essai 10 kW')


class LectureDuDocumentTest(SimpleTestCase):
    """Le compte POSÉ prime, l'orientation n'est jamais devinée."""

    def test_le_compte_pose_prime_sur_le_compte_souhaite(self):
        layout = {'zones': [{'label': 'A', 'neededPanels': 30,
                             'geometry': {'count': 12}}]}

        pans = pans_poses(layout)

        self.assertEqual([(p.label, p.modules) for p in pans], [('A', 12)])

    def test_pan_sans_module_est_ignore(self):
        pans = pans_poses({'zones': [{'label': 'A', 'geometry': {'count': 0}},
                                     {'label': 'B', 'neededPanels': 4}]})

        self.assertEqual([p.label for p in pans], ['B'])

    def test_orientation_absente_reste_inconnue(self):
        pans = pans_poses({'zones': [{'label': 'A', 'neededPanels': 4}]})

        self.assertIsNone(pans[0].azimut_deg)
        self.assertIsNone(pans[0].source_orientation)

    def test_un_groupe_par_pan(self):
        groupes = groupes_electriques(_layout(12, 8, 6))

        self.assertEqual([g.nb_modules for g in groupes], [12, 8, 6])


class TroisPansTest(SimpleTestCase):
    """Le cas à 3 pans sur 2 entrées MPPT."""

    def test_aucune_chaine_ne_melange_deux_pans(self):
        conception = _concevoir(_layout(12, 8, 6))

        self.assertTrue(conception.chaines)
        # Chaque chaîne porte UN pan, et la somme des chaînes d'un pan ne
        # dépasse jamais les modules posés sur ce pan.
        poses = {pan.label: pan.modules for pan in conception.pans}
        chaines_par_pan = {}
        for chaine in conception.chaines:
            self.assertIn(chaine.pan, poses)
            chaines_par_pan.setdefault(chaine.pan, 0)
            chaines_par_pan[chaine.pan] += chaine.nb_modules
        for pan, en_chaine in chaines_par_pan.items():
            self.assertLessEqual(en_chaine, poses[pan])

    def test_depassement_du_nombre_de_mppt_nomme_onduleur_et_pan(self):
        conception = _concevoir(_layout(12, 8, 6))

        message = '\n'.join(conception.alertes)
        self.assertIn("Onduleur d essai 10 kW", message)
        self.assertIn('PAN-3', message)
        self.assertFalse(conception.partage_mppt)
        self.assertIn('NON autorisé', conception.regle_mppt)

    def test_polystring_publie_autorise_le_partage_et_le_dit(self):
        onduleur = dict(ONDULEUR, chaines_max_par_mppt=2)

        conception = _concevoir(_layout(12, 8, 6), onduleur=onduleur)

        self.assertTrue(conception.partage_mppt)
        self.assertIn('AUTORISÉ', conception.regle_mppt)
        self.assertIn("Onduleur d essai 10 kW", conception.regle_mppt)
        # Aucun message de dépassement : la fiche autorise le partage.
        self.assertNotIn("n'a que 2 entrée(s) MPPT",
                         '\n'.join(conception.alertes))

    def test_deux_pans_pour_deux_entrees_ne_declenche_aucun_arbitrage(self):
        conception = _concevoir(_layout(12, 8))

        self.assertFalse(conception.partage_mppt)
        self.assertIn('un pan par entrée MPPT', conception.regle_mppt)
        self.assertNotIn("n'a que", '\n'.join(conception.alertes))

    def test_la_temperature_de_cal123_est_bien_celle_passee_au_noyau(self):
        conception = _concevoir(_layout(12, 8))

        self.assertEqual(conception.entree.temp_froid_c, -5.0)
        self.assertEqual(conception.entree.temp_chaud_c, 70.0)
        self.assertEqual(conception.temperatures.source, 'saisie')


class FicheIncompleteTest(SimpleTestCase):
    """Fiche muette ⇒ SILENCE nommé, jamais un verdict par défaut."""

    def test_module_sans_voc_ne_produit_aucun_verdict(self):
        incomplet = {cle: valeur for cle, valeur in MODULE.items()
                     if cle != 'voc_v'}

        conception = concevoir_par_pan(
            _layout(12), module_specs=incomplet, onduleur_specs=ONDULEUR,
            temperatures=_temperatures())

        self.assertTrue(conception.fiche_incomplete)
        self.assertEqual(conception.chaines, ())
        self.assertEqual(conception.bloquants, ())
        self.assertIn('module : tension à vide (Voc)', conception.manquantes)

    def test_onduleur_sans_plage_mppt_ne_produit_aucun_verdict(self):
        incomplet = {cle: valeur for cle, valeur in ONDULEUR.items()
                     if cle != 'mppt_v_max'}

        conception = concevoir_par_pan(
            _layout(12), module_specs=MODULE, onduleur_specs=incomplet,
            temperatures=_temperatures())

        self.assertTrue(conception.fiche_incomplete)
        self.assertIn('onduleur : haut de plage MPPT', conception.manquantes)

    def test_aucun_module_pose_le_dit_sans_bloquer(self):
        conception = _concevoir({'zones': []})

        self.assertFalse(conception.fiche_incomplete)
        self.assertEqual(conception.bloquants, ())
        self.assertIn("rien à chaîner", '\n'.join(conception.alertes))
