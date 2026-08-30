"""QJR146 — lot de robustesse des chemins secondaires et des documents annexes.

Constats VÉRIFIÉS, non déclenchés aujourd'hui, regroupés en un seul commit :

(a) le duplicata et la gamme sœur perdaient ``echeancier``, ``acompte_pct``,
    ``acompte_montant``, ``entite`` et ``custom_data`` que ``renouveler_devis``
    copiait déjà — un échéancier NÉGOCIÉ repartait sur celui par DÉFAUT de la
    société, et c'est cette première tranche que l'email de confirmation
    annonce au client comme acompte ;
(b) FERMÉ PAR QJR117 : les trois chemins passent par
    ``domain.etudes.etude_params_pour_copie``, qui rend TOUJOURS un dict neuf
    (plus de référence partagée entre source et copie) ;
(c) ``renouveler_devis`` créait le devis puis ses lignes hors transaction ;
(d) ``extra_docs`` affirmait « échéance dépassée » à 0 jour de retard ;
(e) quatre défauts du moteur premium (taux de dérivation HT, tiret sur un prix
    négatif, ``.format()`` sur l'identité du tenant, deux totaux par option) ;
(f) ``industriel/trust`` reconstruisait localement un barème de paiement ;
(g) ``commercial`` repliait sa chaîne de totaux sur des zéros ;
(h) ``solar_design`` tronquait deux courbes de longueurs différentes, rendait
    24 zéros pour « rien de connu », et armait un productible de 1700.

Les classes ``SimpleTestCase`` sont PURES (aucune BD, aucun WeasyPrint) :
exécutables sur l'hôte. Les chemins de copie exigent l'ORM.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr146_robustesse -v 2
"""
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.ventes import solar_design
from apps.ventes.quote_engine import extra_docs
from apps.ventes.quote_engine import generate_devis_premium as moteur


# ════════════════════════════════════════════════════════════════════════════
# (d) — LA LETTRE DE RELANCE N'AFFIRME PAS UN RETARD QU'ELLE NE CHIFFRE PAS
# ════════════════════════════════════════════════════════════════════════════

class TestD_RetardNonChiffre(SimpleTestCase):

    RESUME = {
        "reference": "FAC-202608-0001",
        "date_echeance": "12/08/2026",
        "montant_du": 12000.0,
    }

    def _html(self, jours_retard):
        resume = dict(self.RESUME, jours_retard=jours_retard)
        return extra_docs.build_lettre_relance_html(
            {'entreprise_nom': 'QJR146 Co'},
            {'nom': 'Bennani', 'prenom': 'Sara'}, resume, 1)

    def test_retard_positif_est_imprime(self):
        html = self._html(12)
        self.assertIn("Retard", html)
        self.assertIn("12 jour(s)", html)

    def test_zero_jour_n_affirme_plus_un_depassement(self):
        """LE CONSTAT — « échéance dépassée » sortait sur une facture qui
        échoit AUJOURD'HUI."""
        for valeur in (0, None, "", "n/c"):
            with self.subTest(valeur=valeur):
                html = self._html(valeur)
                self.assertNotIn("échéance dépassée", html)
                self.assertNotIn("<span>Retard</span>", html)
                # Le reste de l'encadré est intact.
                self.assertIn("Montant restant dû", html)
                self.assertIn(self.RESUME["reference"], html)


# ════════════════════════════════════════════════════════════════════════════
# (e) — QUATRE DÉFAUTS DU MOTEUR PREMIUM
# ════════════════════════════════════════════════════════════════════════════

class TestE1_TauxDeDerivationHT(SimpleTestCase):
    """Le P.U. HT dérivé du TTC suit le taux de LA LIGNE."""

    _ABSENT = object()

    def setUp(self):
        # ``TVA_PCT`` n'existe qu'après une ingestion (``apply_quote_data``).
        self._tva = getattr(moteur, "TVA_PCT", self._ABSENT)
        moteur.TVA_PCT = 20.0

    def tearDown(self):
        if self._tva is self._ABSENT:
            del moteur.TVA_PCT
        else:
            moteur.TVA_PCT = self._tva

    def test_le_taux_de_la_ligne_prime_sur_le_taux_global(self):
        it = {"prix_unit_ttc": 110.0, "taux_tva": 10.0}
        self.assertAlmostEqual(moteur._item_pu_ht(it), 100.0, places=6)
        # Le taux GLOBAL aurait rendu 91,67 — 8,3 % trop bas, sous un « 10% »
        # imprimé dans la colonne d'à côté.
        self.assertNotAlmostEqual(moteur._item_pu_ht(it), 110.0 / 1.2, places=2)

    def test_sans_taux_de_ligne_le_taux_global_reste_le_repli(self):
        self.assertAlmostEqual(
            moteur._item_pu_ht({"prix_unit_ttc": 120.0}), 100.0, places=6)
        self.assertAlmostEqual(
            moteur._item_pu_ht({"prix_unit_ttc": 120.0, "taux_tva": None}),
            100.0, places=6)

    def test_un_pu_ht_stocke_n_est_jamais_derive(self):
        self.assertEqual(
            moteur._item_pu_ht({"prix_unit_ht": 42.0, "prix_unit_ttc": 999.0,
                                "taux_tva": 10.0}), 42.0)


