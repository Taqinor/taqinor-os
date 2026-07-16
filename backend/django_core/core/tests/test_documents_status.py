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
from django.test.utils import isolate_apps

from authentication.models import Company
from core import events
from core.documents import (
    DocumentMetier,
    TransitionRefusee,
    changer_statut,
)
from core.models import TenantModel


# ── Modèle document JETABLE (app_label='core', table créée à la main) ─────────
# Défini sous ``isolate_apps('core')`` : enregistré dans un registre d'apps
# TEMPORAIRE, jamais dans le registre global — sinon tout autre test du même
# shard qui supprime une ``Company`` voit le collecteur de suppression suivre la
# FK inverse et interroger ``core_docdetest``, table qui n'existe qu'entre
# setUpClass/tearDownClass d'ici (« UndefinedTable » en CI selon le sharding).
# La FK ``company`` est REDÉCLARÉE avec la CLASSE ``Company`` (la référence
# paresseuse 'authentication.Company' ne se résout pas dans un registre isolé)
# et ``related_name='+'`` (aucun accesseur inverse posé sur le vrai Company).
with isolate_apps('core'):
    class DocDeTest(DocumentMetier):
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

        company = models.ForeignKey(
            Company, on_delete=models.CASCADE, related_name='+',
            verbose_name='Société')
        reference = models.CharField(max_length=64, blank=True, default="")

        class Meta:
            app_label = "core"


