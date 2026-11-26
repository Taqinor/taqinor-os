# -*- coding: utf-8 -*-
"""LANE CHOIX-AVEC (fondateur, 25/08/2026) — le schéma unifilaire d'un devis
« deux options » choisit TOUJOURS l'option AVEC batterie quand elle est
servable, jamais un mélange des deux.

BUG TROUVÉ SUR LE DEVIS RÉEL DEV-202608-0024 (page proposition) : le tableau
matériel du PDF montrait l'onduleur HYBRIDE Deye 15 kW (option avec) pendant
que le SCHÉMA UNIFILAIRE montrait « Huawei 15,0 kW » — l'onduleur RÉSEAU de
l'option SANS — avec la batterie Dyness 15,4 kWh accrochée dessus. Un montage
qui n'existe dans AUCUN document commercial, sur une pièce technique remise au
gestionnaire de réseau.

CAUSE : sur un devis qui porte un onduleur RÉSEAU, un onduleur HYBRIDE et une
BATTERIE en lignes non optionnelles (le même état de données que l'artefact
« deux onduleurs non déclarés » de ``quote_engine/builder.py``, PV86/L-2OPT),
``electrical_service._produit_de_famille`` retournait le PREMIER onduleur
rencontré par ordre d'insertion dans ``devis.lignes.all()`` — sans savoir s'il
s'agissait du réseau ou de l'hybride — pendant que ``_batterie_du_devis``
additionnait la batterie sans se soucier de l'option à laquelle elle
appartient.

CORRECTIF : ``electrical_service._lignes_option_choisie`` scinde les lignes en
un panier SANS et un panier AVEC par les mêmes mots-clés que
``quote_engine.builder._repartir_options``, puis choisit l'option AVEC quand
elle est servable (un onduleur hybride ET une batterie, tous deux en lignes du
panier AVEC), sinon SANS (un onduleur réseau en ligne), sinon replie sur
toutes les lignes (devis mono-option classique — comportement inchangé).
``_produit_de_famille`` (onduleur ET panneau) et ``_batterie_du_devis`` lisent
désormais ce panier plutôt que ``devis.lignes.all()`` brut.

Aucune base de données : devis/produit/fiche DUCK-TYPÉS (même patron que
``test_sld_batterie_packs.py``), le test exerce le vrai sélecteur
``specs_for_produit`` sans migration.

Run :
    python manage.py test apps.ventes.tests.test_l_choix_avec_sld -v 2
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.ventes import conceptions_options as co
from apps.ventes import electrical_service as es


class _FausseFiche:
    def __init__(self, type_fiche, **valeurs):
        self._valeurs = valeurs
        self.type_fiche = type_fiche

    def __getattr__(self, nom):
        return self._valeurs.get(nom)


class _FauxProduit:
    def __init__(self, nom, marque="", description="", fiche=None):
        self.id = None
        self.nom = nom
        self.marque = marque
        self.description = description
        if fiche is not None:
            self.fiche_technique = fiche


class _FausseLigne:
    def __init__(self, designation, quantite=1, produit=None):
        self.designation = designation
        self.quantite = Decimal(str(quantite))
        self.produit = produit
        self.produit_id = None


class _FaussesLignes:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return list(self._lignes)


class _FauxDevis:
    pk = None

    def __init__(self, lignes=(), roof_layout=None):
        self.lignes = _FaussesLignes(lignes)
        self.roof_layout = roof_layout
        self.layout_hash = ""
        self.electrical_design = None
        self.electrical_design_hash = None
        self.reference = "DEV-L-CHOIX-AVEC"


FICHE_CS710 = dict(pmax_wc=Decimal("710.00"), voc_v=Decimal("48.30"),
                   isc_a=Decimal("18.59"), vmp_v=Decimal("40.40"),
                   imp_a=Decimal("17.59"),
                   temp_coeff_voc_pct_c=Decimal("-0.250"),
                   temp_coeff_pmax_pct_c=Decimal("-0.290"))

FICHE_ONDULEUR_HYBRIDE = dict(
    ond_n_mppt=2, ond_mppt_v_min=Decimal("200.0"),
    ond_mppt_v_max=Decimal("650.0"), ond_v_max_abs=Decimal("800.0"),
    ond_i_max_mppt_a=Decimal("26.0"), ond_ac_kw=Decimal("15"),
    ond_phases=3, ond_rendement_euro_pct=Decimal("97.0"))

FICHE_ONDULEUR_RESEAU = dict(
    ond_n_mppt=2, ond_mppt_v_min=Decimal("200.0"),
    ond_mppt_v_max=Decimal("650.0"), ond_v_max_abs=Decimal("800.0"),
    ond_i_max_mppt_a=Decimal("26.0"), ond_ac_kw=Decimal("15"),
    ond_phases=3, ond_rendement_euro_pct=Decimal("97.5"))


def _panneau():
    return _FauxProduit("Panneau Canadien Solar 710W", marque="Canadien Solar",
                        fiche=_FausseFiche("module", **FICHE_CS710))


def _onduleur_hybride():
    return _FauxProduit("Onduleur hybride Deye 15kW Triphasé", marque="Deye",
                        fiche=_FausseFiche(
                            "onduleur", **FICHE_ONDULEUR_HYBRIDE))


def _onduleur_reseau():
    return _FauxProduit("Onduleur réseau Huawei 15kW Triphasé", marque="Huawei",
                        fiche=_FausseFiche(
                            "onduleur", **FICHE_ONDULEUR_RESEAU))


def _batterie(nom="Batterie Dyness 15,4 kWh", marque="Dyness", kwh="15.36",
              v="51.2"):
    return _FauxProduit(nom, marque=marque, fiche=_FausseFiche(
        "batterie", bat_kwh_nominal=Decimal(kwh), bat_v_nominal=Decimal(v)))


def _roof(n):
    return {"_pans_geometry": [{"label": "Sud", "nb_panneaux": n,
                                "azimut_deg": 180, "inclinaison_deg": 20}]}


def _devis_deux_options_servables(n_panneaux=30):
    """Reproduit l'état de lignes de DEV-202608-0024 : réseau + hybride +
    batterie, tous en lignes NON optionnelles — les deux options sont
    physiquement servables."""
    return _FauxDevis(lignes=[
        _FausseLigne("Panneau PV 710 Wc", n_panneaux, produit=_panneau()),
        _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                     produit=_onduleur_reseau()),
        _FausseLigne("Onduleur hybride 15kW triphasé", 1,
                     produit=_onduleur_hybride()),
        _FausseLigne("Batterie lithium 15,4 kWh", 1, produit=_batterie()),
    ], roof_layout=_roof(n_panneaux))


class ChoixOnduleurSurDevisDeuxOptionsTest(SimpleTestCase):
    """Le point de choix : ``_produit_de_famille`` (onduleur) via
    ``_lignes_option_choisie``."""

    def test_onduleur_choisi_est_hybride_jamais_reseau(self):
        devis = _devis_deux_options_servables()
        onduleur, phases = es.spec_onduleur_du_devis(devis)
        self.assertIn("Deye", onduleur.designation)
        self.assertNotIn("Huawei", onduleur.designation)
        self.assertEqual(phases, 3)

    def test_panneau_reste_lu_les_deux_options_le_partagent(self):
        # Les lignes panneau n'appartiennent à AUCUNE option exclusivement :
        # le panier gagnant (AVEC) les porte quand même — aucune régression
        # sur la lecture du module.
        devis = _devis_deux_options_servables()
        module = es.spec_module_du_devis(devis)
        self.assertIn("Canadien Solar", module.designation)

    def test_devis_mono_option_reseau_seul_inchange(self):
        """Non-régression : un devis classique, un seul onduleur réseau,
        aucune batterie — se comporte exactement comme avant ce correctif."""
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_onduleur_reseau()),
        ], roof_layout=_roof(14))
        onduleur, _phases = es.spec_onduleur_du_devis(devis)
        self.assertIn("Huawei", onduleur.designation)

    def test_devis_mono_option_hybride_batterie_seul_inchange(self):
        """Non-régression : un devis classique hybride + batterie, sans
        onduleur réseau — se comporte exactement comme avant ce correctif."""
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur hybride 15kW triphasé", 1,
                         produit=_onduleur_hybride()),
            _FausseLigne("Batterie lithium 15,4 kWh", 1, produit=_batterie()),
        ], roof_layout=_roof(14))
        onduleur, _phases = es.spec_onduleur_du_devis(devis)
        self.assertIn("Deye", onduleur.designation)


class ChoixBatterieSurDevisDeuxOptionsTest(SimpleTestCase):
    """Le point de choix : ``_batterie_du_devis`` via ``_lignes_option_choisie``."""

    def test_batterie_comptee_avec_option_avec_gagnante(self):
        devis = _devis_deux_options_servables()
        presente, designation, kwh, _v = es._batterie_du_devis(devis)
        self.assertTrue(presente)
        self.assertAlmostEqual(kwh, 15.36)
        self.assertIn("Dyness", designation)

    def test_devis_reseau_seul_sans_batterie_ne_declare_rien(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_onduleur_reseau()),
        ], roof_layout=_roof(14))
        presente, _designation, kwh, _v = es._batterie_du_devis(devis)
        self.assertFalse(presente)
        self.assertEqual(kwh, 0.0)


class SchemaUnifilaireDeuxOptionsTest(SimpleTestCase):
    """Bout en bout : le SVG servi au client ne mélange jamais réseau +
    batterie."""

    def test_le_schema_porte_hybride_et_batterie_jamais_reseau(self):
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        svg = es.rendre_schema_du_devis(devis)
        self.assertIsNotNone(svg)
        self.assertIn("Deye", svg)
        self.assertIn("Dyness", svg)
        self.assertNotIn("Huawei", svg)


class SchemaElectriqueParOptionTest(SimpleTestCase):
    """SCHEL-B3 (lot 6) — UN document par option : « sans » montre l'onduleur
    RÉSEAU sans batterie, « avec » l'hybride ET la batterie ; l'autre option est
    conçue à la lecture, et rien de ce qui est rangé ne bouge (empreinte)."""

    def test_deux_options_deux_documents_jamais_melanges(self):
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        options = es.schema_electrique_du_devis(devis)["options"]
        sans, avec = options["sans_batterie"], options["avec_batterie"]
        self.assertIn("Huawei", sans["onduleurs"][0]["designation"])
        self.assertIsNone(sans["batterie"])
        self.assertIn("Deye", avec["onduleurs"][0]["designation"])
        self.assertEqual(avec["batterie"]["unites"], 1)
        self.assertAlmostEqual(avec["batterie"]["capacite_kwh"], 15.4, places=1)
        self.assertIsNone(avec["batterie"]["protection"])
        for doc in (sans, avec):
            self.assertEqual(doc["source"], "conception_devis")
            self.assertTrue(doc["chaines_reparties"])
            self.assertEqual(sum(c["nb_panneaux"] for c in doc["chaines"]), 30)
            self.assertEqual(doc["onduleurs"][0]["nombre"], 1)

    def test_l_empreinte_et_l_etude_rangees_ne_bougent_pas(self):
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        design, empreinte = devis.electrical_design, devis.electrical_design_hash
        copie = dict(design)
        recalculee = es.empreinte_entree(devis, es.construire_entree(devis))
        self.assertEqual(recalculee, empreinte)
        es.schema_electrique_du_devis(devis)
        es.schema_electrique_du_devis(devis, standard=True)
        self.assertIs(devis.electrical_design, design)
        self.assertEqual(devis.electrical_design, copie)
        self.assertEqual(devis.electrical_design_hash, empreinte)
        # La variante imposée ne fuit pas hors de son bloc : l'option retenue
        # et l'empreinte des entrées sont celles d'avant.
        self.assertEqual(es._option_choisie(devis)[1], "avec")
        self.assertEqual(es.empreinte_entree(devis, es.construire_entree(devis)),
                         empreinte)

    def test_sans_etude_le_champ_sans_decoupage(self):
        """Aucune étude ne répartit les panneaux (fiche onduleur absente) : le
        champ est servi SANS découpage, jamais une répartition inventée."""
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_FauxProduit("Onduleur réseau Huawei 15kW")),
        ], roof_layout=_roof(14))
        doc = es.schema_electrique_du_devis(devis)["options"]["sans_batterie"]
        self.assertEqual(doc["source"], "lignes_devis")
        self.assertFalse(doc["chaines_reparties"])
        self.assertEqual(doc["chaines"], [])
        self.assertEqual(doc["panneaux"]["nombre"], 14)
        self.assertEqual(doc["cote_reseau"]["etat"], "a_calculer")
        self.assertIsNone(devis.electrical_design)

    def test_annexe_dessine_l_option_rangee_et_rien_sans_etude(self):
        """SCHEL-B4 — l'annexe PV46 : l'option rangée (« avec », comme la
        planche d'hier), batterie dessinée ; aucune étude ⇒ aucun schéma."""
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        svg = es.rendre_schema_electrique_du_devis(devis, langue="fr", largeur_px=680)
        self.assertIn('data-schema="electrique"', svg)
        self.assertIn("Deye", svg)
        self.assertIn("Batterie", svg)
        self.assertNotIn("Huawei", svg)
        self.assertIn("Battery", es.rendre_schema_electrique_du_devis(devis, langue="en"))
        sans_etude = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_FauxProduit("Onduleur réseau Huawei 15kW")),
        ], roof_layout=_roof(14))
        self.assertEqual(es.rendre_schema_electrique_du_devis(sans_etude), "")

    def test_pompage_sans_onduleur_aucun_document(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau())],
            roof_layout=_roof(14))
        self.assertEqual(es.schema_electrique_du_devis(devis),
                         {"options": {"sans_batterie": None, "avec_batterie": None},
                          "avis_client": {"sans_batterie": None, "avec_batterie": None}})


