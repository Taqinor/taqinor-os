from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0023_fg54_fg61_fg62_fg63_fg64_stock_features"),
    ]

    operations = [
        migrations.AddField(
            model_name="fournisseur",
            name="ice",
            field=models.CharField(
                blank=True, null=True, max_length=20,
                help_text="Identifiant Commun de l'Entreprise (ICE)."),
        ),
        migrations.AddField(
            model_name="fournisseur",
            name="identifiant_fiscal",
            field=models.CharField(
                blank=True, null=True, max_length=20,
                help_text="Identifiant Fiscal (IF)."),
        ),
        migrations.AddField(
            model_name="fournisseur",
            name="rc",
            field=models.CharField(
                blank=True, null=True, max_length=40,
                help_text="Numéro du Registre du Commerce (RC)."),
        ),
        migrations.AddField(
            model_name="fournisseur",
            name="rib",
            field=models.CharField(
                blank=True, null=True, max_length=50,
                help_text="RIB / IBAN du fournisseur (règlements AP)."),
        ),
    ]
