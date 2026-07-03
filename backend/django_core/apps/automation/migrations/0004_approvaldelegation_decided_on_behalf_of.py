# Generated for XKB3 — délégation d'approbation (suppléant).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0010_customuser_supervisor"),
        ("automation", "0003_approvalrequesttype_approvalrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalrequest",
            name="decided_on_behalf_of",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approval_requests_deleguees",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="ApprovalDelegation",
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
                ("date_debut", models.DateTimeField()),
                ("date_fin", models.DateTimeField()),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_delegations",
                        to="authentication.company",
                    ),
                ),
                (
                    "delegant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_delegations_donnees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "suppleant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_delegations_recues",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Délégation d'approbation",
                "verbose_name_plural": "Délégations d'approbation",
                "ordering": ["-date_debut", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="approvaldelegation",
            index=models.Index(
                fields=["company", "delegant"],
                name="automation_deleg_delegant_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="approvaldelegation",
            index=models.Index(
                fields=["company", "suppleant"],
                name="automation_deleg_suppleant_idx",
            ),
        ),
    ]
