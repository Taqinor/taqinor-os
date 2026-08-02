# AOF26 + AOF27 + AOF28 — CALEPINAGE : ``ao_kit_calepinage``,
# ``ao_preset_calepinage``, ``ao_variante_calepinage``.
#
#   * AOF26 — ``KitCalepinage`` : la brique de pose. Le moteur étant PARTAGÉ
#     avec les villas, une villa est simplement un kit à 1 module. AUCUN prix
#     dans le kit : il vient du ``Produit`` lié (string-FK ``stock.Produit``,
#     jamais un import cross-app).
#   * AOF27 — ``PresetCalepinage`` : jeux de paramètres NOMMÉS. La toiture
#     gagne le preset appliqué ET un instantané de ses paramètres — sans
#     l'instantané, éditer un preset plus tard réécrirait l'histoire d'un
#     calepinage déjà publié.
#   * AOF28 — ``VarianteCalepinage`` : le modèle PIVOT (``role`` + ``parent``),
#     pas trois tables jumelles. La PREUVE est un CHAMP, et une contrainte
#     partielle en base garantit UNE SEULE variante retenue par toiture.

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0004_geometrie'),
        ('authentication', '0026_ntmob6_customuser_mobile_home_route'),
        ('core', '0041_ntext16_vuepersonnalisee'),
        ('stock', '0083_ntprt25_fournisseur_statut_validation'),
    ]

    operations = [
        migrations.AddField(
            model_name='toitureao',
            name='parametres_calepinage',
            field=models.JSONField(blank=True, default=dict, verbose_name='Paramètres de calepinage'),
        ),
        migrations.CreateModel(
            name='PresetCalepinage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=120, verbose_name='Nom du preset')),
                ('portee', models.CharField(choices=[('villa', 'Villa'), ('ao', "Appel d'offres"), ('societe', 'Société (tous usages)')], default='ao', max_length=10, verbose_name='Portée')),
                ('parametres', models.JSONField(blank=True, default=dict, verbose_name='Paramètres')),
                ('par_defaut', models.BooleanField(default=False, verbose_name='Preset par défaut')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='presets_calepinage', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Preset de calepinage (AO)',
                'verbose_name_plural': 'Presets de calepinage (AO)',
                'db_table': 'ao_preset_calepinage',
                'ordering': ['portee', 'nom'],
            },
        ),
        migrations.AddField(
            model_name='toitureao',
            name='preset_applique',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='toitures', to='ao.presetcalepinage', verbose_name='Preset appliqué'),
        ),
        migrations.CreateModel(
            name='VarianteCalepinage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('role', models.CharField(choices=[('RETENUE', 'Variante retenue'), ('ALTERNATIVE', 'Alternative comparée'), ('SENSIBILITE', 'Sensibilité défavorable'), ('MARCHE', "Marche de l'échelle de décomposition")], default='RETENUE', max_length=12, verbose_name='Rôle')),
                ('nom', models.CharField(max_length=255, verbose_name='Nom')),
                ('params', models.JSONField(blank=True, default=dict, verbose_name="Paramètres d'entrée")),
                ('entree_hash', models.CharField(blank=True, default='', max_length=64, verbose_name="Empreinte d'entrée")),
                ('resultat', models.JSONField(blank=True, default=dict, verbose_name='Résultat')),
                ('preuve', models.JSONField(blank=True, default=dict, verbose_name='Preuve du calcul')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('calculee', 'Calculée'), ('publiable', 'Publiable'), ('perime', 'Périmée')], default='brouillon', max_length=10, verbose_name='Statut')),
                ('est_retenue', models.BooleanField(default=False, verbose_name='Variante retenue de la toiture')),
                ('est_recommandee', models.BooleanField(default=False, verbose_name='Recommandée')),
                ('score', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='Score')),
                ('justification', models.TextField(blank=True, default='', verbose_name='Justification')),
                ('version_moteur', models.CharField(blank=True, default='', max_length=40, verbose_name='Version du moteur')),
                ('appel_offre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variantes_calepinage', to='ao.appeloffre', verbose_name="Appel d'offres")),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variantes_calepinage', to='authentication.company', verbose_name='Société')),
                ('job', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='variantes_calepinage_ao', to='core.backgroundjob', verbose_name='Job de calcul')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='enfants', to='ao.variantecalepinage', verbose_name='Variante parente')),
                ('toiture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variantes', to='ao.toitureao', verbose_name='Toiture')),
            ],
            options={
                'verbose_name': 'Variante de calepinage (AO)',
                'verbose_name_plural': 'Variantes de calepinage (AO)',
                'db_table': 'ao_variante_calepinage',
                'ordering': ['toiture', 'role', '-score', 'id'],
            },
        ),
        migrations.CreateModel(
            name='KitCalepinage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(max_length=40, verbose_name='Code du kit')),
                ('libelle', models.CharField(max_length=255, verbose_name='Libellé')),
                ('mode', models.CharField(choices=[('table_dos_a_dos', 'Table dos-à-dos'), ('panneau_simple', 'Panneau simple')], default='table_dos_a_dos', max_length=16, verbose_name='Mode de pose')),
                ('modules_par_kit', models.PositiveIntegerField(default=2, verbose_name='Modules par kit')),
                ('pas_rangee_m', models.DecimalField(decimal_places=3, max_digits=8, verbose_name='Pas le long de la rangée (m)')),
                ('longueur_pente_m', models.DecimalField(decimal_places=3, max_digits=8, verbose_name='Longueur du module dans la pente (m)')),
                ('faitage_m', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=6, verbose_name='Jeu de faîtage (m)')),
                ('emprise_transversale_m', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=8, verbose_name='Emprise transversale (m)')),
                ('emprise_mesuree_m', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Emprise MESURÉE (m)')),
                ('emprise_figee', models.BooleanField(default=False, verbose_name='Emprise mesurée figée (prime)')),
                ('ecart_emprise_m', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Écart mesuré − dérivé (m)')),
                ('puissance_module_w', models.PositiveIntegerField(default=625, verbose_name='Puissance unitaire du module (W)')),
                ('inclinaison_deg', models.DecimalField(decimal_places=2, default=Decimal('15.00'), max_digits=5, verbose_name='Inclinaison (°)')),
                ('orientation_modules', models.CharField(choices=[('portrait', 'Portrait'), ('paysage', 'Paysage')], default='portrait', max_length=10, verbose_name='Orientation des modules')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kits_calepinage', to='authentication.company', verbose_name='Société')),
                ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kits_calepinage_ao', to='stock.produit', verbose_name='Produit (prix)')),
            ],
            options={
                'verbose_name': 'Kit de calepinage (AO)',
                'verbose_name_plural': 'Kits de calepinage (AO)',
                'db_table': 'ao_kit_calepinage',
                'ordering': ['code'],
                'indexes': [models.Index(fields=['company', 'actif'], name='ao_kit_cale_company_14dbc9_idx')],
                'constraints': [models.UniqueConstraint(fields=('company', 'code'), name='uniq_kit_calepinage_code')],
            },
        ),
        migrations.AddIndex(
            model_name='presetcalepinage',
            index=models.Index(fields=['company', 'portee'], name='ao_preset_c_company_5e3a9c_idx'),
        ),
        migrations.AddConstraint(
            model_name='presetcalepinage',
            constraint=models.UniqueConstraint(fields=('company', 'nom'), name='uniq_preset_calepinage_nom'),
        ),
        migrations.AddIndex(
            model_name='variantecalepinage',
            index=models.Index(fields=['company', 'appel_offre'], name='ao_variante_company_e1408c_idx'),
        ),
        migrations.AddIndex(
            model_name='variantecalepinage',
            index=models.Index(fields=['company', 'toiture', 'role'], name='ao_variante_company_be9057_idx'),
        ),
        migrations.AddIndex(
            model_name='variantecalepinage',
            index=models.Index(fields=['company', 'entree_hash'], name='ao_variante_company_5d55e8_idx'),
        ),
        migrations.AddConstraint(
            model_name='variantecalepinage',
            constraint=models.UniqueConstraint(condition=models.Q(('est_retenue', True)), fields=('toiture',), name='uniq_variante_retenue_par_toiture'),
        ),
    ]