class _CreateDocTableMixin:
    """Crée/détruit la table du modèle jetable autour de la classe de test."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as schema:
            schema.create_model(DocDeTest)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as schema:
            schema.delete_model(DocDeTest)
        super().tearDownClass()


class DocumentMetierContractTests(TestCase):
    """Contrat de la classe abstraite (aucune table requise)."""

    def test_est_abstraite(self):
        self.assertTrue(DocumentMetier._meta.abstract)

    def test_herite_du_socle_tenant_arc1(self):
        self.assertTrue(issubclass(DocumentMetier, TenantModel))
        champs = {f.name for f in DocDeTest._meta.get_fields()}
        self.assertIn("company", champs)
        self.assertIn("created_at", champs)
        self.assertIn("updated_at", champs)

    def test_statut_field_adosse_aux_choices_de_la_sous_classe(self):
        field = DocDeTest._meta.get_field("statut")
        choix = {c[0] for c in field.choices}
        self.assertEqual(
            choix, {"brouillon", "emis", "cloture", "annule"})
        # default = premier membre de Statut (STATUT_INITIAL calculé).
        self.assertEqual(field.default, "brouillon")
        self.assertEqual(DocDeTest.STATUT_INITIAL, "brouillon")

    def test_transitions_lues_de_la_table_declarative(self):
        doc = DocDeTest(statut="brouillon")
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
        self.doc = DocDeTest.objects.create(
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

        self.assertEqual(recu["sender"], DocDeTest)
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
        fresh = DocDeTest.objects.get(pk=self.doc.pk)
        self.assertEqual(fresh.statut, "brouillon")


# ── DEFECT 1 (repair) — le champ ``statut`` de l'ABSTRAIT n'est JAMAIS muté ────
# Deux « kit docs » aux ``Statut`` DIFFÉRENTS : chacun doit porter SON PROPRE
# champ ``statut`` (choices/default distincts), sans corrompre son frère ni le
# champ partagé de la base abstraite ``DocumentMetier``. Avant la réparation,
# ``__init_subclass__`` mutait EN PLACE le champ résolu par MRO (celui de
# l'abstrait) : le dernier document défini gagnait, écrasant les choices/default
# vus par ses frères ET par la base. On teste ici les MÉTADONNÉES de champ
# (``_meta.get_field('statut')``) — aucune table requise (pas de DB).
# Mêmes raisons d'isolation que ``DocDeTest`` ci-dessus : jetables, jamais dans
# le registre global (ils n'ont d'ailleurs JAMAIS de table — tests de
# métadonnées uniquement).
with isolate_apps('core'):
    class KitDocA(DocumentMetier):
        """Kit doc A — 2 statuts (a1/a2)."""

        class Statut(models.TextChoices):
            A1 = "a1", "A1"
            A2 = "a2", "A2"

        company = models.ForeignKey(
            Company, on_delete=models.CASCADE, related_name='+',
            verbose_name='Société')

        class Meta:
            app_label = "core"

    class KitDocB(DocumentMetier):
        """Kit doc B — 3 statuts DIFFÉRENTS (b1/b2/b3)."""

        class Statut(models.TextChoices):
            B1 = "b1", "B1"
            B2 = "b2", "B2"
            B3 = "b3", "B3"

        company = models.ForeignKey(
            Company, on_delete=models.CASCADE, related_name='+',
            verbose_name='Société')

        class Meta:
            app_label = "core"

    class KitDocSansStatut(DocumentMetier):
        """Kit doc SANS ``Statut`` propre — voie documentée « sans effet » : garde
        le champ hérité de l'abstrait (défaut blanc), jamais les valeurs d'un
        frère."""

        company = models.ForeignKey(
            Company, on_delete=models.CASCADE, related_name='+',
            verbose_name='Société')

        class Meta:
            app_label = "core"


def _choices(model):
    return [c[0] for c in (model._meta.get_field("statut").choices or [])]


def _default(model):
    return model._meta.get_field("statut").default


class DocumentMetierChampStatutIsoleTests(TestCase):
    """DEFECT 1 — chaque document a SON champ ``statut`` ; l'abstrait est intact."""

    def test_chaque_document_porte_ses_propres_choices_et_default(self):
        self.assertEqual(_choices(KitDocA), ["a1", "a2"])
        self.assertEqual(_default(KitDocA), "a1")
        self.assertEqual(_choices(KitDocB), ["b1", "b2", "b3"])
        self.assertEqual(_default(KitDocB), "b1")

    def test_definir_un_document_ne_corrompt_pas_son_frere(self):
        # KitDocB est défini APRÈS KitDocA ; A ne doit PAS avoir hérité les
        # choices/default de B (le bug historique : le dernier défini gagnait).
        self.assertEqual(_choices(KitDocA), ["a1", "a2"])
        self.assertEqual(_default(KitDocA), "a1")
        # Ce sont des objets-champs DISTINCTS (pas le champ partagé de la base).
        champ_a = KitDocA._meta.get_field("statut")
        champ_b = KitDocB._meta.get_field("statut")
        self.assertIsNot(champ_a, champ_b)

    def test_champ_de_l_abstrait_jamais_mute(self):
        # Le champ ``statut`` de l'ABSTRAIT ``DocumentMetier`` reste vide :
        # aucun choices, default blanc — jamais réécrit par une sous-classe.
        champ_base = DocumentMetier._meta.get_field("statut")
        self.assertFalse(champ_base.choices)
        self.assertEqual(champ_base.default, "")

    def test_document_sans_statut_propre_garde_un_default_blanc(self):
        # Voie « sans effet » : pas de ``Statut`` propre → champ hérité blanc,
        # jamais les valeurs d'un frère défini plus tard.
        self.assertEqual(_choices(KitDocSansStatut), [])
        self.assertEqual(_default(KitDocSansStatut), "")

    def test_pilotes_reels_conservent_leur_contrat_statut(self):
        # Les 2 pilotes réels (OST-, DA-) DOIVENT garder choices/default exacts —
        # bit-identiques aux migrations 0094/0095 (max_length=32, blank=True).
        from apps.installations.models_ordre_soustraitance import (
            OrdreSousTraitance,
        )
        from apps.installations.models_demande_achat import DemandeAchat

        ost = OrdreSousTraitance._meta.get_field("statut")
        self.assertEqual(
            [c[0] for c in ost.choices],
            ["brouillon", "emis", "en_cours", "receptionne", "clos"])
        self.assertEqual(ost.default, "brouillon")
        self.assertEqual(ost.max_length, 32)
        self.assertTrue(ost.blank)

        da = DemandeAchat._meta.get_field("statut")
        self.assertEqual(
            [c[0] for c in da.choices],
            ["brouillon", "soumise", "approuvee", "refusee", "commandee"])
        self.assertEqual(da.default, "brouillon")
        self.assertEqual(da.max_length, 32)
        self.assertTrue(da.blank)
