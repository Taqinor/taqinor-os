"""NTI18N51 — compteur des traductions manquantes détectées en production.

Additif : nouvelle table vide. Aucun comportement existant ne change tant
qu'aucun repli FR n'est constaté (le glossaire NTI18N25 est complet aujourd'hui,
donc la table reste vide sur une installation à jour).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
        ('parametres', '0095_companyprofile_timezone_affichage'),
    ]

    operations = [
        migrations.CreateModel(
            name='TraductionManquante',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('langue', models.CharField(
                    max_length=5, verbose_name='Langue demandée')),
                ('cle', models.CharField(
                    max_length=160, verbose_name='Clé')),
                ('occurrences', models.PositiveIntegerField(
                    default=0, verbose_name='Occurrences')),
                ('occurrences_notifiees', models.PositiveIntegerField(
                    default=0,
                    verbose_name='Occurrences déjà notifiées')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Traduction manquante',
                'verbose_name_plural': 'Traductions manquantes',
                'ordering': ['-occurrences', 'langue', 'cle'],
            },
        ),
        migrations.AddConstraint(
            model_name='traductionmanquante',
            constraint=models.UniqueConstraint(
                fields=('company', 'langue', 'cle'),
                name='param_tradmanq_unique'),
        ),
        migrations.AddIndex(
            model_name='traductionmanquante',
            index=models.Index(
                fields=['company', '-occurrences'],
                name='param_tradmanq_occ_idx'),
        ),
    ]
