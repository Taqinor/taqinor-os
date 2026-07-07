# XMKT14 - test A/B avec gagnant automatique : configuration JSON + gagnant
# + horodatage de decision sur Campagne, variante A/B recue sur EnvoiCampagne.
# Additif : JSON vide / champs vides = pas de test A/B (comportement actuel).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0081_xmkt11_campagne_variantes_langue"),
    ]

    operations = [
        migrations.AddField(
            model_name="campagne",
            name="ab_test",
            field=models.JSONField(
                blank=True, default=dict,
                verbose_name="Configuration test A/B (JSON)"),
        ),
        migrations.AddField(
            model_name="campagne",
            name="ab_gagnant",
            field=models.CharField(
                blank=True, default="", max_length=1,
                verbose_name="Variante gagnante (A/B)"),
        ),
        migrations.AddField(
            model_name="campagne",
            name="ab_decide_le",
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Décision A/B prise le"),
        ),
        migrations.AddField(
            model_name="envoicampagne",
            name="variante_ab",
            field=models.CharField(
                blank=True, default="", max_length=1,
                verbose_name="Variante A/B"),
        ),
    ]
