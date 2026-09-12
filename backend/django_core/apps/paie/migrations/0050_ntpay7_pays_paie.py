# NTPAY7 — `PaysPaie` + dispatcher de calcul par pays.
#
# Le moteur était 100 % marocain en dur. `PaysPaie` introduit le pays comme
# donnée (code ISO, devise, clé de moteur) et `ProfilPaie.pays` le rattache au
# salarié. RÉTRO-COMPATIBILITÉ STRICTE : le champ est NULLABLE et vaut NULL
# pour tous les profils existants — `services.calculer_bulletin` délègue alors
# au moteur marocain `calculer_bulletin_ma`, au centime près.
#
# Migration purement ADDITIVE : une nouvelle table + un champ nullable.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0049_ntpay5_depot_declaratif'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaysPaie',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('code_iso', models.CharField(
                    choices=[
                        ('MA', 'Maroc'),
                        ('FR', 'France'),
                        ('SN', 'Sénégal'),
                        ('CI', "Côte d'Ivoire"),
                    ],
                    max_length=2, verbose_name='Code ISO')),
                ('libelle', models.CharField(
                    max_length=80, verbose_name='Libellé')),
                ('devise', models.CharField(
                    default='MAD', max_length=3, verbose_name='Devise')),
                ('moteur', models.CharField(
                    blank=True, default='', max_length=12,
                    verbose_name='Moteur de calcul')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='paie_pays', to='authentication.company',
                    verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Pays de paie',
                'verbose_name_plural': 'Pays de paie',
                'ordering': ['code_iso'],
                'unique_together': {('company', 'code_iso')},
            },
        ),
        migrations.AddField(
            model_name='profilpaie',
            name='pays',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='profils', to='paie.payspaie',
                verbose_name='Pays de paie'),
        ),
    ]
