# XCTR19 — Retour de location : retards, frais automatiques, inspection.
# Champs additifs sur `OrdreLocation`. Aucune donnée existante touchée.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0031_xctr18_caution_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordrelocation",
            name="frais_retard_jour",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name="Frais de retard / jour"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="frais_retard_montant",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name="Frais de retard facturés"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="frais_retard_facture_id",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="ID de la facture (frais de retard)"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="inspection_checklist",
            field=models.JSONField(
                blank=True, null=True,
                verbose_name="Checklist d'inspection"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="inspection_releve_compteur",
            field=models.CharField(
                blank=True, default="", max_length=50,
                verbose_name="Relevé compteur"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="inspection_dommages_montant",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name="Montant des dommages chiffrés"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="inspection_facture_id",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="ID de la facture (dommages)"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="inspection_ticket_sav_id",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="ID du ticket SAV de remise en état"),
        ),
        migrations.AddField(
            model_name="ordrelocation",
            name="inspection_date",
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Date de l'inspection"),
        ),
    ]
