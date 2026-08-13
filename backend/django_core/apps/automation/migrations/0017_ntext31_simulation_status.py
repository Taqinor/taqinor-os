# NTEXT31 — statut `simulation` sur AutomationRun (trace d'un dry-run).
# Additif : AlterField sur les seuls `choices` déclarés en Python, la colonne
# reste un CharField(max_length=20) — aucune ligne existante affectée.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0016_ntext7_scheduled_step'),
    ]

    operations = [
        migrations.AlterField(
            model_name='automationrun',
            name='status',
            field=models.CharField(
                choices=[('success', 'Réussi'), ('skipped', 'Ignoré'),
                         ('failed', 'Échec'),
                         ('pending_approval', "En attente d'approbation"),
                         ('noop', 'Sans effet'),
                         ('simulation', 'Simulation (sans effet)')],
                default='success', max_length=20),
        ),
    ]
