"""FG268 — RegulatoryDossier + DossierChecklistItem.

Additive only : crée deux tables (dossier réglementaire de raccordement + ses
pièces/étapes de checklist). FK chaîne vers ``ventes.Devis`` et
``installations.Installation`` (lien chantier optionnel). Aucune table/colonne
existante modifiée ; entièrement revertable.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('installations', '0001_initial'),
        ('ventes', '0038_fg254_fichetechnique'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RegulatoryDossier',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('regime_8221', models.CharField(
                    choices=[
                        ('non_concerne', 'Non concerné (hors loi 82-21)'),
                        ('declaration_bt', 'Déclaration basse tension'),
                        ('accord_raccordement', 'Accord de raccordement'),
                        ('autorisation_anre', 'Autorisation ANRE')],
                    default='non_concerne', max_length=24,
                    verbose_name='Régime loi 82-21')),
                ('statut', models.CharField(
                    choices=[
                        ('en_constitution', 'En constitution'),
                        ('depose', 'Déposé'),
                        ('en_instruction', 'En instruction'),
                        ('complement_demande', 'Complément demandé'),
                        ('approuve', 'Approuvé'),
                        ('refuse', 'Refusé'),
                        ('comptage_pose', 'Comptage posé')],
                    default='en_constitution', max_length=20,
                    verbose_name='Statut du dossier')),
                ('operateur', models.CharField(
                    blank=True, max_length=120, null=True,
                    verbose_name='Opérateur (ONEE / régie / distributeur)')),
                ('reference_dossier', models.CharField(
                    blank=True, max_length=120, null=True,
                    verbose_name='Référence opérateur')),
                ('date_depot', models.DateField(
                    blank=True, null=True, verbose_name='Date de dépôt')),
                ('date_decision', models.DateField(
                    blank=True, null=True, verbose_name='Date de décision')),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dossiers_reglementaires',
                    to='authentication.company', verbose_name='Société')),
                ('devis', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dossiers_reglementaires',
                    to='ventes.devis', verbose_name='Devis')),
                ('chantier', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='dossiers_reglementaires_ventes',
                    to='installations.installation',
                    verbose_name='Chantier')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='dossiers_reg_crees',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Dossier réglementaire',
                'verbose_name_plural': 'Dossiers réglementaires',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DossierChecklistItem',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('code', models.CharField(
                    max_length=60, verbose_name='Code pièce/étape')),
                ('libelle', models.CharField(
                    max_length=200, verbose_name='Libellé')),
                ('etape', models.CharField(
                    choices=[('depot', 'Dépôt'), ('etude', 'Étude'),
                             ('convention', 'Convention'),
                             ('comptage', 'Comptage')],
                    default='depot', max_length=12,
                    verbose_name='Étape de soumission')),
                ('statut', models.CharField(
                    choices=[('a_faire', 'À faire'), ('en_cours', 'En cours'),
                             ('fourni', 'Fourni'), ('valide', 'Validé'),
                             ('na', 'Non applicable')],
                    default='a_faire', max_length=10,
                    verbose_name='Statut')),
                ('obligatoire', models.BooleanField(
                    default=True, verbose_name='Obligatoire')),
                ('date_echeance', models.DateField(
                    blank=True, null=True, verbose_name='Date limite')),
                ('relance_due', models.BooleanField(
                    default=False, verbose_name='Relance à faire')),
                ('ordre', models.PositiveSmallIntegerField(
                    default=0, verbose_name='Ordre')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dossier_checklist_items',
                    to='authentication.company', verbose_name='Société')),
                ('dossier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='checklist_items',
                    to='ventes.regulatorydossier', verbose_name='Dossier')),
            ],
            options={
                'verbose_name': 'Pièce de dossier',
                'verbose_name_plural': 'Pièces de dossier',
                'ordering': ['etape', 'ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='regulatorydossier',
            index=models.Index(fields=['company', 'statut'],
                               name='ix_dossier_comp_statut'),
        ),
        migrations.AddIndex(
            model_name='dossierchecklistitem',
            index=models.Index(fields=['company', 'dossier'],
                               name='ix_dosit_comp_dossier'),
        ),
    ]
