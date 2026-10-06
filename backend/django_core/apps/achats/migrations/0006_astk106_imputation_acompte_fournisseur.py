"""ASTK106 — table d'imputation acompte ↔ facture fournisseur (additive) +
recopie des imputations existantes (``AcompteFournisseur.facture_imputee`` /
``montant_consomme``) en une ligne d'imputation chacune. Revertable : le
retour arrière supprime la table (la recopie n'a rien modifié d'autre).
"""
import django.db.models.deletion
from django.db import migrations, models


def _recopier_imputations(apps, schema_editor):
    AcompteFournisseur = apps.get_model('stock', 'AcompteFournisseur')
    Imputation = apps.get_model('achats', 'ImputationAcompteFournisseur')
    # Batching (garde check_safe_migrations) : itération bornée + bulk_create
    # par tranches.
    qs = (AcompteFournisseur.objects
          .filter(facture_imputee__isnull=False, montant_consomme__gt=0)
          .values_list('pk', 'company_id', 'facture_imputee_id',
                       'montant_consomme')
          .order_by('pk'))
    batch = []
    for pk, company_id, facture_id, montant in qs.iterator(chunk_size=500):
        batch.append(Imputation(
            company_id=company_id, acompte_id=pk, facture_id=facture_id,
            montant=montant))
        if len(batch) >= 500:
            Imputation.objects.bulk_create(batch)
            batch = []
    if batch:
        Imputation.objects.bulk_create(batch)


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0005_aud208_montant_positif'),
        ('authentication', '0001_initial'),
        ('stock', '0139_aud207_protect_acomptefournisseur_bon_commande'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImputationAcompteFournisseur',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('montant', models.DecimalField(
                    decimal_places=2, max_digits=14)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('acompte', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='imputations',
                    to='stock.acomptefournisseur')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='imputations_acompte_fournisseur',
                    to='authentication.company')),
                ('facture', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='imputations_acompte',
                    to='achats.facturefournisseur')),
            ],
            options={
                'verbose_name': "Imputation d'acompte fournisseur",
                'verbose_name_plural': "Imputations d'acompte fournisseur",
                'ordering': ['date_creation', 'id'],
            },
        ),
        migrations.RunPython(
            _recopier_imputations, migrations.RunPython.noop),
    ]
