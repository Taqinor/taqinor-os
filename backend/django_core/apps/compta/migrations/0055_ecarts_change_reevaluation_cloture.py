"""XACC18 — Écarts de change réalisés & réévaluation de clôture.

Additif : ``ItemOuvertDevise`` (poste ouvert en devise à suivre),
``EcartChange`` (écart RÉALISÉ au règlement, 733/633), ``ReevaluationCloture``
+ ``LigneReevaluation`` (réévaluation de clôture des items ouverts, écart
LATENT 27/17 avec extourne à l'ouverture suivante). Aucun modèle existant
n'est modifié ; sans item ouvert en devise, aucune écriture n'est générée.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0054_tauxdevise'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemOuvertDevise',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_document', models.CharField(choices=[('facture_client', 'Facture client'), ('facture_fournisseur', 'Facture fournisseur')], default='facture_client', max_length=25, verbose_name='Type de document')),
                ('document_id', models.PositiveIntegerField(verbose_name='ID du document')),
                ('document_reference', models.CharField(blank=True, default='', max_length=60, verbose_name='Référence document')),
                ('devise', models.CharField(max_length=10, verbose_name='Devise (ISO 4217)')),
                ('montant_devise', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Montant en devise')),
                ('taux_origine', models.DecimalField(decimal_places=6, max_digits=14, verbose_name="Taux d'origine (devise → MAD)")),
                ('date_origine', models.DateField(verbose_name="Date d'émission")),
                ('solde', models.BooleanField(default=False, verbose_name='Soldé (réglé intégralement)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items_ouverts_devise', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Poste ouvert en devise',
                'verbose_name_plural': 'Postes ouverts en devise',
                'ordering': ['-date_origine', '-id'],
            },
        ),
        migrations.CreateModel(
            name='EcartChange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_reglement', models.DateField(verbose_name='Date de règlement')),
                ('taux_reglement', models.DecimalField(decimal_places=6, max_digits=14, verbose_name='Taux de règlement (devise → MAD)')),
                ('difference', models.DecimalField(decimal_places=2, default='0', max_digits=14, verbose_name='Écart (signé, MAD)')),
                ('posted', models.BooleanField(default=False, verbose_name='Posté au grand livre')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ecarts_change', to='authentication.company', verbose_name='Société')),
                ('item', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ecart_change', to='compta.itemouvertdevise', verbose_name='Poste ouvert en devise')),
                ('ecriture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ecarts_change', to='compta.ecriturecomptable', verbose_name='Écriture comptable')),
            ],
            options={
                'verbose_name': 'Écart de change réalisé',
                'verbose_name_plural': 'Écarts de change réalisés',
                'ordering': ['-date_reglement', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ReevaluationCloture',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_cloture', models.DateField(verbose_name='Date de clôture')),
                ('date_extourne', models.DateField(blank=True, null=True, verbose_name="Date d'extourne (ouverture N+1)")),
                ('total_ecart', models.DecimalField(decimal_places=2, default='0', max_digits=14, verbose_name='Total des écarts latents (signé, MAD)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reevaluations_cloture', to='authentication.company', verbose_name='Société')),
                ('ecriture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reevaluations_cloture', to='compta.ecriturecomptable', verbose_name='Écriture de réévaluation')),
                ('ecriture_extourne', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reevaluations_cloture_extourne', to='compta.ecriturecomptable', verbose_name="Écriture d'extourne")),
            ],
            options={
                'verbose_name': 'Réévaluation de clôture (change)',
                'verbose_name_plural': 'Réévaluations de clôture (change)',
                'ordering': ['-date_cloture', '-id'],
            },
        ),
        migrations.CreateModel(
            name='LigneReevaluation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('taux_cloture', models.DecimalField(decimal_places=6, max_digits=14, verbose_name='Taux de clôture (devise → MAD)')),
                ('ecart', models.DecimalField(decimal_places=2, default='0', max_digits=14, verbose_name='Écart latent (signé, MAD)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_reevaluation', to='authentication.company', verbose_name='Société')),
                ('reevaluation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='compta.reevaluationcloture', verbose_name='Réévaluation')),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_reevaluation', to='compta.itemouvertdevise', verbose_name='Poste ouvert en devise')),
            ],
            options={
                'verbose_name': 'Ligne de réévaluation',
                'verbose_name_plural': 'Lignes de réévaluation',
                'ordering': ['reevaluation_id', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='itemouvertdevise',
            constraint=models.UniqueConstraint(fields=('company', 'type_document', 'document_id'), name='uniq_item_ouvert_devise_document'),
        ),
        migrations.AddConstraint(
            model_name='reevaluationcloture',
            constraint=models.UniqueConstraint(fields=('company', 'date_cloture'), name='uniq_reevaluation_cloture_par_date'),
        ),
    ]
