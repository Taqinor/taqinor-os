# QJ-EQUIPE-2 (14/09/2026) — registre SERVEUR des appareils de l'équipe,
# exclusion permanente et RÉTROACTIVE du traçage T-TRACE (voir models.py
# AppareilEquipe pour la justification complète).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('crm', '0099_vta2_visites_split'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppareilEquipe',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('appareil_id', models.CharField(
                    db_index=True, max_length=64,
                    verbose_name='Identifiant d’appareil')),
                ('libelle', models.CharField(
                    blank=True, default='', max_length=200,
                    verbose_name='Libellé (ex. « Téléphone Reda »)')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('cree_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                    verbose_name='Enregistré par')),
            ],
            options={
                'verbose_name': 'Appareil équipe (exclu du traçage)',
                'verbose_name_plural': 'Appareils équipe (exclus du traçage)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='appareilequipe',
            constraint=models.UniqueConstraint(
                fields=('company', 'appareil_id'),
                name='crm_appareil_equipe_company_uniq'),
        ),
    ]
