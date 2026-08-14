# NTCRM14 — anti-spam pour l'alerte "compte dormant" : un seul champ additif
# nullable, défaut NULL → tous les clients existants restent "jamais alertés"
# (comportement historique inchangé). Additif et révertable.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0068_ntadm2_lead_entite'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='derniere_alerte_dormance',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text="Date de la dernière notification 'compte dormant' "
                          "envoyée pour ce client. Vide = jamais alerté.",
                verbose_name='Dernière alerte de dormance',
            ),
        ),
    ]
