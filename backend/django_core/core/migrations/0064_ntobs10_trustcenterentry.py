# NTOBS10 — page Confiance (trust center). Migration ecrite a la main
# (INTERDIT manage.py sur cette lane) ; state Django equivalent a ce que
# `makemigrations` produirait pour `core.trust_center.TrustCenterEntry`.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0063_ntobs9_maintenancewindow'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrustCenterEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('categorie', models.CharField(choices=[('certification', 'Certification'), ('sous_traitant', 'Sous-traitant'), ('localisation_donnees', 'Localisation des données'), ('politique', 'Politique')], max_length=25, verbose_name='Catégorie')),
                ('titre', models.CharField(max_length=255, verbose_name='Titre')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('document_key', models.CharField(blank=True, default='', help_text='PDF justificatif, optionnel.', max_length=500, verbose_name='Clé document (MinIO)')),
                ('dernier_audit_le', models.DateField(blank=True, null=True, verbose_name='Dernier audit le')),
                ('ordre_affichage', models.PositiveIntegerField(default=100, verbose_name='Ordre')),
            ],
            options={
                'verbose_name': 'Entrée trust center',
                'verbose_name_plural': 'Entrées trust center',
                'ordering': ['ordre_affichage', 'titre'],
            },
        ),
    ]
