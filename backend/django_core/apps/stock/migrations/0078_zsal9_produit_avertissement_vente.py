# ZSAL9 — Avertissement de vente par produit (« sale warnings » façon Odoo).
# Deux champs additifs : un message texte optionnel + un booléen bloquant.
# Défaut vide/False → comportement historique strictement inchangé.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0077_produit_unite'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='avertissement_vente',
            field=models.TextField(
                blank=True, default='',
                help_text='Message affiché au devis quand ce produit est ajouté.',
                verbose_name='Avertissement de vente'),
        ),
        migrations.AddField(
            model_name='produit',
            name='avertissement_bloquant',
            field=models.BooleanField(
                default=False,
                help_text="Si activé, empêche l'acceptation/facturation sans "
                          'override responsable/admin.',
                verbose_name='Avertissement bloquant'),
        ),
    ]
