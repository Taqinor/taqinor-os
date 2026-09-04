"""SOL9 — ajoute le palier « Solaire » aux choix de `PlanLicence.code`.

Pure ALTER de `choices` (validation Django), aucun changement de type ni de
contrainte en base : PostgreSQL ne voit qu'un no-op. Aucune donnée touchée,
aucun plan créé ici — le semis du plan « Solaire » est explicite
(`manage.py seed_plan_solaire`), parce que son périmètre doit être DÉRIVÉ des
manifestes réellement chargés et non figé dans une migration.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminops', '0007_n101_demande_inscription'),
    ]

    operations = [
        migrations.AlterField(
            model_name='planlicence',
            name='code',
            field=models.CharField(
                choices=[('starter', 'Starter'), ('pro', 'Pro'),
                         ('enterprise', 'Enterprise'), ('solaire', 'Solaire')],
                help_text='Palier commercial (starter/pro/enterprise).',
                max_length=20, unique=True),
        ),
    ]
