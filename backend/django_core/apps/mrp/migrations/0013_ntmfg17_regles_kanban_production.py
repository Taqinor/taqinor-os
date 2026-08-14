# NTMFG17 — Ordre de fabrication répétitif / kanban de réappro atelier (pull
# flow) : franchir le seuil déclenche un OF brouillon automatiquement.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mrp', '0012_ntmfg16_ordrefabrication_est_prototype'),
        ('stock', '0085_ntadm2_produit_entite'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReglesKanbanProduction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quantite_lot', models.DecimalField(decimal_places=2, default=1, max_digits=12, verbose_name='Quantité par lot')),
                ('seuil_declenchement', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Seuil de déclenchement')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('poste_charge_defaut', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='regles_kanban', to='mrp.postedecharge', verbose_name='Poste de charge par défaut')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mrp_regles_kanban', to='stock.produit', verbose_name='Produit')),
            ],
            options={
                'verbose_name': 'Règle kanban de production',
                'verbose_name_plural': 'Règles kanban de production',
                'ordering': ['produit_id'],
                'indexes': [models.Index(fields=['company', 'actif'], name='mrp_kanban_co_actif_idx')],
                'constraints': [models.UniqueConstraint(fields=('company', 'produit'), name='mrp_kanban_co_produit_uniq')],
            },
        ),
    ]
