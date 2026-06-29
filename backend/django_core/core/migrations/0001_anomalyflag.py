import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnomalyFlag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.CharField(choices=[('stock', 'Stock'), ('paiement', 'Paiement'), ('fraude', 'Fraude'), ('autre', 'Autre')], default='autre', max_length=20, verbose_name='Catégorie')),
                ('severity', models.CharField(choices=[('info', 'Information'), ('avertissement', 'Avertissement'), ('critique', 'Critique')], default='avertissement', max_length=20, verbose_name='Gravité')),
                ('status', models.CharField(choices=[('ouvert', 'Ouvert'), ('examine', "En cours d'examen"), ('ignore', 'Ignoré'), ('resolu', 'Résolu')], default='ouvert', max_length=20, verbose_name='Statut')),
                ('subject_type', models.CharField(blank=True, help_text='Libellé app.Modèle, ex. « stock.Produit » (générique).', max_length=100, verbose_name='Type de sujet')),
                ('subject_id', models.CharField(blank=True, max_length=64, verbose_name='Identifiant du sujet')),
                ('metric', models.CharField(blank=True, max_length=80, verbose_name='Métrique')),
                ('value', models.FloatField(blank=True, null=True, verbose_name='Valeur observée')),
                ('expected', models.FloatField(blank=True, null=True, verbose_name='Valeur attendue')),
                ('score', models.FloatField(blank=True, help_text='Écart standardisé (z-score) ou amplitude relative.', null=True, verbose_name="Score d'aberration")),
                ('message', models.CharField(max_length=255, verbose_name='Message')),
                ('detail', models.JSONField(blank=True, default=dict, verbose_name='Détail')),
                ('detected_at', models.DateTimeField(auto_now_add=True, verbose_name='Détecté le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='anomaly_flags', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Anomalie détectée',
                'verbose_name_plural': 'Anomalies détectées',
                'ordering': ['-detected_at'],
            },
        ),
        migrations.AddIndex(
            model_name='anomalyflag',
            index=models.Index(fields=['company', 'status'], name='anomaly_company_status_idx'),
        ),
        migrations.AddIndex(
            model_name='anomalyflag',
            index=models.Index(fields=['company', 'category'], name='anomaly_company_cat_idx'),
        ),
    ]
