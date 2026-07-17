"""ADSDEEP46 — Tags de convention de nommage (parser PUR, ``naming.py``).

Additif : ``hook_tag``/``angle_tag``/``format_tag`` sur ``AdMirror`` (source =
``name`` Meta) et ``CreativeAsset`` (source = ``file_key``, la bibliothèque
maison n'a pas de ``name``). Vides par défaut — jamais requis, jamais de
migration de données (le retro-tag est un appel explicite de
``naming.retag_company_ads``/``retag_company_creative_assets``). Chaîne
linéaire : dépend de 0026.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adsengine", "0026_adsdeep42_rulepolicy_cadence_minutes"),
    ]

    operations = [
        migrations.AddField(
            model_name="admirror",
            name="hook_tag",
            field=models.CharField(
                blank=True, default="", max_length=64,
                verbose_name="Tag accroche"),
        ),
        migrations.AddField(
            model_name="admirror",
            name="angle_tag",
            field=models.CharField(
                blank=True, default="", max_length=64,
                verbose_name="Tag angle"),
        ),
        migrations.AddField(
            model_name="admirror",
            name="format_tag",
            field=models.CharField(
                blank=True, default="", max_length=64,
                verbose_name="Tag format"),
        ),
        migrations.AddField(
            model_name="creativeasset",
            name="hook_tag",
            field=models.CharField(
                blank=True, default="", max_length=64,
                verbose_name="Tag accroche"),
        ),
        migrations.AddField(
            model_name="creativeasset",
            name="angle_tag",
            field=models.CharField(
                blank=True, default="", max_length=64,
                verbose_name="Tag angle"),
        ),
        migrations.AddField(
            model_name="creativeasset",
            name="format_tag",
            field=models.CharField(
                blank=True, default="", max_length=64,
                verbose_name="Tag format"),
        ),
    ]
