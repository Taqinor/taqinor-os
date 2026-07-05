"""XACC15 — Charges constatées d'avance (étalement des charges prépayées).

Additif : ``ChargeConstateeAvance`` (échéancier d'étalement, origine 3491) et
``DotationEtalement`` (dotation mensuelle, une ligne par mois, postable au
grand livre 6xx/3491). Aucun modèle existant n'est modifié.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0051_emprunt_echeanceemprunt'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChargeConstateeAvance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(blank=True, default='', max_length=80, verbose_name='Référence')),
                ('libelle', models.CharField(blank=True, default='', max_length=200, verbose_name='Libellé')),
                ('facture_fournisseur_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de la facture fournisseur')),
                ('montant_total', models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Montant total à étaler')),
                ('date_debut', models.DateField(verbose_name="Début de l'étalement")),
                ('nb_mois', models.PositiveIntegerField(default=12, verbose_name="Nombre de mois d'étalement")),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='charges_constatees_avance', to='authentication.company', verbose_name='Société')),
                ('compte_charge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='charges_constatees_avance', to='compta.comptecomptable', verbose_name='Compte de charge (classe 6)')),
                ('ecriture_origine', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='charges_constatees_avance_origine', to='compta.ecriturecomptable', verbose_name="Écriture d'origine (3491)")),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='charges_constatees_avance_creees', to=settings.AUTH_USER_MODEL, verbose_name='Créée par')),
            ],
            options={
                'verbose_name': "Charge constatée d'avance",
                'verbose_name_plural': "Charges constatées d'avance",
                'ordering': ['-date_debut', '-id'],
            },
        ),
        migrations.CreateModel(
            name='DotationEtalement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.PositiveIntegerField(verbose_name='Rang (1..N)')),
                ('date_dotation', models.DateField(verbose_name='Date de dotation')),
                ('montant', models.DecimalField(decimal_places=2, default='0.00', max_digits=14, verbose_name='Dotation')),
                ('posted', models.BooleanField(default=False, verbose_name='Postée au grand livre')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dotations_etalement', to='authentication.company', verbose_name='Société')),
                ('charge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dotations', to='compta.chargeconstateeavance', verbose_name="Charge constatée d'avance")),
                ('ecriture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dotations_etalement', to='compta.ecriturecomptable', verbose_name='Écriture comptable')),
            ],
            options={
                'verbose_name': "Dotation d'étalement",
                'verbose_name_plural': "Dotations d'étalement",
                'ordering': ['charge_id', 'numero'],
            },
        ),
        migrations.AddConstraint(
            model_name='chargeconstateeavance',
            constraint=models.UniqueConstraint(condition=models.Q(('reference__gt', '')), fields=('company', 'reference'), name='uniq_cca_reference'),
        ),
        migrations.AddConstraint(
            model_name='dotationetalement',
            constraint=models.UniqueConstraint(fields=('charge', 'numero'), name='uniq_dotation_etalement_charge_numero'),
        ),
    ]
