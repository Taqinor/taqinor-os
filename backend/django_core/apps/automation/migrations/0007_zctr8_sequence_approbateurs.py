# Generated for ZCTR8 — demande d'information + approbateurs
# séquentiels/parallèles.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0006_zctr7_min_approbations_approvaldecision"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalrequesttype",
            name="sequence_approbateurs",
            field=models.CharField(
                choices=[
                    ("parallele", "Parallèle (tous notifiés d’emblée)"),
                    ("sequentiel", "Séquentiel (rang par rang)"),
                ],
                default="parallele",
                max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name="approvalrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "En attente"),
                    ("approved", "Approuvé"),
                    ("rejected", "Rejeté"),
                    ("info_requested", "Complément d'information demandé"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
