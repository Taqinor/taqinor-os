# Generated manually — PAIE36 clôture mensuelle + bulletins rectificatifs/rappels.
#
# Additive : sur ``BulletinPaie``, ajoute la nature du bulletin
# (normal/rectificatif/rappel), le lien self-FK vers le bulletin d'origine
# corrigé, et le motif. Défaut ``normal`` → comportement historique inchangé
# (tous les bulletins existants restent des bulletins normaux).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE36 — Nature du bulletin + lien rectificatif/rappel."""

    dependencies = [
        ("paie", "0018_ordrevirement"),
    ]

    operations = [
        migrations.AddField(
            model_name="bulletinpaie",
            name="type_bulletin",
            field=models.CharField(
                choices=[("normal", "Normal"),
                         ("rectificatif", "Rectificatif"),
                         ("rappel", "Rappel")],
                default="normal", max_length=14,
                verbose_name="Nature du bulletin"),
        ),
        migrations.AddField(
            model_name="bulletinpaie",
            name="rectifie",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rectifications", to="paie.bulletinpaie",
                verbose_name="Bulletin d'origine corrigé"),
        ),
        migrations.AddField(
            model_name="bulletinpaie",
            name="motif",
            field=models.CharField(
                blank=True, default="", max_length=200,
                verbose_name="Motif (rectificatif / rappel)"),
        ),
    ]
