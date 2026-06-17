# D3 — numérotation par type de pièce (largeur + période de réinitialisation).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0011_regime_8221_thresholds"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="doc_numbering",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