_TOTAUX = {"sans_batterie": {"ttc": 1}, "avec_batterie": {"ttc": 1}}


class RevueSchemaElectriqueTest(SimpleTestCase):
    """Revue de la lane B (26/11/2026) — décisions D1/D2/D3 de l'orchestrateur
    (à confirmer) et points 1, 3, 5, 6, 7."""

    def _plan(self, document, designation=None):
        """Un document de calepinage qui porte une seule chaîne de 30 panneaux."""
        from core.electrique.schema_electrique import chaines_colorees
        plan = dict(document, source="calepinage",
                    chaines=chaines_colorees([{"numero": 7, "nb_panneaux": 30, "entree": 1}]))
        if designation is not None:
            plan["onduleurs"] = [dict(plan["onduleurs"][0], designation=designation)]
        return plan

    def _avec_calepinage(self, plan):
        from unittest import mock
        return (mock.patch("apps.calepinage.selectors.calepinage_du_devis", return_value=object()),
                mock.patch("apps.ventes.selectors_calepinage._conception_a_jour", return_value=True),
                mock.patch("apps.calepinage.selectors.schema_electrique_du_calepinage",
                           return_value=plan))

    def test_d1_la_page_client_ne_recoit_que_l_etude_rangee(self):
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        public = es.schema_electrique_public(devis, standard=False, option_totals=_TOTAUX)
        self.assertIsNone(public["options"]["sans_batterie"])       # conçue à la lecture
        avec = public["options"]["avec_batterie"]
        self.assertEqual(avec["source"], "conception_devis")
        self.assertEqual(avec["cote_reseau"], {"etat": "calcule", "motif": None})
        erp = es.schema_electrique_du_devis(devis)["options"]
        self.assertIsNotNone(erp["sans_batterie"])                  # la fiche ERP la garde

    def test_d1_sans_etude_rangee_rien_ne_part_chez_le_client(self):
        devis = _devis_deux_options_servables()                     # aucune étude rangée
        self.assertIsNone(es.schema_electrique_public(devis, standard=False, option_totals=_TOTAUX))
        lignes = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_FauxProduit("Onduleur réseau Huawei 15kW"))], roof_layout=_roof(14))
        self.assertIsNone(es.schema_electrique_public(lignes, standard=False, option_totals=_TOTAUX))

    def test_point3_le_motif_nomme_la_cause_reelle(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_FauxProduit("Onduleur réseau Huawei 15kW"))], roof_layout=_roof(14))
        motif = es.schema_electrique_du_devis(devis)["options"]["sans_batterie"]["cote_reseau"]["motif"]
        self.assertIn("fiche technique du matériel est incomplète", motif)
        self.assertNotIn("aucune étude électrique n'a été faite", motif)

    def test_point5_etude_rangee_d_un_majeur_perime_recalculee_sans_ecriture(self):
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        perimee = dict(devis.electrical_design, version_moteur="0.0.1")
        devis.electrical_design = perimee
        empreinte = devis.electrical_design_hash
        self.assertTrue(es.artefact_a_rejouer(perimee))
        avec = es.schema_electrique_du_devis(devis)["options"]["avec_batterie"]
        self.assertEqual(avec["source"], "conception_devis")        # pas le champ des lignes
        self.assertTrue(avec["chaines_reparties"])
        self.assertIs(devis.electrical_design, perimee)
        self.assertEqual(devis.electrical_design_hash, empreinte)
        public = es.schema_electrique_public(devis, standard=False, option_totals=_TOTAUX)
        self.assertIsNone(public)                                    # D1 : calculée à la lecture

    def test_point6_unites_de_batterie_par_role_ou_fiche_jamais_par_le_mot(self):
        lignes = [_FausseLigne("Câble batterie 35 mm²", 2),
                  _FausseLigne("Batterie lithium 15,4 kWh", 3, produit=_batterie())]
        self.assertEqual(es._quantites_de_l_option(lignes)[0], 3)
        lignes[0].role_devis = "cable_dc"
        self.assertEqual(es._quantites_de_l_option(lignes)[0], 3)

    def test_point1_l_annexe_n_imprime_rien_sans_etude_meme_avec_un_calepinage(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_FauxProduit("Onduleur réseau Huawei 15kW"))], roof_layout=_roof(14))
        doc = es.schema_electrique_du_devis(devis, avec_calepinage=False)["options"]["sans_batterie"]
        a, b, c = self._avec_calepinage(self._plan(dict(doc, onduleurs=doc["onduleurs"])))
        with a, b, c:
            self.assertEqual(es.rendre_schema_electrique_du_devis(devis), "")
            documents = {"sans_batterie": dict(doc), "avec_batterie": None}
            es._chaines_du_calepinage(devis, documents)
        self.assertEqual(documents["sans_batterie"]["source"], "lignes_devis")
        self.assertEqual(documents["sans_batterie"]["chaines"], [])

    def test_d2_chaines_du_calepinage_seulement_au_meme_onduleur(self):
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        avec = es.schema_electrique_du_devis(devis, avec_calepinage=False)["options"]["avec_batterie"]
        for designation, attendu in ((None, "calepinage"), ("Autre onduleur 15 kW", "conception_devis")):
            a, b, c = self._avec_calepinage(self._plan(avec, designation))
            with a, b, c:
                doc = es.schema_electrique_du_devis(devis)["options"]["avec_batterie"]
            self.assertEqual(doc["source"], attendu, designation)
            self.assertEqual(doc["chaines"][0]["numero"] == 7, attendu == "calepinage")

    def test_d3_la_page_client_ne_relit_pas_le_calepinage(self):
        from unittest import mock
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        with mock.patch("apps.calepinage.selectors.calepinage_du_devis",
                        side_effect=AssertionError("calepinage relu à l'affichage")):
            public = es.schema_electrique_public(devis, standard=False, option_totals=_TOTAUX)
        self.assertIsNotNone(public["options"]["avec_batterie"])

    def test_d_acal_158_envoi_range_l_autre_option_et_la_page_montre_les_deux(self):
        """D-ACAL-158 — envoyé : l'option imposée est rangée ; la page client sert
        DEUX documents, chacun avec son onduleur et sa batterie ; l'étude rangée,
        son empreinte et l'annexe PDF (option rangée seule) ne bougent pas."""
        import copy
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        design, empreinte = devis.electrical_design, devis.electrical_design_hash
        avant, annexe = copy.deepcopy(design), es.rendre_schema_electrique_du_devis(devis)
        devis.statut, devis.clauses_appliquees = "envoye", []
        figees = co.figer_conceptions_des_options(devis)
        self.assertEqual(set(figees), {"sans_batterie"})            # « avec » = electrical_design
        self.assertEqual(devis.clauses_appliquees[0]["type"], "conceptions_options_figees")
        from apps.ventes.domain.envoi import est_gel_interne
        self.assertTrue(est_gel_interne(devis.clauses_appliquees[0]))   # jamais imprimée
        self.assertIs(devis.electrical_design, design)
        self.assertEqual(devis.electrical_design, avant)
        self.assertEqual(devis.electrical_design_hash, empreinte)
        self.assertEqual(es.empreinte_entree(devis, es.construire_entree(devis)), empreinte)
        public = es.schema_electrique_public(devis, standard=False, option_totals=_TOTAUX)["options"]
        sans, avec = public["sans_batterie"], public["avec_batterie"]
        self.assertIn("Huawei", sans["onduleurs"][0]["designation"])
        self.assertIsNone(sans["batterie"])
        self.assertIn("Deye", avec["onduleurs"][0]["designation"])
        self.assertEqual(avec["batterie"]["unites"], 1)
        for doc in (sans, avec):
            self.assertEqual(doc["cote_reseau"], {"etat": "calcule", "motif": None})
        self.assertEqual(es.rendre_schema_electrique_du_devis(devis), annexe)
        # Correction sans changement d'entrée : la conception rangée est gardée telle quelle.
        rangee = devis.clauses_appliquees[0]["options"]["sans_batterie"]
        self.assertIs(co.figer_conceptions_des_options(devis, garder=True)["sans_batterie"], rangee)

    def test_d_acal_158_surcharges_de_site_reportees_sur_l_autre_option(self):
        """Revue D-ACAL-158 (1) — le site saisi par le vendeur (régime, longueurs,
        prise de terre) vaut pour les DEUX options ; des températures saisies,
        dont les valeurs ne sont pas rangées, ne fabriquent pas une option sur
        un autre site : elle n'est pas rangée."""
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis, overrides={
            "regime": "TN", "dc_m": 8, "ac_m": 22, "inclure_prise_terre": True})
        self.assertEqual(devis.electrical_design["source_entree"]["regime"], "surcharge")
        devis.statut, devis.clauses_appliquees = "envoye", []
        sans = co.figer_conceptions_des_options(devis)["sans_batterie"]["design"]
        self.assertEqual(sans["parametres"]["regime"], "TN")
        self.assertEqual((sans["parametres"]["dc_m"], sans["parametres"]["ac_m"]), (8.0, 22.0))
        self.assertEqual(sans["source_entree"], devis.electrical_design["source_entree"])
        self.assertIn("T1", {p["repere"] for p in sans["protections"]})
        self.assertEqual(co._surcharges_de_site(devis.electrical_design),
                         {"regime": "TN", "dc_m": 8.0, "ac_m": 22.0, "inclure_prise_terre": True})
        es.build_electrical_design(devis, overrides={"temp_froid_c": -10})
        self.assertEqual(co.figer_conceptions_des_options(devis), {})

    def test_d_acal_158_avis_au_vendeur_pour_l_option_que_le_client_ne_voit_pas(self):
        """Revue D-ACAL-158 (4) — fiche ERP : une phrase par option que la page
        du client ne reçoit pas ; rien sur un brouillon ni sur une option rangée."""
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        devis.statut, devis.clauses_appliquees = "brouillon", []
        self.assertEqual(es.schema_electrique_du_devis(devis)["avis_client"],
                         {"sans_batterie": None, "avec_batterie": None})
        devis.statut = "envoye"                                      # envoyé avant la règle
        self.assertEqual(es.schema_electrique_du_devis(devis)["avis_client"],
                         {"sans_batterie": es.AVIS_OPTION_NON_RANGEE, "avec_batterie": None})
        co.figer_conceptions_des_options(devis)
        self.assertEqual(es.schema_electrique_du_devis(devis)["avis_client"],
                         {"sans_batterie": None, "avec_batterie": None})

    def test_d_acal_158_avis_d_une_conception_rangee_devenue_indessinable(self):
        """Revue 2 (point 3) — une conception EST rangée (l'étude du devis ou celle
        de l'envoi) mais une fiche a changé depuis : la phrase le dit, avec sa
        cause, pour l'option retenue comme pour l'autre ; jamais « aucune
        conception rangée »."""
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        devis.statut, devis.clauses_appliquees = "envoye", []
        co.figer_conceptions_des_options(devis)
        attendu = es.AVIS_CONCEPTION_NON_DESSINABLE % es.CAUSE_FICHE_MODIFIEE
        reseau, hybride = devis.lignes.all()[1].produit, devis.lignes.all()[2].produit
        for produit, cle, autre in ((hybride, "avec_batterie", "sans_batterie"),
                                    (reseau, "sans_batterie", "avec_batterie")):
            fiche = produit.fiche_technique
            produit.fiche_technique = _FausseFiche("onduleur")             # fiche vidée depuis l'envoi
            avis = es.schema_electrique_du_devis(devis)["avis_client"]
            produit.fiche_technique = fiche
            self.assertEqual(avis[cle], attendu, cle)
            self.assertNotEqual(avis[cle], es.AVIS_OPTION_NON_RANGEE)
            self.assertIsNone(avis[autre], cle)

    def test_d_acal_166_annexe_une_page_par_option_rangee_seulement(self):
        """D-ACAL-166 — l'annexe PDF reçoit une entrée par option RANGÉE (sans,
        puis avec), chacune avec SA conception et SON schéma ; sans l'entrée
        rangée à l'envoi, rien (l'annexe d'une page d'aujourd'hui)."""
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        devis.statut, devis.clauses_appliquees = "envoye", []
        self.assertEqual(es.annexes_par_option(devis), [])            # envoyé avant la règle
        co.figer_conceptions_des_options(devis)
        sans, avec = es.annexes_par_option(devis, langue="fr", largeur_px=680)
        self.assertEqual((sans["option"], avec["option"]), ("sans_batterie", "avec_batterie"))
        self.assertIs(avec["electrical_design"], devis.electrical_design)
        self.assertIs(sans["electrical_design"], co._conceptions_figees(devis)["sans_batterie"]["design"])
        self.assertIn("Huawei", sans["sld_svg"])
        self.assertNotIn("Batterie", sans["sld_svg"])
        self.assertIn("Deye", avec["sld_svg"])
        self.assertIn("Batterie", avec["sld_svg"])
        devis.statut = "brouillon"
        self.assertEqual(es.annexes_par_option(devis), [])

    def test_d_acal_158_option_a_un_autre_nombre_de_panneaux_non_rangee(self):
        """Revue D-ACAL-158 (2) — 30 panneaux posés au toit, l'option « sans » en
        vend 20 : son dessin serait celui de 30, elle n'est pas rangée."""
        avec_30, sans_20 = (_FausseLigne("Panneau PV 710 Wc", 30, produit=_panneau()),
                            _FausseLigne("Panneau PV 710 Wc", 20, produit=_panneau()))
        avec_30.variante, sans_20.variante = "avec", "sans"
        devis = _FauxDevis(lignes=[
            avec_30, sans_20,
            _FausseLigne("Onduleur réseau 15kW triphasé", 1, produit=_onduleur_reseau()),
            _FausseLigne("Onduleur hybride 15kW triphasé", 1, produit=_onduleur_hybride()),
            _FausseLigne("Batterie lithium 15,4 kWh", 1, produit=_batterie())], roof_layout=_roof(30))
        es.build_electrical_design(devis)
        devis.statut, devis.clauses_appliquees = "envoye", []
        self.assertEqual(co.figer_conceptions_des_options(devis), {})
        sans_20.quantite = Decimal("30")
        self.assertEqual(set(co.figer_conceptions_des_options(devis)), {"sans_batterie"})

    def test_d_acal_158_envoye_avant_brouillon_et_mono_option_inchanges(self):
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        devis.statut, devis.clauses_appliquees = "envoye", []          # envoyé avant la règle
        avant = es.schema_electrique_public(devis, standard=False, option_totals=_TOTAUX)
        self.assertIsNone(avant["options"]["sans_batterie"])
        es.schema_electrique_du_devis(devis)
        es.rafraichir_conception_electrique_devis(devis)               # correction sur place
        self.assertEqual(devis.clauses_appliquees, [])                 # jamais rétro-rempli
        co.figer_conceptions_des_options(devis)
        devis.statut = "brouillon"                                    # brouillon porteur d'une entrée : ignorée
        self.assertEqual(es.schema_electrique_public(devis, standard=False, option_totals=_TOTAUX), avant)
        mono = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1, produit=_onduleur_reseau())],
            roof_layout=_roof(14))
        es.build_electrical_design(mono)
        mono.statut, mono.clauses_appliquees = "envoye", None
        charge = es.schema_electrique_public(mono, standard=False, option_totals=_TOTAUX)
        self.assertEqual(co.figer_conceptions_des_options(mono), {})
        # Revue 3 — le marqueur « envoyé sous D-ACAL-158 », options vides.
        self.assertEqual(mono.clauses_appliquees,
                         [{"type": "conceptions_options_figees", "options": {}}])
        self.assertEqual(es.schema_electrique_public(mono, standard=False, option_totals=_TOTAUX), charge)

    def test_d_acal_158_un_mono_option_qui_gagne_sa_seconde_option_apres_l_envoi(self):
        """Revue D-ACAL-158 (3) — envoyé à une option (marqueur), corrigé sur place
        en deux options : la seconde est rangée et la page montre les deux."""
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 30, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1, produit=_onduleur_reseau())],
            roof_layout=_roof(30))
        es.build_electrical_design(devis)
        devis.statut, devis.clauses_appliquees = "envoye", []
        co.figer_conceptions_des_options(devis)
        devis.lignes._lignes += [
            _FausseLigne("Onduleur hybride 15kW triphasé", 1, produit=_onduleur_hybride()),
            _FausseLigne("Batterie lithium 15,4 kWh", 1, produit=_batterie())]
        es.rafraichir_conception_electrique_devis(devis)
        self.assertEqual(set(co._conceptions_figees(devis)), {"sans_batterie"})
        public = es.schema_electrique_public(devis, standard=False, option_totals=_TOTAUX)["options"]
        self.assertIsNotNone(public["sans_batterie"])
        self.assertIsNotNone(public["avec_batterie"])

    def test_d_acal_158_option_incalculable_non_rangee_sans_lever(self):
        from unittest import mock
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 30, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_FauxProduit("Onduleur réseau Huawei 15kW")),   # sans fiche
            _FausseLigne("Onduleur hybride 15kW triphasé", 1, produit=_onduleur_hybride()),
            _FausseLigne("Batterie lithium 15,4 kWh", 1, produit=_batterie())], roof_layout=_roof(30))
        es.build_electrical_design(devis)
        devis.statut, devis.clauses_appliquees = "envoye", []
        with self.assertLogs("apps.ventes.electrical_service", level="WARNING"):
            self.assertEqual(co.figer_conceptions_des_options(devis), {})
        self.assertEqual(devis.clauses_appliquees[0]["options"], {})
        public = es.schema_electrique_public(devis, standard=False, option_totals=_TOTAUX)["options"]
        self.assertIsNone(public["sans_batterie"])
        self.assertIsNotNone(public["avec_batterie"])
        with mock.patch("apps.ventes.conceptions_options._conception_de_l_option", side_effect=RuntimeError("panne")):
            self.assertEqual(co.figer_conceptions_des_options(devis), {})

    def test_d_acal_158_chaines_du_calepinage_a_l_option_de_son_onduleur(self):
        """D-ACAL-141 par option : les deux conceptions rangées, le calepinage ne
        remplace que les chaînes de l'option dont l'onduleur est le sien."""
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        devis.statut, devis.clauses_appliquees = "envoye", []
        co.figer_conceptions_des_options(devis)
        options = es.schema_electrique_du_devis(devis, avec_calepinage=False)["options"]
        for cle, autre in (("sans_batterie", "avec_batterie"), ("avec_batterie", "sans_batterie")):
            a, b, c = self._avec_calepinage(self._plan(options[cle]))
            with a, b, c:
                docs = es.schema_electrique_du_devis(devis)["options"]
            self.assertEqual(docs[cle]["source"], "calepinage", cle)
            self.assertEqual(docs[autre]["source"], "conception_devis", cle)

    def test_point7_le_chemin_calepinage_ne_journalise_aucune_erreur(self):
        """Une panne du chemin calepinage ne se cache plus derrière son ``except`` :
        sur un devis sain, AUCUN avertissement n'est journalisé ; et une erreur
        hors des lectures attendues REMONTE."""
        from unittest import mock
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        with self.assertNoLogs("apps.ventes.electrical_service", level="WARNING"):
            es.schema_electrique_du_devis(devis)
        with mock.patch("apps.calepinage.selectors.calepinage_du_devis",
                        side_effect=RuntimeError("chemin cassé")):
            with self.assertRaises(RuntimeError):
                es.schema_electrique_du_devis(devis)


