# XPUR3 — Multi-devises sur les achats (imports panneaux/onduleurs).
# Additif : devise/taux_change (défaut MAD/1) sur BonCommandeFournisseur et
# FactureFournisseur ; prix_achat_unitaire_devise sur la ligne BCF (null =
# document en MAD, comportement historique inchangé) ; montant_ttc_devise
# sur la facture. prix_achat_unitaire / montant_ttc restent la contre-valeur
# MAD utilisée partout en interne.
from django.db import migrations, models


DEVISE_CHOICES = [
    ("MAD", "Dirham marocain (MAD)"),
    ("EUR", "Euro (EUR)"),
    ("USD", "Dollar américain (USD)"),
    ("CNY", "Yuan chinois (CNY)"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0030_xpur2_ras_tva"),
    ]

    operations = [
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="devise",
            field=models.CharField(
                choices=DEVISE_CHOICES, default="MAD", max_length=3),
        ),
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="taux_change",
            field=models.DecimalField(
                decimal_places=6, default=1, max_digits=12,
                help_text='Taux de change devise → MAD à la date du '
                          'document (saisie manuelle, aucun appel externe).',
            ),
        ),
        migrations.AddField(
            model_name="ligneboncommandefournisseur",
            name="prix_achat_unitaire_devise",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                help_text="Prix d'achat unitaire dans la devise du "
                          'document (optionnel — null = document en MAD).',
            ),
        ),
        migrations.AddField(
            model_name="facturefournisseur",
            name="devise",
            field=models.CharField(
                choices=DEVISE_CHOICES, default="MAD", max_length=3),
        ),
        migrations.AddField(
            model_name="facturefournisseur",
            name="taux_change",
            field=models.DecimalField(
                decimal_places=6, default=1, max_digits=12,
                help_text='Taux de change devise → MAD à la date du '
                          'document (saisie manuelle, aucun appel externe).',
            ),
        ),
        migrations.AddField(
            model_name="facturefournisseur",
            name="montant_ttc_devise",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True,
                help_text='Montant TTC dans la devise du document '
                          '(optionnel — null = document en MAD).',
            ),
        ),
    ]
