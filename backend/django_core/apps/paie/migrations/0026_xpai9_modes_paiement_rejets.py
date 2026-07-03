# Generated manually — XPAI9 modes de paiement & suivi des rejets de virement.
#
# Additif : ProfilPaie.mode_paiement (virement/cheque/especes),
# BulletinPaie.paye + date_paiement (décompte de paiement), et suivi de
# rejet sur LigneVirement (rejetee/motif_rejet/date_rejet/ligne_correction —
# self-FK pour la réémission). Aucun champ existant modifié.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI9 — Modes de paiement & suivi des rejets de virement."""

    dependencies = [
        ("paie", "0025_xpai6_echeance_declarative"),
    ]

    operations = [
        migrations.AddField(
            model_name="profilpaie",
            name="mode_paiement",
            field=models.CharField(
                choices=[
                    ("virement", "Virement"),
                    ("cheque", "Chèque"),
                    ("especes", "Espèces"),
                ],
                default="virement", max_length=10,
                verbose_name="Mode de paiement"),
        ),
        migrations.AddField(
            model_name="bulletinpaie",
            name="paye",
            field=models.BooleanField(default=False, verbose_name="Payé"),
        ),
        migrations.AddField(
            model_name="bulletinpaie",
            name="date_paiement",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Payé le"),
        ),
        migrations.AddField(
            model_name="lignevirement",
            name="rejetee",
            field=models.BooleanField(default=False, verbose_name="Rejetée"),
        ),
        migrations.AddField(
            model_name="lignevirement",
            name="motif_rejet",
            field=models.CharField(
                blank=True, default="", max_length=200,
                verbose_name="Motif du rejet"),
        ),
        migrations.AddField(
            model_name="lignevirement",
            name="date_rejet",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Rejetée le"),
        ),
        migrations.AddField(
            model_name="lignevirement",
            name="ligne_correction",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="corrige", to="paie.lignevirement",
                verbose_name="Ligne de correction (réémission)"),
        ),
    ]