class TestE2_PrixNegatifVisible(SimpleTestCase):
    """Un prix NÉGATIF pèse dans le sous-total : il s'imprime."""

    def test_le_tiret_ne_masque_plus_un_montant_negatif(self):
        from apps.ventes.tests._moteur_fixtures import (
            donnees_legacy, html_legacy)
        base = donnees_legacy("deux")
        remise = {**base["sans_items"][0], "designation": "Reprise ancien parc",
                  "quantite": 1.0, "prix_unit_ht": -1500.0,
                  "prix_unit_ttc": -1800.0, "taux_tva": 20.0}
        html = html_legacy("deux", sans_items=base["sans_items"] + [remise])
        self.assertIn("Reprise ancien parc", html)
        self.assertIn(moteur._fmt2(-1500.0), html)

    def test_un_prix_nul_reste_un_tiret(self):
        from apps.ventes.tests._moteur_fixtures import (
            donnees_legacy, html_legacy)
        base = donnees_legacy("deux")
        offert = {**base["sans_items"][0], "designation": "Mise en service",
                  "quantite": 1.0, "prix_unit_ht": 0.0, "prix_unit_ttc": 0.0,
                  "taux_tva": 20.0}
        html = html_legacy("deux", sans_items=base["sans_items"] + [offert])
        self.assertIn("Mise en service", html)


class TestE3_IdentiteAvecAccolades(SimpleTestCase):
    """Une raison sociale portant « { » ne fait plus échouer le PDF."""

    def test_la_ligne_rib_ne_passe_plus_par_format(self):
        _rib = moteur.ENT_RIB_LINE
        try:
            moteur.ENT_RIB_LINE = (
                '<strong style="color:{cg7}">SOCIÉTÉ {SARL} & Fils</strong> '
                '· Banque · RIB 000')
            # Avant : ``.format(cg7=…)`` levait KeyError('SARL') hors de tout
            # try — le PDF ENTIER échouait sur un caractère du nom de société.
            rendu = moteur.ENT_RIB_LINE.replace("{cg7}", moteur.CG7)
            self.assertIn("{SARL}", rendu)
            self.assertNotIn("{cg7}", rendu)
        finally:
            moteur.ENT_RIB_LINE = _rib

    def test_le_document_rend_une_raison_sociale_a_accolades(self):
        from apps.ventes.tests._moteur_fixtures import html_legacy
        html = html_legacy("deux", entreprise={
            "nom": "SOCIÉTÉ {SARL}", "rib": "000111222",
            "banque": "Banque Test"})
        self.assertIn("{SARL}", html)


class TestE4_UnSeulTotalParOption(SimpleTestCase):
    """``total_*`` et ``totaux_*`` ne peuvent plus diverger en silence."""

    def _data(self, **surcharges):
        from apps.ventes.tests._moteur_fixtures import donnees_legacy
        return donnees_legacy("deux", **surcharges)

    def test_la_charge_utile_coherente_passe(self):
        d = self._data()
        self.assertEqual(d["total_sans"], d["totaux_sans"]["ttc"])
        moteur.apply_quote_data(d)          # ne lève pas

    def test_deux_totaux_pour_une_option_levent(self):
        d = self._data()
        d["total_sans"] = d["totaux_sans"]["ttc"] + 1000.0
        with self.assertRaises(ValueError) as ctx:
            moteur.apply_quote_data(d)
        self.assertIn("total_sans", str(ctx.exception))

    def test_un_ttc_canonique_illisible_leve(self):
        d = self._data()
        d["totaux_avec"] = {**d["totaux_avec"], "ttc": "beaucoup"}
        with self.assertRaises(ValueError):
            moteur.apply_quote_data(d)


# ════════════════════════════════════════════════════════════════════════════
# (f) / (g) — AUCUN BARÈME NI AUCUNE CHAÎNE DE TOTAUX RECONSTRUITS
# ════════════════════════════════════════════════════════════════════════════

