"""ARC8/ARC26 — unit tests des garde-fous ``check_platform``.

ARC8 : rejeter toute NOUVELLE classe modèle ``*Activity`` hors de
``apps/records`` (le chatter doit converger sur ``records.Activity``).
ARC26 : rejeter tout NOUVEAU ``FileField``/``ImageField`` hors de la liste
gelée (toute nouvelle pièce jointe passe par ``records.Attachment`` ou
``ged.Document``). On teste la logique PURE (``apps.records.platform_guards``)
— pas d'accès disque — que le script ``scripts/check_platform.py`` réutilise
comme source unique de vérité.
"""
from django.test import SimpleTestCase

from apps.records.platform_guards import (
    BASELINE_BRANDING,
    BASELINE_HANDROLLED_MODELS,
    BASELINE_KIT_BYPASS_DOCUMENTS,
    BASELINE_UNSCOPED_VIEWSETS,
    GRANDFATHERED_ACTIVITY_CLASSES,
    GRANDFATHERED_FILEFIELDS,
    GRANDFATHERED_FLAT_STORAGE_KEYS,
    GRANDFATHERED_NUMBERING,
    GRANDFATHERED_WEASYPRINT,
    KIT_PERMANENT_EXCLUSIONS,
    NUMBERING_HOME_FILES,
    SOCLE_DEFINING_APPS,
    is_test_path,
    new_branding_hits,
    new_handrolled_models,
    new_kit_bypass_documents,
    new_unscoped_viewsets,
    scan_activity_classes,
    scan_branding,
    scan_filefields,
    scan_flat_storage_key,
    scan_handrolled_models,
    scan_kit_bypass_documents,
    scan_numbering,
    scan_unscoped_viewsets,
    scan_weasyprint_import,
)

# Une NOUVELLE classe *Activity fictive dans une app métier (ex. flotte).
FICTIVE_NEW_ACTIVITY = (
    "class SinistreActivity(models.Model):\n"
    "    company = models.ForeignKey('authentication.Company', on_delete=1)\n"
)

# Une classe *Activity déjà grand-fatherée (existe à l'heure d'ARC8).
GRANDFATHERED_SOURCE = (
    "class LeadActivity(models.Model):\n"
    "    pass\n"
)


class TestActivityGuard(SimpleTestCase):
    def test_new_activity_class_is_red(self):
        """Une nouvelle classe *Activity fictive hors records = violation."""
        found = scan_activity_classes("flotte", FICTIVE_NEW_ACTIVITY)
        self.assertIn("flotte.SinistreActivity", found)

    def test_grandfathered_class_is_green(self):
        """Une des 13 classes héritées ne déclenche jamais le garde-fou."""
        found = scan_activity_classes("crm", GRANDFATHERED_SOURCE)
        self.assertEqual(found, [])

    def test_records_app_is_exempt(self):
        """records POSSÈDE l'Activity générique : jamais signalé, même une
        classe nommée *Activity."""
        found = scan_activity_classes(
            "records", "class WeirdActivity(models.Model):\n    pass\n")
        self.assertEqual(found, [])

    def test_non_model_class_ignored(self):
        """Une classe *Activity qui n'est PAS un modèle Django (pas de base
        ``Model``) est ignorée (ex. un helper, une TextChoices n'est pas au
        niveau module)."""
        found = scan_activity_classes(
            "flotte", "class HelperActivity(object):\n    pass\n")
        self.assertEqual(found, [])

    def test_grandfathered_set_covers_real_tree(self):
        """Garde-fou du garde-fou : les 13 classes héritées réelles sont bien
        gelées (sinon le scan du dépôt serait rouge dès l'introduction du
        script). On vérifie la présence des pilotes ARC8."""
        self.assertIn("contrats.ContratActivity", GRANDFATHERED_ACTIVITY_CLASSES)
        self.assertIn("flotte.ActiviteFlotte", GRANDFATHERED_ACTIVITY_CLASSES)


