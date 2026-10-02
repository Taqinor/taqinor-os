"""ARRONDI-100 (fondateur, 02/10/2026) — palier d'arrondi du TTC hérité du
devis sur ``Facture`` (facture de BC) et repris sur l'``Avoir`` total.

ADDITIF : défaut 0 = aucun arrondi, donc toute facture et tout avoir existants
gardent leurs chiffres au centime. Réversible :
``python manage.py migrate facturation 0008``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0008_aud422_rls_argent'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='arrondi_pas',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name="Palier d'arrondi du TTC (MAD)",
                help_text="Hérité du devis : TTC ramené au multiple inférieur "
                          "de ce palier (0 = aucun arrondi)."),
        ),
        migrations.AddField(
            model_name='facture',
            name='arrondi_unites',
            field=models.PositiveSmallIntegerField(
                default=1,
                verbose_name="Unités d'arrondi (villas)",
                help_text="Hérité du devis ×N villas : le palier s'applique "
                          "par villa."),
        ),
        migrations.AddField(
            model_name='avoir',
            name='arrondi_unites',
            field=models.PositiveSmallIntegerField(
                default=1,
                verbose_name="Unités d'arrondi (villas)",
                help_text="Repris de la facture : le palier s'applique par "
                          "villa."),
        ),
        migrations.AddField(
            model_name='avoir',
            name='arrondi_pas',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name="Palier d'arrondi du TTC (MAD)",
                help_text="Repris de la facture : TTC ramené au multiple "
                          "inférieur de ce palier (0 = aucun arrondi)."),
        ),
    ]
