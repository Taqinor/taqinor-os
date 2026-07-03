# XPLT14 — custom_data sur Fournisseur (couverture module 'fournisseur').

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0028_dc34_fournisseur_type_soustraitantprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="fournisseur",
            name="custom_data",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
