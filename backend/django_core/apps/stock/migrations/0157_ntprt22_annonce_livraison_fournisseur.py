# NTPRT22 — ASN entrant : annonce de livraison déposée par le fournisseur sur
# un bon de commande. Additive : une nouvelle table, aucune colonne existante
# touchée. Le modèle est INFORMATIF (aucun mouvement de stock).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0005_aud208_montant_positif'),
        ('authentication', '0001_initial'),
        ('stock', '0156_ntprt3_compte_fournisseur_portail'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnnonceLivraisonFournisseur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_expedition', models.DateField(blank=True, null=True, verbose_name="Date d'expédition")),
                ('date_livraison_prevue', models.DateField(blank=True, null=True, verbose_name='Date de livraison prévue')),
                ('transporteur', models.CharField(blank=True, default='', max_length=120, verbose_name='Transporteur')),
                ('numero_suivi', models.CharField(blank=True, default='', max_length=100, verbose_name='Numéro de suivi')),
                ('lignes', models.JSONField(blank=True, default=list, help_text="Quantités annoncées par produit. Jamais un prix : le fournisseur annonce ce qu'il envoie, pas ce qu'il facture.", verbose_name='Quantités annoncées')),
                ('statut', models.CharField(choices=[('annoncee', 'Annoncée'), ('en_transit', 'En transit'), ('livree', 'Livrée')], default='annoncee', max_length=20, verbose_name='Statut')),
                ('bon_commande_fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='annonces_livraison', to='achats.boncommandefournisseur', verbose_name='Bon de commande')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Annonce de livraison fournisseur',
                'verbose_name_plural': 'Annonces de livraison fournisseur',
                'ordering': ['-date_expedition', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='annoncelivraisonfournisseur',
            index=models.Index(fields=['company', 'statut'],
                               name='idx_asnfou_co_statut'),
        ),
        migrations.AddIndex(
            model_name='annoncelivraisonfournisseur',
            index=models.Index(fields=['bon_commande_fournisseur', 'statut'],
                               name='idx_asnfou_bcf_statut'),
        ),
    ]
