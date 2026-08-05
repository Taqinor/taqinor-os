import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """N100(e) — registre de facturation de LICENCE (côté éditeur).

    Purement additif. Sans rapport avec les factures MÉTIER du tenant à ses
    propres clients (`apps.ventes`) : les deux ne se mélangent jamais.
    """

    dependencies = [
        ('adminops', '0005_ntadm18_annonce_produit'),
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
    ]

    operations = [
        migrations.CreateModel(
            name='FactureLicence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reference', models.CharField(blank=True, default='', max_length=40, verbose_name='Référence')),
                ('periode', models.DateField(verbose_name='Période facturée')),
                ('plan_code', models.CharField(blank=True, default='', max_length=40, verbose_name='Plan (snapshot)')),
                ('montant_ht', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Montant HT')),
                ('tva', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='TVA')),
                ('montant_ttc', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Montant TTC')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('emise', 'Émise'), ('payee', 'Payée')], default='brouillon', max_length=12, verbose_name='Statut')),
                ('date_emission', models.DateField(blank=True, null=True)),
                ('date_paiement', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, default='', verbose_name='Notes')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Facture de licence',
                'verbose_name_plural': 'Factures de licence',
                'ordering': ['-periode', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='facturelicence',
            index=models.Index(
                fields=['company', 'statut'], name='adminops_lic_co_statut'),
        ),
    ]
