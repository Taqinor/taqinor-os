# XMKT31 - conteneur de campagne multi-canal : FK auto-referente `parente`
# + rattachements JSON (sequences/formulaires/codes promo/evenements) sur
# Campagne. Additif : NULL/liste vide = campagne autonome (comportement
# actuel).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0090_xmkt29_support_offline"),
    ]

    operations = [
        migrations.AddField(
            model_name="campagne",
            name="parente",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="enfants", to="compta.campagne",
                verbose_name="Campagne mère"),
        ),
        migrations.AddField(
            model_name="campagne",
            name="rattachements",
            field=models.JSONField(
                blank=True, default=list,
                verbose_name="Rattachements (JSON, campagne mère)"),
        ),
    ]
