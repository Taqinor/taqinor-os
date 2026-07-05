# XSTK19 — code SH (HS) + pays d'origine sur Produit -> dossier d'import.
# Additif : deux champs nullables, aucun comportement existant modifie.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0058_xstk17_profil_saisonnier"),
    ]

    operations = [
        migrations.AddField(
            model_name="produit",
            name="code_sh",
            field=models.CharField(
                blank=True, max_length=20, null=True,
                verbose_name="Code SH (HS)"),
        ),
        migrations.AddField(
            model_name="produit",
            name="pays_origine",
            field=models.CharField(
                blank=True, max_length=100, null=True,
                verbose_name="Pays d'origine"),
        ),
    ]
