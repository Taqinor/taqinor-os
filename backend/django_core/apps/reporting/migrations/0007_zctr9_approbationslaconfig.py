import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('reporting', '0006_alter_classeur_proprietaire'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApprobationSlaConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sla_jours', models.PositiveIntegerField(default=3, help_text="Nombre de jours ouvrés en attente au-delà duquel une demande d'approbation est signalée en retard.")),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='approbation_sla_config', to='authentication.company')),
            ],
            options={
                'verbose_name': "Réglage SLA d'approbation",
                'verbose_name_plural': "Réglages SLA d'approbation",
            },
        ),
    ]