class TestFileFieldGuard(SimpleTestCase):
    """ARC26 — « plus de FileField sauvage »."""

    def test_new_filefield_in_new_file_is_red(self):
        """Un FileField fictif dans un fichier non gelé = violation."""
        src = "    piece = models.FileField(upload_to='x/')\n"
        found = scan_filefields("apps/sav/models.py", src)
        self.assertEqual(found, ["apps/sav/models.py:piece"])

    def test_imagefield_is_red_too(self):
        src = "    photo_avant = models.ImageField(upload_to='x/')\n"
        found = scan_filefields("apps/qhse/models.py", src)
        self.assertEqual(found, ["apps/qhse/models.py:photo_avant"])

    def test_grandfathered_exact_count_is_green(self):
        """Les deux ``fichier`` gelés de compta ne déclenchent rien."""
        src = (
            "    fichier = models.FileField(upload_to='a/')\n"
            "    fichier = models.FileField(upload_to='b/')\n"
        )
        found = scan_filefields("apps/compta/models.py", src)
        self.assertEqual(found, [])

    def test_count_overflow_is_red(self):
        """Un 3ᵉ ``fichier`` dans compta (compte gelé = 2) = violation."""
        src = (
            "    fichier = models.FileField(upload_to='a/')\n"
            "    fichier = models.FileField(upload_to='b/')\n"
            "    fichier = models.FileField(upload_to='c/')\n"
        )
        found = scan_filefields("apps/compta/models.py", src)
        self.assertEqual(found, ["apps/compta/models.py:fichier"])

    def test_frozen_list_shape(self):
        """La liste gelée committée couvre bien les 7 fichiers / 17 champs de
        l'inventaire ARC26 (grep du 2026-07-10)."""
        self.assertEqual(len(GRANDFATHERED_FILEFIELDS), 7)
        total = sum(sum(v.values()) for v in GRANDFATHERED_FILEFIELDS.values())
        self.assertEqual(total, 17)


class TestWeasyPrintGuard(SimpleTestCase):
    """ARC11 — import WeasyPrint hors allowlist = rouge (ARC52 garde b)."""

    def test_new_direct_import_is_red(self):
        """Un nouvel importeur WeasyPrint hors allowlist = violation."""
        self.assertTrue(
            scan_weasyprint_import("apps/nouveau/report.py", "import weasyprint\n"))

    def test_new_from_import_is_red(self):
        self.assertTrue(scan_weasyprint_import(
            "apps/nouveau/builder.py", "    from weasyprint import HTML\n"))

    def test_allowlisted_service_is_green(self):
        """``core/pdf.py`` (le service partagé) est allowlisté."""
        self.assertFalse(
            scan_weasyprint_import("core/pdf.py", "        import weasyprint\n"))

    def test_rule4_quote_engine_is_green(self):
        """Les fichiers du moteur de devis règle #4 sont exemptés en permanence."""
        self.assertFalse(scan_weasyprint_import(
            "apps/ventes/quote_engine/residential/render.py",
            "    from weasyprint import HTML\n"))

    def test_grandfathered_importer_is_green(self):
        """Un importeur direct gelé (à migrer) ne déclenche rien."""
        self.assertFalse(scan_weasyprint_import(
            "apps/qhse/services.py", "import weasyprint\n"))

    def test_test_file_is_exempt(self):
        """Un fichier de tests peut importer WeasyPrint (rendu réel validé)."""
        self.assertFalse(scan_weasyprint_import(
            "apps/ventes/tests/test_x.py", "from weasyprint import HTML\n"))
        self.assertFalse(scan_weasyprint_import(
            "apps/x/tests_y.py", "import weasyprint\n"))

    def test_commented_import_is_green(self):
        """Un import commenté n'est pas un vrai import."""
        self.assertFalse(scan_weasyprint_import(
            "apps/x/report.py", "# import weasyprint\n"))

    def test_allowlist_covers_pilots(self):
        """Garde-fou du garde-fou : le service + un pilote règle #4 + un gelé
        sont bien dans l'allowlist (sinon le scan du dépôt serait rouge)."""
        self.assertIn("core/pdf.py", GRANDFATHERED_WEASYPRINT)
        self.assertIn(
            "apps/ventes/quote_engine/generate_devis_premium.py",
            GRANDFATHERED_WEASYPRINT)
        # ARC12 a migré apps/ged/services.py vers core.pdf.render_pdf (retiré
        # de l'allowlist, il n'importe plus weasyprint directement) —
        # apps/qhse/services.py reste l'importeur direct GELÉ (à migrer).
        self.assertIn("apps/qhse/services.py", GRANDFATHERED_WEASYPRINT)


