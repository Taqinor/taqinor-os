"""VISITE-CADENCE — `visite_proposition` et `visite_confirmation` entrent dans
`MessageTemplate.Cle`.

Ordre fondateur du 15/09/2026 : la visite technique est une ÉTAPE DU SUIVI
COMMERCIAL, placée APRÈS l'envoi du devis (outil de closing, pas préalable à
l'étude). Deux textes la portent — la PROPOSER, puis la CONFIRMER la veille —
et leurs textes sont validés dans `docs/crm/messages_meryem.md` (c'est ce qui
les distingue de `visite_veille`/`visite_matin`/`apres_visite`, toujours
délibérément absents).

`AlterField(choices)` UNIQUEMENT — même patron que 0083 : aucune donnée n'est
touchée, aucune ligne n'est créée. Les textes par défaut vivent dans
`MESSAGE_TEMPLATE_DEFAULTS` (du code, pas des lignes) ; une société ne reçoit
une ligne que le jour où elle personnalise son message.
"""
from django.db import migrations, models

from apps.parametres.models_messages import MessageTemplate


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0088_companyprofile_rto_annonce_heures'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagetemplate',
            name='cle',
            field=models.CharField(
                choices=MessageTemplate.Cle.choices, max_length=40),
        ),
    ]
