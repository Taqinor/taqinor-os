# XPLT15 — conditions dynamiques (visible_si/requis_si/lecture_seule_si).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customfields", "0004_xplt14_relation_fichier"),
    ]

    operations = [
        migrations.AddField(
            model_name="customfielddef",
            name="conditions",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
