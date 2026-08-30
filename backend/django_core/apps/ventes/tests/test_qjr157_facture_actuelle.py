# -*- coding: utf-8 -*-
"""QJR157 — la « facture électrique actuelle » compte ce que le client paie.

``two_bills_savings`` ne modélisait que l'ÉNERGIE — ni redevance de compteur
(39,94 MAD/mois) ni TPPAN — alors que sur le chemin ``savings_model='horaire'``
la MÊME vignette est servie par ``bareme``, charges comprises : **le même
client voyait deux factures actuelles différentes selon qu'un bloc horaire
existe ou non**. Trois écarts DÉRIVÉS ici, tous vérifiés :

* 400 kWh/mois : **6 632 MAD/an** publiés (énergie seule) contre **7 891**
  réels (barème complet) ;
* profil saisonnier 700/100 kWh : **6 632** (mois moyen × 12, énergie seule)
  contre **7 366** (douze mois, énergie seule) — le défaut frère (b), la
  docstring promettait « on ne divise JAMAIS l'année avant de tarifer » et le
  code faisait exactement cela ; **8 505** une fois les charges comptées ;
* inversion de la facture SRM de référence (592,77 MAD TTC) :
  **429 kWh/mois** au lieu de **359**, soit **+19 %** — défaut frère (a).

Tests purs — aucune base, aucun réseau.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import bareme as B
from apps.ventes.quote_engine import pricing as P

#: Les trois profils du test de parité (le troisième est saisonnier).
PROFIL_PLAT = [400.0] * 12
PROFIL_SAISONNIER = [700.0] * 6 + [100.0] * 6
PROFIL_PETIT = [120.0] * 12


def _facture_bareme(mois_kwh):
    """La MÊME facture, calculée directement par ``bareme`` — la référence."""
    return round(sum(B.facture_mad(kwh)['total_mad'] for kwh in mois_kwh))


class PariteAvecBaremeTests(SimpleTestCase):
    """« une seule facture actuelle pour un même client » — sur trois profils."""

    def _sans(self, mois_kwh, **kwargs):
        conso = sum(mois_kwh)
        resultat = P.two_bills_savings(
            production_kwh=10000, conso_annuelle_kwh=conso,
            autoconso_ratio=0.6, utility='onee',
            repartition_mensuelle=mois_kwh, **kwargs)
        self.assertIsNotNone(resultat)
        return resultat

    def test_profil_plat(self):
        self.assertEqual(self._sans(PROFIL_PLAT)['facture_sans'],
                         _facture_bareme(PROFIL_PLAT))

    def test_profil_saisonnier(self):
        self.assertEqual(self._sans(PROFIL_SAISONNIER)['facture_sans'],
                         _facture_bareme(PROFIL_SAISONNIER))

    def test_profil_petit_consommateur(self):
        self.assertEqual(self._sans(PROFIL_PETIT)['facture_sans'],
                         _facture_bareme(PROFIL_PETIT))

    def test_les_charges_fixes_sont_bien_comptees(self):
        """Écart DÉRIVÉ face à l'ancien modèle énergie-seule, sur 400 kWh."""
        energie_seule = round(
            P._monthly_bill_from_kwh(400.0, P.ONEE_TRANCHES) * 12)
        self.assertEqual(energie_seule, 6632)
        self.assertEqual(self._sans(PROFIL_PLAT)['facture_sans'], 7891)

    def test_une_autoconsommation_totale_laisse_l_abonnement(self):
        """La facture APRÈS n'est jamais nulle : le compteur reste loué."""
        resultat = P.two_bills_savings(
            production_kwh=100000, conso_annuelle_kwh=4800,
            autoconso_ratio=1.0, utility='onee')
        self.assertEqual(resultat['facture_avec'],
                         round(B.charges_fixes_ttc() * 12))

    def test_le_reglage_societe_des_charges_fixes_est_respecte(self):
        avec_reglage = self._sans(PROFIL_PLAT, charges_fixes_mad=50.0)
        self.assertEqual(
            avec_reglage['facture_sans'],
            round(sum(B.facture_mad(k, charges_fixes_mad=50.0)['total_mad']
                      for k in PROFIL_PLAT)))


