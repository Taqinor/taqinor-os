# GED19 — ACL par dossier/document (héritage + override).
#
# Ajoute le modèle `AclGed` : une entrée de liste de contrôle d'accès qui
# octroie à un principal (utilisateur ET/OU rôle) un `niveau`
# (lecture/ecriture/gestion) sur EXACTEMENT une cible (un dossier OU un
# document). Le drapeau `herite` indique si l'entrée se propage vers le bas.
#
# Additive et réversible. Deux contraintes base reflètent la garde `clean()` :
#   - exactement-une cible (folder XOR document) ;
#   - au moins-un principal (utilisateur OU rôle).
# Backward-compatible : sans aucune entrée ACL, le comportement existant
# (ACL coffre-fort GED8 + scoping société) est strictement préservé. Niveaux
# LOCAUX à la GED, distincts du funnel STAGES.py.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        ("roles", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0012_demandeapprobation"),
    ]

    operations = [
        migrations.CreateModel(
            name="AclGed",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "niveau",
                    models.CharField(
                        choices=[
                            ("lecture", "Lecture"),
                            ("ecriture", "Écriture"),
                            ("gestion", "Gestion"),
                        ],
                        default="lecture",
                        max_length=8,
                        verbose_name="niveau d'accès",
                    ),
                ),
                (
                    "herite",
                    models.BooleanField(
                        default=True, verbose_name="héritée vers le bas"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_acls",
                        to="authentication.company",
                    ),
                ),
                (
                    "folder",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_acls",
                        to="ged.folder",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_acls",
                        to="ged.document",
                    ),
                ),
                (
                    "utilisateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_acls",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="utilisateur",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_acls",
                        to="roles.role",
                        verbose_name="rôle",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_acls_crees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Droit d'accès GED",
                "verbose_name_plural": "Droits d'accès GED",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="aclged",
            index=models.Index(
                fields=["company", "folder"], name="ged_acl_co_folder_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="aclged",
            index=models.Index(
                fields=["company", "document"], name="ged_acl_co_doc_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="aclged",
            index=models.Index(
                fields=["utilisateur"], name="ged_acl_user_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="aclged",
            index=models.Index(fields=["role"], name="ged_acl_role_idx"),
        ),
        migrations.AddConstraint(
            model_name="aclged",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(folder__isnull=False, document__isnull=True)
                    | models.Q(folder__isnull=True, document__isnull=False)
                ),
                name="ged_acl_exactly_one_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="aclged",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(utilisateur__isnull=False)
                    | models.Q(role__isnull=False)
                ),
                name="ged_acl_principal_required",
            ),
        ),
    ]
