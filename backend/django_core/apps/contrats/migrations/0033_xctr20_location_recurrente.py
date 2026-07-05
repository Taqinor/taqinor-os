# XCTR20 — Location longue durée en facturation récurrente +
# prolongation/écourtage. Champs additifs sur `OrdreLocation` + nouveau choix
# de `CycleFacturationLog.source_type` (ordre_location). Additif.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0032_xctr19_retour_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordrelocation",
            name="facturation_recurrente_active",
            field=models.BooleanField(
                default=False, verbose_name="Facturation récurrente active"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="facturation_periodicite",
            field=models.CharField(
                choices=[("mensuelle", "Mensuelle")],
                default="mensuelle", max_length=20,
                verbose_name="Périodicité"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="facturation_moment",
            field=models.CharField(
                choices=[("avance", "D'avance"), ("echu", "À terme échu")],
                default="avance", max_length=10, verbose_name="Facturé"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="derniere_facturation",
            field=models.DateField(
                blank=True, null=True, verbose_name="Dernière facturation"),
        ),
        migrations.AlterField(
            model_name="cyclefacturationlog",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("contrat", "Contrat (échéancier)"),
                    ("sav_maintenance", "Maintenance SAV"),
                    ("ordre_location", "Location longue durée"),
                ],
                max_length=20, verbose_name="Type de source"),
        ),
    ]
