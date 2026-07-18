"""ADSDEEP34 — Experiment.meta_study_id : lien vers l'étude A/B NATIVE Meta.

Additif : une expérience (test A/B/n interne, ADSENG3) peut désormais porter
l'id de son étude ``ad_studies`` (SPLIT_TEST_V2) côté Meta, quand elle en a une
(vide sinon — chaîne linéaire, dépend de 0023).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("adsengine", "0023_adsdeep31_edit_kinds"),
    ]

    operations = [
        migrations.AddField(
            model_name="experiment",
            name="meta_study_id",
            field=models.CharField(
                blank=True, default="", max_length=64,
                verbose_name="ID d'étude native Meta (ad_studies)"),
        ),
    ]
