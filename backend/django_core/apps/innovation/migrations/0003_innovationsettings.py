import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0023_yhard1_encrypt_totp_secret'),
        ('innovation', '0002_voteidee'),
    ]

    operations = [
        migrations.CreateModel(
            name='InnovationSettings',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campagnes_activees', models.BooleanField(
                    default=False, verbose_name='Campagnes activées')),
                ('segment_defaut', models.CharField(
                    blank=True, default='', max_length=80,
                    verbose_name='Segment par défaut')),
                (
                    'theme_couleur_cta',
                    models.CharField(
                        choices=[
                            ('primary', 'Primaire'),
                            ('success', 'Succès'),
                            ('warning', 'Avertissement'),
                            ('info', 'Info'),
                            ('destructive', 'Destructive'),
                        ],
                        default='primary', max_length=12,
                        verbose_name='Thème couleur du CTA'),
                ),
                ('message_relance', models.TextField(
                    blank=True, default='', verbose_name='Message de relance')),
                (
                    'company',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='innovation_settings',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Paramètres innovation',
                'verbose_name_plural': 'Paramètres innovation',
            },
        ),
    ]