class TestNumberingGuard(SimpleTestCase):
    """ARC6 — .count()+1 de référence hors socle = rouge (ARC52 garde c)."""

    def test_count_plus_1_reference_is_red(self):
        """Un ``.count() + 1`` en contexte de référence hors socle = violation."""
        src = "    ticket.reference = f'T-{Ticket.objects.count() + 1}'\n"
        found = scan_numbering("apps/sav/services.py", src)
        self.assertEqual(found, ["apps/sav/services.py:count+1"])

    def test_count_plus_1_numero_is_red(self):
        src = "    numero = qs.count() + 1\n"
        found = scan_numbering("apps/x/services.py", src)
        self.assertEqual(found, ["apps/x/services.py:count+1"])

    def test_slug_fallback_is_green(self):
        """Un ``count()+1`` pour un SLUG (pas une référence) = pas de violation
        (évite le faux positif sur authentication/models.py)."""
        src = '    self.slug = base or f"company-{Company.objects.count() + 1}"\n'
        self.assertEqual(scan_numbering("authentication/models.py", src), [])

    def test_loop_bound_is_green(self):
        """Un ``count()+1`` comme borne de boucle (pas une référence) = OK
        (évite le faux positif sur core/scoping.py:max_depth)."""
        src = "    max_depth = base.count() + 1\n"
        self.assertEqual(scan_numbering("core/scoping.py", src), [])

    def test_max_plus_1_is_green(self):
        """Le motif CORRECT ``max(...)+1`` (versionnage race-safe) n'est jamais
        visé — seul ``count()+1`` l'est."""
        src = "    numero = (max(nums) if nums else 0) + 1  # reference suivante\n"
        self.assertEqual(scan_numbering("apps/contrats/services.py", src), [])

    def test_home_file_is_exempt(self):
        """Les fichiers socle de numérotation sont exemptés."""
        src = "    ref = f'{p}-{qs.count() + 1}'\n"
        self.assertEqual(scan_numbering("core/numbering.py", src), [])
        self.assertEqual(
            scan_numbering("apps/ventes/utils/references.py", src), [])

    def test_test_file_is_exempt(self):
        """Un test peut fabriquer une référence jetable via count()."""
        src = "    reference=f'T-{Ticket.objects.count() + 1}'\n"
        self.assertEqual(scan_numbering("apps/sav/tests_x.py", src), [])

    def test_baseline_is_empty(self):
        """La baseline gelée est VIDE au 2026-07-10 (elle ne peut que décroître)
        et les deux fichiers socle sont bien référencés."""
        self.assertEqual(GRANDFATHERED_NUMBERING, frozenset())
        self.assertIn("core/numbering.py", NUMBERING_HOME_FILES)
        self.assertIn("apps/ventes/utils/references.py", NUMBERING_HOME_FILES)


class TestIsTestPath(SimpleTestCase):
    """Helper partagé (ARC11/ARC6) : reconnaître un fichier de tests."""

    def test_recognises_test_files(self):
        for p in ("apps/x/tests.py", "apps/x/test_y.py", "apps/x/tests_y.py",
                  "apps/x/tests/test_z.py", "apps/x/tests/helpers.py"):
            self.assertTrue(is_test_path(p), p)

    def test_rejects_source_files(self):
        for p in ("apps/x/services.py", "core/pdf.py", "apps/x/views.py"):
            self.assertFalse(is_test_path(p), p)


class TestHandrolledModelGuard(SimpleTestCase):
    """SCA4 garde (M) — nouveau modèle FK company à la main hors socle = rouge."""

    def test_new_handrolled_model_is_red(self):
        src = (
            "class SinistreVoyou(models.Model):\n"
            "    company = models.ForeignKey('authentication.Company', on_delete=1)\n"
            "    x = models.IntegerField()\n"
        )
        found = scan_handrolled_models("flotte", src)
        self.assertEqual(found, ["flotte.SinistreVoyou"])
        # Absent de la baseline → violation réelle.
        self.assertEqual(new_handrolled_models(found), ["flotte.SinistreVoyou"])

    def test_onetoonefield_is_red_too(self):
        src = (
            "class UnParSociete(models.Model):\n"
            "    company = models.OneToOneField('authentication.Company', on_delete=1)\n"
        )
        self.assertEqual(
            scan_handrolled_models("flotte", src), ["flotte.UnParSociete"])

    def test_tenantmodel_subclass_is_green(self):
        """Un modèle qui hérite de TenantModel ne déclare pas la FK → jamais rouge."""
        src = "class Propre(TenantModel):\n    x = models.IntegerField()\n"
        self.assertEqual(scan_handrolled_models("flotte", src), [])

    def test_socle_defining_apps_exempt(self):
        """core/authentication DÉFINISSENT le socle : FK company à la main légitime."""
        src = (
            "class Base(models.Model):\n"
            "    company = models.ForeignKey('authentication.Company', on_delete=1)\n"
        )
        for app in SOCLE_DEFINING_APPS:
            self.assertEqual(scan_handrolled_models(app, src), [], app)

    def test_baseline_entry_is_green(self):
        """Un offender déjà dans la baseline gelée n'est PAS une violation."""
        baselined = next(iter(BASELINE_HANDROLLED_MODELS))
        self.assertEqual(new_handrolled_models([baselined]), [])

    def test_baseline_covers_current_tree(self):
        """La baseline gelée est non vide (inventaire pré-socle du 2026-07-10)."""
        self.assertGreater(len(BASELINE_HANDROLLED_MODELS), 0)


