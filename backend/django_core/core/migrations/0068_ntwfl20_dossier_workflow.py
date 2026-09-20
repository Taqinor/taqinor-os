# NTWFL20 — un dossier transverse peut porter SON PROPRE processus BPM
# (FG366). Champ ADDITIF nullable : tout dossier existant reste sans
# processus, comportement strictement inchangé.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0067_ntwfl18_dossier_activity'),
    ]

    operations = [
        migrations.AddField(
            model_name='dossier',
            name='workflow_instance',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='dossiers', to='core.workflowinstance',
                verbose_name='Processus attaché'),
        ),
    ]
