"""SCA31 — Tests de ``LigneDocumentMetier`` + ``TotauxDocumentMixin``.

Prouve que les abstraits factorisés produisent EXACTEMENT les mêmes calculs que
le motif existant ``ventes.LigneDevis`` (non-régression du money-path) :

  (a) ``LigneDocumentMetier.total_ht`` == ``quantite × prix_unitaire ×
      (1 − remise/100)``, sémantique Decimal MIROIR de ``LigneDevis.total_ht``
      (aucun quantize — l'arrondi reste à l'agrégat) ;
  (b) ``taux_tva_effectif`` retombe sur le taux du PARENT quand la ligne est
      NULL (contrat de ``LigneDevis.taux_tva_effectif``) ;
  (c) ``TotauxDocumentMixin`` : montants GELÉS priment, sinon recompute depuis
      les lignes (patron ``ventes.Facture.total_ht/total_tva/total_ttc``) ;
  (d) zéro modèle existant modifié (les 5 copies ne bougent pas — vérifié par le
      fait que ce module n'importe QUE les abstraits du kit).

Modèles JETABLES (``app_label='core'``, tables créées via ``schema_editor``,
jamais vus par ``makemigrations``) : un document + sa ligne, pour exercer la
composition parent↔ligne.
"""
from decimal import Decimal

from django.db import connection, models
from django.test import TestCase

from authentication.models import Company
from core.documents import (
    DocumentMetier,
    LigneDocumentMetier,
    TotauxDocumentMixin,
)


# ── Document + ligne JETABLES ─────────────────────────────────────────────────
class DocTotaux(TotauxDocumentMixin, DocumentMetier):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"

    TRANSITIONS = {"brouillon": set()}
    LIGNES_ATTR = "lignes"

    reference = models.CharField(max_length=64, blank=True, default="")
    # Taux du document (repli du taux de ligne), comme Devis.taux_tva.
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=20)

    class Meta:
        app_label = "core"


class LigneTotaux(LigneDocumentMetier):
    PARENT_FIELD = "document"
    document = models.ForeignKey(
        DocTotaux, on_delete=models.CASCADE, related_name="lignes")

    class Meta:
        app_label = "core"


class _KitTablesMixin:
    MODELS = (DocTotaux, LigneTotaux)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as schema:
            for m in cls.MODELS:
                schema.create_model(m)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as schema:
            for m in reversed(cls.MODELS):
                schema.delete_model(m)
        super().tearDownClass()


class LigneTotalHtSemanticsTests(TestCase):
    """``total_ht`` : miroir EXACT de ``LigneDevis.total_ht`` (aucune table)."""

    def _ligne(self, q, pu, remise=0, taux=None):
        return LigneTotaux(
            designation="x", quantite=Decimal(str(q)),
            prix_unitaire=Decimal(str(pu)), remise=Decimal(str(remise)),
            taux_tva=None if taux is None else Decimal(str(taux)))

    def test_total_ht_sans_remise(self):
        ligne = self._ligne("3", "100.00")
        self.assertEqual(ligne.total_ht, Decimal("300.00"))

    def test_total_ht_avec_remise(self):
        # 2 × 150 × (1 − 10/100) = 270.
        ligne = self._ligne("2", "150.00", remise="10")
        self.assertEqual(ligne.total_ht, Decimal("270.0000"))

    def test_total_ht_identique_a_la_formule_ligne_devis(self):
        # Réplique la formule ventes.LigneDevis.total_ht au bit près :
        # quantite * prix_unitaire * (1 - remise/100), sans quantize.
        q, pu, r = Decimal("1.5"), Decimal("99.99"), Decimal("7.5")
        attendu = q * pu * (1 - r / 100)
        ligne = self._ligne("1.5", "99.99", remise="7.5")
        self.assertEqual(ligne.total_ht, attendu)

    def test_taux_tva_effectif_utilise_la_ligne_si_presente(self):
        doc = DocTotaux(taux_tva=Decimal("20"))
        ligne = self._ligne("1", "100", taux="10")
        ligne.document = doc
        self.assertEqual(ligne.taux_tva_effectif, Decimal("10"))

    def test_taux_tva_effectif_retombe_sur_le_parent_si_null(self):
        doc = DocTotaux(taux_tva=Decimal("20"))
        ligne = self._ligne("1", "100", taux=None)
        ligne.document = doc
        # NULL sur la ligne → taux du document (contrat LigneDevis).
        self.assertEqual(ligne.taux_tva_effectif, Decimal("20"))


class TotauxMixinFrozenAndFallbackTests(_KitTablesMixin, TestCase):
    """Montants gelés priment, sinon recompute depuis les lignes (patron Facture)."""

    def setUp(self):
        self.company = Company.objects.create(nom="SCA31 Test SARL")

    def _doc(self, **kw):
        return DocTotaux.objects.create(
            company=self.company, reference="MDOC-0001", **kw)

    def test_recompute_depuis_les_lignes_quand_non_gele(self):
        doc = self._doc(taux_tva=Decimal("20"))
        LigneTotaux.objects.create(
            document=doc, designation="a", quantite=Decimal("2"),
            prix_unitaire=Decimal("100"), remise=Decimal("0"))
        LigneTotaux.objects.create(
            document=doc, designation="b", quantite=Decimal("1"),
            prix_unitaire=Decimal("50"), remise=Decimal("0"))
        # HT = 200 + 50 = 250 ; TVA @20% = 50 ; TTC = 300.
        self.assertEqual(doc.total_ht, Decimal("250"))
        self.assertEqual(doc.total_tva, Decimal("50.00"))
        self.assertEqual(doc.total_ttc, Decimal("300.00"))

    def test_taux_par_ligne_applique_en_repli(self):
        doc = self._doc(taux_tva=Decimal("20"))
        # Ligne 1 : taux ligne 10 % ; Ligne 2 : NULL → 20 % du document.
        LigneTotaux.objects.create(
            document=doc, designation="pv", quantite=Decimal("1"),
            prix_unitaire=Decimal("100"), remise=Decimal("0"),
            taux_tva=Decimal("10"))
        LigneTotaux.objects.create(
            document=doc, designation="autre", quantite=Decimal("1"),
            prix_unitaire=Decimal("100"), remise=Decimal("0"), taux_tva=None)
        # TVA = 100×10% + 100×20% = 10 + 20 = 30.
        self.assertEqual(doc.total_ht, Decimal("200"))
        self.assertEqual(doc.total_tva, Decimal("30.00"))

    def test_montants_geles_priment_sur_les_lignes(self):
        # Montants figés (acompte/tranche) : priment, les lignes sont ignorées.
        doc = self._doc(
            montant_ht=Decimal("1000.00"), montant_tva=Decimal("200.00"),
            montant_ttc=Decimal("1200.00"))
        LigneTotaux.objects.create(
            document=doc, designation="ignoree", quantite=Decimal("9"),
            prix_unitaire=Decimal("9"), remise=Decimal("0"))
        self.assertEqual(doc.total_ht, Decimal("1000.00"))
        self.assertEqual(doc.total_tva, Decimal("200.00"))
        self.assertEqual(doc.total_ttc, Decimal("1200.00"))

    def test_document_sans_ligne_totaux_a_zero(self):
        doc = self._doc(taux_tva=Decimal("20"))
        self.assertEqual(doc.total_ht, Decimal("0"))
        self.assertEqual(doc.total_tva, Decimal("0"))
        self.assertEqual(doc.total_ttc, Decimal("0"))