class TestUnscopedViewSetGuard(SimpleTestCase):
    """SCA4 garde (V) — nouveau ModelViewSet hors CompanyScopedModelViewSet = rouge."""

    def test_new_unscoped_viewset_is_red(self):
        src = "class VoyouViewSet(viewsets.ModelViewSet):\n    pass\n"
        found = scan_unscoped_viewsets("flotte", src)
        self.assertEqual(found, ["flotte.VoyouViewSet"])
        self.assertEqual(new_unscoped_viewsets(found), ["flotte.VoyouViewSet"])

    def test_scoped_viewset_is_green(self):
        src = "class PropreViewSet(CompanyScopedModelViewSet):\n    pass\n"
        self.assertEqual(scan_unscoped_viewsets("flotte", src), [])

    def test_readonly_viewset_excluded(self):
        """ReadOnlyModelViewSet (pas de create) est hors périmètre du socle ARC2."""
        src = "class LectureViewSet(viewsets.ReadOnlyModelViewSet):\n    pass\n"
        self.assertEqual(scan_unscoped_viewsets("flotte", src), [])

    def test_baseline_entry_is_green(self):
        baselined = next(iter(BASELINE_UNSCOPED_VIEWSETS))
        self.assertEqual(new_unscoped_viewsets([baselined]), [])

    def test_baseline_covers_current_tree(self):
        self.assertGreater(len(BASELINE_UNSCOPED_VIEWSETS), 0)


class TestFlatStorageKeyGuard(SimpleTestCase):
    """SCA42 — nouvelle clé de stockage plate (non préfixée company) = rouge."""

    def test_new_flat_attachment_key_is_red(self):
        src = "    key = f'attachments/{uuid.uuid4().hex}.pdf'\n"
        self.assertTrue(scan_flat_storage_key("apps/nouveau/store.py", src))

    def test_new_flat_avatar_key_is_red(self):
        src = "    key = f'avatars/{uuid.uuid4().hex}.png'\n"
        self.assertTrue(scan_flat_storage_key("apps/nouveau/store.py", src))

    def test_company_prefixed_key_is_green(self):
        for src in (
            "    key = f'attachments/{cid}/{uuid.uuid4().hex}.pdf'\n",
            "    key = f'avatars/{company_id}/{uuid}.png'\n",
            "    key = f'attachments/{company.id}/{uuid}.pdf'\n",
        ):
            self.assertFalse(
                scan_flat_storage_key("apps/nouveau/store.py", src), src)

    def test_grandfathered_files_are_green(self):
        """Les branches de repli + la clé GED historique sont gelées."""
        src = "    key = f'attachments/{uuid.uuid4().hex}.pdf'\n"
        for relpath in GRANDFATHERED_FLAT_STORAGE_KEYS:
            self.assertFalse(scan_flat_storage_key(relpath, src), relpath)

    def test_test_file_is_exempt(self):
        src = "    key = f'attachments/{uuid.uuid4().hex}.pdf'\n"
        self.assertFalse(
            scan_flat_storage_key("apps/x/tests/test_y.py", src))

    def test_unrelated_prefix_is_green(self):
        """Une clé déjà préfixée par un autre schéma (devis/…) n'est pas visée."""
        src = "    key = f'devis/{ref}.pdf'\n"
        self.assertFalse(scan_flat_storage_key("apps/x/store.py", src))

    def test_baseline_shape(self):
        self.assertIn("apps/records/storage.py", GRANDFATHERED_FLAT_STORAGE_KEYS)
        self.assertIn("authentication/avatars.py", GRANDFATHERED_FLAT_STORAGE_KEYS)
        self.assertIn("apps/ged/services.py", GRANDFATHERED_FLAT_STORAGE_KEYS)


