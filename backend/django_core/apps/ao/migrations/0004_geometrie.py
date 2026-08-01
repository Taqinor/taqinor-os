# AOF18 + AOF20 — GÉOMÉTRIE du projet : ``ao_batiment``, ``ao_toiture`` et
# ``ao_plan_source``.
#
# Trois tables NEUVES (aucun impact sur les tables ``compta_*`` héritées).
#
#   * AOF18 — la toiture stocke son enveloppe en repère LOCAL MÉTRIQUE
#     (``contour_local_m``, liste de ``[x, y]`` en mètres) : le nom du champ
#     porte l'unité ET l'ordre des axes, précisément pour rendre DÉTECTABLE
#     l'inversion lat/lng constatée entre l'outil de tracé (``[lng, lat]``) et
#     le lead CRM (``[lat, lng]``). La conversion vit à la frontière (AOF19).
#     ``surface_m2`` est une valeur CALCULÉE persistée, jamais une saisie ; les
#     agrégats du projet restent des propriétés, jamais des colonnes recopiées.
#   * AOF20 — ``PlanSource`` : les TROIS portes d'entrée du plan de toiture
#     (plan fourni / tracé manuel / reprise de carte) sont UN CHAMP
#     (``origine``), pas trois chemins de données. Le fichier passe par
#     ``records.Attachment`` (FK nullable) — JAMAIS un ``FileField`` (garde
#     ARC26). Plusieurs supports sont CUMULABLES sur une même toiture : c'est
#     ce qui rend naturel le cas « plan fourni MAIS à compléter ».

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0003_projet_ao'),
        ('authentication', '0026_ntmob6_customuser_mobile_home_route'),
        ('records', '0013_vx210_snooze_trigger_event'),
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
        migrations.CreateModel(
            name='PlanSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('origine', models.CharField(choices=[('plan_fourni', 'Plan fourni (PDF/DXF/image)'), ('trace_manuel', 'Tracé manuel'), ('carte', 'Reprise depuis une carte')], default='plan_fourni', max_length=14, verbose_name="Porte d'entrée")),
                ('type_fichier', models.CharField(choices=[('pdf', 'PDF'), ('dxf', 'DXF'), ('image', 'Image'), ('aucun', 'Aucun fichier')], default='aucun', max_length=8, verbose_name='Type de fichier')),
                ('page', models.PositiveIntegerField(default=1, verbose_name='Page')),
                ('calib_point_a_px', models.JSONField(blank=True, default=list, verbose_name='Point A [x, y] en pixels')),
                ('calib_point_b_px', models.JSONField(blank=True, default=list, verbose_name='Point B [x, y] en pixels')),
                ('calib_distance_reelle_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='Distance réelle A→B (m)')),
                ('echelle_m_par_px', models.DecimalField(blank=True, decimal_places=8, max_digits=14, null=True, verbose_name='Échelle (m/px)')),
                ('origine_px', models.JSONField(blank=True, default=list, verbose_name='Origine du repère [x, y] en pixels')),
                ('rotation_deg', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6, verbose_name='Rotation (°)')),
                ('miroir_x', models.BooleanField(default=False, verbose_name='Miroir X')),
                ('miroir_y', models.BooleanField(default=False, verbose_name='Miroir Y')),
                ('empreinte_sha256', models.CharField(blank=True, default='', max_length=64, verbose_name='Empreinte SHA-256 du fichier')),
                ('etat', models.CharField(choices=[('brut', 'Brut (non calibré)'), ('calibre', 'Calibré'), ('vectorise', 'Vectorisé')], default='brut', max_length=10, verbose_name='État')),
                ('fourni_par', models.CharField(blank=True, default='', max_length=255, verbose_name='Fourni par')),
                ('attachment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='plans_source_ao', to='records.attachment', verbose_name='Fichier (MinIO)')),
                ('batiment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='plans_source', to='ao.batimentao', verbose_name='Bâtiment')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plans_source_ao', to='authentication.company', verbose_name='Société')),
                ('toiture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='plans_source', to='ao.toitureao', verbose_name='Toiture')),
            ],
            options={
                'verbose_name': 'Support de plan (AO)',
                'verbose_name_plural': 'Supports de plan (AO)',
                'db_table': 'ao_plan_source',
                'ordering': ['toiture', 'batiment', 'id'],
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
        migrations.AddIndex(
            model_name='plansource',
            index=models.Index(fields=['company', 'toiture'], name='ao_plan_sou_company_4981b3_idx'),
        ),
        migrations.AddIndex(
            model_name='plansource',
            index=models.Index(fields=['company', 'empreinte_sha256'], name='ao_plan_sou_company_77f0d6_idx'),
        ),
    ]
