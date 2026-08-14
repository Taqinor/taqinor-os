# NTWMS34 — contrôle qualité à réception avec échantillonnage.
# Additive : deux nouvelles tables, aucune colonne touchée sur l'existant.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0003_protect_fournisseur_prix'),
        ('authentication', '0028_company_tours_actifs'),
        ('stock', '0106_merge_20260814_1422'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanEchantillonnage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('taux_echantillon_pct', models.PositiveIntegerField(default=0, help_text='Part des unités reçues à contrôler (0 = aucun contrôle exigé, comportement historique).')),
                ('actif', models.BooleanField(default=True)),
                ('note', models.TextField(blank=True, default='')),
                ('categorie', models.ForeignKey(blank=True, help_text='Catégorie visée. Vide = plan par défaut de la société.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='plans_echantillonnage', to='stock.categorie')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Plan d'échantillonnage à réception",
                'verbose_name_plural': "Plans d'échantillonnage à réception",
                'ordering': ['categorie_id', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ControleReception',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resultat', models.CharField(choices=[('conforme', 'Conforme'), ('non_conforme', 'Non conforme')], max_length=20)),
                ('unites_controlees', models.PositiveIntegerField(default=0)),
                ('unites_attendues', models.PositiveIntegerField(default=0, help_text="Échantillon exigé par le plan au moment de la saisie.")),
                ('observation', models.TextField(blank=True, default='')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('controle_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='controles_reception_stock', to=settings.AUTH_USER_MODEL)),
                ('reception', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='controle_reception_stock', to='achats.receptionfournisseur')),
            ],
            options={
                'verbose_name': 'Contrôle qualité de réception',
                'verbose_name_plural': 'Contrôles qualité de réception',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['company', 'resultat'], name='idx_ctrlrecep_co_resultat')],
            },
        ),
        migrations.AddConstraint(
            model_name='planechantillonnage',
            constraint=models.UniqueConstraint(condition=models.Q(('categorie__isnull', False)), fields=('company', 'categorie'), name='stock_planechant_company_categorie_uniq'),
        ),
        migrations.AddConstraint(
            model_name='planechantillonnage',
            constraint=models.UniqueConstraint(condition=models.Q(('categorie__isnull', True)), fields=('company',), name='stock_planechant_company_defaut_uniq'),
        ),
    ]
