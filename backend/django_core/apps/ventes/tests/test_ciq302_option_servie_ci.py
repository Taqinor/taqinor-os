"""CIQ302 — devis C&I à deux options : l'offre RÉSEAU seule est l'offre
principale ; la batterie est une option qui ne montre que la valeur chiffrée
par le moteur.

Avant : ``builder`` faisait de l'option AVEC le tableau, les totaux et
``display_total`` dès qu'il y avait deux options, pendant que la couverture
C&I imprimait l'économie de l'option SANS — couverture et page 3 se
contredisaient (C3-05, C3-VA-03). Le noyau (``option_effective``) suivait la
même règle AVEC.

Après (convention 5) : commercial / industriel → ``option_servie = 'sans'`` ;
``all_items`` / ``totaux_all`` / ``display_total`` décrivent l'offre réseau ;
``option_effective`` = SANS dans le MÊME commit (jumeau, leçon QJR400) ; le
panier batterie part dans ``option_batterie``. L'option acceptée et un
scénario mono déclaré gardent la priorité. Le résidentiel ne bouge pas.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_ciq302_option_servie_ci -v 2
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ventes.utils import options as opts_mod

LIGNES_DEUX_OPTIONS = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '11700'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '24000'),
    ('Panneau Canadien Solar 710W', '14', '1100'),
    ('Batterie Dyness 10 kWh', '1', '14000'),
    ('Structures acier', '14', '375'),
    ('Installation', '1', '4000'),
]


class _Devis:
    def __init__(self, mode):
        self.mode_installation = mode


class TestRegleDuNoyau(SimpleTestCase):
    """La règle partagée moteur ↔ noyau (aucune BD)."""

    def test_ci_met_en_avant_l_offre_reseau(self):
        for mode in ('commercial', 'industriel', ' Industriel '):
            with self.subTest(mode=mode):
                self.assertEqual(opts_mod.option_mise_en_avant(_Devis(mode)),
                                 opts_mod.SANS_BATTERIE)

    def test_residentiel_et_autres_gardent_avec(self):
        for mode in ('residentiel', 'agricole', '', None):
            with self.subTest(mode=mode):
                self.assertEqual(opts_mod.option_mise_en_avant(_Devis(mode)),
                                 opts_mod.AVEC_BATTERIE)


class TestOptionServieCI(TestCase):
    """``build_quote_data`` RÉEL (jamais mocké) + noyau monnaie."""

    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, mode, reference, etude=None):
        from apps.ventes.tests._quote_engine_common import (
            DEUX_OPTIONS, make_devis)
        devis = make_devis(self.company, self.user, self.client_obj,
                           LIGNES_DEUX_OPTIONS, reference=reference,
                           etude_params=dict(etude or DEUX_OPTIONS))
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        return devis

    def _data(self, devis):
        from apps.ventes.models import Devis
        from apps.ventes.quote_engine.builder import build_quote_data
        return build_quote_data(Devis.objects.get(pk=devis.pk),
                                {'pdf_mode': 'full'})

    @staticmethod
    def _designations(rows):
        return sorted(r['designation'] for r in rows)

    def test_ci_deux_options_sert_le_reseau_seul(self):
        from apps.ventes.models import Devis
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                devis = self._devis(mode, f'DEV-CIQ302-{mode[:3].upper()}')
                data = self._data(devis)
                self.assertTrue(data['deux_options'])
                self.assertEqual(data['option_servie'], 'sans')
                self.assertEqual(data['display_total'],
                                 data['totaux_sans']['ttc'])
                self.assertEqual(data['totaux_all']['ttc'],
                                 data['totaux_sans']['ttc'])
                self.assertEqual(self._designations(data['all_items']),
                                 self._designations(data['sans_items']))
                self.assertFalse(any('Batterie' in r['designation']
                                     for r in data['all_items']))
                ob = data['option_batterie']
                self.assertEqual(ob['totaux'], data['totaux_avec'])
                self.assertTrue(any('Batterie' in r['designation']
                                    for r in ob['lignes']))
                self.assertIsNone(ob['valeur_chiffree'])
                self.assertTrue(ob['motif'])
                # Noyau monnaie : la MÊME option, le MÊME nombre.
                frais = Devis.objects.get(pk=devis.pk)
                self.assertEqual(opts_mod.option_effective(frais),
                                 opts_mod.SANS_BATTERIE)
                self.assertEqual(Decimal(str(frais.total_ttc)),
                                 Decimal(str(data['display_total'])))

    def test_ci_accepte_sur_avec_garde_avec(self):
        from apps.ventes.models import Devis
        devis = self._devis('industriel', 'DEV-CIQ302-ACC')
        Devis.objects.filter(pk=devis.pk).update(
            option_acceptee=opts_mod.AVEC_BATTERIE)
        frais = Devis.objects.get(pk=devis.pk)
        self.assertEqual(opts_mod.option_effective(frais),
                         opts_mod.AVEC_BATTERIE)
        data = self._data(devis)
        self.assertEqual(data['option_servie'], 'avec')
        self.assertEqual(data['display_total'], data['totaux_avec']['ttc'])
        self.assertNotIn('option_batterie', data)

    def test_ci_scenario_mono_avec_garde_la_priorite(self):
        from apps.ventes.models import Devis
        devis = self._devis('commercial', 'DEV-CIQ302-MONO',
                            {'scenario': 'Avec batterie'})
        frais = Devis.objects.get(pk=devis.pk)
        # Le scénario mono décide (QJR400) : jamais l'offre réseau imposée.
        self.assertNotEqual(opts_mod.option_effective(frais),
                            opts_mod.SANS_BATTERIE)
        data = self._data(devis)
        self.assertNotIn('option_servie', data)
        self.assertEqual(data['display_total'], data['totaux_avec']['ttc'])

    def test_residentiel_deux_options_inchange(self):
        """Non-régression : un résidentiel à deux options titre AVEC."""
        from apps.ventes.models import Devis
        devis = self._devis('residentiel', 'DEV-CIQ302-RES')
        data = self._data(devis)
        self.assertTrue(data['deux_options'])
        self.assertNotIn('option_servie', data)
        self.assertNotIn('option_batterie', data)
        self.assertEqual(data['display_total'], data['totaux_avec']['ttc'])
        self.assertEqual(
            opts_mod.option_effective(Devis.objects.get(pk=devis.pk)),
            opts_mod.AVEC_BATTERIE)

    def test_repli_sans_moteur_suit_la_meme_regle(self):
        devis = self._devis('commercial', 'DEV-CIQ302-REPLI')
        data = self._data(devis)
        repli = opts_mod.totaux_affichage_repli(devis)
        self.assertEqual(repli['nb_options'], 2)
        self.assertAlmostEqual(repli['total'],
                               float(data['totaux_sans']['ttc']), places=2)

    def test_echappement_option_batterie_un_seul(self):
        from apps.ventes.quote_engine.builder import echapper_textes_client
        devis = self._devis('industriel', 'DEV-CIQ302-ESC')
        sortie = echapper_textes_client(self._data(devis))
        self.assertIs(sortie['option_batterie']['lignes'],
                      sortie['avec_items'])


# ── CPDF1 / CPDF10 — la synthèse C&I lit les chiffres de l'option SERVIE ────

def _economie_complete(total_mad, retour_ans):
    """Un ``economie_ci`` calculé à la forme complète (base, flux,
    indicateurs) — ce que la page finance lit."""
    return {"statut": "calcule", "base": "ht",
            "economie_annee1": {"total_mad": total_mad,
                                "total_mad_ttc": total_mad * 1.2},
            "flux_ht": [{"annee": 1, "cumul_mad": total_mad}],
            "indicateurs": {"retour_ans": retour_ans},
            "remplacements": []}


def _option_avec(**surcharges):
    """``etude_ci.option_avec`` à la forme servie
    (``domain/etude_ci_batterie._bloc``)."""
    mois = [{"mois": m, "production_kwh": 12000, "consommation_kwh": 15000,
             "autoconso_kwh": 11000, "surplus_kwh": 1000}
            for m in range(1, 13)]
    bloc = {
        "kwc": 80.0, "nb_panneaux": 140,
        "batterie": {"capacite_utile_kwh": 92.2, "besoin_nocturne_kwh": 100},
        "bilan": {"production_kwh": 144000, "autoconso_kwh": 132000,
                  "surplus_kwh": 12000, "injecte_valorise_kwh": 0,
                  "non_valorise_kwh": 12000, "taux_autoconso": 0.917,
                  "taux_couverture": 0.733, "par_mois": mois,
                  "batterie": {"capacite_utile_kwh": 92.2,
                               "restitue_kwh_an": 31000}},
        "economie_ci": _economie_complete(95767.0, 4.2),
        "economie_annuelle_mad": 95767.0,
        "retour_simple_ans": 4.9,
    }
    bloc.update(surcharges)
    return bloc


def _data_ci(option_servie="avec", option_avec=True, **surcharges):
    from apps.ventes.tests.test_ciq303_synthese_ci_coeur import (
        _data, _etude_ci)
    etude = _etude_ci(taille={"retenue_kwc": 55.0})
    etude["bilan"]["par_mois"] = [
        {"mois": m, "production_kwh": 8000, "consommation_kwh": 15000,
         "autoconso_kwh": 5800, "surplus_kwh": 2200} for m in range(1, 13)]
    if option_avec:
        etude["option_avec"] = (_option_avec() if option_avec is True
                                else option_avec)
    data = _data(etude, option_servie=option_servie, sans_ok=True,
                 avec_ok=True, puissance_kwc_sans=55.0,
                 puissance_kwc_avec=80.0, total_sans=157700.0,
                 total_avec=473100.0,
                 economie_ci=_economie_complete(53123.0, 3.0),
                 jalons_paiement=[
                     {"jalon": "commande", "pct": 40, "montant_ttc": 63080.0},
                     {"jalon": "livraison_materiel", "pct": 50,
                      "montant_ttc": 78850.0},
                     {"jalon": "mise_en_service", "pct": 10,
                      "montant_ttc": 15770.0}])
    data.update(surcharges)
    return data


class TestCpdf1OptionAvecServie(SimpleTestCase):
    """CPDF1 — option « avec batterie » servie : production, énergie,
    argent et échéancier de CETTE option, jamais ceux de l'offre sans."""

    def _s(self, data):
        from apps.ventes.quote_engine.ci.synthese import synthese_ci
        return synthese_ci(data)

    def test_chiffres_de_l_option_avec(self):
        s = self._s(_data_ci())
        self.assertEqual(s["option_servie"], "avec_batterie")
        self.assertEqual(s["systeme"]["kwc"], 80)
        self.assertEqual(s["systeme"]["production_kwh_an"], 144000)
        self.assertEqual(s["energie"]["taux_autoconso_pct"], 91.7)
        self.assertEqual(s["energie"]["taux_couverture_pct"], 73.3)
        self.assertEqual(s["energie"]["par_mois"][0]["production_kwh"], 12000)
        self.assertEqual(s["energie"]["surplus"]["kwh_an"], 12000)
        self.assertEqual(s["argent"]["economie_annee1"]["total_mad"], 95767.0)
        self.assertEqual(s["argent"]["indicateurs"]["retour_ans"], 4.2)
        self.assertNotIn("53123", str(s["argent"]))

    def test_echeancier_sur_le_total_avec(self):
        ech = self._s(_data_ci())["echeancier"]
        self.assertEqual([j["pct"] for j in ech], [40, 50, 10])
        self.assertEqual([j["montant_ttc"] for j in ech],
                         [189240.0, 236550.0, 47310.0])
        self.assertAlmostEqual(sum(j["montant_ttc"] for j in ech),
                               473100.0, 2)

    def test_sans_economie_de_l_option_argent_omis(self):
        from apps.ventes.quote_engine.ci.synthese import (
            MOTIF_ARGENT_OPTION_AVEC)
        for economie in (None, {"statut": "calcule",
                                "economie_annee1": {"total_mad": 1.0}}):
            with self.subTest(economie=economie):
                s = self._s(_data_ci(option_avec=_option_avec(
                    economie_ci=economie)))
                self.assertNotIn("argent", s)
                motifs = {o["bloc"]: o["motif"] for o in s["omissions"]}
                self.assertEqual(motifs["argent"], MOTIF_ARGENT_OPTION_AVEC)

    def test_argent_avec_economie_ci_et_son_flux_25_ans(self):
        """CMP6 — ``option_avec.economie_ci`` (sortie de ``valoriser`` :
        tarif, économie an 1, sans flux) complété de ``economie_flux``
        (forme ``economie_ci_options.flux_option_avec``)."""
        valorise = {"statut": "calcule", "motifs_omission": [],
                    "tarif": {"origine": "declare_facture"},
                    "economie_annee1": {"total_mad": 95767.0,
                                        "total_mad_ttc": 114920.4},
                    "facture_avant": None, "facture_apres": None,
                    "revente": None, "hypotheses": [],
                    "vue_interne": {"secret": 1}}
        flux = {"base": "ht", "motif_base": "TVA récupérable déclarée",
                "flux_ht": [{"annee": 1, "cumul_mad": -300000.0}],
                "flux_ttc": None, "jalons": [],
                "indicateurs": {"tri_pct": 18.2, "retour_ans": 5,
                                "retour_dixieme_ans": 4.6},
                "remplacements": [{"composant": "batterie", "annee": 12,
                                   "montant_ht_mad": 140000.0,
                                   "montant_ttc_mad": 168000.0,
                                   "source": "fiche"}],
                "om": None, "entretien": None}
        s = self._s(_data_ci(option_avec=_option_avec(
            economie_ci=valorise, economie_flux=flux)))
        argent = s["argent"]
        self.assertEqual(argent["economie_annee1"]["total_mad"], 95767.0)
        self.assertEqual(argent["base"], "ht")
        self.assertEqual(argent["indicateurs"]["retour_dixieme_ans"], 4.6)
        self.assertEqual(argent["remplacements"][0]["composant"], "batterie")
        self.assertEqual(argent["flux_ht"], flux["flux_ht"])
        self.assertNotIn("vue_interne", argent)
        # Le flux seul, sans ``economie_ci`` calculé : argent omis.
        s = self._s(_data_ci(option_avec=_option_avec(
            economie_ci=None, economie_flux=flux)))
        self.assertNotIn("argent", s)

    def test_sous_serie_absente_omise_jamais_empruntee(self):
        avec = _option_avec()
        del avec["bilan"]["par_mois"]
        del avec["bilan"]["surplus_kwh"]
        s = self._s(_data_ci(option_avec=avec))
        self.assertNotIn("par_mois", s["energie"])
        self.assertNotIn("surplus", s["energie"])
        self.assertEqual(s["energie"]["taux_couverture_pct"], 73.3)

    def test_taux_de_l_option_dans_la_valeur_chiffree(self):
        s = self._s(_data_ci(option_servie="sans", option_batterie={
            "totaux": {"ttc": 473100.0}, "valeur_chiffree": None}))
        valeur = s["option_batterie"]["valeur_chiffree"]
        self.assertEqual(valeur["taux_couverture_pct"], 73.3)
        self.assertEqual(valeur["taux_autoconso_pct"], 91.7)

    def test_offre_sans_et_les_deux_inchangees(self):
        s = self._s(_data_ci(option_servie="sans"))
        self.assertEqual(s["systeme"]["production_kwh_an"], 95425)
        self.assertEqual(s["energie"]["taux_couverture_pct"], 46.6)
        self.assertEqual(s["argent"]["economie_annee1"]["total_mad"], 53123.0)
        self.assertEqual([j["montant_ttc"] for j in s["echeancier"]],
                         [63080.0, 78850.0, 15770.0])

    def test_avec_sans_option_avec_servie_inchange(self):
        s = self._s(_data_ci(option_avec=False))
        # L'étude décrit 55 kWc, l'option servie 80 : rien d'emprunté.
        self.assertIsNone(s["systeme"]["production_kwh_an"])
        self.assertNotIn("energie", s)


