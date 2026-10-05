"""VEIL23 — Précision et rappel sur l'échantillon étiqueté (D-VEIL-4/9).

Fixture aux étiquettes connues → matrice, P/R/F1 et Wilson EXACTS (valeurs de
référence publiées : 9/10 → [0,5958 ; 0,9821], 8/10 → [0,4902 ; 0,9433]).
Refus : < 200 étiquettes de test, étiquette non humaine, étiquette de test
ayant servi à l'étalonnage.
"""
import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import veille_mesures as vm
from apps.adsengine.models import (
    VeilleAnnonceur, VeilleDecouverte, VeilleVerdict,
)

PAIRES = (
    [('vendeur', 'vendeur')] * 4 + [('vendeur', 'incertain')]
    + [('hors_sujet', 'vendeur')] + [('pas_vendeur', 'pas_vendeur')] * 2
    + [('place_de_marche', 'place_de_marche')] + [('incertain', 'incertain')])
PAIRES_DROP = [('oui', 'oui')] * 9 + [('non', 'oui')] + [('oui', 'non')] * 2


class EvaluerTests(SimpleTestCase):
    def test_wilson_valeurs_de_reference(self):
        self.assertEqual(vm.wilson(9, 10), [0.5958, 0.9821])
        self.assertEqual(vm.wilson(8, 10), [0.4902, 0.9433])
        self.assertIsNone(vm.wilson(0, 0))

    def test_matrice_et_scores_exacts(self):
        rapport = vm.evaluer(PAIRES, PAIRES_DROP, passage_humain=0.2,
                             seuils_={'liste_precision': 0.9,
                                      'liste_rappel': 0.9,
                                      'dropshipper_precision': 0.8})
        m = rapport['matrice']
        self.assertEqual(m['vendeur']['vendeur'], 4)
        self.assertEqual(m['vendeur']['incertain'], 1)
        self.assertEqual(m['hors_sujet']['vendeur'], 1)
        self.assertEqual(m['doublon'], {c: 0 for c in m['doublon']})
        vendeur = rapport['par_classe']['vendeur']
        self.assertEqual((vendeur['vp'], vendeur['fp'], vendeur['fn']),
                         (4, 1, 1))
        self.assertEqual((vendeur['precision'], vendeur['rappel'],
                          vendeur['f1']), (0.8, 0.8, 0.8))
        self.assertEqual(vendeur['ic_precision'], vm.wilson(4, 5))
        hors = rapport['par_classe']['hors_sujet']
        self.assertIsNone(hors['precision'])          # jamais 0 inventé
        self.assertEqual(hors['rappel'], 0.0)
        self.assertIsNone(hors['f1'])
        incertain = rapport['par_classe']['incertain']
        self.assertEqual((incertain['precision'], incertain['rappel'],
                          incertain['f1']), (0.5, 1.0, 0.6667))
        drop = rapport['dropshipper']
        self.assertEqual((drop['precision'], drop['rappel']), (0.9, 0.8182))
        self.assertEqual(drop['ic_precision'], [0.5958, 0.9821])
        self.assertEqual(rapport['verdict'], {
            'liste_vendeurs': 'non atteint', 'dropshipper': 'atteint',
            'dropshipper_interne': False})


class MesurerDecouverteTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='YB', slug='yb-mesurer')
        self.dec = VeilleDecouverte.objects.create(
            company=self.company, plafond_appels=1,
            plafond_pages_par_requete=1)

    def peupler(self, n_test, *, faux=0, incertains=0, n_etalonnage=50):
        annonceurs = VeilleAnnonceur.objects.bulk_create([
            VeilleAnnonceur(company=self.company, page_id=f'p{i}',
                            jeu='test' if i < n_test else 'etalonnage',
                            jeu_decouverte=self.dec)
            for i in range(n_test + n_etalonnage)])
        verdicts = []
        for i, ann in enumerate(annonceurs):
            vrai = 'hors_sujet' if i < faux else 'vendeur'
            predit = 'incertain' if faux <= i < faux + incertains \
                else 'vendeur'
            verdicts.append(VeilleVerdict(
                company=self.company, annonceur=ann, classe=predit,
                decide_par='regle', dropshipper='incertain',
                modele='sonnet' if i % 4 == 0 else ''))
            verdicts.append(VeilleVerdict(
                company=self.company, annonceur=ann, classe=vrai,
                decide_par='humain', dropshipper='non',
                est_etiquette_mesure=True, jeu=ann.jeu))
        VeilleVerdict.objects.bulk_create(verdicts)
        return annonceurs

    def test_rapport_complet_et_seuils(self):
        self.peupler(200, faux=20)
        rapport = vm.mesurer_decouverte(self.dec, modele_ambigu='sonnet')
        self.assertEqual(rapport['n'], 200)
        vendeur = rapport['par_classe']['vendeur']
        self.assertEqual((vendeur['precision'], vendeur['rappel']),
                         (0.9, 1.0))
        self.assertEqual(vendeur['ic_precision'], [0.8506, 0.9343])
        self.assertEqual(rapport['verdict']['liste_vendeurs'], 'atteint')
        # aucune prédiction « oui » : précision dropshipper non calculable
        self.assertIsNone(rapport['dropshipper']['precision'])
        self.assertEqual(rapport['verdict']['dropshipper'], 'non atteint')
        self.assertTrue(rapport['verdict']['dropshipper_interne'])
        self.assertEqual(rapport['passage_second_modele'], 0.25)
        self.assertEqual(rapport['passage_humain'], 0.0)
        self.assertEqual(rapport['etiquettes_etalonnage'], 50)
        self.assertIn('trouves', rapport['rappel_decouverte'])

    def test_passage_humain(self):
        self.peupler(200, incertains=30)
        rapport = vm.mesurer_decouverte(self.dec)
        self.assertEqual(rapport['passage_humain'], 0.15)
        self.assertIsNone(rapport['passage_second_modele'])

    def test_refus_moins_de_200(self):
        self.peupler(199)
        with self.assertRaises(vm.MesureRefusee) as ctx:
            vm.mesurer_decouverte(self.dec)
        self.assertIn('200', ctx.exception.message_fr)

    def test_refus_etiquette_non_humaine(self):
        annonceurs = self.peupler(200)
        VeilleVerdict.objects.create(
            company=self.company, annonceur=annonceurs[0], classe='vendeur',
            decide_par='ia', est_etiquette_mesure=True, jeu='test')
        with self.assertRaises(vm.MesureRefusee) as ctx:
            vm.mesurer_decouverte(self.dec)
        self.assertIn('humain', ctx.exception.message_fr)

    def test_refus_etiquette_de_test_servie_a_l_etalonnage(self):
        annonceurs = self.peupler(200)
        VeilleVerdict.objects.create(
            company=self.company, annonceur=annonceurs[3], classe='vendeur',
            decide_par='humain', est_etiquette_mesure=True,
            jeu='etalonnage')
        with self.assertRaises(vm.MesureRefusee) as ctx:
            vm.mesurer_decouverte(self.dec)
        self.assertIn('étalonnage', ctx.exception.message_fr)

    def test_commande(self):
        self.peupler(200, faux=20)
        sortie = StringIO()
        call_command('veille_mesurer', '--decouverte', str(self.dec.pk),
                     '--modele-ambigu', 'sonnet', stdout=sortie)
        rapport = json.loads(sortie.getvalue())
        self.assertEqual(rapport['verdict']['liste_vendeurs'], 'atteint')

    def test_commande_refus_message_fr(self):
        self.peupler(10)
        with self.assertRaises(CommandError) as ctx:
            call_command('veille_mesurer', '--decouverte', str(self.dec.pk))
        self.assertIn('étiquette(s) de test', str(ctx.exception))
