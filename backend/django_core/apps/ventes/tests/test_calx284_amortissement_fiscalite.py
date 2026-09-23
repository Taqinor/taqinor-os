"""CALX284 — amortissement et fiscalité en paramètres société.

Ce qui est prouvé (le « Done » de CALX284) :

* société VIERGE (``TariffSettings()`` à ses défauts) ⇒ aucun réglage fiscal
  n'est rendu, et le flux APRÈS impôt égale le flux AVANT impôt terme à
  terme ; le flux avant impôt reste EXACTEMENT celui de
  :func:`flux_de_tresorerie` (contrat CALX280 inchangé) ;
* ``lineaire`` sur 10 ans pour 100 000 MAD ⇒ dotation 10 000 MAD/an pendant
  10 ans, somme des dotations = 100 000 MAD EXACTEMENT ;
* ``degressif`` sans ``amortissement_coefficient`` ⇒ refus NOMMANT le champ
  (réglage société ET calcul) ;
* ``taux_imposition_pct`` saisi sans source ⇒ refus nommant la source
  (``fiscalite_source`` au réglage, ``taux_imposition_pct.source`` au
  calcul) ;
* LECTURE STRICTE : sans taux d'imposition, les indicateurs après impôt
  valent ``None`` et le motif NOMME ``taux_imposition_pct`` ; un taux SAISI
  à 0 reste fourni (indicateurs après impôt = avant impôt) ;
* le résultat imposable déduit la dotation et les intérêts d'emprunt ; une
  année déficitaire ne porte aucun impôt et l'omission le dit ;
* les clés de mode sont les mêmes au modèle, au service tarifaire et au
  calcul ; aucune clé publiée ne contient ``prix``, ``cout`` ni ``marge``.

Tests PURS : ``TariffSettings()`` est instancié sans base (aucune requête).

Run :
    python -m pytest apps/ventes/tests/test_calx284_amortissement_fiscalite.py -q
"""
import unittest
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.parametres import tariff
from apps.parametres.models_tariff import TariffSettings
from apps.ventes import economie
from apps.ventes.economie import (EconomieInvalide, dotations_amortissement,
                                  flux_apres_impot, flux_de_tresorerie)

SOURCE = 'Code général des impôts (jeu d’essai)'


def reference():
    """Le cas de référence de CALX281 (tous les taux saisis, à 0)."""
    return dict(investissement_mad=100000, economie_annee1_mad=12000,
                production_annee1_kwh=10000, horizon_ans=10,
                taux_actualisation_pct=0, indexation_pct=0,
                degradation_pct=0)


def cles_omises(bloc):
    return {o['cle'] for o in bloc['omissions']}


def toutes_les_cles(valeur):
    if isinstance(valeur, dict):
        for cle, sous in valeur.items():
            yield cle
            yield from toutes_les_cles(sous)
    elif isinstance(valeur, list):
        for sous in valeur:
            yield from toutes_les_cles(sous)


class DotationsTest(unittest.TestCase):
    def test_lineaire_10_ans_100000_dotation_10000_somme_exacte(self):
        dotations = dotations_amortissement(
            base_mad=100000, mode='lineaire', duree_ans=10)
        self.assertEqual(len(dotations), 10)
        self.assertEqual([d['annee'] for d in dotations], list(range(1, 11)))
        for dotation in dotations:
            self.assertEqual(dotation['dotation_mad'], 10000.0)
        self.assertEqual(sum(d['dotation_mad'] for d in dotations), 100000)
        self.assertEqual(sum(Decimal(str(d['dotation_mad']))
                             for d in dotations), Decimal('100000'))
        self.assertEqual(dotations[-1]['valeur_nette_mad'], 0.0)

    def test_lineaire_non_divisible_la_derniere_solde_au_centime(self):
        dotations = dotations_amortissement(
            base_mad=100000, mode='lineaire', duree_ans=3)
        self.assertEqual([d['dotation_mad'] for d in dotations],
                         [33333.33, 33333.33, 33333.34])
        self.assertEqual(sum(Decimal(str(d['dotation_mad']))
                             for d in dotations), Decimal('100000.00'))

    def test_degressif_bascule_en_lineaire_quand_il_depasse(self):
        # Coefficient 2 sur 5 ans ⇒ taux dégressif 40 % : 40 000, 24 000,
        # 14 400, puis le linéaire sur les 2 ans restants (21 600 ÷ 2 =
        # 10 800 > 8 640) — la règle PV*SOL citée.
        dotations = dotations_amortissement(
            base_mad=100000, mode='degressif', duree_ans=5, coefficient=2)
        self.assertEqual([d['dotation_mad'] for d in dotations],
                         [40000.0, 24000.0, 14400.0, 10800.0, 10800.0])
        self.assertEqual(sum(d['dotation_mad'] for d in dotations), 100000)
        self.assertEqual(dotations[-1]['valeur_nette_mad'], 0.0)

    def test_degressif_sans_coefficient_refuse_en_nommant_le_champ(self):
        with self.assertRaises(EconomieInvalide) as ctx:
            dotations_amortissement(base_mad=100000, mode='degressif',
                                    duree_ans=5)
        self.assertEqual(ctx.exception.champ, 'amortissement_coefficient')
        self.assertIn('amortissement_coefficient', str(ctx.exception))

    def test_lineaire_sans_duree_refuse_en_nommant_le_champ(self):
        with self.assertRaises(EconomieInvalide) as ctx:
            dotations_amortissement(base_mad=100000, mode='lineaire')
        self.assertEqual(ctx.exception.champ, 'amortissement_duree_ans')

    def test_aucun_ne_dote_rien_et_mode_inconnu_refuse(self):
        self.assertEqual(dotations_amortissement(base_mad=100000,
                                                 mode='aucun'), [])
        with self.assertRaises(EconomieInvalide) as ctx:
            dotations_amortissement(base_mad=100000, mode='sofa',
                                    duree_ans=5)
        self.assertEqual(ctx.exception.champ, 'amortissement_mode')


