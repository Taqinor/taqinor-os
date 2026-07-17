import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0023_yhard1_encrypt_totp_secret'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Idee',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('titre', models.CharField(max_length=255, verbose_name='Titre')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('contexte', models.CharField(
                    blank=True, default='', max_length=80,
                    verbose_name='Contexte')),
                (
                    'statut',
                    models.CharField(
                        choices=[
                            ('ouvert', 'Ouvert'),
                            ('examinee', 'Examinée'),
                            ('retenue', 'Retenue'),
                            ('realisee', 'Réalisée'),
                            ('fermee', 'Fermée'),
                        ],
                        default='ouvert', max_length=10,
                        verbose_name='Statut'),
                ),
                ('votes_count', models.PositiveIntegerField(
                    default=0, verbose_name='Votes (dénormalisé)')),
                (
                    'linked_type',
                    models.CharField(
                        blank=True,
                        choices=[
                            ('devis', 'Devis'),
                            ('ticket', 'Ticket SAV'),
                            ('chantier', 'Chantier'),
                        ],
                        default='', max_length=10,
                        verbose_name='Type lié (devis/ticket/chantier)'),
                ),
                ('linked_id', models.PositiveIntegerField(
                    blank=True, null=True, verbose_name='ID lié (opaque)')),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='innovation_idees',
                        to='authentication.company', verbose_name='Société'),
                ),
                (
                    'auteur',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='idees_proposees',
                        to=settings.AUTH_USER_MODEL, verbose_name='Auteur'),
                ),
            ],
            options={
                'verbose_name': 'Idée',
                'verbose_name_plural': 'Idées',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='idee',
            index=models.Index(
                fields=['company', 'statut'], name='innovation_idee_co_statut'),
        ),
        migrations.AddIndex(
            model_name='idee',
            index=models.Index(
                fields=['company', 'contexte'], name='innovation_idee_co_ctx'),
        ),
    ]
