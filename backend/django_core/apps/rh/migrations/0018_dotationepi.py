# Generated 2026-06-29 — FG178 Catalogue & dotation EPI par employé

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0017_visitemedicale"),
    ]

    operations = [
        migrations.CreateModel(
            name='EpiCatalogue',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('type_epi', models.CharField(
                    choices=[
                        ('casque', 'Casque'),
                        ('harnais', 'Harnais antichute'),
                        ('gants_isolants', 'Gants isolants'),
                        ('chaussures', 'Chaussures de sécurité'),
                        ('lunettes', 'Lunettes de protection'),
                        ('autre', 'Autre'),
                    ],
                    default='casque', max_length=20,
                    verbose_name="Type d'EPI")),
                ('designation', models.CharField(
                    max_length=160, verbose_name='Désignation')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_epi_catalogue',
                    to='authentication.company',
                    verbose_name='Société')),
            ],
            options={
                'verbose_name': 'EPI (catalogue)',
                'verbose_name_plural': 'EPI (catalogue)',
                'ordering': ['type_epi', 'designation'],
            },
        ),
        migrations.CreateModel(
            name='DotationEpi',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('taille', models.CharField(
                    blank=True, default='', max_length=20,
                    verbose_name='Taille')),
                ('date_dotation', models.DateField(
                    blank=True, null=True,
                    verbose_name='Date de dotation')),
                ('date_renouvellement', models.DateField(
                    blank=True, null=True,
                    verbose_name='Date de renouvellement (échéance)')),
                ('quantite', models.PositiveIntegerField(
                    default=1, verbose_name='Quantité')),
                ('note', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Note')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_dotations_epi',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dotations_epi',
                    to='rh.dossieremploye',
                    verbose_name='Employé')),
                ('epi', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='dotations',
                    to='rh.epicatalogue',
                    verbose_name='EPI')),
            ],
            options={
                'verbose_name': 'Dotation EPI',
                'verbose_name_plural': 'Dotations EPI',
                'ordering': ['employe', 'epi'],
            },
        ),
        migrations.AddIndex(
            model_name='epicatalogue',
            index=models.Index(
                fields=['company', 'type_epi'],
                name='rh_epicat_comp_type_idx'),
        ),
        migrations.AddIndex(
            model_name='dotationepi',
            index=models.Index(
                fields=['company', 'employe'],
                name='rh_dotepi_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='dotationepi',
            index=models.Index(
                fields=['company', 'date_renouvellement'],
                name='rh_dotepi_comp_renouv_idx'),
        ),
    ]
