"""ACAL598 — le rôle « échafaudage » d'un composant de fixation.

Additive et réversible : seuls les ``choices`` de ``ComposantFixation.role``
changent, aucune donnée n'est touchée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0039_acal822_gabarit_verifie_limites'),
    ]

    operations = [
        migrations.AlterField(
            model_name='composantfixation',
            name='role',
            field=models.CharField(choices=[
                ('rail', 'Rail'), ('pince_milieu', 'Pince de milieu'),
                ('pince_fin', 'Pince de fin'), ('crochet', 'Crochet'),
                ('embout', 'Embout'), ('lest', 'Lest'), ('visserie', 'Visserie'),
                ('echafaudage', 'Échafaudage')],
                max_length=20, verbose_name='Rôle'),
        ),
    ]
