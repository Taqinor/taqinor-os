# -*- coding: utf-8 -*-
"""QJR411 (DR4, 31/08/2026) — le plafond de 120 panneaux est GARDÉ, mais il
cesse de mentir au client.

``MAX_PANNEAUX_BALAYAGE`` (``dimensionnement.py:131``) reste à 120 : ce n'est
PAS un bug, DR4 le CONSERVE — aucune borne n'est déplacée par cette tâche. Ce
qui était faux, c'est le DISCOURS : un consommateur PARFAITEMENT légitime
au-dessus de ~9 000 kWh/mois recevait (1) un dimensionnement tronqué SOUS la
parité, présenté COMME LA RECOMMANDATION, et (2) un message affirmant à tort
que sa facture était douteuse (``dimensionnement.py:1375-1378`` avant
correctif : « la consommation déduite est anormalement élevée — vérifier la
facture saisie »).

Ce module épingle les DEUX corrections, jamais un déplacement de la borne :

1. le message rendu au client nomme l'étude sur mesure, plus jamais une
   facture douteuse ;
2. le résultat tronqué reste affiché dans le tableau mais n'est plus
   sélectionné par :func:`choisir_recommandation` — il perd son étiquette
   « recommandé », il ne perd rien d'autre.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_qjr411_plafond_message_honnete"
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.ventes import dimensionnement as D
from apps.ventes.courbes_journalieres import OCCUPATION_PRESENCE
from authentication.models import Company

User = get_user_model()
VILLE = 'Casablanca'

#: Les DEUX phrases interdites par DR4 — un chiffre de facture inhabituel
#: n'est plus jamais présenté comme une erreur de saisie du client.
PHRASES_INTERDITES = ('anormalement élevée', 'vérifier la facture')


def _ligne_tableau(panneaux, cout, economie, couverture, plafond=False):
    """Une ligne FABRIQUÉE — la forme que rend ``balayer_tailles`` (même
    fixture que ``test_deux_optimiseurs._ligne_tableau``), avec en plus le
    champ QJR411 quand la ligne appartient à un balayage plafonné."""
    payback = D._payback(cout, economie)
    ligne = {
        'panneaux': panneaux, 'kwc': round(panneaux * 0.55, 3),
        'composable': True,
        'payback_sans_annees': None if payback is None else round(payback, 2),
        'cout_sans_ttc': cout, 'economie_sans_mad': economie,
        'couverture_sans': couverture,
        'verdicts_bloquants_sans': [], 'verdicts_bloquants_avec': [],
        'batterie_disponible': False, 'payback_avec_annees': None,
        'residuel_kwh_mois': 400.0, 'batterie_kwh': 0.0,
        'balayage_stockage': [],
        'avertissements': [],
    }
    if plafond:
        ligne['plafond_panneaux_atteint'] = True
        ligne['avertissements'] = [
            'Balayage plafonné à %d panneaux : profil au-delà du '
            'dimensionnement résidentiel — étude sur mesure.'
            % D.MAX_PANNEAUX_BALAYAGE]
    return ligne


class LePlafondResteGardeTest(SimpleTestCase):
    """DR4 : la borne elle-même n'est JAMAIS déplacée par cette tâche."""

    def test_le_plafond_vaut_toujours_120(self):
        self.assertEqual(D.MAX_PANNEAUX_BALAYAGE, 120)


class RecommandationExclutLeResultatTronqueTest(SimpleTestCase):
    """``choisir_recommandation`` — un tableau entièrement plafonné (le seul
    cas qu'un vrai balayage tronqué produit, voir ``balayer_tailles``) ne doit
    plus désigner de ligne « recommandée »."""

    def test_rouge_un_tableau_plafonne_n_est_plus_recommande(self):
        """ROUGE avant le correctif : ``choisir_recommandation`` ignorait le
        marqueur de plafond et recommandait quand même la meilleure ligne du
        balayage tronqué — exactement ce que DR4 interdit."""
        tableau = [
            _ligne_tableau(118, 400000, 45000, 0.55, plafond=True),
            _ligne_tableau(119, 404000, 45200, 0.55, plafond=True),
            _ligne_tableau(120, 408000, 45400, 0.56, plafond=True),
        ]
        reco, motivation = D.choisir_recommandation(tableau)
        self.assertIsNone(
            reco,
            'un tableau entièrement plafonné ne doit plus recommander aucune '
            'ligne : le résultat tronqué n\'est pas une recommandation '
            'honnête (DR4)')
        self.assertIn('étude sur mesure', motivation)
        self.assertIn(str(D.MAX_PANNEAUX_BALAYAGE), motivation)
        for phrase in PHRASES_INTERDITES:
            self.assertNotIn(phrase, motivation)
        # Le tableau lui-même reste INTACT — rien n'est retiré, rien n'est
        # renommé : seul le VERDICT (la recommandation) a changé.
        self.assertEqual(len(tableau), 3)
        self.assertTrue(all(ligne.get('plafond_panneaux_atteint')
                            for ligne in tableau))

    def test_un_profil_sous_le_plafond_est_inchange_a_l_octet(self):
        """Non-régression : sans ``plafond_panneaux_atteint`` sur aucune
        ligne, le choix reste EXACTEMENT celui d'avant cette tâche (même
        fixture que ``test_deux_optimiseurs.LaDoctrineDOptimum``)."""
        tableau = [
            _ligne_tableau(8, 40000, 8000, 0.50),
            _ligne_tableau(9, 49000, 9000, 0.56),
            _ligne_tableau(10, 57000, 9500, 0.60),
        ]
        reco, motivation = D.choisir_recommandation(tableau)
        self.assertIsNotNone(reco)
        self.assertEqual(reco['panneaux'], 9)
        for phrase in PHRASES_INTERDITES:
            self.assertNotIn(phrase, motivation)


