# ZSAL9 — Avertissement de vente par client (« sale warnings » façon Odoo).
# Deux champs additifs : un message texte optionnel + un booléen bloquant.
# Défaut vide/False → comportement historique strictement inchangé.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0056_vx98_lead_updated_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='avertissement_vente',
            field=models.TextField(
                blank=True, default='',
                help_text='Message affiché au devis quand ce client est '
                          'sélectionné.',
                verbose_name='Avertissement de vente'),
        ),
        migrations.AddField(
            model_name='client',
            name='avertissement_bloquant',
            field=models.BooleanField(
                default=False,
                help_text="Si activé, empêche l'acceptation/facturation sans "
                          'override responsable/admin.',
                verbose_name='Avertissement bloquant'),
        ),
    ]