class TestF_BaremeIndustriel(SimpleTestCase):

    def _html(self, **surcharges):
        from apps.ventes.quote_engine.industriel import (
            render, renderer, sample_data)
        d = dict(sample_data.build())
        d.update(surcharges)
        return render.build_html(renderer._augment(d))

    def test_avec_bareme_servi_les_tranches_sont_rendues(self):
        html = self._html(payment_terms={"acompte": 40, "materiel": 50,
                                         "solde": 10})
        self.assertIn("Tranches de paiement", html)
        self.assertIn("40%", html)
        self.assertIn("50%", html)

    def test_sans_bareme_servi_le_bloc_est_omis(self):
        """LE CONSTAT — le repli 50/40/10 refabriquait un échéancier dont la
        source canonique est le RÉGLAGE SOCIÉTÉ, et calculait des MONTANTS
        dessus."""
        for absent in ({}, None, {"acompte": 50}):
            with self.subTest(absent=absent):
                html = self._html(payment_terms=absent)
                self.assertNotIn("Tranches de paiement", html)
                # Le reste de la page 3 est intact.
                self.assertIn("Conformité", html)


class TestG_TotauxCommercial(SimpleTestCase):

    def test_sans_totaux_canoniques_le_renderer_refuse(self):
        from apps.ventes.quote_engine.commercial import renderer, sample_data
        for absent in ({}, None):
            with self.subTest(absent=absent):
                d = dict(sample_data.build("boulangerie"))
                d["totaux_all"] = absent
                with self.assertRaises(renderer.Unsupported):
                    renderer._augment(d)

    def test_avec_totaux_canoniques_le_rendu_est_celui_d_hier(self):
        from apps.ventes.quote_engine.commercial import (
            render, renderer, sample_data)
        html = render.build_html(
            renderer._augment(sample_data.build("boulangerie")))
        self.assertIn("Sous-total", html)


# ════════════════════════════════════════════════════════════════════════════
# (h) — SOLAR_DESIGN : REFUSER PLUTÔT QUE TRONQUER OU FABRIQUER
# ════════════════════════════════════════════════════════════════════════════

class TestH_SolarDesign(SimpleTestCase):

    def test_deux_courbes_de_longueurs_differentes_sont_refusees(self):
        with self.assertRaises(ValueError):
            solar_design.hourly_self_consumption(
                load_curve=[1.0] * 288, production_curve=[2.0] * 24)

    def test_une_serie_vide_rend_zero_heure(self):
        res = solar_design.hourly_self_consumption(
            load_curve=[1.0] * 288, production_curve=[])
        self.assertEqual(res["hours"], 0)
        self.assertEqual(res["total_production_kwh"], 0.0)

    def test_rien_de_connu_ne_rend_plus_vingt_quatre_zeros(self):
        self.assertEqual(solar_design._scaled_typical_pv(0), [])
        self.assertEqual(solar_design._scaled_typical_pv(None), [])
        self.assertEqual(solar_design._scaled_typical_load(0), [])
        self.assertEqual(solar_design._scaled_typical_load(None), [])
        # Une énergie CONNUE se distribue toujours sur 24 h.
        self.assertEqual(len(solar_design._scaled_typical_pv(10.0)), 24)

    def test_les_sources_des_series_sont_publiees(self):
        res = solar_design.hourly_self_consumption(
            load_curve=[1.0] * 24, production_curve=[2.0] * 24)
        self.assertEqual(res["load_source"], "courbe fournie")
        self.assertEqual(res["production_source"], "courbe fournie")

    def test_aucun_productible_n_est_arme_par_defaut(self):
        """LE CONSTAT — 1700 kWh/kWc/an s'appliquait en silence dès qu'un
        appelant donnait un kWc sans productible."""
        sans = solar_design.ev_charger_sizing(
            borne_kw=7.4, pv_kwc=5.0, energy_per_session_kwh=8.0)
        self.assertIsNone(sans["pv_impact"]["pv_daily_production_kwh"])
        avec = solar_design.ev_charger_sizing(
            borne_kw=7.4, pv_kwc=5.0, energy_per_session_kwh=8.0,
            productible_kwh_kwc_year=1700.0)
        self.assertAlmostEqual(
            avec["pv_impact"]["pv_daily_production_kwh"], 23.29, places=1)


# ════════════════════════════════════════════════════════════════════════════
# (i) — OTP : COMPARAISON À TEMPS CONSTANT, DESTINATAIRE VIDE REFUSÉ
# ════════════════════════════════════════════════════════════════════════════