class BalayageReelDeclencheLePlafondTest(TestCase):
    """Intégration : un vrai profil hors résidentiel, sur le catalogue seedé,
    déclenche VRAIMENT le plafond — le message RENDU au client ne ment plus,
    et le résultat tronqué ne porte plus l'étiquette « recommandé ».

    La consommation de ce profil est DÉRIVÉE des deux entrées réelles (table
    PVGIS de la ville + panneau retenu par le catalogue), jamais posée en dur :
    voir :meth:`_conso_qui_declenche_le_plafond`.
    """

    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        cls.company, _ = Company.objects.get_or_create(
            slug='qjr411-plafond-co', defaults={'nom': 'QJR411 Plafond'})
        cls.user = User.objects.create_user(
            username='qjr411_plafond', password='x',
            role_legacy='responsable', company=cls.company)
        call_command('seed_catalogue', company_slug=cls.company.slug,
                     stdout=StringIO())

    def _sizer(self, conso_mensuelle):
        from apps.ventes.etude_horaire import _reglages_tarifaires
        tranches, charges_fixes = _reglages_tarifaires(self.company)
        return D.recommander_taille(
            company=self.company, conso_kwh_mensuelles=[conso_mensuelle] * 12,
            ville=VILLE, occupation=OCCUPATION_PRESENCE, tranches=tranches,
            charges_fixes_mad=charges_fixes)

    def _conso_qui_declenche_le_plafond(self):
        """La consommation mensuelle DÉRIVÉE des vraies données, jamais devinée.

        Le plafond tombe quand la taille de PARITÉ dépasse
        ``MAX_PANNEAUX_BALAYAGE`` (``bornes_candidates`` :
        ``ceil(conso_an / productible_an × 1000 / watt) + 1 > 120``). Les deux
        entrées de cette inégalité sont LUES, pas estimées :

        * ``productible_an`` — la table PVGIS de la ville (Casablanca ≈ 1 719
          kWh/kWc/an) ;
        * ``watt`` — le panneau que le catalogue SEEDÉ retient réellement, lu
          sur une ligne d'un balayage sonde (le même champ ``panel_watt`` que
          rend ``balayer_tailles``).

        La version précédente de ce test posait 10 000 kWh/mois depuis une
        estimation de productible (~1 278) qui n'est pas celle de la table :
        à 1 719 kWh/kWc/an et 710 W, la parité tombe à ~100 panneaux et le
        plafond ne se déclenchait jamais. Dérivé, le seuil suit la table et le
        catalogue au lieu de les contredire.
        """
        import math

        from apps.parametres.pvgis_profils import productible_mensuel

        productibles, _source = productible_mensuel(ville=VILLE)
        productible_an = sum(productibles)
        self.assertGreater(productible_an, 0)

        sonde = self._sizer(300.0)['tableau']
        self.assertTrue(sonde, 'le catalogue seedé doit composer au moins une '
                               'taille, même sur un petit profil')
        watt = float(sonde[0]['panel_watt'])
        self.assertGreater(watt, 0)

        # +20 panneaux de marge au-dessus de la borne : le plafond est franchi
        # sans ambiguïté d'arrondi, quel que soit le panneau du catalogue.
        panneaux_vises = D.MAX_PANNEAUX_BALAYAGE + 20
        conso_an = panneaux_vises * (watt / 1000.0) * productible_an
        mensuel = math.ceil(conso_an / 12.0 / 100.0) * 100.0
        # Contrôle de la dérivation elle-même (l'inégalité de bornes_candidates).
        parite = math.ceil((mensuel * 12.0 / productible_an) * 1000.0 / watt)
        self.assertGreater(
            parite + 1, D.MAX_PANNEAUX_BALAYAGE,
            'la consommation dérivée doit vraiment dépasser le plafond')
        return mensuel

    def test_profil_hors_residentiel_plafonne_avec_message_honnete(self):
        """ROUGE avant le correctif : le message rendu contenait « la
        consommation déduite est anormalement élevée — vérifier la facture
        saisie » sur un profil pourtant parfaitement légitime."""
        resultat = self._sizer(self._conso_qui_declenche_le_plafond())
        tableau = resultat['tableau']
        self.assertTrue(tableau, 'le catalogue seedé doit composer au moins '
                                 'une taille pour ce profil')
        plafonnees = [ligne for ligne in tableau
                      if ligne.get('plafond_panneaux_atteint')]
        self.assertTrue(
            plafonnees,
            'un profil dont la taille de parité dépasse la borne doit '
            'déclencher MAX_PANNEAUX_BALAYAGE=%d (borne inchangée par DR4)'
            % D.MAX_PANNEAUX_BALAYAGE)

        for ligne in plafonnees:
            texte = ' '.join(ligne.get('avertissements') or ())
            self.assertIn('étude sur mesure', texte)
            for phrase in PHRASES_INTERDITES:
                self.assertNotIn(
                    phrase, texte,
                    'ROUGE avant le correctif : « %s » ne doit plus '
                    'apparaître dans le message rendu au client' % phrase)

        # Le résultat tronqué ne doit plus être étiqueté « recommandé ».
        if resultat['recommandation'] is not None:
            self.assertFalse(
                resultat['recommandation'].get('plafond_panneaux_atteint'),
                'la recommandation ne doit jamais désigner une ligne issue '
                'd\'un balayage plafonné')