class ReglagesSocieteTest(unittest.TestCase):
    """La validation vit dans ``tariff.erreurs_reglages_tarif`` (patron lot 5)."""

    def test_les_modes_sont_les_memes_partout(self):
        self.assertEqual(
            tuple(c for c, _ in TariffSettings.AMORTISSEMENT_MODES_CHOICES),
            tariff.AMORTISSEMENT_MODES)
        self.assertEqual(tariff.AMORTISSEMENT_MODES,
                         economie.AMORTISSEMENT_MODES)

    def test_societe_vierge_champs_vides_et_valide(self):
        vierge = TariffSettings()
        self.assertIsNone(vierge.taux_imposition_pct)
        self.assertEqual(vierge.amortissement_mode, 'aucun')
        self.assertIsNone(vierge.amortissement_duree_ans)
        self.assertIsNone(vierge.amortissement_coefficient)
        self.assertEqual(vierge.fiscalite_source, '')
        self.assertEqual(tariff.erreurs_reglages_tarif(vierge), {})
        self.assertEqual(tariff.fiscalite_depuis_reglages(vierge), {})

    def test_degressif_sans_coefficient_refuse_en_nommant_le_champ(self):
        reglages = TariffSettings(amortissement_mode='degressif',
                                  amortissement_duree_ans=5,
                                  fiscalite_source=SOURCE)
        erreurs = tariff.erreurs_reglages_tarif(reglages)
        self.assertEqual(set(erreurs), {'amortissement_coefficient'})
        self.assertIn('amortissement_coefficient',
                      erreurs['amortissement_coefficient'])
        with self.assertRaises(ValidationError) as ctx:
            reglages.clean()
        self.assertIn('amortissement_coefficient', ctx.exception.message_dict)
        self.assertEqual(tariff.fiscalite_depuis_reglages(reglages), {})

    def test_taux_sans_source_refuse_en_nommant_la_source(self):
        reglages = TariffSettings(taux_imposition_pct=Decimal('31'))
        erreurs = tariff.erreurs_reglages_tarif(reglages)
        self.assertEqual(set(erreurs), {'fiscalite_source'})
        self.assertIn('fiscalite_source', erreurs['fiscalite_source'])
        with self.assertRaises(ValidationError) as ctx:
            reglages.clean()
        self.assertIn('fiscalite_source', ctx.exception.message_dict)
        # Jamais une valeur sans provenance vers le calcul.
        self.assertEqual(tariff.fiscalite_depuis_reglages(reglages), {})

    def test_amortissement_sans_source_ni_duree_refuse(self):
        erreurs = tariff.erreurs_fiscalite(None, 'lineaire', None, None, '')
        self.assertEqual(set(erreurs),
                         {'amortissement_duree_ans', 'fiscalite_source'})

    def test_bornes_du_taux_et_du_coefficient(self):
        self.assertIn('taux_imposition_pct', tariff.erreurs_fiscalite(
            '100', 'aucun', None, None, SOURCE))
        self.assertIn('taux_imposition_pct', tariff.erreurs_fiscalite(
            '-1', 'aucun', None, None, SOURCE))
        self.assertIn('amortissement_coefficient', tariff.erreurs_fiscalite(
            None, 'degressif', 5, '1', SOURCE))
        self.assertIn('amortissement_mode', tariff.erreurs_fiscalite(
            None, 'sofa', None, None, SOURCE))
        self.assertEqual(tariff.erreurs_fiscalite(
            '0', 'aucun', None, None, SOURCE), {})

    def test_reglages_saisis_deviennent_des_grandeurs_sourcees(self):
        reglages = TariffSettings(
            taux_imposition_pct=Decimal('31'), amortissement_mode='degressif',
            amortissement_duree_ans=5,
            amortissement_coefficient=Decimal('2'), fiscalite_source=SOURCE)
        self.assertEqual(tariff.erreurs_reglages_tarif(reglages), {})
        parametres = tariff.fiscalite_depuis_reglages(reglages)
        self.assertEqual(set(parametres), {
            'taux_imposition_pct', 'amortissement_mode',
            'amortissement_duree_ans', 'amortissement_coefficient'})
        for grandeur in parametres.values():
            self.assertEqual(grandeur['source'], SOURCE)
        self.assertEqual(parametres['taux_imposition_pct']['valeur'], 31.0)
        self.assertEqual(parametres['amortissement_duree_ans']['valeur'], 5)


