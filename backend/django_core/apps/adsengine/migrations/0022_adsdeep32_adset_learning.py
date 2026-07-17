"""ADSDEEP32 — AdSetMirror : champs de phase d'apprentissage (learning_stage_info).

Additif : ``learning_status`` (badge UI), ``last_sig_edit`` (dernière édition
significative) et ``learning_stage_info`` (dict brut Meta). Alimentés par
``tasks.sync_adset_learning``. Chaîne linéaire : dépend de 0021.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adsengine", "0021_adsdeep27_capi_odoo_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="adsetmirror",
            name="learning_status",
            field=models.CharField(
                blank=True, default="", max_length=16,
                choices=[
                    ("LEARNING", "En apprentissage"),
                    ("SUCCESS", "Apprentissage réussi"),
                    ("FAIL", "Apprentissage limité"),
                ],
                verbose_name="Phase d'apprentissage"),
        ),
        migrations.AddField(
            model_name="adsetmirror",
            name="last_sig_edit",
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Dernière édition significative"),
        ),
        migrations.AddField(
            model_name="adsetmirror",
            name="learning_stage_info",
            field=models.JSONField(
                blank=True, default=dict,
                verbose_name="Info de phase d'apprentissage (brut Meta)"),
        ),
    ]