class TestBrandingGuard(SimpleTestCase):
    """SCA29 — marque « taqinor » hardcodée dans une surface user-facing = rouge."""

    def test_uppercase_brand_is_red(self):
        self.assertTrue(scan_branding(
            "apps/nouveau/views.py", "    msg = 'Bienvenue chez TAQINOR'\n"))

    def test_public_domain_is_red(self):
        self.assertTrue(scan_branding(
            "frontend/src/pages/X.jsx", "  const u = 'https://taqinor.ma/x';\n"))

    def test_contact_email_is_red(self):
        self.assertTrue(scan_branding(
            "apps/x/mail.py", "    to = 'contact@taqinor.ma'\n"))

    def test_comment_line_is_green(self):
        """Un motif en COMMENTAIRE (py ou JS) n'est pas une surface client."""
        self.assertFalse(scan_branding(
            "apps/x/views.py", "    # voir taqinor.ma pour la doc\n"))
        self.assertFalse(scan_branding(
            "frontend/src/x.jsx", "  // contact@taqinor legacy\n"))

    def test_generic_lowercase_taqinor_is_green(self):
        """Un « taqinor » générique (chemin d'infra, non client-facing) n'est pas
        un motif de MARQUE visé (seuls TAQINOR/taqinor.ma/contact@taqinor le sont)."""
        self.assertFalse(scan_branding(
            "apps/x/settings.py", "    path = '/opt/taqinor/data'\n"))

    def test_test_file_is_exempt(self):
        self.assertFalse(scan_branding("apps/x/tests/test_y.py", "    x = 'TAQINOR'\n"))

    def test_baseline_entry_is_green(self):
        baselined = next(iter(BASELINE_BRANDING))
        self.assertEqual(new_branding_hits([baselined]), [])

    def test_novel_hit_is_red(self):
        self.assertEqual(
            new_branding_hits(["apps/brandnew/views.py"]),
            ["apps/brandnew/views.py"])

    def test_baseline_covers_current_tree(self):
        """Baseline datée non vide (état post-SCA25-27 du 2026-07-10)."""
        self.assertGreater(len(BASELINE_BRANDING), 0)


