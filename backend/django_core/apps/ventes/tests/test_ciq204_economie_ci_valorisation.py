"""CIQ204 — valorisation ``economie_ci`` (1/6) : avant − après, heure par
heure au prix du poste, jamais la prime fixe.

SimpleTestCase : aucune base. Entrée = forme de l'aperçu C&I (contrat CIQ2).
"""
import json
import os
import random

from django.test import SimpleTestCase

from apps.ventes import economie_ci as eco
from apps.ventes import tarif_ci as tc


def _apercu(auto_par_heure, charge_par_heure, tension='bt', mois=range(1, 13),
            nb_jours=30):
    horaire, jours = [], []
    for m in mois:
        horaire.append({'mois': m, 'type_jour': 'ouvre', 'nb_jours': nb_jours,
                        'autoconso_kwh': list(auto_par_heure(m)),
                        'surplus_kwh': [0.0] * 24})
        jours.append({'mois': m, 'type_jour': 'ouvre', 'nb_jours': nb_jours,
                      'charge_kwh': list(charge_par_heure(m))})
    return {
        'entrees_resolues': {'tension': {'valeur': tension}},
        'profil_charge': {'jours_types': jours},
        'bilan': {'horaire': horaire, 'non_valorise_kwh': 1234,
                  'surplus_kwh': 1234},
    }


def _soleil(pic):
    return lambda _m: [pic if 8 <= h < 17 else 0.0 for h in range(24)]


def _plat(v):
    return lambda _m: [v] * 24


TARIF_MT_REPLI = tc.tarif_applicable(None, tension='mt')
TARIF_MT_FACTURE = tc.tarif_applicable({
    'contrat': 'mt_general', 'base_tarifs': 'ht', 'provenance': 'facture',
    'date_facture': '2026-08-31', 'saisi_le': '2026-09-15',
    'mt': {'tarif_pointe': 1.18, 'tarif_pleines': 0.84, 'tarif_creuses': 0.62,
           'prime_fixe_kva_an': 427.18, 'puissance_souscrite_kva': 250}})
TARIF_PATENTE = tc.tarif_applicable({'contrat': 'bt_patente'})


class ProprieteTest(SimpleTestCase):
    def test_economie_jamais_au_dessus_de_la_facture_avant(self):
        rng = random.Random(204)
        for _ in range(40):
            auto = [rng.uniform(0, 60) for _h in range(24)]
            charge = [rng.uniform(0, 40) for _h in range(24)]
            for tarif, tension in ((TARIF_MT_REPLI, 'mt'),
                                   (TARIF_MT_FACTURE, 'mt'),
                                   (TARIF_PATENTE, 'bt')):
                res = eco.valoriser(
                    _apercu(lambda _m: auto, lambda _m: charge, tension),
                    tarif)
                avant = sum(e['mad_ht'] for e in
                            res['facture_avant']['energie_par_poste'])
                apres = sum(e['mad_ht'] for e in
                            res['facture_apres']['energie_par_poste'])
                total = res['economie_annee1']['total_mad']
                self.assertLessEqual(total, avant + 0.05)
                self.assertAlmostEqual(total, avant - apres, delta=0.5)


class PosteHoraireTest(SimpleTestCase):
    def test_solaire_en_pleines_vaut_pleines_meme_si_conso_en_pointe(self):
        # Tout le solaire tombe 9 h-16 h GMT (heures pleines toute l'année) ;
        # le client consomme surtout en pointe : jamais la moyenne pondérée.
        def charge(m):
            pointe = range(17, 22) if m in (1, 2, 3, 10, 11, 12) else range(18, 23)
            return [60.0 if h in pointe else (10.0 if 9 <= h < 16 else 2.0)
                    for h in range(24)]
        auto = lambda _m: [10.0 if 9 <= h < 16 else 0.0 for h in range(24)]  # noqa: E731
        res = eco.valoriser(_apercu(auto, charge, 'mt'), TARIF_MT_REPLI)
        par_poste = res['economie_annee1']['par_poste']
        self.assertEqual([p['poste'] for p in par_poste], ['pleines'])
        self.assertEqual(par_poste[0]['tarif_kwh_ttc'], 1.0101)

    def test_prime_fixe_identique_avant_apres(self):
        res = eco.valoriser(_apercu(_soleil(20.0), _plat(30.0), 'mt'),
                            TARIF_MT_FACTURE)
        self.assertEqual(res['facture_avant']['prime_fixe_mad'], 106795.0)
        self.assertEqual(res['facture_avant']['prime_fixe_mad'],
                         res['facture_apres']['prime_fixe_mad'])
        self.assertIsNone(res['revente'])  # MT : étape dédiée


