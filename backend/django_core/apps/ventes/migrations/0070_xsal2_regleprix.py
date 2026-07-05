# XSAL2 — Règles de prix + paliers de quantité (remises volume automatiques).
# Additive/reversible: one brand-new table.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0001_initial'),
        ('ventes', '0069_xsal1_listeprix'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegleListePrix',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categorie_nom', models.CharField(blank=True, default='', max_length=150)),
                ('marque', models.CharField(blank=True, default='', max_length=100)),
                ('type_regle', models.CharField(choices=[('prix_fixe', 'Prix fixe'), ('remise_pct', 'Remise %'), ('formule_sur_prix_vente', 'Formule sur prix de vente')], max_length=25)),
                ('valeur', models.DecimalField(decimal_places=4, help_text='Prix fixe (MAD), % de remise, ou coefficient formule selon type_regle.', max_digits=10)),
                ('quantite_min', models.DecimalField(decimal_places=2, default=1, help_text="Palier : quantité minimale pour que la règle s'applique.", max_digits=10)),
                ('priorite', models.PositiveIntegerField(default=0, help_text='Priorité explicite (plus haut = préféré) à portée égale.')),
                ('actif', models.BooleanField(default=True)),
                ('liste', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regles', to='ventes.listeprix')),
                ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='regles_liste_prix', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Règle de liste de prix',
                'verbose_name_plural': 'Règles de liste de prix',
                'ordering': ['-priorite', '-quantite_min'],
            },
        ),
    ]
