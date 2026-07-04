from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0033_alter_itemchecklisttache_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='projetactivity',
            name='cible_type',
            field=models.CharField(
                choices=[
                    ('projet', 'Projet'),
                    ('tache', 'Tâche'),
                    ('jalon', 'Jalon'),
                ],
                default='projet', max_length=10,
                verbose_name='Type de cible'),
        ),
        migrations.AddField(
            model_name='projetactivity',
            name='cible_id',
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name='ID de la cible'),
        ),
        migrations.AddField(
            model_name='projetactivity',
            name='champ',
            field=models.CharField(
                blank=True, default='', max_length=50,
                verbose_name='Champ modifié'),
        ),
        migrations.AlterField(
            model_name='projetactivity',
            name='old_value',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='Ancien statut'),
        ),
        migrations.AlterField(
            model_name='projetactivity',
            name='new_value',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='Nouveau statut'),
        ),
    ]
