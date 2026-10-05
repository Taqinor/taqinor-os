# -*- coding: utf-8 -*-
"""QJR612 — CAD170 RÉELLEMENT APPLIQUÉ : la batterie retenue couvre la recharge
VE nocturne, et le CHAMP monte pour qu'elle reste pleine.

DÉCISION FONDATEUR (30/09/2026, verbatim) : « add more panels so battery is
always charged. and btw this is a rule that exists already for batteries in
general in my ERP ».

Ce que ces tests épinglent :

* le plancher est UNE fonction d'``etude_horaire`` — base = besoin du même lead
  SANS la couche VE nocturne (pas de double compte), + la recharge nocturne,
  servi par une taille RÉELLEMENT composée (jamais inventée), plafonné à la plus
  grande avec le motif ``plafonne`` ;
* dans ``balayer_tailles``, un palier SOUS le plancher n'est plus candidat — et
  la règle « batteries toujours pleines » (déjà en place : un palier qui ne se
  remplit pas tous les jours n'est jamais candidat) fait que la grille
  champ × stockage (``choisir_recommandation_avec``) TIRE les panneaux
  nécessaires : aucune batterie retenue ne dépasse le surplus quotidien du mois
  le plus faible de SON champ ;
* un lead SANS recharge nocturne : strictement rien ne change (aucune clé, aucun
  palier filtré).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_cad170_cablage_dimensionnement"
"""
from decimal import Decimal
from io import StringIO

from django.test import SimpleTestCase, TestCase

from apps.ventes import courbes_journalieres as CJ
from apps.ventes.horaire import ve_nocturne as VE

TAILLES = (5.0, 10.0, 15.0, 20.0)


def _couches(ve=True, creneau=None, km=300):
    entree = {'clim': True, 'clim_pieces': 2}
    if ve:
        entree.update({'voiture_electrique': True, 've_km_semaine': km})
        if creneau:
            entree['ve_creneau'] = creneau
    return CJ.composer_equipements(entree)


class LePlancherEstUneFonctionDEtudeHoraire(SimpleTestCase):
    def test_sans_recharge_nocturne_aucun_plancher(self):
        self.assertIsNone(VE.plancher_batterie_recharge_ve(
            5.0, _couches(ve=False), TAILLES))
        self.assertIsNone(VE.plancher_batterie_recharge_ve(
            5.0, _couches(creneau='jour'), TAILLES))
        self.assertIsNone(VE.plancher_batterie_recharge_ve(5.0, None, TAILLES))

    def test_le_plancher_est_la_plus_petite_taille_couvrant_base_plus_recharge(self):
        couches = _couches(km=300)
        recharge = VE.recharge_ve_nocturne_kwh_jour(couches)
        self.assertGreater(recharge, 0)
        sortie = VE.plancher_batterie_recharge_ve(5.0, couches, TAILLES)
        attendu = min(t for t in TAILLES if t >= 5.0 + recharge)
        self.assertEqual(sortie['taille_retenue_kwh'], attendu)
        self.assertFalse(sortie['plafonne'])

    def test_plafonne_a_la_plus_grande_taille_vendue(self):
        sortie = VE.plancher_batterie_recharge_ve(
            19.0, _couches(km=600), TAILLES)
        self.assertEqual(sortie['taille_retenue_kwh'], 20.0)
        self.assertTrue(sortie['plafonne'])
        self.assertTrue(sortie['motif'])

    def test_la_base_se_mesure_SANS_la_couche_ve_nocturne(self):
        couches = _couches()
        sans = VE.equipements_sans_recharge_ve_nocturne(couches)
        self.assertNotIn('ve', sans)
        self.assertIn('clim', sans)
        # Une recharge de JOUR n'est pas la couche nocturne : on la garde.
        jour = _couches(creneau='jour')
        self.assertEqual(VE.equipements_sans_recharge_ve_nocturne(jour), jour)
        self.assertIsNone(VE.equipements_sans_recharge_ve_nocturne(None))


class LeBalayageAppliqueLePlancher(TestCase):
    """Catalogue réel seedé une fois — le balayage compose pour de vrai."""

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        from authentication.models import Company
        cls.company, _ = Company.objects.get_or_create(
            slug='qjr612-ve-co', defaults={'nom': 'QJR612 VE'})
        call_command('seed_catalogue', company_slug=cls.company.slug,
                     stdout=StringIO())

    def _recommander(self, equipements):
        from apps.ventes.dimensionnement import recommander_taille
        from apps.ventes.etude_horaire import _reglages_tarifaires
        tranches, charges_fixes = _reglages_tarifaires(self.company)
        conso = [450.0] * 12
        return recommander_taille(
            company=self.company, conso_kwh_mensuelles=conso,
            ville='Casablanca', occupation=None, equipements=equipements,
            phase=None, taux_tva=Decimal('20'), tranches=tranches,
            charges_fixes_mad=charges_fixes)

    def test_lead_ve_nocturne_le_palier_couvre_base_plus_recharge_et_se_remplit(self):
        couches = _couches(km=150)
        recharge = VE.recharge_ve_nocturne_kwh_jour(couches)
        resultat = self._recommander(couches)
        tableau = resultat['tableau']
        self.assertTrue(tableau)
        avec_plancher = 0
        for ligne in tableau:
            plancher = ligne.get('plancher_recharge_ve')
            self.assertIsNotNone(
                plancher, '%s panneaux : plancher VE absent' % ligne['panneaux'])
            self.assertAlmostEqual(plancher['recharge_ve_kwh'],
                                   round(recharge, 2), places=2)
            surplus_min = ligne.get('stockage_surplus_jour_min_kwh')
            for palier in ligne.get('balayage_stockage') or []:
                # « batteries toujours pleines » : jamais au-dessus du surplus
                # quotidien du mois le plus faible de CE champ.
                self.assertLessEqual(palier['capacite_kwh'],
                                     round(surplus_min, 2) + 0.01)
                if not plancher['plafonne']:
                    self.assertGreaterEqual(
                        palier['capacite_kwh'] + 0.05,
                        plancher['taille_retenue_kwh'])
                    self.assertGreaterEqual(
                        palier['capacite_kwh'] + 0.05,
                        plancher['besoin_total_kwh'])
            if ligne.get('batterie_disponible') and not plancher['plafonne']:
                avec_plancher += 1
                self.assertGreaterEqual(ligne['batterie_kwh'] + 0.05,
                                        plancher['taille_retenue_kwh'])
        reco = resultat.get('recommandation_avec')
        self.assertIsNotNone(reco, resultat.get('motivation_avec'))
        plancher = reco['plancher_recharge_ve']
        self.assertGreaterEqual(reco['batterie_kwh'] + 0.05,
                                plancher['taille_retenue_kwh'])
        self.assertLessEqual(reco['batterie_kwh'],
                             round(reco['stockage_surplus_jour_min_kwh'], 2)
                             + 0.01)
        self.assertGreater(avec_plancher, 0)

    def test_lead_sans_ve_nocturne_strictement_inchange(self):
        from apps.ventes.dimensionnement import _meilleur_palier
        resultat = self._recommander(_couches(ve=False))
        for ligne in resultat['tableau']:
            self.assertNotIn('plancher_recharge_ve', ligne)
            meilleur = _meilleur_palier(ligne.get('balayage_stockage'))
            if meilleur is not None:
                self.assertEqual(ligne['batterie_kwh'],
                                 meilleur['capacite_kwh'])
