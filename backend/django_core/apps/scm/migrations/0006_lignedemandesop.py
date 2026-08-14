# NTSCM13 — LigneDemandeSOP (snapshot gele de la demande consensuelle par cycle S&OP).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0085_ntadm2_produit_entite'),
        ('scm', '0005_cycleplanificationsop'),
    ]

    operations = [
        migrations.CreateModel(
            name='LigneDemandeSOP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quantite_prevision_systeme', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Quantité prévision système (gelée)')),
                ('quantite_ajustee_commercial', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Quantité ajustée (commercial)')),
                ('motif_ajustement', models.TextField(blank=True, default='', verbose_name="Motif de l'ajustement")),
                ('quantite_finale', models.DecimalField(decimal_places=2, default=0, help_text='Ajustée si renseignée, sinon système — recalculée à chaque save().', max_digits=12, verbose_name='Quantité finale')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scm_lignes_demande_sop', to='authentication.company', verbose_name='Société')),
                ('cycle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_demande', to='scm.cycleplanificationsop', verbose_name='Cycle S&OP')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scm_lignes_demande_sop', to='stock.produit', verbose_name='Produit')),
            ],
            options={
                'verbose_name': 'Ligne de demande S&OP',
                'verbose_name_plural': 'Lignes de demande S&OP',
                'ordering': ['cycle_id', 'produit_id'],
            },
        ),
        migrations.AddConstraint(
            model_name='lignedemandesop',
            constraint=models.UniqueConstraint(fields=('cycle', 'produit'), name='uniq_scm_ligne_demande_sop_produit'),
        ),
    ]
