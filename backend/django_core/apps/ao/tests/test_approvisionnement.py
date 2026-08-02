"""AOF119 — l'argument « aucun approvisionnement nouveau » est PROUVÉ ou tu.

    python -m unittest apps.ao.tests.test_approvisionnement -v
"""
import unittest

from apps.ao.fabrique import approvisionnement as appro


def equipements():
    return [
        {'role': 'module', 'reference': 'MOD-625', 'quantite': 560,
         'designation': 'Module 625 Wc'},
        {'role': 'onduleur', 'reference': 'OND-110', 'quantite': 3,
         'designation': 'Onduleur 110 kW'},
    ]


def catalogue(**remplacements):
    base = {
        'MOD-625': {'existe': True, 'archive': False, 'prix_renseigne': True,
                    'disponible': 600, 'delai_jours': 0,
                    'deja_approvisionne': True,
                    'designation': 'Module 625 Wc'},
        'OND-110': {'existe': True, 'archive': False, 'prix_renseigne': True,
                    'disponible': 4, 'delai_jours': 15,
                    'deja_approvisionne': True,
                    'designation': 'Onduleur 110 kW'},
    }
    for cle, valeurs in remplacements.items():
        base[cle] = dict(base[cle], **valeurs)
    return base


class TestArgumentProuve(unittest.TestCase):

    def test_argument_fourni_quand_tout_est_deja_approvisionne(self):
        rapport = appro.controler(equipements(), catalogue())
        self.assertTrue(rapport.argument_disponible)
        self.assertEqual(appro.argument_aucun_approvisionnement(rapport),
                         appro.PHRASE_ARGUMENT)

    def test_argument_indisponible_des_qu_un_produit_est_archive(self):
        rapport = appro.controler(equipements(),
                                  catalogue(**{'OND-110': {'archive': True}}))
        self.assertFalse(rapport.argument_disponible)
        self.assertIsNone(appro.argument_aucun_approvisionnement(rapport))

    def test_argument_indisponible_si_un_approvisionnement_est_requis(self):
        rapport = appro.controler(equipements(), catalogue(**{
            'MOD-625': {'deja_approvisionne': False, 'disponible': 120}}))
        self.assertFalse(rapport.argument_disponible)
        self.assertTrue(any('approvisionnement nouveau' in m
                            for m in rapport.motifs()))

    def test_argument_disponible_si_le_stock_couvre_le_besoin(self):
        rapport = appro.controler(equipements(), catalogue(**{
            'MOD-625': {'deja_approvisionne': False, 'disponible': 600}}))
        self.assertTrue(rapport.argument_disponible)


class TestAvertissements(unittest.TestCase):

    def test_produit_archive_remonte_en_avertissement(self):
        """Les 6 coffrets placeholders sont ARCHIVÉS par le seeder."""
        rapport = appro.controler(equipements(),
                                  catalogue(**{'OND-110': {'archive': True}}))
        avertissements = rapport.avertissements
        self.assertEqual(len(avertissements), 1)
        self.assertEqual(avertissements[0].gravite, appro.AVERTISSEMENT)
        self.assertIn('ARCHIVÉ', avertissements[0].motif)

    def test_produit_sans_prix_remonte_en_avertissement(self):
        """Les 11 pompes OSP sont livrées DÉLIBÉRÉMENT sans prix."""
        rapport = appro.controler(equipements(), catalogue(
            **{'MOD-625': {'prix_renseigne': False}}))
        self.assertTrue(any('sans prix' in c.motif
                            for c in rapport.avertissements))

    def test_produit_inconnu_du_catalogue(self):
        rapport = appro.controler(
            [{'role': 'ems', 'reference': 'EMS-X', 'quantite': 1}], {})
        self.assertTrue(any('inconnu' in c.motif
                            for c in rapport.avertissements))

    def test_disponibilite_inconnue_signale(self):
        rapport = appro.controler(equipements(), catalogue(**{
            'MOD-625': {'deja_approvisionne': False, 'disponible': None}}))
        self.assertTrue(any('inconnue' in c.motif
                            for c in rapport.avertissements))

    def test_delai_superieur_au_marche_signale(self):
        rapport = appro.controler(equipements(), catalogue(),
                                  delai_marche_jours=10)
        self.assertTrue(any('délai' in c.motif
                            for c in rapport.avertissements))

    def test_delai_dans_le_marche_ne_signale_rien(self):
        rapport = appro.controler(equipements(), catalogue(),
                                  delai_marche_jours=60)
        self.assertTrue(rapport.argument_disponible)

    def test_un_dossier_sans_equipement_ne_prouve_rien_de_faux(self):
        rapport = appro.controler([], catalogue())
        self.assertEqual(rapport.controles, ())
        self.assertTrue(rapport.argument_disponible)


class TestAucuneDonneeDeCout(unittest.TestCase):

    def test_un_etat_portant_un_prix_achat_est_refuse(self):
        pollue = catalogue()
        pollue['MOD-625']['prix_achat'] = 2100
        with self.assertRaises(appro.EtatCatalogueInvalide):
            appro.controler(equipements(), pollue)

    def test_un_etat_portant_une_marge_est_refuse(self):
        pollue = catalogue()
        pollue['OND-110']['marge_pct'] = 32
        with self.assertRaises(appro.EtatCatalogueInvalide):
            appro.controler(equipements(), pollue)

    def test_le_rapport_serialise_ne_porte_aucun_champ_de_cout(self):
        serialise = repr(appro.controler(equipements(), catalogue()).vers_dict())
        for interdit in ('prix_achat', 'cout', 'marge', 'benefice'):
            self.assertNotIn(interdit, serialise.lower(), interdit)


class TestRapport(unittest.TestCase):

    def test_les_constats_positifs_restent_en_info(self):
        rapport = appro.controler(equipements(), catalogue())
        self.assertTrue(all(c.gravite == appro.INFO for c in rapport.controles))
        self.assertEqual(rapport.motifs(), ())

    def test_serialisation_complete(self):
        d = appro.controler(equipements(), catalogue()).vers_dict()
        self.assertIn('controles', d)
        self.assertIs(d['argument_disponible'], True)

    def test_controle_deterministe(self):
        a = appro.controler(equipements(), catalogue()).vers_dict()
        b = appro.controler(equipements(), catalogue()).vers_dict()
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
