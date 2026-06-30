# Generated for PROJ38 -- Sous-traitance & clôture + retour d'expérience.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestion_projet', '0021_portailprojettoken'),
    ]

    operations = [
        migrations.CreateModel(
            name='SousTraitant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom / raison sociale')),
                ('specialite', models.CharField(blank=True, default='', max_length=150, verbose_name='Spécialité')),
                ('contact', models.CharField(blank=True, default='', max_length=150, verbose_name='Contact')),
                ('telephone', models.CharField(blank=True, default='', max_length=40, verbose_name='Téléphone')),
                ('email', models.EmailField(blank=True, default='', max_length=254, verbose_name='E-mail')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_sous_traitants', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Sous-traitant',
                'verbose_name_plural': 'Sous-traitants',
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.CreateModel(
            name='LotSousTraitance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=200, verbose_name='Libellé du lot')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('montant', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14, verbose_name='Montant (interne)')),
                ('statut', models.CharField(choices=[('prevu', 'Prévu'), ('en_cours', 'En cours'), ('receptionne', 'Réceptionné'), ('annule', 'Annulé')], default='prevu', max_length=12, verbose_name='Statut')),
                ('date_debut', models.DateField(blank=True, null=True, verbose_name='Date de début')),
                ('date_fin', models.DateField(blank=True, null=True, verbose_name='Date de fin')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_lots_st', to='authentication.company', verbose_name='Société')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lots_sous_traitance', to='gestion_projet.projet', verbose_name='Projet')),
                ('sous_traitant', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lots', to='gestion_projet.soustraitant', verbose_name='Sous-traitant')),
            ],
            options={
                'verbose_name': 'Lot de sous-traitance',
                'verbose_name_plural': 'Lots de sous-traitance',
                'ordering': ['projet', 'id'],
                'indexes': [models.Index(fields=['projet', 'statut'], name='gp_lotst_proj_stat_idx')],
            },
        ),
        migrations.CreateModel(
            name='ClotureProjet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_cloture', models.DateField(verbose_name='Date de clôture')),
                ('date_reception', models.DateField(blank=True, null=True, verbose_name='Date de réception')),
                ('points_positifs', models.TextField(blank=True, default='', verbose_name='Points positifs')),
                ('points_amelioration', models.TextField(blank=True, default='', verbose_name="Points d'amélioration")),
                ('recommandations', models.TextField(blank=True, default='', verbose_name='Recommandations')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('cloture_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gestion_projet_clotures', to=settings.AUTH_USER_MODEL, verbose_name='Clôturé par')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_clotures', to='authentication.company', verbose_name='Société')),
                ('projet', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='cloture', to='gestion_projet.projet', verbose_name='Projet')),
            ],
            options={
                'verbose_name': 'Clôture de projet',
                'verbose_name_plural': 'Clôtures de projet',
                'ordering': ['-date_cloture', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='soustraitant',
            constraint=models.UniqueConstraint(fields=('company', 'nom'), name='gp_soustraitant_co_nom_uniq'),
        ),
    ]
