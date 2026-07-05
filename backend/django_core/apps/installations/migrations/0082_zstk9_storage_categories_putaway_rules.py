import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0062_xstk15_unites_conditionnements'),
        ('installations', '0081_zstk8_retour_livraison'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategorieStockage',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('nom', models.CharField(max_length=120)),
                ('poids_max_kg', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True)),
                ('qte_max', models.PositiveIntegerField(blank=True, null=True)),
                ('melange_autorise', models.BooleanField(default=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='installations_categories_stockage',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': 'Catégorie de stockage',
                'verbose_name_plural': 'Catégories de stockage',
                'ordering': ['nom'],
                'unique_together': {('company', 'nom')},
            },
        ),
        migrations.AddField(
            model_name='binlocation',
            name='categorie',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bins', to='installations.categoriestockage'),
        ),
        migrations.CreateModel(
            name='RegleRangement',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('categorie_produit', models.CharField(
                    blank=True, max_length=120, null=True)),
                ('priorite', models.PositiveIntegerField(default=100)),
                ('actif', models.BooleanField(default=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='installations_regles_rangement',
                    to='authentication.company')),
                ('produit', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='+', to='stock.produit')),
                ('bin_cible', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='regles_rangement',
                    to='installations.binlocation')),
            ],
            options={
                'verbose_name': 'Règle de rangement',
                'verbose_name_plural': 'Règles de rangement',
                'ordering': ['priorite', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='reglerangement',
            index=models.Index(
                fields=['company', 'produit'], name='idx_regrang_co_produit'),
        ),
        migrations.AddIndex(
            model_name='reglerangement',
            index=models.Index(
                fields=['company', 'actif'], name='idx_regrang_co_actif'),
        ),
    ]
