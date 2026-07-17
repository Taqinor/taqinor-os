import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0023_yhard1_encrypt_totp_secret'),
        ('innovation', '0006_idee_archived'),
    ]

    operations = [
        migrations.CreateModel(
            name='CampagneInnovation',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=255, verbose_name='Nom')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                (
                    'statut',
                    models.CharField(
                        choices=[
                            ('brouillon', 'Brouillon'),
                            ('active', 'Active'),
                            ('fermee', 'Fermée'),
                        ],
                        default='brouillon', max_length=10,
                        verbose_name='Statut'),
                ),
                ('cible_departement', models.CharField(
                    blank=True, default='', max_length=80,
                    verbose_name='Cible (département ou rôle)')),
                ('segment', models.JSONField(
                    blank=True, default=list, verbose_name='Segment')),
                ('date_debut', models.DateField(
                    blank=True, null=True, verbose_name='Date de début')),
                ('date_fin', models.DateField(
                    blank=True, null=True, verbose_name='Date de fin')),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='innovation_campagnes',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Campagne innovation',
                'verbose_name_plural': 'Campagnes innovation',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='campagneinnovation',
            index=models.Index(
                fields=['company', 'statut'], name='innovation_camp_co_statut'),
        ),
    ]