class BtTest(SimpleTestCase):
    def test_bt_aucune_revente_et_mention(self):
        res = eco.valoriser(_apercu(_soleil(5.0), _plat(1.0), 'bt'),
                            TARIF_PATENTE)
        self.assertEqual(res['revente']['statut'], 'absente_bt')
        self.assertEqual(res['revente']['tarifs'], [])
        self.assertIsNone(res['revente']['valeur_mad_an'])
        from apps.ventes.quote_engine.constants_82_21 import MENTION_BT
        self.assertIn(MENTION_BT, res['revente']['mentions'])

    def test_lecture_progressive_par_tranche(self):
        # 10 kWh/h × 24 h × 30 j = 7 200 kWh/mois ; 1 kWh/h évité 9 h → 270 kWh
        res = eco.valoriser(
            _apercu(lambda _m: [1.0 if 8 <= h < 17 else 0.0
                                for h in range(24)], _plat(10.0), 'bt'),
            TARIF_PATENTE)
        par_poste = res['economie_annee1']['par_poste']
        # Conso très au-dessus de 150 kWh : tout l'évité tombe en tranche 2.
        self.assertEqual([p['poste'] for p in par_poste], ['tranche_2'])
        self.assertEqual(par_poste[0]['kwh_evites'], 270 * 12)

    def test_conso_inversee_plafonnee_et_etiquetee(self):
        res = eco.valoriser(_apercu(_soleil(5.0), _plat(5.0), 'bt'),
                            TARIF_PATENTE, facture_energie_declaree_ttc=1000)
        self.assertLessEqual(res['economie_annee1']['total_mad_ttc'], 1000.01)
        self.assertTrue(any(eco.ETIQUETTE_CONSO_ESTIMEE == h['source']
                            for h in res['hypotheses']))


class OmisTest(SimpleTestCase):
    def test_tarif_omis_statut_omis(self):
        res = eco.valoriser(_apercu(_soleil(5.0), _plat(5.0)),
                            tc.tarif_applicable(None))
        self.assertEqual(res['statut'], 'omis')
        self.assertEqual(res['motifs_omission'], [eco.MOTIF_TARIF_OMIS])
        self.assertIsNone(res['economie_annee1'])


class GardesTest(SimpleTestCase):
    def test_aucun_prix_plat_dans_le_module(self):
        with open(eco.__file__, encoding='utf-8') as fh:
            src = fh.read()
        for interdit in ('KWH_PRICE', 'onee_tarif_kwh', 'AUTOCONSO_SANS',
                         '_FALLBACK_KWH_PRICE'):
            self.assertNotIn(interdit, src)

    def test_aucune_cle_interdite(self):
        from apps.calepinage.services.note_calcul import (
            CLES_INTERDITES, CLES_INTERDITES_EXACTES)
        res = eco.valoriser(_apercu(_soleil(20.0), _plat(30.0), 'mt'),
                            TARIF_MT_FACTURE)

        def cles(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    yield k
                    yield from cles(v)
            elif isinstance(o, list):
                for v in o:
                    yield from cles(v)
        for k in cles(res):
            self.assertNotIn(k, CLES_INTERDITES_EXACTES)
            jetons = '_%s_' % k
            for interdit in CLES_INTERDITES:
                self.assertNotIn('_%s_' % interdit, jetons)

    def test_forme_du_contrat(self):
        chemin = os.path.join(os.path.dirname(__file__), os.pardir,
                              'contract_samples', 'economie_ci.json')
        with open(chemin, encoding='utf-8') as fh:
            ex = json.load(fh)['exemple_industriel_mt']
        res = eco.valoriser(_apercu(_soleil(20.0), _plat(30.0), 'mt'),
                            TARIF_MT_FACTURE)
        self.assertEqual(set(ex['economie_annee1']) - {'total_mad_ttc'},
                         set(res['economie_annee1']) - {'total_mad_ttc'})
        self.assertLessEqual(set(ex['economie_annee1']['par_poste'][0]),
                             set(res['economie_annee1']['par_poste'][0]))
        self.assertLessEqual(set(ex['facture_avant']['energie_par_poste'][0]),
                             set(res['facture_avant']['energie_par_poste'][0]))
