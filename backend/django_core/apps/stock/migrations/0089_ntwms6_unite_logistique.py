"""NTWMS6 — unités logistiques : colis, palette, SSCC GS1.

Deux NOUVEAUX modèles, purement additifs (aucune table existante touchée) :
  * ``UniteLogistique`` — colis/palette adressable, SSCC 18 chiffres unique par
    société, hiérarchie palette → colis (self-FK) ;
  * ``UniteLogistiqueLigne`` — son contenu (produit, quantité, lot).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('stock', '0088_ntwms5_mouvement_bins'),
    ]

    operations = [
        migrations.CreateModel(
            name='UniteLogistique',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_unite', models.CharField(
                    choices=[('colis', 'Colis'), ('palette', 'Palette')],
                    default='colis', max_length=10)),
                ('sscc', models.CharField(
                    help_text='Serial Shipping Container Code GS1 (18 '
                              'chiffres, clé de contrôle mod-10 incluse).',
                    max_length=18)),
                ('poids_kg', models.DecimalField(
                    blank=True, decimal_places=3, max_digits=10, null=True)),
                ('dimensions', models.CharField(
                    blank=True, default='',
                    help_text='L × l × h en cm, texte libre (ex. « 120 × 80 × '
                              '145 »).',
                    max_length=60)),
                ('statut', models.CharField(
                    choices=[('en_preparation', 'En préparation'),
                             ('scelle', 'Scellé'),
                             ('expedie', 'Expédié')],
                    default='en_preparation', max_length=20)),
                ('date_scellage', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('parent', models.ForeignKey(
                    blank=True,
                    help_text='Palette contenante (vide = unité de premier '
                              'niveau).',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='enfants', to='stock.unitelogistique')),
                ('scelle_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='unites_logistiques_scellees',
                    to=settings.AUTH_USER_MODEL)),
                ('vague', models.ForeignKey(
                    blank=True,
                    help_text="Vague de prélèvement d'origine (NTWMS4), si "
                              'applicable.',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='unites_logistiques',
                    to='stock.vaguepicking')),
            ],
            options={
                'verbose_name': 'Unité logistique',
                'verbose_name_plural': 'Unités logistiques',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='UniteLogistiqueLigne',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quantite', models.PositiveIntegerField(default=0)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('ligne_picking', models.ForeignKey(
                    blank=True,
                    help_text="Ligne de vague d'origine (NTWMS4), si "
                              'applicable.',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lignes_unite_logistique',
                    to='stock.lignepicking')),
                ('lot', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lignes_unite_logistique',
                    to='stock.lotentrepot')),
                ('produit', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='lignes_unite_logistique',
                    to='stock.produit')),
                ('unite', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lignes', to='stock.unitelogistique')),
            ],
            options={
                'verbose_name': "Ligne d'unité logistique",
                'verbose_name_plural': "Lignes d'unité logistique",
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='unitelogistique',
            index=models.Index(fields=['company', 'statut'],
                               name='idx_unitelog_co_statut'),
        ),
        migrations.AddConstraint(
            model_name='unitelogistique',
            constraint=models.UniqueConstraint(
                fields=('company', 'sscc'),
                name='stock_unitelogistique_company_sscc_uniq'),
        ),
        migrations.AddIndex(
            model_name='unitelogistiqueligne',
            index=models.Index(fields=['company', 'unite'],
                               name='idx_unitelogl_co_unite'),
        ),
    ]
