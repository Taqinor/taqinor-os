"""SOL8 — pays du tenant (ISO 3166-1 alpha-2), additif et non destructif.

Défaut ``MA`` : chaque société existante devient explicitement marocaine, ce
qui est la vérité (TAQINOR et ses tenants actuels le sont) — donc AUCUN
comportement ne change. Le champ ne sert qu'au semis « pack pays » à la
CRÉATION d'un nouveau tenant ; il n'est jamais lu pour les sociétés existantes.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='pays',
            field=models.CharField(
                default='MA', max_length=2,
                help_text='Code pays ISO du tenant (MA = Maroc). Détermine le '
                          '« pack pays » éteint au démarrage : einvoice, '
                          'fiscal, paie.',
                verbose_name='Pays (ISO 3166-1 alpha-2)'),
        ),
    ]
