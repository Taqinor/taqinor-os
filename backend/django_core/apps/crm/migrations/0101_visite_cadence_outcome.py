"""VISITE-CADENCE — l'issue « visite acceptée » entre dans
``LeadActivity.OUTCOMES``.

Ordre fondateur du 15/09/2026 : la visite technique est une ÉTAPE DU SUIVI
COMMERCIAL, proposée APRÈS l'envoi du devis pour verrouiller la proposition.
Il manquait au moteur la façon de dire « le client a accepté la visite » — une
issue de SUCCÈS qui n'arrête pourtant pas la cadence (la proposition reste à
relancer si la visite tombe à l'eau) et qui ne fait pas naître le barreau
suivant du protocole : la seule suite utile est de CALER la date.

``AlterField(choices)`` UNIQUEMENT : les ``choices`` ne sont pas contraints en
base, aucune ligne n'est touchée, aucune donnée n'est réécrite. ``max_length``
reste 20 — « visite_acceptee » fait 16 caractères.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0100_qjequipe2_appareil_equipe'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leadactivity',
            name='outcome',
            field=models.CharField(
                blank=True, default='', max_length=20,
                choices=[
                    ('', '—'),
                    ('joint', 'Joint'),
                    ('non_joint', 'Non joint'),
                    ('rappel', 'À rappeler'),
                    ('refuse', 'Refus'),
                    ('interesse', 'Intéressé'),
                    ('visite_acceptee', 'Visite acceptée'),
                ],
                verbose_name="Résultat de l'interaction"),
        ),
    ]
