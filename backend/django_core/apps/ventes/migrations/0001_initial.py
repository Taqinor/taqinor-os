import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('crm', '0001_initial'),
        ('stock', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Devis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50, unique=True)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('envoye', 'Envoyé'), ('accepte', 'Accepté'), ('refuse', 'Refusé'), ('expire', 'Expiré')], default='brouillon', max_length=20)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_validite', models.DateField(blank=True, null=True)),
                ('taux_tva', models.DecimalField(decimal_places=2, default=20.0, max_digits=5)),
                ('remise_globale', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('note', models.TextField(blank=True, null=True)),
                ('fichier_pdf', models.CharField(blank=True, max_length=500, null=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='devis', to='crm.client')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='devis_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Devis', 'verbose_name_plural': 'Devis', 'ordering': ['-date_creation']},
        ),
        migrations.CreateModel(
            name='LigneDevis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('designation', models.CharField(max_length=255)),
                ('quantite', models.DecimalField(decimal_places=2, max_digits=10)),
                ('prix_unitaire', models.DecimalField(decimal_places=2, max_digits=10)),
                ('remise', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('devis', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='ventes.devis')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lignes_devis', to='stock.produit')),
            ],
            options={'verbose_name': 'Ligne de Devis', 'verbose_name_plural': 'Lignes de Devis'},
        ),
        migrations.CreateModel(
            name='BonCommande',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50, unique=True)),
                ('statut', models.CharField(choices=[('en_attente', 'En attente'), ('confirme', 'Confirmé'), ('livre', 'Livré'), ('annule', 'Annulé')], default='en_attente', max_length=20)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_livraison_prevue', models.DateField(blank=True, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bons_commande', to='crm.client')),
                ('devis', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bon_commande', to='ventes.devis')),
            ],
            options={'verbose_name': 'Bon de Commande', 'verbose_name_plural': 'Bons de Commande', 'ordering': ['-date_creation']},
        ),
        migrations.CreateModel(
            name='Facture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=50, unique=True)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('emise', 'Émise'), ('payee', 'Payée'), ('en_retard', 'En retard'), ('annulee', 'Annulée')], default='brouillon', max_length=20)),
                ('date_emission', models.DateField(auto_now_add=True)),
                ('date_echeance', models.DateField(blank=True, null=True)),
                ('taux_tva', models.DecimalField(decimal_places=2, default=20.0, max_digits=5)),
                ('remise_globale', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('note', models.TextField(blank=True, null=True)),
                ('fichier_pdf', models.CharField(blank=True, max_length=500, null=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='factures', to='crm.client')),
                ('bon_commande', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='facture', to='ventes.boncommande')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='factures_creees', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Facture', 'verbose_name_plural': 'Factures', 'ordering': ['-date_emission']},
        ),
        migrations.CreateModel(
            name='LigneFacture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('designation', models.CharField(max_length=255)),
                ('quantite', models.DecimalField(decimal_places=2, max_digits=10)),
                ('prix_unitaire', models.DecimalField(decimal_places=2, max_digits=10)),
                ('remise', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('facture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='ventes.facture')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lignes_facture', to='stock.produit')),
            ],
            options={'verbose_name': 'Ligne de Facture', 'verbose_name_plural': 'Lignes de Facture'},
        ),
    ]
