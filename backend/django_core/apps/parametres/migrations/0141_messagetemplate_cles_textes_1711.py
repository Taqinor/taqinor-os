"""17/11/2026 — douze clés entrent dans `MessageTemplate.Cle` (corrections de
textes de la cadence de suivi, approuvées par le fondateur) : l'appel d'ouverture
par origine (`appel_ouverture_reference|telephone|whatsapp_entrant|ancien_dossier`
et `appel_ouverture_deuxieme_affaire`), un script par appel après devis
(`appel_validite`, `appel_dernier_suivi`), le réveil J30 en appel
(`appel_reveil_devis`, `appel_reveil_sans_devis`) et les étapes du moteur qui
n'avaient rien à dire (`message_creneau`, `appel_rappel_convenu`,
`appel_planifier_visite`). Les libellés de six clés encore planifiées sont aussi
ramenés à leur jour du protocole v4.

`AlterField(choices)` UNIQUEMENT — même patron que 0140 : aucune donnée n'est
touchée, aucune ligne n'est créée. Les textes par défaut vivent dans
`MESSAGE_TEMPLATE_DEFAULTS` (du code).
"""
from django.db import migrations, models

from apps.parametres.models_messages import MessageTemplate


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0140_messagetemplate_cle_relance_pieces'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagetemplate',
            name='cle',
            field=models.CharField(
                choices=MessageTemplate.Cle.choices, max_length=40),
        ),
    ]
