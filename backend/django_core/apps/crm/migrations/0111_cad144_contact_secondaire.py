# CAD144 (audit L3 du 21/09/2026) — un achat de coopérative ou un comité
# industriel a plusieurs interlocuteurs : un contact SECONDAIRE libre (nom +
# téléphone) sur la fiche lead, qu'aucune cadence ne lit. Deux AddField
# additifs et nullables (même convention que `telephone`/`whatsapp`) : aucune
# donnée existante n'est touchée.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0110_cad163_objectif_sans_8221'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='contact_secondaire_nom',
            field=models.CharField(blank=True, help_text='Co-associé de coopérative, technicien d’usine, membre du comité… Aucune relance automatique ne lui est adressée.', max_length=255, null=True, verbose_name='Contact secondaire (nom)'),
        ),
        migrations.AddField(
            model_name='lead',
            name='contact_secondaire_telephone',
            field=models.CharField(blank=True, help_text='Numéro du second interlocuteur — jamais utilisé par la cadence : le contacter reste un geste manuel.', max_length=50, null=True, verbose_name='Contact secondaire (téléphone)'),
        ),
    ]
