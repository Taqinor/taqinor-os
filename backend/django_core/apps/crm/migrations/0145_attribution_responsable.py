"""Attribution des leads par le responsable d'équipe (fondateur, 27/10/2026).

ADDITIF : deux colonnes sur l'équipe commerciale (défauts = comportement
inchangé) et deux tables neuves (règles d'attribution, leads en attente).
Réversible : ``migrate crm 0143``.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0035_customuser_fonction'),
        ('crm', '0144_agv1_depense_electricite_pompe'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipecommerciale',
            name='confirmation_responsable',
            field=models.BooleanField(default=False, verbose_name='Le responsable confirme chaque lead'),
        ),
        migrations.AddField(
            model_name='equipecommerciale',
            name='delai_attribution_minutes',
            field=models.PositiveIntegerField(default=5, verbose_name='Délai avant attribution automatique (minutes ouvrées)'),
        ),
        migrations.CreateModel(
            name='RegleAttribution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('villes', models.TextField(blank=True, default='')),
                ('type_installation', models.CharField(blank=True, default='', max_length=20)),
                ('source', models.CharField(blank=True, default='', max_length=20)),
                ('facture_min', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('facture_max', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('actif', models.BooleanField(default=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('equipe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regles_attribution', to='crm.equipecommerciale')),
                ('membre', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='regles_attribution', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Règle d'attribution",
                'verbose_name_plural': "Règles d'attribution",
                'ordering': ['ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='AttributionEnAttente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('raison', models.CharField(blank=True, default='', max_length=255)),
                ('echeance', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('equipe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attributions_en_attente', to='crm.equipecommerciale')),
                ('lead', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='attribution_en_attente', to='crm.lead')),
                ('proposee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attributions_proposees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Attribution en attente',
                'verbose_name_plural': 'Attributions en attente',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
