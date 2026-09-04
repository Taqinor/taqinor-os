"""AUD529 — lien de retour Ticket SAV → litiges.Reclamation (additif).

Champ entier optionnel (loose FK, jamais un import cross-app des modèles
litiges), NULL par défaut : aucun ticket existant n'est touché.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0050_alter_equipement_client_vente_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='reclamation_id_ext',
            field=models.IntegerField(
                blank=True, null=True,
                help_text='ID de la litiges.Reclamation ouverte depuis ce '
                          'ticket (escalade AUD529).'),
        ),
    ]
