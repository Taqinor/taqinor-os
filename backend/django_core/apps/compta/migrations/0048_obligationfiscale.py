"""XACC9 — Calendrier des obligations fiscales.

Additif : nouveau modèle, aucune donnée existante touchée.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0047_modeleecriture_abonnementecriture'),
    ]

    operations = [
        migrations.CreateModel(
            name='ObligationFiscale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_obligation', models.CharField(choices=[('tva', 'TVA'), ('is_acompte', 'Acompte IS'), ('ras', 'Retenue à la source'), ('timbre', 'Droit de timbre'), ('etat_9421', 'État 9421'), ('liasse_fiscale', 'Liasse fiscale')], max_length=20, verbose_name='Type')),
                ('periode_debut', models.DateField(verbose_name='Début de période')),
                ('periode_fin', models.DateField(verbose_name='Fin de période')),
                ('date_limite', models.DateField(verbose_name='Date limite')),
                ('statut', models.CharField(choices=[('a_preparer', 'À préparer'), ('deposee', 'Déposée'), ('payee', 'Payée')], default='a_preparer', max_length=12, verbose_name='Statut')),
                ('libelle', models.CharField(blank=True, default='', max_length=200, verbose_name='Libellé')),
                ('source_type', models.CharField(blank=True, default='', max_length=30, verbose_name='Type de déclaration source')),
                ('source_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de la déclaration source')),
                ('rappel_envoye_le', models.DateTimeField(blank=True, null=True, verbose_name='Rappel envoyé le')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='obligations_fiscales', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Obligation fiscale',
                'verbose_name_plural': 'Obligations fiscales',
                'ordering': ['date_limite', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='obligationfiscale',
            constraint=models.UniqueConstraint(fields=('company', 'type_obligation', 'periode_debut', 'periode_fin'), name='uniq_obligation_fiscale_periode'),
        ),
    ]