class TestCpdf10EcheancierAuReliquat(SimpleTestCase):
    """CPDF10 — pourcentages imprimés = montants : le dernier jalon imprime
    le reliquat quand le réglage ne somme pas à 100."""

    def _s(self, data):
        from apps.ventes.quote_engine.ci.synthese import synthese_ci
        return synthese_ci(data)

    def test_jalons_50_39_10_dernier_au_reliquat(self):
        data = _data_ci(option_servie="sans", jalons_paiement=[
            {"jalon": "commande", "pct": 50, "montant_ttc": 78850.0},
            {"jalon": "livraison_materiel", "pct": 39,
             "montant_ttc": 61503.0},
            {"jalon": "mise_en_service", "pct": 10, "montant_ttc": 17347.0}])
        ech = self._s(data)["echeancier"]
        self.assertEqual([j["pct"] for j in ech], [50, 39, 11])
        self.assertEqual([j["montant_ttc"] for j in ech],
                         [78850.0, 61503.0, 17347.0])

    def test_somme_a_cent_inchangee(self):
        ech = self._s(_data_ci(option_servie="sans"))["echeancier"]
        self.assertEqual([j["pct"] for j in ech], [40, 50, 10])

    def test_repli_payment_terms_au_reliquat(self):
        data = _data_ci(option_servie="sans", jalons_paiement=None,
                        payment_terms={"acompte": 50, "materiel": 39,
                                       "solde": 10})
        ech = self._s(data)["echeancier"]
        self.assertEqual([j["pct"] for j in ech], [50, 39, 11])
        self.assertAlmostEqual(ech[-1]["montant_ttc"] / 157700.0 * 100, 11, 6)