class FluxApresImpotTest(unittest.TestCase):
    def test_societe_vierge_les_deux_flux_egaux_terme_a_terme(self):
        parametres = tariff.fiscalite_depuis_reglages(TariffSettings())
        resultat = flux_apres_impot(**parametres, **reference())
        avant, apres = resultat['avant_impot'], resultat['apres_impot']
        # Le flux avant impôt est EXACTEMENT celui de flux_de_tresorerie.
        self.assertEqual(avant, flux_de_tresorerie(**reference()))
        self.assertEqual(len(apres['flux']), len(avant['flux']))
        self.assertEqual(len(apres['flux']), 11)
        for ligne_apres, ligne_avant in zip(apres['flux'], avant['flux']):
            self.assertEqual(ligne_apres['annee'], ligne_avant['annee'])
            self.assertEqual(ligne_apres['flux_mad'], ligne_avant['flux_mad'])
            self.assertEqual(ligne_apres['cumul_mad'],
                             ligne_avant['cumul_mad'])
            self.assertEqual(ligne_apres['flux_avant_impot_mad'],
                             ligne_avant['flux_mad'])
            self.assertIsNone(ligne_apres['impot_mad'])
            self.assertEqual(ligne_apres['dotation_mad'], 0.0)
        self.assertEqual(apres['dotations'], [])
        # Lecture stricte : aucun indicateur après impôt sans taux saisi.
        for cle in economie.INDICATEURS_APRES_IMPOT:
            self.assertIsNone(apres[cle])
            motif = next(o['motif'] for o in apres['omissions']
                         if o['cle'] == cle)
            self.assertIn('taux_imposition_pct', motif)
        self.assertIn('taux_imposition_pct', cles_omises(apres))
        self.assertIn('amortissement_mode', cles_omises(apres))

    def test_lineaire_10_ans_et_taux_30_impot_sur_le_resultat(self):
        resultat = flux_apres_impot(
            taux_imposition_pct={'valeur': 30, 'source': SOURCE},
            amortissement_mode={'valeur': 'lineaire', 'source': SOURCE},
            amortissement_duree_ans={'valeur': 10, 'source': SOURCE},
            **reference())
        apres = resultat['apres_impot']
        self.assertEqual([d['dotation_mad'] for d in apres['dotations']],
                         [10000.0] * 10)
        self.assertEqual(sum(d['dotation_mad'] for d in apres['dotations']),
                         100000)
        # 12 000 d'économie − 10 000 de dotation = 2 000 imposables ⇒ 600.
        annee1 = apres['flux'][1]
        self.assertEqual(annee1['dotation_mad'], 10000.0)
        self.assertEqual(annee1['base_imposable_mad'], 2000.0)
        self.assertEqual(annee1['impot_mad'], 600.0)
        self.assertEqual(annee1['flux_mad'], 11400.0)
        self.assertEqual(apres['flux'][0]['flux_mad'], -100000.0)
        # Le flux avant impôt n'a pas bougé.
        self.assertEqual(resultat['avant_impot']['flux'][1]['flux_mad'],
                         12000.0)
        self.assertAlmostEqual(apres['van_mad'], 14000, delta=1)
        self.assertIsNotNone(apres['tri_pct'])
        # Base amortissable DÉRIVÉE de l'investissement, dérivation publiée.
        base = next(h for h in apres['hypotheses']
                    if h['cle'] == 'base_amortissable_mad')
        self.assertEqual(base['valeur'], 100000)
        self.assertIn('investissement_mad', base['source'])
        for hypothese in apres['hypotheses']:
            self.assertTrue(hypothese['source'])

    def test_taux_saisi_a_zero_reste_fourni(self):
        resultat = flux_apres_impot(
            taux_imposition_pct={'valeur': 0, 'source': SOURCE},
            **reference())
        avant, apres = resultat['avant_impot'], resultat['apres_impot']
        self.assertNotIn('taux_imposition_pct', cles_omises(apres))
        self.assertAlmostEqual(apres['van_mad'], avant['van_mad'], delta=0.01)
        self.assertEqual(apres['tri_pct'], avant['tri_pct'])
        self.assertEqual(apres['retour_ans'], avant['retour_ans'])
        self.assertEqual(apres['retour_actualise_ans'],
                         avant['retour_actualise_ans'])

    def test_taux_sans_source_refuse_en_nommant_la_source(self):
        with self.assertRaises(EconomieInvalide) as ctx:
            flux_apres_impot(taux_imposition_pct={'valeur': 30, 'source': ''},
                             **reference())
        self.assertEqual(ctx.exception.champ, 'taux_imposition_pct.source')
        self.assertIn('source', str(ctx.exception))

    def test_degressif_sans_coefficient_refuse_au_calcul(self):
        with self.assertRaises(EconomieInvalide) as ctx:
            flux_apres_impot(taux_imposition_pct=30,
                             amortissement_mode='degressif',
                             amortissement_duree_ans=5, **reference())
        self.assertEqual(ctx.exception.champ, 'amortissement_coefficient')

    def test_annee_deficitaire_aucun_impot_et_omission(self):
        # Dégressif 2 sur 5 ans : 40 000 de dotation en année 1 > 12 000
        # d'économie ⇒ résultat négatif, aucun impôt, rien de supposé.
        resultat = flux_apres_impot(
            taux_imposition_pct=30, amortissement_mode='degressif',
            amortissement_duree_ans=5, amortissement_coefficient=2,
            **reference())
        apres = resultat['apres_impot']
        annee1 = apres['flux'][1]
        self.assertEqual(annee1['base_imposable_mad'], -28000.0)
        self.assertEqual(annee1['impot_mad'], 0.0)
        self.assertEqual(annee1['flux_mad'], 12000.0)
        motif = next(o['motif'] for o in apres['omissions']
                     if o['cle'] == 'impot_mad')
        self.assertIn('1', motif)
        self.assertIn('report déficitaire', motif)
        # Année 6 : plus de dotation ⇒ 12 000 imposables, 3 600 d'impôt.
        self.assertEqual(apres['flux'][6]['impot_mad'], 3600.0)

    def test_les_interets_d_emprunt_sont_deduits(self):
        # In fine 50 000 MAD à 12 %/an sur 12 mois : 500 MAD d'intérêts par
        # mois ⇒ 6 000 MAD déduits en année 1 ⇒ 6 000 imposables ⇒ 1 800.
        resultat = flux_apres_impot(
            taux_imposition_pct=30,
            pret={'principal_mad': 50000, 'taux_annuel_pct': 12,
                  'duree_mois': 12, 'type_pret': 'in_fine'},
            **reference())
        annee1 = resultat['apres_impot']['flux'][1]
        self.assertEqual(annee1['base_imposable_mad'], 6000.0)
        self.assertEqual(annee1['impot_mad'], 1800.0)
        self.assertEqual(annee1['flux_mad'],
                         annee1['flux_avant_impot_mad'] - 1800.0)

    def test_sans_flux_avant_impot_rien_apres_impot(self):
        resultat = flux_apres_impot(taux_imposition_pct=30,
                                    investissement_mad=100000)
        apres = resultat['apres_impot']
        self.assertEqual(apres['flux'], [])
        for cle in economie.INDICATEURS_APRES_IMPOT:
            self.assertIsNone(apres[cle])
            self.assertIn(cle, cles_omises(apres))

    def test_aucune_cle_prix_cout_marge(self):
        resultat = flux_apres_impot(
            taux_imposition_pct=30, amortissement_mode='lineaire',
            amortissement_duree_ans=10, **reference())
        for cle in toutes_les_cles(resultat):
            for interdit in ('prix', 'cout', 'marge'):
                self.assertNotIn(interdit, cle)


if __name__ == '__main__':
    unittest.main()