def _envoye_avant_la_coupure(devis):
    """``devis`` envoyé la veille de la coupure « rôle rangé » : il garde les mots-clés."""
    from datetime import date, timedelta

    from apps.ventes.domain.regles_calcul import COUPURE_CLASSE_PAR_ROLE
    devis.statut, devis.regles_calcul = "envoye", 14
    devis.date_envoi = date(*COUPURE_CLASSE_PAR_ROLE) - timedelta(days=1)
    return devis


def _rangee(ligne, produit_id, role=None):
    """La ligne LIÉE à son produit, avec le rôle RANGÉ à son écriture (``role_devis``)."""
    ligne.produit_id, ligne.role_devis = produit_id, role
    return ligne


def _devis_hybride_haute_tension():
    """Cas A en lignes : le 80 kW de Reda et sa batterie BOS-B, aux noms muets,
    RANGÉS hybride / batterie à l'écriture ; des panneaux 715 Wc rangés panneau."""
    fiche_715 = dict(FICHE_CS710, pmax_wc=Decimal("715.00"))
    return _FauxDevis(lignes=[
        _rangee(_FausseLigne("Canadian Solar TOPBiHiKu7 CS7N-715TB", 30, produit=_FauxProduit(
            "Canadian Solar TOPBiHiKu7 CS7N-715TB", marque="Canadian Solar",
            fiche=_FausseFiche("module", **fiche_715))), 1, "panneau"),
        _rangee(_FausseLigne("DEYE SUN-80K-SG02HP3-EU-EM6", 1, produit=_FauxProduit(
            "DEYE SUN-80K-SG02HP3-EU-EM6", marque="Deye", fiche=_FausseFiche(
                "onduleur", ond_bat_max_charge_kw=Decimal("80"), **FICHE_ONDULEUR_HYBRIDE))),
                2, "onduleur_hybride"),
        _rangee(_FausseLigne("Deye BOS-B Pro-A3 16 kWh", 1, produit=_FauxProduit(
            "Deye BOS-B Pro-A3 16 kWh", marque="Deye", fiche=_FausseFiche(
                "batterie", bat_kwh_nominal=Decimal("16.08"), bat_v_nominal=Decimal("51.2")))),
                3, "batterie"),
    ], roof_layout=_roof(30))


