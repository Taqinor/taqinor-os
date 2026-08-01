# AOF18 — GÉOMÉTRIE du projet : ``ao_batiment`` + ``ao_toiture``.
#
# Deux tables NEUVES (aucun impact sur les tables ``compta_*`` héritées). La
# toiture stocke son enveloppe en repère LOCAL MÉTRIQUE (``contour_local_m``,
# liste de ``[x, y]`` en mètres) : le nom du champ porte l'unité ET l'ordre des
# axes, précisément pour rendre DÉTECTABLE l'inversion lat/lng constatée entre
# l'outil de tracé (``[lng, lat]``) et le lead CRM (``[lat, lng]``). La
# conversion depuis/vers les degrés vit à la FRONTIÈRE (AOF19).
#
# ``surface_m2`` est une valeur CALCULÉE persistée (recalculée à chaque
# écriture) et non une saisie ; les agrégats du projet (surface totale,
# engagement par bâtiment) restent des propriétés calculées, jamais des
# colonnes recopiées.

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0003_projet_ao'),
        ('authentication', '0026_ntmob6_customuser_mobile_home_route'),
    ]

    operations = [
        migrations.CreateModel(
            name='BatimentAO',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(max_length=30, verbose_name='Code du bâtiment')),
                ('designation', models.CharField(blank=True, default='', max_length=255, verbose_name='Désignation')),
                ('ordre', models.PositiveIntegerField(default=1, verbose_name='Ordre')),
                ('engagement_modules', models.PositiveIntegerField(blank=True, null=True, verbose_name='Engagement (modules)')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Notes')),
                ('appel_offre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batiments', to='ao.appeloffre', verbose_name="Appel d'offres")),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batiments_ao', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Bâtiment (AO)',
                'verbose_name_plural': 'Bâtiments (AO)',
                'db_table': 'ao_batiment',
                'ordering': ['appel_offre', 'ordre', 'code'],
            },
        ),
        migrations.CreateModel(
            name='ToitureAO',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code_document', models.CharField(blank=True, default='', max_length=20, verbose_name='Code de la planche (05H, 06H, 06I…)')),
                ('designation', models.CharField(blank=True, default='', max_length=255, verbose_name='Désignation')),
                ('forme', models.CharField(choices=[('rectangle', 'Rectangle'), ('polygone', 'Polygone'), ('forme_l', 'Forme en L'), ('arc', 'Arc / aile courbe')], default='rectangle', max_length=12, verbose_name='Forme')),
                ('contour_local_m', models.JSONField(blank=True, default=list, verbose_name='Contour local [x, y] en mètres')),
                ('angle_nord_deg', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6, verbose_name='Azimut du repère local vs Nord (°)')),
                ('rayon_ext_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='Rayon extérieur (m)')),
                ('largeur_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='Largeur de la bande (m)')),
                ('arc_segments', models.JSONField(blank=True, default=list, verbose_name="Segments de l'arc (découpage)")),
                ('murets', models.JSONField(blank=True, default=list, verbose_name='Murets / refends')),
                ('niveau', models.IntegerField(default=0, verbose_name='Niveau')),
                ('altitude_m', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Altitude / hauteur du plan (m)')),
                ('type_couverture', models.CharField(choices=[('bac_acier', 'Bac acier'), ('dalle_beton', 'Dalle béton'), ('tuile', 'Tuile'), ('membrane', 'Membrane / étanchéité'), ('fibrociment', 'Fibrociment'), ('autre', 'Autre')], default='autre', max_length=14, verbose_name='Type de couverture')),
                ('contraintes_structure', models.TextField(blank=True, default='', verbose_name='Contraintes de structure')),
                ('surface_m2', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=12, verbose_name='Surface calculée (m²)')),
                ('batiment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='toitures', to='ao.batimentao', verbose_name='Bâtiment')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='toitures_ao', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Toiture (AO)',
                'verbose_name_plural': 'Toitures (AO)',
                'db_table': 'ao_toiture',
                'ordering': ['batiment', 'code_document', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='batimentao',
            index=models.Index(fields=['company', 'appel_offre'], name='ao_batiment_company_974dc7_idx'),
        ),
        migrations.AddConstraint(
            model_name='batimentao',
            constraint=models.UniqueConstraint(fields=('company', 'appel_offre', 'code'), name='uniq_batiment_ao_code'),
        ),
        migrations.AddIndex(
            model_name='toitureao',
            index=models.Index(fields=['company', 'batiment'], name='ao_toiture_company_128213_idx'),
        ),
    ]
