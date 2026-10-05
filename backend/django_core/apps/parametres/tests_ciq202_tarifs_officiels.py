"""CIQ202 — grille officielle ONEE sourcée (module PUR de fondation).

SimpleTestCase : aucune base. Forme d'une ligne = ``grille_officielle``
du contrat partagé ``apps/ventes/contract_samples/tarifs_ci.json``.
"""
import json
import os

from django.test import SimpleTestCase

from apps.parametres import tarifs_officiels as t

_CONTRAT = os.path.join(os.path.dirname(__file__), os.pardir, 'ventes',
                        'contract_samples', 'tarifs_ci.json')


class GrilleMtTest(SimpleTestCase):
    def test_valeurs_mt_publiees(self):
        self.assertEqual(t.MT_GENERAL['pointe']['valeur'], 1.4157)
        self.assertEqual(t.MT_GENERAL['pleines']['valeur'], 1.0101)
        self.assertEqual(t.MT_GENERAL['creuses']['valeur'], 0.7398)
        self.assertEqual(t.MT_GENERAL['prime_fixe_kva_an']['valeur'], 512.62)
        self.assertEqual(t.MT_GENERAL['pointe']['tva_libelle_page'], 18)
        self.assertEqual(t.MT_GENERAL['pointe']['base'], 'TTC publié')
        self.assertEqual(t.MT_GENERAL['pointe']['inchange_depuis'], '2023-11-30')

    def test_forme_de_ligne_du_contrat(self):
        with open(_CONTRAT, encoding='utf-8') as fh:
            contrat = json.load(fh)
        exemple = contrat['grille_officielle']['exemple_ligne']
        ligne = t.MT_GENERAL['pointe']
        self.assertEqual(set(contrat['grille_officielle']['forme_ligne']),
                         set(ligne))
        for cle in ('cle', 'valeur', 'unite', 'base', 'tva_libelle_page',
                    'page_audience', 'releve_le', 'inchange_depuis',
                    'regle_tranches'):
            self.assertEqual(ligne[cle], exemple[cle], cle)

    def test_grands_comptes_exclus(self):
        valeurs = {v['valeur'] for v in t.MT_GENERAL.values()}
        for exclue in (494.09, 1.3645, 0.9736, 0.7131):
            self.assertNotIn(exclue, valeurs)


class PostesHorairesTest(SimpleTestCase):
    def test_hiver_18h_pointe(self):
        self.assertEqual(t.poste_horaire(12, 18), 'pointe')

    def test_ete_18h_pointe(self):
        self.assertEqual(t.poste_horaire(6, 18), 'pointe')

    def test_ete_17h_pleines(self):
        self.assertEqual(t.poste_horaire(6, 17), 'pleines')

    def test_hiver_6h_creuses(self):
        self.assertEqual(t.poste_horaire(12, 6), 'creuses')

    def test_creuses_enjambe_minuit(self):
        self.assertEqual(t.poste_horaire(1, 23), 'creuses')
        self.assertEqual(t.poste_horaire(7, 23), 'creuses')
        self.assertEqual(t.poste_horaire(7, 0), 'creuses')

    def test_chaque_heure_a_un_poste(self):
        for mois in range(1, 13):
            for h in range(24):
                self.assertIn(t.poste_horaire(mois, h),
                              ('pointe', 'pleines', 'creuses'))

    def test_bornes_de_saison(self):
        self.assertEqual(t.saison(3), 'hiver')
        self.assertEqual(t.saison(4), 'ete')
        self.assertEqual(t.saison(9), 'ete')
        self.assertEqual(t.saison(10), 'hiver')


class GrilleBtTest(SimpleTestCase):
    def test_patente(self):
        g = t.grille_bt('bt_patente')
        self.assertEqual([x['valeur'] for x in g], [1.5146, 1.7090])
        self.assertEqual(g[0]['regle_tranches'], 'non_publiee')
        self.assertIn('20250216142859', g[0]['source_url'])

    def test_force_motrice(self):
        g = t.grille_bt('bt_force_motrice')
        self.assertEqual([x['valeur'] for x in g], [1.3639, 1.4663, 1.6758])

    def test_bi_horaire_force_motrice(self):
        g = t.grille_bt('bt_force_motrice', option_bi_horaire=True)
        self.assertEqual([x['valeur'] for x in g], [2.4250, 1.3472])

    def test_bi_horaire_patente_refuse(self):
        with self.assertRaises(ValueError) as ctx:
            t.grille_bt('bt_patente', option_bi_horaire=True)
        self.assertIn('option_bi_horaire', str(ctx.exception))

    def test_copies_jamais_les_originaux(self):
        g = t.grille_bt('bt_patente')
        g[0]['valeur'] = 0
        self.assertEqual(t.BT_PATENTE[0]['valeur'], 1.5146)


class PureteTest(SimpleTestCase):
    def test_aucun_import_d_app(self):
        with open(t.__file__, encoding='utf-8') as fh:
            src = fh.read()
        self.assertNotIn('from apps', src)
        self.assertNotIn('import django', src)
