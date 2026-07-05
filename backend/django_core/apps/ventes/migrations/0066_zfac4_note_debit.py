import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('crm', '0001_initial'),
        ('stock', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ventes', '0065_zfac7_paiement_cheque'),
    ]

    operations = [
        migrations.CreateModel(
            name='NoteDebit',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('reference', models.CharField(max_length=50)),
                ('statut', models.CharField(
                    choices=[
                        ('brouillon', 'Brouillon'),
                        ('emise', 'Émise'),
                        ('annulee', 'Annulée'),
                    ], default='brouillon', max_length=20)),
                ('motif', models.TextField(blank=True, default='')),
                ('date_emission', models.DateField(auto_now_add=True)),
                ('taux_tva', models.DecimalField(
                    decimal_places=2, default=20.0, max_digits=5)),
                ('montant_ht', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True)),
                ('montant_tva', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True)),
                ('montant_ttc', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True)),
                ('fichier_pdf', models.CharField(
                    blank=True, max_length=500, null=True)),
                ('client', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='notes_debit', to='crm.client')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notes_debit', to='authentication.company')),
                ('created_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='notes_debit_creees',
                    to=settings.AUTH_USER_MODEL)),
                ('facture', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='notes_debit', to='ventes.facture')),
            ],
            options={
                'verbose_name': 'Note de débit',
                'verbose_name_plural': 'Notes de débit',
                'ordering': ['-date_emission', '-id'],
            },
        ),
        migrations.CreateModel(
            name='LigneNoteDebit',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('designation', models.CharField(max_length=255)),
                ('quantite', models.DecimalField(
                    decimal_places=2, max_digits=10)),
                ('prix_unitaire', models.DecimalField(
                    decimal_places=2, max_digits=10)),
                ('remise', models.DecimalField(
                    decimal_places=2, default=0, max_digits=5)),
                ('taux_tva', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=5, null=True)),
                ('note_debit', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lignes', to='ventes.notedebit')),
                ('produit', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lignes_note_debit', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Ligne de note de débit',
                'verbose_name_plural': 'Lignes de note de débit',
            },
        ),
        migrations.AlterUniqueTogether(
            name='notedebit',
            unique_together={('company', 'reference')},
        ),
    ]