class DouzeMoisContreMoisMoyenTests(SimpleTestCase):
    """(b) « on ne divise JAMAIS l'année avant de tarifer » — tenu."""

    def _resultat(self, **kwargs):
        return P.two_bills_savings(
            production_kwh=10000, conso_annuelle_kwh=sum(PROFIL_SAISONNIER),
            autoconso_ratio=0.6, utility='onee', **kwargs)

    def test_un_profil_saisonnier_coute_plus_que_son_mois_moyen(self):
        mois_moyen = self._resultat()
        douze_mois = self._resultat(repartition_mensuelle=PROFIL_SAISONNIER)
        self.assertGreater(douze_mois['facture_sans'],
                           mois_moyen['facture_sans'])

    def test_l_ecart_derive_du_seul_effet_saisonnier(self):
        """Énergie seule, pour isoler (b) de l'ajout des charges : 6 632 → 7 366."""
        moyen = round(P._monthly_bill_from_kwh(
            sum(PROFIL_SAISONNIER) / 12, P.ONEE_TRANCHES) * 12)
        douze = round(sum(P._monthly_bill_from_kwh(k, P.ONEE_TRANCHES)
                          for k in PROFIL_SAISONNIER))
        self.assertEqual(moyen, 6632)
        self.assertEqual(douze, 7366)

    def test_un_profil_plat_ne_change_pas_de_methode(self):
        """Douze mois identiques ⇒ mois moyen == douze mois, par construction."""
        conso = sum(PROFIL_PLAT)
        moyen = P.two_bills_savings(10000, conso, 0.6, utility='onee')
        douze = P.two_bills_savings(10000, conso, 0.6, utility='onee',
                                    repartition_mensuelle=PROFIL_PLAT)
        self.assertEqual(moyen['facture_sans'], douze['facture_sans'])

    def test_la_repartition_accepte_des_parts_comme_des_kwh(self):
        conso = sum(PROFIL_SAISONNIER)
        parts = [k / conso for k in PROFIL_SAISONNIER]
        self.assertEqual(
            self._resultat(repartition_mensuelle=PROFIL_SAISONNIER)
            ['facture_sans'],
            self._resultat(repartition_mensuelle=parts)['facture_sans'])

    def test_une_repartition_illisible_retombe_sur_le_mois_moyen(self):
        for mauvaise in (None, [], [1.0] * 5, [0.0] * 12, ['x'] * 12):
            resultat = self._resultat(repartition_mensuelle=mauvaise)
            self.assertEqual(resultat['note_methode'], P.NOTE_MOIS_MOYEN,
                             msg=repr(mauvaise))


class NoteDeMethodeTests(SimpleTestCase):
    """« note de méthode disant le mois moyen si la répartition manque »."""

    def test_sans_repartition_la_note_dit_le_mois_moyen(self):
        note = P.two_bills_savings(
            10000, 4800, 0.6, utility='onee')['note_methode']
        self.assertEqual(note, P.NOTE_MOIS_MOYEN)
        self.assertIn('MOIS MOYEN', note)

    def test_avec_repartition_la_note_dit_les_douze_mois(self):
        note = P.two_bills_savings(
            10000, sum(PROFIL_SAISONNIER), 0.6, utility='onee',
            repartition_mensuelle=PROFIL_SAISONNIER)['note_methode']
        self.assertEqual(note, P.NOTE_DOUZE_MOIS)
        self.assertIn('MOIS PAR MOIS', note)

    def test_la_note_remonte_jusqu_au_roi(self):
        roi = P.calculate_savings_roi(
            puissance_kwc=6.0, total_sans=90000, total_avec=140000,
            utility='onee', conso_annuelle_kwh=4800)
        self.assertEqual(roi['savings_model'], 'factures')
        self.assertEqual(roi['factures_note_methode'], P.NOTE_MOIS_MOYEN)

    def test_hors_modele_factures_la_note_est_absente(self):
        roi = P.calculate_savings_roi(
            puissance_kwc=6.0, total_sans=90000, total_avec=140000,
            utility='onee')
        self.assertNotEqual(roi['savings_model'], 'factures')
        self.assertIsNone(roi['factures_note_methode'])


class InversionFactureTotaleTests(SimpleTestCase):
    """(a) Inverser un TOTAL avec le modèle énergie-seule surestime de +19 %."""

    #: La facture SRM de référence du dépôt : 592,77 MAD TTC ⇒ 359 kWh.
    FACTURE_TTC = 592.77
    KWH_PROUVES = 359.0

    def test_le_mode_facture_totale_retrouve_les_kwh_prouves(self):
        sortie = P.kwh_from_bill(self.FACTURE_TTC, utility='onee',
                                 facture_totale=True)
        self.assertAlmostEqual(sortie['kwh_mensuel'], self.KWH_PROUVES,
                               places=1)
        self.assertFalse(sortie['estimation'])

    def test_le_mode_energie_seule_surestime_d_environ_19_pct(self):
        """Régression NOMMÉE : c'est ce que l'écran envoie aujourd'hui."""
        energie = P.kwh_from_bill(self.FACTURE_TTC, utility='onee')
        self.assertAlmostEqual(energie['kwh_mensuel'], 429.0, places=1)
        surestimation = energie['kwh_mensuel'] / self.KWH_PROUVES - 1.0
        self.assertGreater(surestimation, 0.18)
        self.assertLess(surestimation, 0.20)

    def test_le_defaut_reste_l_inverse_exact_du_bareme_energie(self):
        """Le miroir JS et la garde d'aller-retour ne bougent pas d'un octet."""
        for kwh in (80.0, 140.0, 300.0, 600.0):
            facture = P._monthly_bill_from_kwh(kwh, P.ONEE_TRANCHES)
            self.assertAlmostEqual(
                P.kwh_from_bill(facture, utility='onee')['kwh_mensuel'],
                kwh, places=1, msg=str(kwh))

    def test_une_facture_hors_plage_ne_fabrique_pas_de_kwh(self):
        sortie = P.kwh_from_bill(1e9, utility='onee', facture_totale=True)
        self.assertEqual(sortie['kwh_mensuel'], 0.0)
        self.assertTrue(sortie['estimation'])

    def test_une_facture_vide_reste_une_estimation(self):
        for vide in (0, None, -5):
            sortie = P.kwh_from_bill(vide, utility='onee', facture_totale=True)
            self.assertTrue(sortie['estimation'], msg=repr(vide))
