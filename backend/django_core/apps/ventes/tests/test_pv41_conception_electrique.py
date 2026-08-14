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
from apps.stock.models import Produit
from apps.ventes import electrical_service as es
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / "contract_samples"
     / "conception_electrique.json").read_text(encoding="utf-8"))
CLES_CONTRAT = set(CONTRAT["exemple"])


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


def _devis_villa():
    return _FauxDevis(
        lignes=[
            _FausseLigne("Panneau PV 550 Wc mono", 24),
            _FausseLigne("Onduleur réseau 10 kW triphasé", 1),
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
            _FausseLigne("Panneau PV 550 Wc mono", 12),
            _FausseLigne("Onduleur réseau 6 kW", 1),
        ])
        design = es.build_electrical_design(devis)
        self.assertEqual(sum(c["nb_modules"] for c in design["chaines"]), 12)
        self.assertEqual({c["pan"] for c in design["chaines"]}, {1})

    def test_aucun_prix_dans_la_sortie(self):
        blob = json.dumps(es.build_electrical_design(_devis_villa()),
                          ensure_ascii=False).lower()
        for interdit in ("prix", "prix_achat", "marge", "montant", "mad"):
            self.assertNotIn(interdit, blob)

    def test_longueurs_par_defaut_depuis_le_nombre_de_chaines(self):
        design = es.build_electrical_design(_devis_villa())
        nb_chaines = len(design["chaines"])
        self.assertEqual(design["parametres"]["dc_m"],
                         max(es.DC_M_MINIMUM, nb_chaines * es.DC_M_PAR_CHAINE))
        self.assertEqual(design["parametres"]["ac_m"], es.AC_M_DEFAUT)

    def test_triphase_lu_dans_le_libelle(self):
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(design["parametres"]["phases"], 3)
        self.assertEqual(design["parametres"]["regime"], "TT")


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
            sku="PV41-PV-%s" % company.id, prix_vente=Decimal("1000"),
            prix_achat=Decimal("600"), quantite_stock=100)
        onduleur = Produit.objects.create(
            company=company, nom="Onduleur réseau 10kW triphasé",
            sku="PV41-OND-%s" % company.id, prix_vente=Decimal("12000"),
            prix_achat=Decimal("9000"), quantite_stock=10)
        LigneDevis.objects.create(
            devis=devis, produit=panneau, designation="Panneau PV 550W mono",
            quantite=20, prix_unitaire=Decimal("1000"))
        LigneDevis.objects.create(
            devis=devis, produit=onduleur,
            designation="Onduleur réseau 10kW triphasé",
            quantite=1, prix_unitaire=Decimal("12000"))
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
        for interdit in ("prix", "marge", "12000", "600"):
            self.assertNotIn(interdit, blob)
