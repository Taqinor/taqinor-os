"""ZACC6 — Note de frais MULTI-LIGNES : ``RapportNoteFrais`` regroupe N
``NoteFrais`` d'un même employé en UN rapport soumis/validé/remboursé en
bloc. Additif : nouveau modèle + FK nullable ``NoteFrais.rapport`` (les notes
isolées, sans rapport, gardent leur cycle actuel intact).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0076_abonnementmonitoring_facturation_resiliation'),
    ]

    operations = [
        migrations.CreateModel(
            name='RapportNoteFrais',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(blank=True, default='', max_length=50, verbose_name='Référence')),
                ('libelle', models.CharField(blank=True, default='', max_length=200, verbose_name='Libellé')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('soumis', 'Soumis'), ('valide', 'Validé'), ('rembourse', 'Remboursé')], default='brouillon', max_length=10, verbose_name='Statut')),
                ('date_validation', models.DateTimeField(blank=True, null=True, verbose_name='Validé le')),
                ('mode_remboursement', models.CharField(choices=[('virement', 'Virement bancaire'), ('especes', 'Espèces'), ('cheque', 'Chèque')], default='virement', max_length=10, verbose_name='Mode de remboursement')),
                ('date_remboursement', models.DateField(blank=True, null=True, verbose_name='Date de remboursement')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rapports_notes_frais', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rapports_notes_frais', to=settings.AUTH_USER_MODEL, verbose_name='Employé')),
                ('valide_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rapports_notes_frais_valides', to=settings.AUTH_USER_MODEL, verbose_name='Validé par')),
                ('ecriture_charge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rapports_notes_frais_charge', to='compta.ecriturecomptable', verbose_name='Écriture de charge agrégée')),
                ('compte_tresorerie', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rapports_notes_frais', to='compta.comptetresorerie', verbose_name='Compte de trésorerie (payeur)')),
                ('rembourse_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rapports_notes_frais_rembourses', to=settings.AUTH_USER_MODEL, verbose_name='Remboursé par')),
                ('ecriture_remboursement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rapports_notes_frais_remboursement', to='compta.ecriturecomptable', verbose_name='Écriture de remboursement')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rapports_notes_frais_crees', to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
            ],
            options={
                'verbose_name': 'Rapport de notes de frais',
                'verbose_name_plural': 'Rapports de notes de frais',
                'ordering': ['-date_creation', '-id'],
            },
        ),
        migrations.AddField(
            model_name='notefrais',
            name='rapport',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notes', to='compta.rapportnotefrais', verbose_name='Rapport de frais'),
        ),
        migrations.AddConstraint(
            model_name='rapportnotefrais',
            constraint=models.UniqueConstraint(condition=models.Q(('reference__gt', '')), fields=('company', 'reference'), name='uniq_rapport_note_frais_reference'),
        ),
    ]
