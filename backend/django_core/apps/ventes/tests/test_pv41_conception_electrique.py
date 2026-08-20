"""PV41 — l'étude électrique persistée du devis.

Trois garanties :

* la sortie est celle du CONTRAT PARTAGÉ
  ``apps/ventes/contract_samples/conception_electrique.json`` — comparée AU
  FICHIER, jamais à une liste retapée (PACT10/PACT13 : un exemple retapé est
  une deuxième source de vérité, c'est-à-dire l'incident du 03/08/2026) ;
* recalculer aux MÊMES entrées n'écrit rien (idempotence par empreinte, QJ17) ;
* les surcharges font l'aller-retour et ne touchent ni statut, ni ligne, ni
  prix (règle #4).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv41_conception_electrique -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import electrical_service as es
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / "contract_samples"
     / "conception_electrique.json").read_text(encoding="utf-8"))
CLES_CONTRAT = set(CONTRAT["exemple"])

# Prix SENTINELLES du montage d'endpoint. ``test_aucun_prix_dans_la_reponse``
# cherche ces nombres TELS QUELS dans la réponse : ils doivent donc être
# impossibles à confondre avec une grandeur ÉLECTRIQUE. Le montage précédent
# achetait le panneau 600 MAD — soit exactement la « tension maximale onduleur
# 600,0 V » que la note de calcul écrit en toutes lettres : la garde se
# déclenchait sur sa propre physique, jamais sur une fuite de prix. Ces quatre
# valeurs n'apparaissent dans AUCUNE tension, intensité, section ni longueur.
PRIX_PANNEAU_VENTE = Decimal("314159")
PRIX_PANNEAU_ACHAT = Decimal("271828")
PRIX_ONDULEUR_VENTE = Decimal("161803")
PRIX_ONDULEUR_ACHAT = Decimal("141421")


class _FausseLigne:
    def __init__(self, designation, quantite=1, produit=None):
        self.designation = designation
        self.quantite = Decimal(str(quantite))
        self.produit = produit
        self.produit_id = getattr(produit, 'id', None)
        self.prix_unitaire = Decimal("0")
        self.groupe_index = 0
        self.remise_pct = Decimal("0")
        self.taux_tva = Decimal("20")


class _FaussesLignes:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return list(self._lignes)


class _FauxDevis:
    """Devis DUCK-TYPÉ — le service ne lit que ces attributs (calcul pur)."""

    pk = None

    def __init__(self, lignes=(), roof_layout=None, layout_hash=""):
        self.lignes = _FaussesLignes(lignes)
        self.roof_layout = roof_layout
        self.layout_hash = layout_hash
        self.electrical_design = None
        self.electrical_design_hash = None


# ── PVFCH (fondateur 20/08/2026) — « never invent numbers » ─────────────────
# Le montage portait jusqu'ici des lignes NUES (« Onduleur réseau 10 kW
# triphasé ») et le service comblait tout le reste avec les défauts de marché
# de ``solar_design`` : ces tests VALIDAIENT donc l'invention. Ils montent
# désormais de VRAIES fiches techniques — ``specs_for_produit`` ne fait que des
# ``getattr``, aucune base n'est nécessaire.
#
# Les valeurs sont celles du catalogue seedé (Canadian Solar TOPHiKu7 710 Wc et
# un onduleur triphasé 10 kW), pour que le montage ressemble à la production.
class _FausseFiche:
    def __init__(self, type_fiche, **champs):
        self.type_fiche = type_fiche
        for cle, valeur in champs.items():
            setattr(self, cle, valeur)


class _FauxProduit:
    def __init__(self, nom, fiche=None, marque="", description="",
                 garantie=""):
        self.id = None
        self.nom = nom
        self.marque = marque
        self.description = description
        self.garantie = garantie
        self.fiche_technique = fiche


def _produit_panneau():
    return _FauxProduit("Panneau PV 710 Wc mono", marque="Canadien Solar",
                        fiche=_FausseFiche(
                            "module",
                            pmax_wc=Decimal("710.00"),
                            voc_v=Decimal("48.30"),
                            isc_a=Decimal("18.59"),
                            vmp_v=Decimal("40.40"),
                            imp_a=Decimal("17.59"),
                            temp_coeff_voc_pct_c=Decimal("-0.250"),
                            temp_coeff_pmax_pct_c=Decimal("-0.290"),
                            longueur_mm=2384, largeur_mm=1303))


def _produit_onduleur(phases=3, ac_kw="10.00"):
    return _FauxProduit("Onduleur réseau 10 kW", marque="Huawei",
                        fiche=_FausseFiche(
                            "onduleur",
                            ond_ac_kw=Decimal(ac_kw),
                            ond_phases=phases,
                            ond_n_mppt=2,
                            ond_mppt_v_min=Decimal("200.0"),
                            ond_mppt_v_max=Decimal("950.0"),
                            ond_v_max_abs=Decimal("1100.0"),
                            ond_i_max_mppt_a=Decimal("26.0"),
                            ond_rendement_euro_pct=Decimal("98.0"),
                            ond_v_demarrage_v=None,
                            ond_isc_max_mppt_a=None,
                            ond_bat_aucune=True,
                            ond_bat_v_min=None, ond_bat_v_max=None))


def _devis_villa():
    return _FauxDevis(
        lignes=[
            _FausseLigne("Panneau PV 710 Wc mono", 24,
                         produit=_produit_panneau()),
            _FausseLigne("Onduleur réseau 10 kW triphasé", 1,
                         produit=_produit_onduleur()),
        ],
        roof_layout={"_pans_geometry": [
            {"label": "Sud", "nb_panneaux": 16, "azimut_deg": 180,
             "inclinaison_deg": 25},
            {"label": "Est", "nb_panneaux": 8, "azimut_deg": 90,
             "inclinaison_deg": 25},
        ]},
        layout_hash="abc123")


class ContratConceptionElectriqueTest(SimpleTestCase):
    """Le service rend EXACTEMENT les clés du contrat committé."""

    def test_cles_de_premier_niveau(self):
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(set(design), CLES_CONTRAT)

    def test_cles_imbriquees(self):
        exemple = CONTRAT["exemple"]
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(set(design["conformite"]),
                         set(exemple["conformite"]))
        self.assertEqual(set(design["parametres"]),
                         set(exemple["parametres"]))
        for clef in ("chaines", "protections", "cables", "bom"):
            attendues = set(exemple[clef][0])
            self.assertTrue(design[clef], "%s ne doit pas être vide" % clef)
            for element in design[clef]:
                self.assertEqual(set(element), attendues, clef)

    def test_toutes_les_cles_meme_sans_donnees(self):
        # Devis vide : les listes valent [], jamais une clé absente — l'écran
        # ne peut pas .map() sur undefined.
        design = es.build_electrical_design(_FauxDevis())
        self.assertEqual(set(design), CLES_CONTRAT)
        for clef in ("chaines", "protections", "cables", "bom"):
            self.assertEqual(design[clef], [])
        self.assertEqual(design["conformite"]["bloquants"], [])
        # La NOTE DE CALCUL, elle, existe toujours : elle DIT pourquoi le
        # dossier est vide plutôt que de rendre une page blanche.
        self.assertTrue(design["note"])
        self.assertIn("aucun module à répartir",
                      " ".join(design["conformite"]["alertes"]))

    def test_pans_deviennent_des_groupes_distincts(self):
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(sorted({c["pan"] for c in design["chaines"]}), [1, 2])
        self.assertEqual(sum(c["nb_modules"] for c in design["chaines"]), 24)

    def test_repli_sur_les_lignes_sans_calepinage(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc mono", 12,
                         produit=_produit_panneau()),
            _FausseLigne("Onduleur réseau 6 kW", 1,
                         produit=_produit_onduleur(ac_kw="6.00")),
        ])
        design = es.build_electrical_design(devis)
        self.assertEqual(sum(c["nb_modules"] for c in design["chaines"]), 12)
        self.assertEqual({c["pan"] for c in design["chaines"]}, {1})

    def test_aucun_prix_dans_la_sortie(self):
        blob = json.dumps(es.build_electrical_design(_devis_villa()),
                          ensure_ascii=False).lower()
        for interdit in ("prix", "prix_achat", "marge", "montant", "mad"):
            self.assertNotIn(interdit, blob)

    def test_longueur_dc_par_defaut_est_le_forfait_par_paire(self):
        """F2 (fondateur 19/08/2026) : forfait fixe, indépendant du nombre de
        chaînes — seul le nombre de PAIRES MPPT (core.electrique.cables) suit
        les chaînes, pas la longueur elle-même."""
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(design["parametres"]["dc_m"], es.DC_M_PAR_DEFAUT)
        self.assertEqual(design["parametres"]["ac_m"], es.AC_M_DEFAUT)

    def test_longueur_dc_par_defaut_ne_bouge_pas_avec_le_devis(self):
        villa = es.build_electrical_design(_devis_villa())
        petit = es.build_electrical_design(_FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc mono", 4,
                         produit=_produit_panneau()),
            _FausseLigne("Onduleur réseau 3 kW", 1,
                         produit=_produit_onduleur(ac_kw="3.00")),
        ]))
        self.assertEqual(villa["parametres"]["dc_m"],
                         petit["parametres"]["dc_m"])

    def test_phases_lues_sur_la_fiche(self):
        """PVFCH — les phases viennent de ``FicheTechnique.ond_phases``.

        La regex historique sur le LIBELLÉ est supprimée : elle retombait en
        monophasé dès que le mot « triphasé » manquait à la ligne, divisant
        tout le courant AC par √3 sans le dire.
        """
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(design["parametres"]["phases"], 3)
        self.assertEqual(design["parametres"]["regime"], "TT")

    def test_phases_monophase_de_la_fiche_malgre_un_libelle_muet(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc mono", 8,
                         produit=_produit_panneau()),
            # Le libellé ne dit RIEN des phases : seule la fiche tranche.
            _FausseLigne("Onduleur réseau 5 kW", 1,
                         produit=_produit_onduleur(phases=1, ac_kw="5.00")),
        ])
        design = es.build_electrical_design(devis)
        self.assertEqual(design["parametres"]["phases"], 1)


class FicheIncompleteTest(SimpleTestCase):
    """PVFCH (fondateur 20/08/2026) — « never invent numbers ».

    Une variable d'ÉQUIPEMENT vient de la fiche technique, ou le calcul REFUSE
    en nommant le champ manquant. Aucun défaut de marché, aucune regex sur le
    libellé de la ligne, aucune valeur déduite d'une autre.
    """

    def _devis_sans_fiche(self):
        return _FauxDevis(
            lignes=[
                _FausseLigne("Panneau PV 550 Wc mono", 24),
                _FausseLigne("Onduleur réseau 10 kW triphasé", 1),
            ],
            roof_layout={"_pans_geometry": [
                {"label": "Sud", "nb_panneaux": 24, "azimut_deg": 180,
                 "inclinaison_deg": 25}]},
            layout_hash="sansfiche")

    def test_sans_fiche_aucun_nombre_calcule(self):
        design = es.build_electrical_design(self._devis_sans_fiche())
        # La FORME du contrat reste entière (l'écran ne .map() jamais sur
        # undefined) — mais elle ne porte AUCUN nombre fabriqué.
        self.assertEqual(set(design), CLES_CONTRAT)
        for clef in ("chaines", "protections", "cables", "bom"):
            self.assertEqual(design[clef], [], clef)
        self.assertIsNone(design["ratio_dc_ac"])
        self.assertIsNone(design["ratio_ac_dc"])

    def test_sans_fiche_le_refus_nomme_les_champs_manquants(self):
        design = es.build_electrical_design(self._devis_sans_fiche())
        self.assertFalse(design["conformite"]["conforme"])
        motifs = " ".join(design["conformite"]["bloquants"])
        # Le fondateur doit lire le NOM DU CHAMP à remplir, pas « données
        # insuffisantes » — et l'écran où le remplir.
        for attendu in ("plage MPPT — tension mini (V)",
                        "tension DC maximale (V)",
                        "nombre d'entrées MPPT",
                        "courant court-circuit — Isc (A)",
                        "puissance crête (Wc)",
                        "Stock → Catalogue"):
            self.assertIn(attendu, motifs)

    def test_une_seule_variable_manquante_suffit_a_refuser(self):
        """Le verrou est PAR VARIABLE : une fiche à 99 % refuse quand même."""
        onduleur = _produit_onduleur()
        onduleur.fiche_technique.ond_v_max_abs = None   # la borne BLOQUANTE
        devis = _FauxDevis(
            lignes=[
                _FausseLigne("Panneau PV 710 Wc mono", 12,
                             produit=_produit_panneau()),
                _FausseLigne("Onduleur réseau 10 kW", 1, produit=onduleur),
            ],
            roof_layout={"_pans_geometry": [
                {"label": "Sud", "nb_panneaux": 12, "azimut_deg": 180,
                 "inclinaison_deg": 25}]})
        design = es.build_electrical_design(devis)
        self.assertEqual(design["chaines"], [])
        motifs = " ".join(design["conformite"]["bloquants"])
        self.assertIn("tension DC maximale (V)", motifs)
        # …et RIEN d'autre ne doit être réclamé : les 6 autres variables de
        # l'onduleur et les 7 du panneau sont bien lues sur la fiche.
        self.assertEqual(len(design["conformite"]["bloquants"]), 1)

    def test_un_refus_n_est_pas_une_etude_et_ne_se_persiste_pas(self):
        """Le refus ne doit pas se faire passer pour une étude faite.

        ``Devis.electrical_design`` reste ``None`` : c'est lui qui déclenche
        l'annexe technique du PDF et le bloc public. Le persister ferait sortir
        une annexe portant l'esquisse HISTORIQUE (repli du builder) au-dessus
        d'une nomenclature VIDE — un document d'aspect officiel bâti sur rien.
        """
        devis = self._devis_sans_fiche()
        design = es.build_electrical_design(devis)
        self.assertTrue(design["conformite"]["bloquants"])
        self.assertIsNone(devis.electrical_design)
        self.assertIsNone(devis.electrical_design_hash)

    def test_aucun_schema_unifilaire_sans_fiche(self):
        """Un schéma remis au gestionnaire de réseau ne se dessine JAMAIS avec
        une tension maximale ou un Isc supposés."""
        devis = self._devis_sans_fiche()
        es.build_electrical_design(devis)
        self.assertIsNone(es.rendre_schema_du_devis(devis))

    def test_schema_rendu_quand_la_fiche_est_complete(self):
        devis = _devis_villa()
        es.build_electrical_design(devis)
        svg = es.rendre_schema_du_devis(devis)
        self.assertTrue(svg and svg.lstrip().startswith("<svg"))

    def test_fiche_complete_ne_manque_de_rien(self):
        self.assertEqual(es.fiches_manquantes_du_devis(_devis_villa()), [])
        self.assertEqual(es.motifs_fiche_incomplete(_devis_villa()), [])

    def test_devis_sans_materiel_ne_reclame_aucune_fiche(self):
        """Un devis VIDE n'a pas une fiche incomplète : il n'a pas de matériel.
        C'est « aucun module à répartir », que le moteur dit déjà lui-même."""
        self.assertEqual(es.fiches_manquantes_du_devis(_FauxDevis()), [])

    def test_aucun_defaut_de_marche_ne_subsiste_dans_les_specs(self):
        """Garde ANTI-RETOUR : les défauts de ``solar_design`` (450 Wc, 34 V,
        41 V, 2 MPPT, 120-500 V, 600 V, 90 V) ne doivent plus JAMAIS traverser
        ce module. Un futur repli « bien intentionné » rallume ce test."""
        devis = self._devis_sans_fiche()
        module = es.spec_module_du_devis(devis)
        onduleur, phases = es.spec_onduleur_du_devis(devis)
        for valeur in (module.pmax_wc, module.vmp_v, module.voc_v,
                       module.isc_a, module.imp_a,
                       module.temp_coeff_voc_pct_c,
                       module.temp_coeff_pmax_pct_c,
                       onduleur.n_mppt, onduleur.mppt_v_min,
                       onduleur.mppt_v_max, onduleur.v_max_abs,
                       onduleur.i_max_mppt_a, onduleur.ac_kw, phases):
            self.assertEqual(valeur, 0)
        # Isc/Imp ne sont plus DÉDUITS l'un de l'autre ni de Pmax/Vmp.
        self.assertEqual(module.isc_a, 0.0)