class TestI_Otp(SimpleTestCase):

    def test_l_email_otp_vide_ne_part_pas(self):
        from apps.ventes.domain import cycle_vie
        with mock.patch("django.core.mail.send_mail") as envoi:
            for vide in ("", "   ", None):
                with self.subTest(vide=vide):
                    self.assertFalse(cycle_vie._send_otp_email(
                        vide, "123456", "DEV-1"))
            envoi.assert_not_called()

    def test_la_comparaison_d_otp_est_a_temps_constant(self):
        """PREUVE PAR LECTURE DE SOURCE — ``!=`` sort au premier caractère
        différent : le temps de réponse fuit la longueur du préfixe correct.
        Le plafond de tentatives borne le brute-force, pas ce canal-là."""
        import ast
        import inspect
        from pathlib import Path
        from apps.ventes.domain import cycle_vie

        source = Path(inspect.getsourcefile(cycle_vie)).read_text(
            encoding="utf-8")
        arbre = ast.parse(source)
        vus = 0
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.FunctionDef):
                continue
            if noeud.name not in ("validate_esign_otp", "validate_otp_lecture"):
                continue
            vus += 1
            appels = {
                n.func.attr for n in ast.walk(noeud)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
            }
            self.assertIn("compare_digest", appels,
                          f"{noeud.name} compare encore l'OTP avec ==/!=")
        self.assertEqual(vus, 2, "les deux validateurs d'OTP n'ont pas été vus")


# ════════════════════════════════════════════════════════════════════════════
# (a) / (b) / (c) — LES TROIS CHEMINS DE COPIE (ORM)
# ════════════════════════════════════════════════════════════════════════════

class TestAbc_ChemminsDeCopie(TestCase):
    """Les conditions de paiement suivent la copie ; l'étude n'est jamais
    partagée par référence ; le renouvellement est atomique."""

    LIGNES = [
        ('Onduleur hybride Deye 5kW', '1', '14166.67'),
        ('Panneau mono 550W', '10', '1100'),
    ]

    ECHEANCIER = [
        {"key": "acompte", "libelle": "Acompte", "valeur": 50,
         "unite": "pct"},
        {"key": "solde", "libelle": "Solde", "valeur": 50, "unite": "pct"},
    ]

    def setUp(self):
        from ._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, self.LIGNES,
            reference='DEV-QJR146-SRC',
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        self.devis.echeancier = list(self.ECHEANCIER)
        self.devis.acompte_pct = Decimal('50.00')
        self.devis.acompte_montant = Decimal('1000.00')
        self.devis.custom_data = {'chantier': 'Bouskoura'}
        self.devis.save()

    def test_a_le_duplicata_garde_les_conditions_de_paiement(self):
        from apps.ventes.services import dupliquer_devis
        copie = dupliquer_devis(self.devis, user=self.user)
        self.assertEqual(copie.echeancier, self.ECHEANCIER)
        self.assertEqual(copie.acompte_pct, self.devis.acompte_pct)
        self.assertEqual(copie.acompte_montant, self.devis.acompte_montant)
        self.assertEqual(copie.custom_data, {'chantier': 'Bouskoura'})
        self.assertEqual(copie.entite_id, self.devis.entite_id)

    def test_a_les_json_ne_sont_jamais_partages(self):
        """Même piège que ``etude_params`` avant QJR117 : muter la copie ne
        doit pas toucher la source."""
        from apps.ventes.services import dupliquer_devis
        copie = dupliquer_devis(self.devis, user=self.user)
        self.assertIsNot(copie.echeancier, self.devis.echeancier)
        self.assertIsNot(copie.custom_data, self.devis.custom_data)
        self.assertIsNot(copie.etude_params, self.devis.etude_params)

    def test_a_la_gamme_soeur_herite_des_conditions_pas_du_montant(self):
        """La sœur a « sa composition et SES prix propres » : le POURCENTAGE
        est une condition (il suit), le MONTANT décrit le total du frère."""
        from apps.ventes.services import creer_variante_gamme
        soeur = creer_variante_gamme(self.devis, 'Premium', user=self.user)
        self.assertEqual(soeur.echeancier, self.ECHEANCIER)
        self.assertEqual(soeur.acompte_pct, self.devis.acompte_pct)
        self.assertIsNone(soeur.acompte_montant)
        self.assertEqual(soeur.custom_data, {'chantier': 'Bouskoura'})

    def test_c_le_renouvellement_est_atomique(self):
        """Une erreur pendant le clonage des lignes ne laisse PAS un
        renouvellement brouillon à zéro ligne dans la liste."""
        from apps.ventes.models import Devis
        from apps.ventes.services import renouveler_devis
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        avant = Devis.objects.filter(company=self.company).count()
        with mock.patch('apps.ventes.domain.cycle_vie.cloner_lignes',
                        side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                renouveler_devis(self.devis, user=self.user)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), avant,
            "un renouvellement orphelin (0 ligne) a survécu à l'échec")
