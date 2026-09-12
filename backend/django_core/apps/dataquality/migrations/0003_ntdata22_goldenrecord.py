"""NTDATA22 — `GoldenRecord` : la fiche consolidée d'une entité dédoublonnée.

Table NEUVE, purement additive : aucune colonne existante n'est touchée, aucune
donnée n'est réécrite. Générique par CHAÎNE (``entite`` + ``source_ids``) —
aucun FK dur vers une app métier, pour que `dataquality` reste consultable même
quand le module propriétaire des fiches est désactivé.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('dataquality', '0002_ntdata15_resultatqualite'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoldenRecord',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'entite',
                    models.CharField(
                        choices=[('client', 'Client'),
                                 ('fournisseur', 'Fournisseur'),
                                 ('produit', 'Produit')],
                        max_length=20, verbose_name='Entité'),
                ),
                (
                    'cle_metier',
                    models.CharField(
                        max_length=120, verbose_name='Clé métier',
                        help_text="Clé stable qui identifie l'entité (ICE, "
                                  'téléphone normalisé, référence '
                                  'catalogue).'),
                ),
                (
                    'source_ids',
                    models.JSONField(
                        blank=True, default=list,
                        verbose_name='Fiches sources',
                        help_text='Identifiants des fiches contributrices '
                                  '(ordre de lecture).'),
                ),
                (
                    'attributs',
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name='Attributs consolidés'),
                ),
                (
                    'derniere_consolidation_le',
                    models.DateTimeField(
                        blank=True, null=True,
                        verbose_name='Dernière consolidation',
                        help_text="Vide tant qu'aucune consolidation n'a "
                                  "tourné — « jamais calculé » n'est pas "
                                  '« calculé et vide ».'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Golden record',
                'verbose_name_plural': 'Golden records',
                'ordering': ['entite', 'cle_metier', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='goldenrecord',
            constraint=models.UniqueConstraint(
                fields=('company', 'entite', 'cle_metier'),
                name='uniq_goldenrecord_co_entite_cle'),
        ),
    ]
