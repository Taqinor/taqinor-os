"""Catalogue « Réalisations » (ordre fondateur 08/09/2026) — table nouvelle.

Purement ADDITIF : un `CreateModel` et rien d'autre. Aucune table existante
n'est touchée, aucune donnée n'est écrite (le catalogue se remplit depuis
Paramètres → Réalisations). Réversible sans perte de données préexistantes :
le retour supprime une table qui n'existait pas avant.

Les noms d'index et de contrainte sont ceux DÉCLARÉS VERBATIM dans
`models_realisations.py` (`param_realisation_co_url` /
`param_realisation_idx`) — exigence de `scripts/check_migration_safety.py`
contre la dérive modèle ↔ migration.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
        ('parametres', '0085_companyprofile_message_heure_debut'),
    ]

    operations = [
        migrations.CreateModel(
            name='Realisation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('titre', models.CharField(help_text='Nom de l\'installation, ex. « Villa à Bouskoura ».', max_length=120, verbose_name='Titre')),
                ('ville', models.CharField(help_text='Ville de la réalisation. Corrigée automatiquement quand elle est reconnue (« belksiri » → « Mechraa Bel Ksiri »).', max_length=80, verbose_name='Ville')),
                ('puissance_kwc', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name='Puissance (kWc)')),
                ('mise_en_service', models.DateField(blank=True, help_text='Mois de la mise en service (le jour est ramené au 1er).', null=True, verbose_name='Mise en service')),
                ('url_page', models.URLField(help_text='Page de la réalisation sur le site de la société, ex. .../realisations/villa-bouskoura/', max_length=300, verbose_name='Page publique')),
                ('lien_suivi', models.URLField(blank=True, default='', help_text='Suivi de production en temps réel, quand il est public.', max_length=300, verbose_name='Lien de suivi de production')),
                ('actif', models.BooleanField(default=True, help_text='Une réalisation inactive ne sert plus aucune preuve.', verbose_name='Actif')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='realisations', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Réalisation',
                'verbose_name_plural': 'Réalisations',
                'ordering': ['-mise_en_service', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='realisation',
            index=models.Index(fields=['company', 'actif'], name='param_realisation_idx'),
        ),
        migrations.AddConstraint(
            model_name='realisation',
            constraint=models.UniqueConstraint(fields=('company', 'url_page'), name='param_realisation_co_url'),
        ),
    ]
