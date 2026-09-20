"""CAL147 — le profil de consommation depuis les factures du lead.

Tests PURS : le lead est LU par un point d'injection qui remplace le sélecteur
CRM (``apps.crm.selectors.get_company_lead``), donc aucune base n'est
nécessaire et la frontière inter-apps reste celle du code de production.
"""
from __future__ import annotations

import unittest
from decimal import Decimal

from apps.calepinage.services.consommation import (
    ProfilInvalide, interpoler_factures, profil_depuis_lead, profil_mensuel,
)


class LeadEssai:
    """Un lead d'ESSAI : seulement les champs que le service a le droit de lire."""

    def __init__(self, **champs):
        self.facture_hiver = champs.get('facture_hiver')
        self.facture_ete = champs.get('facture_ete')
        self.ete_differente = champs.get('ete_differente', False)
        self.conso_mensuelle_kwh = champs.get('conso_mensuelle_kwh')


def lecteur(lead):
    def lire(company, lead_id):
        return lead
    return lire


class InterpolationTest(unittest.TestCase):
    """La forme est le PORT EXACT de celle de l'écran devis."""

    def test_sept_mois_vers_lete_puis_cinq_vers_lhiver(self):
        montants = interpoler_factures(600, 1200)
        self.assertEqual(len(montants), 12)
        self.assertEqual(montants[0], 600)        # janvier = facture d'hiver
        self.assertEqual(montants[6], 1200)       # juillet = facture d'été
        self.assertEqual(montants[7], 1200)       # la seconde pente démarre à l'été
        self.assertEqual(montants[11], 600)       # décembre revient à l'hiver
        self.assertEqual(montants[1] - montants[0], 100)

    def test_sans_facture_dete_le_profil_est_plat(self):
        self.assertEqual(interpoler_factures(750, None), [750.0] * 12)

    def test_sans_facture_du_tout_les_douze_mois_sont_vides(self):
        self.assertEqual(interpoler_factures(None, None), [None] * 12)


class ProfilMensuelTest(unittest.TestCase):

    def test_chaque_mois_porte_sa_source(self):
        profil = profil_mensuel(facture_hiver=600, facture_ete=1200,
                                ete_differente=True)
        par_mois = {ligne['mois']: ligne for ligne in profil['mois']}
        self.assertEqual(par_mois[1]['source'], 'facture')
        self.assertEqual(par_mois[7]['source'], 'facture')
        self.assertEqual(par_mois[4]['source'], 'interpole')
        self.assertEqual(par_mois[1]['facture_mad'], 600.0)
        self.assertEqual(par_mois[7]['facture_mad'], 1200.0)
        self.assertEqual(profil['annuel_mad'],
                         round(sum(interpoler_factures(600, 1200)), 2))

    def test_ete_non_different_reprend_la_facture_dhiver(self):
        profil = profil_mensuel(facture_hiver=800, facture_ete=1500,
                                ete_differente=False)
        self.assertEqual({ligne['facture_mad'] for ligne in profil['mois']},
                         {800.0})
        self.assertTrue(profil['ete_differente'] is False)

    def test_ete_different_annonce_mais_non_renseigne_est_dit(self):
        profil = profil_mensuel(facture_hiver=800, facture_ete=None,
                                ete_differente=True)
        self.assertTrue(any("facture d'été" in avis
                            for avis in profil['avertissements']))
        self.assertEqual({ligne['facture_mad'] for ligne in profil['mois']},
                         {800.0})

    def test_une_saisie_prime_et_est_marquee_saisie(self):
        profil = profil_mensuel(facture_hiver=600, facture_ete=1200,
                                ete_differente=True, saisies={3: 999})
        mars = [ligne for ligne in profil['mois'] if ligne['mois'] == 3][0]
        self.assertEqual(mars['facture_mad'], 999.0)
        self.assertEqual(mars['source'], 'saisi')

    def test_les_kwh_restent_non_calcules_et_la_raison_est_dite(self):
        profil = profil_mensuel(facture_hiver=600)
        self.assertTrue(all(ligne['kwh'] is None for ligne in profil['mois']))
        self.assertTrue(any('barème du distributeur' in avis
                            for avis in profil['avertissements']))

    def test_montant_illisible_refuse_en_nommant_le_mois(self):
        with self.assertRaises(ProfilInvalide) as capture:
            profil_mensuel(facture_hiver=600, saisies={5: 'beaucoup'})
        self.assertEqual(capture.exception.champ, 'mois[5]')

    def test_montant_negatif_refuse(self):
        with self.assertRaises(ProfilInvalide) as capture:
            profil_mensuel(facture_hiver=-10)
        self.assertEqual(capture.exception.champ, 'facture_hiver')


class ProfilDepuisLeadTest(unittest.TestCase):

    def test_lead_avec_factures_prerempli_et_editable(self):
        lead = LeadEssai(facture_hiver=Decimal('600'),
                         facture_ete=Decimal('1200'), ete_differente=True,
                         conso_mensuelle_kwh=Decimal('850'))
        profil = profil_depuis_lead('SOCIETE', 42, lire_lead=lecteur(lead),
                                    saisies={2: 700})
        self.assertEqual(profil['source'], 'lead')
        self.assertEqual(profil['conso_mensuelle_kwh_saisie'], 850.0)
        fevrier = [ligne for ligne in profil['mois']
                   if ligne['mois'] == 2][0]
        self.assertEqual((fevrier['facture_mad'], fevrier['source']),
                         (700.0, 'saisi'))

    def test_lead_sans_facture_laisse_le_profil_vide(self):
        profil = profil_depuis_lead('SOCIETE', 42,
                                    lire_lead=lecteur(LeadEssai()))
        self.assertTrue(all(ligne['facture_mad'] is None
                            for ligne in profil['mois']))
        self.assertTrue(all(ligne['source'] is None
                            for ligne in profil['mois']))
        self.assertIsNone(profil['annuel_mad'])
        self.assertIsNone(profil['source'])
        self.assertTrue(any('aucune facture moyenne' in avis.lower()
                            for avis in profil['avertissements']))

    def test_lead_dune_autre_societe_est_traite_comme_absent(self):
        # Le sélecteur CRM rend ``None`` pour un lead hors société : le
        # profil part vide, il n'emprunte jamais les factures d'autrui.
        profil = profil_depuis_lead('SOCIETE', 42, lire_lead=lecteur(None))
        self.assertIsNone(profil['source'])
        self.assertIn("Aucun lead n'est rattaché",
                      profil['avertissements'][0])

    def test_sans_lead_aucun_acces_au_crm(self):
        appels = []

        def lire(company, lead_id):  # pragma: no cover - ne doit pas courir
            appels.append((company, lead_id))
            return None

        profil = profil_depuis_lead('SOCIETE', None, lire_lead=lire)
        self.assertEqual(appels, [])
        self.assertIsNone(profil['source'])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
