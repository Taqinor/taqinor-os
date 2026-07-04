# Generated manually — YHIRE14 approbation de réquisition (OuverturePoste) :
# nouveaux statuts amont (brouillon/en_approbation) + traçabilité SoD.
# Additif ; les ouvertures existantes restent "ouvert" (seul le DÉFAUT à la
# création change).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """YHIRE14 — OuverturePoste : statuts brouillon/en_approbation + demandeur/
    approbateur/date_soumission/date_decision/motif_refus (additif)."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rh", "0069_yhire13_epi_stock_link"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ouvertureposte",
            name="statut",
            field=models.CharField(
                choices=[
                    ("brouillon", "Brouillon"),
                    ("en_approbation", "En approbation"),
                    ("ouvert", "Ouvert"),
                    ("pourvu", "Pourvu"),
                    ("clos", "Clos"),
                    ("annule", "Annulé"),
                ],
                default="brouillon", max_length=20, verbose_name="Statut"),
        ),
        migrations.AddField(
            model_name="ouvertureposte",
            name="demandeur",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rh_ouvertures_demandees",
                to=settings.AUTH_USER_MODEL, verbose_name="Demandeur"),
        ),
        migrations.AddField(
            model_name="ouvertureposte",
            name="approbateur",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rh_ouvertures_approuvees",
                to=settings.AUTH_USER_MODEL, verbose_name="Approbateur"),
        ),
        migrations.AddField(
            model_name="ouvertureposte",
            name="date_soumission",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Soumise le"),
        ),
        migrations.AddField(
            model_name="ouvertureposte",
            name="date_decision",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Décidée le"),
        ),
        migrations.AddField(
            model_name="ouvertureposte",
            name="motif_refus",
            field=models.CharField(
                blank=True, default="", max_length=255,
                verbose_name="Motif de refus"),
        ),
    ]
