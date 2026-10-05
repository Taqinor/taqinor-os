"""CIQ207 — ``economie_ci`` (4/6) : revente 82-21 du surplus HORAIRE, MT/HT
seulement, tarif ANRE brut HT, plafond 20 % de la production, hors retour.

SimpleTestCase : aucune base.
"""
from django.test import SimpleTestCase

from apps.parametres import tarifs_officiels as officiels
from apps.ventes import economie_ci as eco
from apps.ventes.quote_engine.constants_82_21 import MENTION_BT


def _apercu(surplus_heure=11, kwh=100.0, nb_jours=25, production=100000):
    horaire = []
    for m in range(1, 13):
        surplus = [0.0] * 24
        surplus[surplus_heure] = kwh
        horaire.append({'mois': m, 'type_jour': 'ouvre', 'nb_jours': nb_jours,
                        'autoconso_kwh': [0.0] * 24, 'surplus_kwh': surplus})
    return {'bilan': {'horaire': horaire, 'production_kwh': production,
                      'surplus_kwh': kwh * nb_jours * 12}}


class BtTest(SimpleTestCase):
    def test_bt_revente_demandee_aucun_chiffre_mention_bt(self):
        res = eco.revente_ci(_apercu(), tension='bt', revente_demandee=True)
        self.assertEqual(res['statut'], 'absente_bt')
        self.assertIsNone(res['valeur_mad_an'])
        self.assertIsNone(res['kwh_an'])
        self.assertEqual(res['tarifs'], [])
        self.assertIn(MENTION_BT, res['mentions'])
        self.assertIn(eco.MENTION_REVENTE_IGNOREE_BT, res['mentions'])


class MtTest(SimpleTestCase):
    def test_heure_hors_pointe(self):
        # Garde du jeu d'essai : 11 h GMT est hors pointe toute l'année.
        for m in range(1, 13):
            self.assertNotEqual(officiels.poste_horaire(m, 11), 'pointe')

    def test_30000_surplus_100000_produits_plafond_20000(self):
        res = eco.revente_ci(_apercu(), tension='mt', revente_demandee=True)
        self.assertEqual(res['statut'], 'calculee')
        self.assertEqual(res['plafond_kwh'], 20000)
        self.assertEqual(res['kwh_an'], 20000)
        self.assertEqual(res['valeur_mad_an'], 3600.0)
        self.assertEqual(res['tarifs'], [
            {'poste': 'hors_pointe', 'kwh': 20000, 'tarif_kwh_ht': 0.18}])
        self.assertIn(eco.MENTION_NON_GARANTI, res['mentions'])
        self.assertIn(eco.MENTION_SECOND_COMPTEUR, res['mentions'])

    def test_sous_le_plafond_tout_le_surplus(self):
        res = eco.revente_ci(_apercu(kwh=10.0), tension='mt',
                             revente_demandee=True)
        self.assertEqual(res['kwh_an'], 3000)
        self.assertEqual(res['valeur_mad_an'], 540.0)

    def test_mt_sans_revente_demandee_rien(self):
        self.assertIsNone(eco.revente_ci(_apercu(), tension='mt',
                                         revente_demandee=False))

    def test_signature_apres_fevrier_2027_omise(self):
        res = eco.revente_ci(_apercu(), tension='mt', revente_demandee=True,
                             date_signature_prevue='2027-03-01')
        self.assertEqual(res['statut'], 'omise')
        self.assertIsNone(res['valeur_mad_an'])
        self.assertIn('28/02/2027', res['mentions'][0])

    def test_retour_identique_avec_et_sans_revente(self):
        base = eco.base_economique(
            'oui', investissement={'ht': 400000.0, 'ttc': 480000.0},
            economie_annee1={'total_mad': 80000.0, 'total_mad_ttc': 96000.0})
        sans = eco.flux_ci(base, production_annee1_kwh=100000)
        revente = eco.revente_ci(_apercu(), tension='mt',
                                 revente_demandee=True)
        self.assertEqual(revente['valeur_mad_an'], 3600.0)
        avec = eco.flux_ci(base, production_annee1_kwh=100000)
        self.assertEqual(avec['indicateurs']['retour_ans'],
                         sans['indicateurs']['retour_ans'])
        self.assertEqual(avec['indicateurs']['tri_pct'],
                         sans['indicateurs']['tri_pct'])
