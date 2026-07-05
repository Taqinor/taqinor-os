# Generated manually — ZPAI6 SaisieArret.statut/date_annulation/motif_annulation :
# champs additifs (défaut 'en_cours' = comportement historique inchangé, calculé
# via le booléen ``actif`` existant, conservé). Aucune donnée existante touchée.

from django.db import migrations, models


class Migration(migrations.Migration):
    """ZPAI6 — SaisieArret : cycle de vie explicite (additif)."""

    dependencies = [
        ("paie", "0035_zpai3_rubrique_cout_employeur"),
    ]

    operations = [
        migrations.AddField(
            model_name="saisiearret",
            name="statut",
            field=models.CharField(
                choices=[
                    ("en_cours", "En cours"),
                    ("soldee", "Soldée"),
                    ("annulee", "Annulée"),
                ],
                default="en_cours",
                max_length=10,
                verbose_name="Statut"),
        ),
        migrations.AddField(
            model_name="saisiearret",
            name="date_annulation",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Annulée le"),
        ),
        migrations.AddField(
            model_name="saisiearret",
            name="motif_annulation",
            field=models.CharField(
                blank=True, default="", max_length=200,
                verbose_name="Motif d'annulation"),
        ),
    ]
