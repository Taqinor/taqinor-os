# XGED7/8/9/13/15/16/18/19/20 — round-2 GED lane, batched additive migration.
#
# Strictly ADDITIVE (revertable): adds new models (DepotPublic, ExigenceDossier,
# DemandeDocument, ValidationOcrDocument, AnnotationDocument, TamponSociete,
# RegleDossier, ExecutionRegleDossier, RegleApprobationGed, ChaineApprobationGed,
# DocumentActivity, PlanificationDocument) plus new fields on existing models
# (Folder.alias_email for XGED9's email-intake routing, Document.url_externe for
# XGED18's link-documents). No existing table is removed or renamed.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.ged.models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0027_xged6_controleintegrite"),
    ]

    operations = [
        # ── Folder.alias_email (XGED9) ──────────────────────────────────
        migrations.AddField(
            model_name="folder",
            name="alias_email",
            field=models.CharField(
                blank=True, default="", max_length=100,
                verbose_name="alias d'ingestion email"),
        ),
        migrations.AddConstraint(
            model_name="folder",
            constraint=models.UniqueConstraint(
                condition=models.Q(("alias_email", ""), _negated=True),
                fields=("company", "alias_email"),
                name="ged_folder_unique_alias_email",
            ),
        ),
        # ── Document.url_externe (XGED18) ───────────────────────────────
        migrations.AddField(
            model_name="document",
            name="url_externe",
            field=models.URLField(
                blank=True, default="", max_length=2000,
                verbose_name="URL externe (document-lien)"),
        ),
        # ── DepotPublic (XGED7) ─────────────────────────────────────────
        migrations.CreateModel(
            name="DepotPublic",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("token", models.CharField(
                    default=apps.ged.models._default_partage_token,
                    editable=False, max_length=64, unique=True)),
                ("message", models.TextField(
                    blank=True, default="", verbose_name="message d'instruction")),
                ("expires_at", models.DateTimeField(
                    blank=True, null=True, verbose_name="expire le")),
                ("quota_fichiers", models.PositiveIntegerField(
                    blank=True, null=True, verbose_name="quota de fichiers")),
                ("quota_octets", models.BigIntegerField(
                    blank=True, null=True,
                    verbose_name="quota d'octets cumulés")),
                ("depots_effectues", models.PositiveIntegerField(
                    default=0, verbose_name="fichiers déposés")),
                ("octets_deposes", models.BigIntegerField(
                    default=0, verbose_name="octets déposés")),
                ("actif", models.BooleanField(default=True, verbose_name="actif")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_depots_publics", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_depots_publics_crees", to=settings.AUTH_USER_MODEL)),
                ("folder", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="depots_publics", to="ged.folder")),
            ],
            options={
                "verbose_name": "Lien de dépôt public",
                "verbose_name_plural": "Liens de dépôt public",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="depotpublic",
            index=models.Index(
                fields=["company", "folder"], name="ged_depot_co_folder_idx"),
        ),
        # ── ExigenceDossier (XGED8) ──────────────────────────────────────
        migrations.CreateModel(
            name="ExigenceDossier",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("libelle", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                ("obligatoire", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("cabinet", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="exigences", to="ged.cabinet")),
                ("company", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_exigences", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_exigences_creees", to=settings.AUTH_USER_MODEL)),
                ("folder", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="exigences", to="ged.folder")),
            ],
            options={
                "verbose_name": "Exigence de dossier",
                "verbose_name_plural": "Exigences de dossier",
                "ordering": ["libelle", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="exigencedossier",
            index=models.Index(
                fields=["company", "folder"], name="ged_exig_co_folder_idx"),
        ),
        migrations.AddIndex(
            model_name="exigencedossier",
            index=models.Index(
                fields=["company", "cabinet"], name="ged_exig_co_cabinet_idx"),
        ),
        # ── DemandeDocument (XGED8) ──────────────────────────────────────
        migrations.CreateModel(
            name="DemandeDocument",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("libelle", models.CharField(max_length=200)),
                ("destinataire_nom", models.CharField(
                    blank=True, default="", max_length=200)),
                ("destinataire_email", models.EmailField(
                    blank=True, default="", max_length=254)),
                ("echeance", models.DateField(blank=True, null=True)),
                ("statut", models.CharField(
                    choices=[("en_attente", "En attente"), ("soldee", "Soldée"),
                             ("annulee", "Annulée")],
                    default="en_attente", max_length=10)),
                ("derniere_relance_le", models.DateTimeField(blank=True, null=True)),
                ("nombre_relances", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_demandes_document", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_demandes_document_creees",
                    to=settings.AUTH_USER_MODEL)),
                ("document", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="demandes_soldees", to="ged.document")),
                ("exigence", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="demandes", to="ged.exigencedossier")),
                ("folder", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="demandes_document", to="ged.folder")),
                ("utilisateur", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_demandes_document_recues",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Demande de document",
                "verbose_name_plural": "Demandes de document",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="demandedocument",
            index=models.Index(
                fields=["company", "folder"], name="ged_ddoc_co_folder_idx"),
        ),
        migrations.AddIndex(
            model_name="demandedocument",
            index=models.Index(
                fields=["company", "statut"], name="ged_ddoc_co_statut_idx"),
        ),
        # ── ValidationOcrDocument (XGED13) ──────────────────────────────
        migrations.CreateModel(
            name="ValidationOcrDocument",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("score_confiance", models.FloatField(default=0.0)),
                ("champs_extraits", models.JSONField(
                    blank=True, default=dict, null=True)),
                ("valide", models.BooleanField(default=False)),
                ("valide_le", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_validations_ocr", to="authentication.company")),
                ("document", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="validation_ocr", to="ged.document")),
                ("valide_par", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_validations_ocr_faites",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Validation OCR",
                "verbose_name_plural": "Validations OCR",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="validationocrdocument",
            index=models.Index(
                fields=["company", "valide"], name="ged_valocr_co_valide_idx"),
        ),
        # ── AnnotationDocument + TamponSociete (XGED16) ─────────────────
        migrations.CreateModel(
            name="AnnotationDocument",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type_annotation", models.CharField(
                    choices=[("note", "Note"), ("surlignage", "Surlignage"),
                             ("tampon", "Tampon")],
                    default="note", max_length=12)),
                ("page", models.PositiveIntegerField(default=0)),
                ("x", models.FloatField(default=0.0)),
                ("y", models.FloatField(default=0.0)),
                ("contenu", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("auteur", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_annotations_creees", to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_annotations", to="authentication.company")),
                ("version", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="annotations", to="ged.documentversion")),
            ],
            options={
                "verbose_name": "Annotation de document",
                "verbose_name_plural": "Annotations de document",
                "ordering": ["page", "created_at", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="annotationdocument",
            index=models.Index(
                fields=["company", "version"], name="ged_annot_co_version_idx"),
        ),
        migrations.CreateModel(
            name="TamponSociete",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("libelle", models.CharField(max_length=60)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_tampons", to="authentication.company")),
            ],
            options={
                "verbose_name": "Tampon (société)",
                "verbose_name_plural": "Tampons (société)",
                "ordering": ["libelle", "id"],
                "unique_together": {("company", "libelle")},
            },
        ),
        # ── RegleDossier + ExecutionRegleDossier (XGED19) ───────────────
        migrations.CreateModel(
            name="RegleDossier",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=200)),
                ("condition_group", models.JSONField(blank=True, default=dict)),
                ("actions", models.JSONField(blank=True, default=list)),
                ("actif", models.BooleanField(default=True)),
                ("ordre", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_regles_dossier", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_regles_dossier_creees",
                    to=settings.AUTH_USER_MODEL)),
                ("folder", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="regles", to="ged.folder")),
            ],
            options={
                "verbose_name": "Règle de dossier",
                "verbose_name_plural": "Règles de dossier",
                "ordering": ["ordre", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="regledossier",
            index=models.Index(
                fields=["company", "folder", "actif"],
                name="ged_regle_co_folder_idx"),
        ),
        migrations.CreateModel(
            name="ExecutionRegleDossier",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("declenchee", models.BooleanField(default=False)),
                ("resultats", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_executions_regle", to="authentication.company")),
                ("document", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="executions_regle", to="ged.document")),
                ("regle", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="executions", to="ged.regledossier")),
            ],
            options={
                "verbose_name": "Exécution de règle de dossier",
                "verbose_name_plural": "Exécutions de règle de dossier",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="executionregledossier",
            index=models.Index(
                fields=["company", "regle"], name="ged_execregle_co_regle_idx"),
        ),
        # ── RegleApprobationGed + ChaineApprobationGed (XGED20) ─────────
        migrations.CreateModel(
            name="RegleApprobationGed",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("libelle", models.CharField(max_length=200)),
                ("condition_group", models.JSONField(blank=True, default=dict)),
                ("approbateurs", models.JSONField(blank=True, default=list)),
                ("priorite", models.PositiveIntegerField(default=0)),
                ("actif", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_regles_approbation", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_regles_approbation_creees",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Règle d'approbation GED",
                "verbose_name_plural": "Règles d'approbation GED",
                "ordering": ["-priorite", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="regleapprobationged",
            index=models.Index(
                fields=["company", "actif"], name="ged_regleapp_co_actif_idx"),
        ),
        migrations.CreateModel(
            name="ChaineApprobationGed",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("etapes", models.JSONField(blank=True, default=list)),
                ("etape_courante", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_chaines_approbation", to="authentication.company")),
                ("demande", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="chaine_approbation", to="ged.demandeapprobation")),
                ("regle", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="chaines", to="ged.regleapprobationged")),
            ],
            options={
                "verbose_name": "Chaîne d'approbation GED",
                "verbose_name_plural": "Chaînes d'approbation GED",
            },
        ),
        # ── DocumentActivity + PlanificationDocument (XGED15) ───────────
        migrations.CreateModel(
            name="DocumentActivity",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type_evenement", models.CharField(max_length=40)),
                ("message", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_document_activities", to="authentication.company")),
                ("document", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="activities", to="ged.document")),
                ("utilisateur", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_document_activities", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Activité de document (journal)",
                "verbose_name_plural": "Activités de document (journal)",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="documentactivity",
            index=models.Index(
                fields=["company", "document"], name="ged_docact_co_doc_idx"),
        ),
        migrations.CreateModel(
            name="PlanificationDocument",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("libelle", models.CharField(max_length=200)),
                ("echeance", models.DateField()),
                ("faite", models.BooleanField(default=False)),
                ("notifiee", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assigne_a", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_planifications_assignees",
                    to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ged_planifications", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ged_planifications_creees",
                    to=settings.AUTH_USER_MODEL)),
                ("document", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="planifications", to="ged.document")),
            ],
            options={
                "verbose_name": "Planification de document",
                "verbose_name_plural": "Planifications de document",
                "ordering": ["echeance", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="planificationdocument",
            index=models.Index(
                fields=["company", "echeance", "faite"],
                name="ged_plandoc_co_echeance_idx"),
        ),
    ]
