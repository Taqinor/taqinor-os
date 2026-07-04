from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0027_chronoencours'),
    ]

    operations = [
        migrations.AddField(
            model_name='tache',
            name='assigne',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='taches_assignees',
                to='gestion_projet.ressourceprofil',
                verbose_name='Assigné',
            ),
        ),
        migrations.AddField(
            model_name='tache',
            name='priorite',
            field=models.CharField(
                choices=[
                    ('basse', 'Basse'),
                    ('normale', 'Normale'),
                    ('haute', 'Haute'),
                    ('urgente', 'Urgente'),
                ],
                default='normale', max_length=10, verbose_name='Priorité',
            ),
        ),
        migrations.AddField(
            model_name='tache',
            name='etiquettes',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='Étiquettes',
            ),
        ),
    ]
