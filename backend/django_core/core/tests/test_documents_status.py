"""SCA30 — Tests du bundle abstrait ``DocumentMetier`` (statut + transitions).

Couvre :
  (a) ``DocumentMetier`` est ABSTRAIT (aucune table) et hérite ARC1
      (``TenantModel`` : FK ``company`` + timestamps) ;
  (b) le champ ``statut`` d'un document CONCRET s'adosse à SON ``Statut``
      (choices/default dérivés de la sous-classe) ;
  (c) ``transitions_permises`` / ``transition_permise`` lisent la table
      ``TRANSITIONS`` déclarative (jamais une transition hardcodée) ;
  (d) ``changer_statut`` : transition PERMISE (mute + persiste), transition
      REFUSÉE (``TransitionRefusee``, aucune écriture), ÉVÉNEMENT bus émis
      (``core.events.document_statut_change``) avec ancien/nouveau/user/company.

Modèle de test JETABLE : ``core`` n'a aucun modèle concret (aucune migration) —
on déclare un document concret ``app_label='core'`` UNIQUEMENT dans ce module de
test (jamais vu par ``makemigrations``, qui n'importe que ``core.models``) et on
crée/détruit sa table via ``schema_editor`` autour de la classe de test. C'est
le patron Django natif pour tester un modèle abstrait sans polluer les
migrations.
"""
from django.db import connection, models
from django.test import TestCase

from authentication.models import Company
from core import events
from core.documents import (
    DocumentMetier,
    TransitionRefusee,
    changer_statut,
)
from core.models import TenantModel


# ── Modèle document JETABLE (app_label='core', table créée à la main) ─────────
class _DocDeTest(DocumentMetier):
    """Document concret jetable — mêmes statuts qu'un flux simple à 4 états."""

    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        EMIS = "emis", "Émis"
        CLOTURE = "cloture", "Clôturé"
        ANNULE = "annule", "Annulé"

    TRANSITIONS = {
        "brouillon": {"emis", "annule"},
        "emis": {"cloture", "annule"},
        "cloture": set(),   # terminal
        "annule": set(),    # terminal
    }

    reference = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        app_label = "core"


class _CreateDocTableMixin:
    """Crée/détruit la table du modèle jetable autour de la classe de test."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as schema:
            schema.create_model(_DocDeTest)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as schema:
            schema.delete_model(_DocDeTest)
        super().tearDownClass()


class DocumentMetierContractTests(TestCase):
    """Contrat de la classe abstraite (aucune table requise)."""

    def test_est_abstraite(self):
        self.assertTrue(DocumentMetier._meta.abstract)

    def test_herite_du_socle_tenant_arc1(self):
        self.assertTrue(issubclass(DocumentMetier, TenantModel))
        champs = {f.name for f in _DocDeTest._meta.get_fields()}
        self.assertIn("company", champs)
        self.assertIn("created_at", champs)
        self.assertIn("updated_at", champs)

    def test_statut_field_adosse_aux_choices_de_la_sous_classe(self):
        field = _DocDeTest._meta.get_field("statut")
        choix = {c[0] for c in field.choices}
        self.assertEqual(
            choix, {"brouillon", "emis", "cloture", "annule"})
        # default = premier membre de Statut (STATUT_INITIAL calculé).
        self.assertEqual(field.default, "brouillon")
        self.assertEqual(_DocDeTest.STATUT_INITIAL, "brouillon")

    def test_transitions_lues_de_la_table_declarative(self):
        doc = _DocDeTest(statut="brouillon")
        self.assertEqual(doc.transitions_permises(), {"emis", "annule"})
        self.assertTrue(doc.transition_permise("emis"))
        self.assertFalse(doc.transition_permise("cloture"))
        # Statut terminal → aucune transition.
        doc.statut = "cloture"
        self.assertEqual(doc.transitions_permises(), set())


class ChangerStatutTests(_CreateDocTableMixin, TestCase):
    """``changer_statut`` : permise / refusée / événement émis."""

    def setUp(self):
        self.company = Company.objects.create(nom="SCA30 Test SARL")
        self.doc = _DocDeTest.objects.create(
            company=self.company, reference="MDOC-0001")

    def _default_statut_a_la_creation(self):
        self.assertEqual(self.doc.statut, "brouillon")

    def test_transition_permise_mute_et_persiste(self):
        self._default_statut_a_la_creation()
        changer_statut(self.doc, "emis")
        self.assertEqual(self.doc.statut, "emis")
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.statut, "emis")

    def test_transition_refusee_leve_et_ne_mute_pas(self):
        # brouillon → cloture n'est PAS dans la table.
        with self.assertRaises(TransitionRefusee):
            changer_statut(self.doc, "cloture")
        # Aucune écriture : ni en mémoire ni en base.
        self.assertEqual(self.doc.statut, "brouillon")
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.statut, "brouillon")

    def test_transition_vers_statut_terminal_puis_refus(self):
        changer_statut(self.doc, "emis")
        changer_statut(self.doc, "cloture")
        self.assertEqual(self.doc.statut, "cloture")
        # cloture est terminal → toute transition ultérieure refusée.
        with self.assertRaises(TransitionRefusee):
            changer_statut(self.doc, "emis")

    def test_evenement_bus_emis_avec_contexte(self):
        recu = {}

        def _handler(sender, instance, ancien_statut, nouveau_statut,
                     user, company, **kwargs):
            recu.update(
                sender=sender, instance=instance, ancien=ancien_statut,
                nouveau=nouveau_statut, user=user, company=company)

        events.document_statut_change.connect(_handler, weak=False)
        try:
            user = object()  # marqueur d'identité (posé côté serveur)
            changer_statut(self.doc, "emis", user=user)
        finally:
            events.document_statut_change.disconnect(_handler)

        self.assertEqual(recu["sender"], _DocDeTest)
        self.assertIs(recu["instance"], self.doc)
        self.assertEqual(recu["ancien"], "brouillon")
        self.assertEqual(recu["nouveau"], "emis")
        self.assertIs(recu["user"], user)
        self.assertEqual(recu["company"], self.company)

    def test_transition_refusee_n_emet_aucun_evenement(self):
        compte = {"n": 0}

        def _handler(sender, **kwargs):
            compte["n"] += 1

        events.document_statut_change.connect(_handler, weak=False)
        try:
            with self.assertRaises(TransitionRefusee):
                changer_statut(self.doc, "cloture")
        finally:
            events.document_statut_change.disconnect(_handler)
        self.assertEqual(compte["n"], 0)

    def test_save_false_ne_persiste_pas_mais_mute_en_memoire(self):
        changer_statut(self.doc, "emis", save=False)
        self.assertEqual(self.doc.statut, "emis")
        # Pas persisté : la base garde l'ancien.
        fresh = _DocDeTest.objects.get(pk=self.doc.pk)
        self.assertEqual(fresh.statut, "brouillon")
