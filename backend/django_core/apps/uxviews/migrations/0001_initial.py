import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('roles', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedView',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ecran', models.CharField(max_length=80)),
                ('nom', models.CharField(max_length=120)),
                ('configuration', models.JSONField(blank=True, default=dict)),
                (
                    'visibilite',
                    models.CharField(
                        choices=[
                            ('PERSONNELLE', 'Personnelle'),
                            ('EQUIPE', "Partagée à l'équipe"),
                        ],
                        default='PERSONNELLE', max_length=12),
                ),
                ('est_defaut_role', models.BooleanField(default=False)),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
                (
                    'owner',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='saved_views',
                        to=settings.AUTH_USER_MODEL),
                ),
                (
                    'role',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='saved_views_defaut',
                        to='roles.role'),
                ),
            ],
            options={
                'verbose_name': 'Vue sauvegardée',
                'verbose_name_plural': 'Vues sauvegardées',
                'ordering': ['ecran', 'nom'],
            },
        ),
    ]
