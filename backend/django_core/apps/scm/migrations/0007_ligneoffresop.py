# NTSCM14 — LigneOffreSOP (snapshot capacite/offre par cycle S&OP).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0085_ntadm2_produit_entite'),
        ('scm', '0006_lignedemandesop'),
    ]

    operations = [
        migrations.CreateModel(
            name='LigneOffreSOP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('stock_disponible_snapshot', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Stock disponible (snapshot)')),
                ('capacite_appro_fournisseur_estimee', models.DecimalField(decimal_places=2, default=0, help_text='Quantité déjà en commande (BCF brouillon/envoyé) chez un fournisseur.', max_digits=12, verbose_name='Capacité appro fournisseur estimée')),
                ('ecart_offre_demande', models.DecimalField(decimal_places=2, default=0, help_text='Négatif = pénurie prévisible sur ce produit pour ce cycle.', max_digits=12, verbose_name='Écart offre − demande')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scm_lignes_offre_sop', to='authentication.company', verbose_name='Société')),
                ('cycle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_offre', to='scm.cycleplanificationsop', verbose_name='Cycle S&OP')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scm_lignes_offre_sop', to='stock.produit', verbose_name='Produit')),
            ],
            options={
                'verbose_name': "Ligne d'offre S&OP",
                'verbose_name_plural': "Lignes d'offre S&OP",
                'ordering': ['ecart_offre_demande', 'produit_id'],
            },
        ),
        migrations.AddConstraint(
            model_name='ligneoffresop',
            constraint=models.UniqueConstraint(fields=('cycle', 'produit'), name='uniq_scm_ligne_offre_sop_produit'),
        ),
    ]
