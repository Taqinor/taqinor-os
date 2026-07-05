# ZPUR11 - motif d'annulation obligatoire (trace horodatee + acteur via
# records.Comment) + reouverture d'un BCF annule. Additif : nullable = aucun
# BCF existant modifie (aucun n'a jamais ete annule sans motif jusqu'ici).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0069_zpur8_bcf_other_information"),
    ]

    operations = [
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="motif_annulation",
            field=models.TextField(blank=True, null=True),
        ),
    ]