class TestKitBypassDocumentGuard(SimpleTestCase):
    """SCA37 — garde CI kit : plus de « document métier » hand-rollé (statut à
    choices + ligne sœur Ligne<Nom> + montant_ttc) hors core.documents.DocumentMetier
    (SCA30/31), sauf l'exclusion PERMANENTE règle #4 (Devis/Facture/BonCommande/Avoir)."""

    # Un NOUVEAU document fictif hand-rollé : statut à choices + ligne sœur +
    # montant_ttc sur la ligne, sans hériter DocumentMetier.
    FICTIVE_HANDROLLED_DOC = (
        "class SinistreDoc(models.Model):\n"
        "    statut = models.CharField(max_length=20, choices=Statut.choices,"
        " default=Statut.BROUILLON)\n"
        "\n"
        "class LigneSinistreDoc(models.Model):\n"
        "    montant_ttc = models.DecimalField(max_digits=12, decimal_places=2)\n"
    )

    def test_fictive_handrolled_doc_is_red(self):
        """Un document fictif hand-rollé (statut+ligne sœur+montant_ttc) = violation."""
        found = scan_kit_bypass_documents("flotte", self.FICTIVE_HANDROLLED_DOC)
        self.assertEqual(found, ["flotte.SinistreDoc"])
        # Absent de la baseline → violation réelle.
        self.assertEqual(new_kit_bypass_documents(found), ["flotte.SinistreDoc"])

    def test_montant_ttc_on_parent_is_also_red(self):
        """montant_ttc peut être sur le PARENT plutôt que la ligne — toujours rouge."""
        src = (
            "class BonDivers(models.Model):\n"
            "    statut = models.CharField(max_length=20, choices=Statut.choices)\n"
            "    montant_ttc = models.DecimalField(max_digits=12, decimal_places=2)\n"
            "\n"
            "class LigneBonDivers(models.Model):\n"
            "    pass\n"
        )
        found = scan_kit_bypass_documents("qhse", src)
        self.assertEqual(found, ["qhse.BonDivers"])

    def test_no_sibling_line_is_green(self):
        """Pas de classe Ligne<Nom> sœur → pas l'anatomie visée, jamais rouge."""
        src = (
            "class SoloDoc(models.Model):\n"
            "    statut = models.CharField(max_length=20, choices=Statut.choices)\n"
            "    montant_ttc = models.DecimalField(max_digits=12, decimal_places=2)\n"
        )
        self.assertEqual(scan_kit_bypass_documents("qhse", src), [])

    def test_no_montant_ttc_is_green(self):
        """Statut+ligne sœur SANS montant_ttc (ex. DemandeAchat-like) → pas visé
        (SCA36 : le kit est composable sans le mixin totaux)."""
        src = (
            "class DemandeDivers(models.Model):\n"
            "    statut = models.CharField(max_length=20, choices=Statut.choices)\n"
            "\n"
            "class LigneDemandeDivers(models.Model):\n"
            "    quantite = models.IntegerField()\n"
        )
        self.assertEqual(scan_kit_bypass_documents("installations", src), [])

    def test_no_statut_choices_is_green(self):
        """Pas de statut à choices → pas l'anatomie visée."""
        src = (
            "class NonStatutDoc(models.Model):\n"
            "    montant_ttc = models.DecimalField(max_digits=12, decimal_places=2)\n"
            "\n"
            "class LigneNonStatutDoc(models.Model):\n"
            "    pass\n"
        )
        self.assertEqual(scan_kit_bypass_documents("qhse", src), [])

    def test_kit_inheriting_doc_is_green(self):
        """Un document QUI HÉRITE DocumentMetier n'est jamais un offender, même
        avec les trois traits (statut+ligne sœur+montant_ttc)."""
        src = (
            "class OrdreMission(DocumentMetier):\n"
            "    statut = models.CharField(max_length=20, choices=Statut.choices)\n"
            "    montant_ttc = models.DecimalField(max_digits=12, decimal_places=2)\n"
            "\n"
            "class LigneOrdreMission(LigneDocumentMetier):\n"
            "    pass\n"
        )
        self.assertEqual(scan_kit_bypass_documents("rh", src), [])

    def test_rule4_permanent_exclusion_is_green(self):
        """Devis/Facture/BonCommande/Avoir ne sont JAMAIS des offenders, même
        avec les trois traits réunis — exclusion permanente règle #4."""
        for name in ("Devis", "Facture", "BonCommande", "Avoir"):
            src = (
                f"class {name}(models.Model):\n"
                f"    statut = models.CharField(max_length=20, choices=Statut.choices)\n"
                f"    montant_ttc = models.DecimalField(max_digits=12, decimal_places=2)\n"
                f"\n"
                f"class Ligne{name}(models.Model):\n"
                f"    pass\n"
            )
            self.assertEqual(scan_kit_bypass_documents("ventes", src), [], name)

    def test_permanent_exclusion_set_is_named(self):
        """L'exclusion permanente règle #4 couvre exactement les 4 documents
        nommés dans CLAUDE.md — jamais retirable par un nettoyage de baseline."""
        self.assertEqual(
            KIT_PERMANENT_EXCLUSIONS,
            frozenset({
                "ventes.Devis", "ventes.Facture",
                "ventes.BonCommande", "ventes.Avoir",
            }),
        )

    def test_permanent_exclusion_never_enters_baseline(self):
        """Même si un exclu permanent apparaissait dans ``found`` (défense en
        profondeur), new_kit_bypass_documents ne le laisse jamais passer."""
        self.assertEqual(new_kit_bypass_documents(["ventes.Devis"]), [])

    def test_baseline_entry_is_green(self):
        """Un offender déjà dans la baseline gelée n'est PAS une violation."""
        baselined = next(iter(BASELINE_KIT_BYPASS_DOCUMENTS))
        self.assertEqual(new_kit_bypass_documents([baselined]), [])

    def test_baseline_covers_current_tree(self):
        """Baseline datée non vide (inventaire pré-kit du 2026-07-10) et couvre
        les deux pilotes réels connus (achats.FactureFournisseur, ventes.NoteDebit)."""
        self.assertGreater(len(BASELINE_KIT_BYPASS_DOCUMENTS), 0)
        self.assertIn("achats.FactureFournisseur", BASELINE_KIT_BYPASS_DOCUMENTS)
        self.assertIn("ventes.NoteDebit", BASELINE_KIT_BYPASS_DOCUMENTS)
        # Les 4 exclus permanents ne sont JAMAIS dans la baseline (ils vivent
        # dans KIT_PERMANENT_EXCLUSIONS, pas dans le fichier baseline).
        self.assertFalse(BASELINE_KIT_BYPASS_DOCUMENTS & KIT_PERMANENT_EXCLUSIONS)