class SurchargesTest(SimpleTestCase):
    def test_aller_retour_des_surcharges(self):
        design = es.build_electrical_design(
            _devis_villa(),
            overrides={"dc_m": 42.5, "ac_m": 7.0, "phases": 1,
                       "regime": "TN"})
        self.assertEqual(design["parametres"],
                         {"dc_m": 42.5, "ac_m": 7.0, "phases": 1,
                          "regime": "TN"})

    def test_surcharge_inconnue_ignoree_sans_erreur(self):
        design = es.build_electrical_design(
            _devis_villa(), overrides={"prix_achat": 999, "n_importe": "quoi"})
        self.assertEqual(set(design), CLES_CONTRAT)

    def test_regime_invalide_retombe_sur_tt(self):
        design = es.build_electrical_design(
            _devis_villa(), overrides={"regime": "ZZ"})
        self.assertEqual(design["parametres"]["regime"], "TT")

    def test_longueur_de_chaine_imposee_hors_plage_est_bloquante(self):
        design = es.build_electrical_design(
            _devis_villa(), overrides={"longueur_chaine_forcee": 99})
        self.assertFalse(design["conformite"]["conforme"])
        self.assertTrue(design["conformite"]["bloquants"])

    def test_empreinte_change_avec_les_entrees(self):
        devis = _devis_villa()
        entree = es.construire_entree(devis)
        autre = es.construire_entree(devis, {"ac_m": 99.0})
        self.assertNotEqual(es.empreinte_entree(devis, entree),
                            es.empreinte_entree(devis, autre))
        # Deux constructions identiques → MÊME empreinte (aucun horodatage).
        self.assertEqual(
            es.empreinte_entree(devis, es.construire_entree(devis)),
            es.empreinte_entree(devis, entree))


class ConceptionElectriqueEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv41-acme")
        self.other = Company.objects.create(nom="Autre", slug="pv41-autre")
        self.user = User.objects.create_user(
            username="pv41_resp", password="x",
            role_legacy="responsable", company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV41", email="pv41@example.com")

    def _make_devis(self, company):
        devis = Devis.objects.create(
            company=company, reference="DV-PV41-%s" % company.id,
            client=self.crm_client,
            roof_layout={"_pans_geometry": [
                {"label": "Sud", "nb_panneaux": 20, "azimut_deg": 180,
                 "inclinaison_deg": 20}]},
            layout_hash="h-%s" % company.id)
        panneau = Produit.objects.create(
            company=company, nom="Panneau PV 550W mono",
            sku="PV41-PV-%s" % company.id, prix_vente=PRIX_PANNEAU_VENTE,
            prix_achat=PRIX_PANNEAU_ACHAT, quantite_stock=100)
        onduleur = Produit.objects.create(
            company=company, nom="Onduleur réseau 10kW triphasé",
            sku="PV41-OND-%s" % company.id, prix_vente=PRIX_ONDULEUR_VENTE,
            prix_achat=PRIX_ONDULEUR_ACHAT, quantite_stock=10)
        # PVFCH — les deux fiches techniques : sans elles le service REFUSE de
        # calculer (« never invent numbers »), et l'endpoint ne testerait plus
        # que le chemin de refus.
        FicheTechnique.objects.create(
            company=company, produit=panneau, type_fiche="module",
            pmax_wc=Decimal("550.00"), voc_v=Decimal("49.90"),
            isc_a=Decimal("14.02"), vmp_v=Decimal("41.80"),
            imp_a=Decimal("13.16"),
            temp_coeff_voc_pct_c=Decimal("-0.270"),
            temp_coeff_pmax_pct_c=Decimal("-0.350"))
        FicheTechnique.objects.create(
            company=company, produit=onduleur, type_fiche="onduleur",
            ond_ac_kw=Decimal("10.00"), ond_phases=3, ond_n_mppt=2,
            ond_mppt_v_min=Decimal("200.0"), ond_mppt_v_max=Decimal("950.0"),
            ond_v_max_abs=Decimal("1100.0"),
            ond_i_max_mppt_a=Decimal("26.0"),
            ond_rendement_euro_pct=Decimal("98.0"), ond_bat_aucune=True)
        LigneDevis.objects.create(
            devis=devis, produit=panneau, designation="Panneau PV 550W mono",
            quantite=20, prix_unitaire=PRIX_PANNEAU_VENTE)
        LigneDevis.objects.create(
            devis=devis, produit=onduleur,
            designation="Onduleur réseau 10kW triphasé",
            quantite=1, prix_unitaire=PRIX_ONDULEUR_VENTE)
        return devis

    def _url(self, devis):
        return ("/api/django/ventes/devis/%s/conception-electrique/"
                % devis.id)

    def test_get_calcule_puis_persiste(self):
        devis = self._make_devis(self.company)
        self.assertIsNone(devis.electrical_design)
        resp = self.api.get(self._url(devis))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.data), CLES_CONTRAT)
        devis.refresh_from_db()
        self.assertIsInstance(devis.electrical_design, dict)
        self.assertEqual(len(devis.electrical_design_hash), 64)

    def test_get_idempotent_par_empreinte(self):
        devis = self._make_devis(self.company)
        self.api.get(self._url(devis))
        devis.refresh_from_db()
        empreinte = devis.electrical_design_hash
        design = dict(devis.electrical_design)
        # Marqueur : si le second appel RÉÉCRIT, il disparaît.
        devis.electrical_design = {**design, "_temoin": True}
        devis.save(update_fields=["electrical_design"])

        resp = self.api.post(self._url(devis), {}, format="json")
        self.assertEqual(resp.status_code, 200)
        devis.refresh_from_db()
        self.assertEqual(devis.electrical_design_hash, empreinte)
        self.assertTrue(devis.electrical_design.get("_temoin"))

    def test_post_avec_surcharges_recalcule(self):
        devis = self._make_devis(self.company)
        self.api.get(self._url(devis))
        devis.refresh_from_db()
        empreinte = devis.electrical_design_hash

        resp = self.api.post(self._url(devis), {"ac_m": 33.0},
                             format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["parametres"]["ac_m"], 33.0)
        devis.refresh_from_db()
        self.assertNotEqual(devis.electrical_design_hash, empreinte)

    def test_ne_touche_ni_statut_ni_lignes(self):
        devis = self._make_devis(self.company)
        statut, nb_lignes = devis.statut, devis.lignes.count()
        self.api.post(self._url(devis), {"phases": 1}, format="json")
        devis.refresh_from_db()
        self.assertEqual(devis.statut, statut)
        self.assertEqual(devis.lignes.count(), nb_lignes)

    def test_scope_societe(self):
        devis = self._make_devis(self.other)
        resp = self.api.get(self._url(devis))
        self.assertEqual(resp.status_code, 404)

    def test_role_insuffisant_refuse(self):
        devis = self._make_devis(self.company)
        technicien = User.objects.create_user(
            username="pv41_tech", password="x", role_legacy="technicien",
            company=self.company)
        api = APIClient()
        api.force_authenticate(technicien)
        resp = api.get(self._url(devis))
        self.assertIn(resp.status_code, (401, 403))

    def test_aucun_prix_dans_la_reponse(self):
        devis = self._make_devis(self.company)
        resp = self.api.get(self._url(devis))
        blob = json.dumps(resp.data, ensure_ascii=False, default=str).lower()
        interdits = ["prix", "marge"] + [
            str(int(montant)) for montant in (
                PRIX_PANNEAU_VENTE, PRIX_PANNEAU_ACHAT,
                PRIX_ONDULEUR_VENTE, PRIX_ONDULEUR_ACHAT)]
        for interdit in interdits:
            self.assertNotIn(interdit, blob)
