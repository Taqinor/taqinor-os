# NTSCM6 — PolitiqueStock (min/max, ROP, stock de securite par produit).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0085_ntadm2_produit_entite'),
        ('scm', '0003_classificationabc'),
    ]

    operations = [
        migrations.CreateModel(
            name='PolitiqueStock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('classe_abc', models.CharField(blank=True, default='', max_length=1, verbose_name='Classe ABC (snapshot)')),
                ('service_level_pct', models.DecimalField(decimal_places=2, default=95, max_digits=5, verbose_name='Niveau de service (%)')),
                ('stock_min', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Stock min')),
                ('stock_max', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Stock max')),
                ('point_commande', models.DecimalField(decimal_places=2, default=0, help_text='Dérivé : conso_moy × délai fournisseur moyen + stock de sécurité.', max_digits=12, verbose_name='Point de commande (ROP)')),
                ('stock_securite_calcule', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Stock de sécurité calculé')),
                ('stock_securite_manuel', models.DecimalField(blank=True, decimal_places=2, help_text='Prime toujours sur le calculé quand renseigné.', max_digits=12, null=True, verbose_name='Stock de sécurité (override manuel)')),
                ('revise_le', models.DateTimeField(blank=True, null=True, verbose_name='Révisé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scm_politiques_stock', to='authentication.company', verbose_name='Société')),
                ('produit', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='scm_politique_stock', to='stock.produit', verbose_name='Produit')),
            ],
            options={
                'verbose_name': 'Politique de stock',
                'verbose_name_plural': 'Politiques de stock',
                'ordering': ['produit_id'],
            },
        ),
    ]