class TestCpdfNiveauRegles3(SimpleTestCase):
    """CPDF — les corrections de CHIFFRE du PDF C&I ne touchent que les
    nouveaux rendus (``regles_au_moins(devis, REGLES_CORRIGEES_2710)``) : un
    devis envoyé avant (``data['regles_avant_2710']``, posé par le builder et
    relu par chaque renderer) imprime ce que le client a reçu."""

    def setUp(self):
        from apps.ventes.quote_engine.montants import poser_regles_origine
        poser_regles_origine(False, avant_2710=True)
        self.addCleanup(poser_regles_origine, False)

    def _s(self, data):
        from apps.ventes.quote_engine.ci.synthese import synthese_ci
        return synthese_ci(data)

    def test_option_avec_servie_garde_les_chiffres_imprimes(self):
        s = self._s(_data_ci())
        # Avant CPDF1 : l'étude décrit 55 kWc, l'option servie 80 — production
        # omise (AMOT62), argent et échéancier de l'offre servie au builder.
        self.assertIsNone(s["systeme"]["production_kwh_an"])
        self.assertEqual(s["argent"]["economie_annee1"]["total_mad"], 53123.0)
        self.assertEqual([j["montant_ttc"] for j in s["echeancier"]],
                         [63080.0, 78850.0, 15770.0])

    def test_echeancier_garde_ses_pourcentages(self):
        data = _data_ci(option_servie="sans", jalons_paiement=[
            {"jalon": "commande", "pct": 50, "montant_ttc": 78850.0},
            {"jalon": "livraison_materiel", "pct": 39,
             "montant_ttc": 61503.0},
            {"jalon": "mise_en_service", "pct": 10, "montant_ttc": 17347.0}])
        self.assertEqual([j["pct"] for j in self._s(data)["echeancier"]],
                         [50, 39, 10])

    def test_retour_servi_et_quotient_de_l_option_avec(self):
        from apps.ventes.quote_engine.ci import couverture, mentions
        argent = {"base": "ht", "flux_ht": {"flux": [
            {"annee": 0, "flux_net_mad": -100.0, "cumul_mad": -100.0},
            {"annee": 1, "flux_net_mad": 40.0, "cumul_mad": -60.0},
            {"annee": 2, "flux_net_mad": 40.0, "cumul_mad": -20.0},
            {"annee": 3, "flux_net_mad": 40.0, "cumul_mad": 20.0}]}}
        self.assertEqual(couverture.retour_dixieme(argent, 3), 3)
        data = _data_ci(option_servie="sans", option_batterie={
            "totaux": {"ht_net": 383000.0}})
        valeur = mentions.valeur_option_avec(data)
        self.assertEqual(valeur["retour_simple_ans"],
                         round(383000.0 / 95767.0, 1))

    def test_phrase_soir_nuit_d_origine(self):
        from apps.ventes.quote_engine.ci import mentions
        data = _data_ci(option_servie="sans", option_batterie={
            "totaux": {"ttc": 473100.0}})
        self.assertIs(mentions._textes_pointe_option_avec(data),
                      mentions.TEXTES_POINTE_SANS_OPTION_AVEC)