class LecteursAvalRoleRangeTest(SimpleTestCase):
    """Lecteurs en aval (fondateur 24/11/2026) — l'étude électrique lit
    l'onduleur, la batterie et le module par le rôle RANGÉ sur la ligne à son
    écriture, puis les mots-clés ; un devis envoyé avant la coupure garde les
    mots-clés, et une empreinte ne bouge pas quand la classe ne change pas."""

    def test_cas_a_hybride_et_batterie_ranges(self):
        devis = _devis_hybride_haute_tension()
        self.assertEqual(es._option_choisie(devis)[1], "avec")
        onduleur, _phases = es.spec_onduleur_du_devis(devis)
        self.assertIn("Deye", onduleur.designation)
        self.assertEqual(onduleur.ac_kw, 15.0)
        self.assertEqual(es.spec_module_du_devis(devis).pmax_wc, 715.0)
        presente, designation, kwh, _v = es._batterie_du_devis(devis)
        self.assertTrue(presente)
        self.assertAlmostEqual(kwh, 16.08)
        self.assertIn("Deye", designation)

    def test_devis_envoye_avant_la_coupure_garde_les_mots_cles(self):
        devis = _envoye_avant_la_coupure(_devis_hybride_haute_tension())
        self.assertEqual(es.spec_module_du_devis(devis).pmax_wc, 0.0)
        self.assertEqual(es.spec_onduleur_du_devis(devis)[0].ac_kw, 0.0)
        self.assertFalse(es._batterie_du_devis(devis)[0])

    def test_le_produit_vivant_n_est_jamais_relu(self):
        """Les mêmes produits (rôle déclaré et fiche) sur des lignes écrites SANS
        rôle : les mots-clés d'hier, comme avant toute retouche du catalogue."""
        devis = _devis_hybride_haute_tension()
        for ligne in devis.lignes.all():
            ligne.produit.role_devis, ligne.role_devis = ligne.role_devis, None
        self.assertFalse(es._batterie_du_devis(devis)[0])
        self.assertEqual(es.spec_module_du_devis(devis).pmax_wc, 0.0)

    def test_empreinte_inchangee_quand_la_classe_ne_change_pas(self):
        """Un devis d'aujourd'hui dont les rôles rangés disent ce que disent les
        noms : la même entrée, donc la même ``electrical_design_hash``, que la
        ligne porte son rôle (ouvert), ne le porte pas, ou que le devis soit
        envoyé avant la coupure."""
        roles = ("panneau", "onduleur_reseau", "onduleur_hybride", "batterie")

        def devis(ranges, ferme=False):
            d = _devis_deux_options_servables()
            if ranges:
                for k, (ligne, role) in enumerate(zip(d.lignes.all(), roles), start=1):
                    _rangee(ligne, k, role)
            return _envoye_avant_la_coupure(d) if ferme else d
        empreintes = {es.empreinte_entree(d, es.construire_entree(d))
                      for d in (devis(False), devis(True), devis(True, ferme=True))}
        self.assertEqual(len(empreintes), 1)
