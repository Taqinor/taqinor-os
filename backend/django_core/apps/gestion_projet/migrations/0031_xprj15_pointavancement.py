import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('gestion_projet', '0030_xprj14_itemchecklisttache'),
    ]

    operations = [
        migrations.CreateModel(
            name='PointAvancement',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('sante', models.CharField(
                    choices=[
                        ('vert', 'Vert'), ('orange', 'Orange'),
                        ('rouge', 'Rouge'),
                    ],
                    max_length=10, verbose_name='Santé')),
                ('avancement_pct', models.PositiveSmallIntegerField(
                    default=0,
                    validators=[django.core.validators.MaxValueValidator(100)],
                    verbose_name='Avancement (%)')),
                ('realisations', models.TextField(
                    blank=True, default='', verbose_name='Réalisations')),
                ('risques', models.TextField(
                    blank=True, default='', verbose_name='Risques')),
                ('prochaines_etapes', models.TextField(
                    blank=True, default='',
                    verbose_name='Prochaines étapes')),
                ('date_point', models.DateField(
                    verbose_name='Date du point')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('auteur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                    verbose_name='Auteur')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gp_points_avancement',
                    to='authentication.company', verbose_name='Société')),
                ('projet', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='points_avancement',
                    to='gestion_projet.projet', verbose_name='Projet')),
            ],
            options={
                'verbose_name': "Point d'avancement",
                'verbose_name_plural': "Points d'avancement",
                'ordering': ['-date_point', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='pointavancement',
            index=models.Index(
                fields=['projet', '-date_point'],
                name='gp_point_av_projet_date_idx'),
        ),
    ]
