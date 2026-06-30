# Generated 2026-06-30 — FG199 Portail self-service (note de frais)
#
# Entièrement additive : ``CreateModel`` (``NoteDeFrais``) + index nommés —
# réversible. Déclaration de frais professionnels par un employé (catégorie,
# montant, date, libellé) avec statut de remboursement (soumise → approuvée →
# remboursée, ou refusée). Saisie via le portail self-service (FG199) ;
# l'approbation reste Administrateur/Responsable. Société posée côté serveur.
# RUNTIME-SAFETY : codes bornés ≤ 20 ; montant en DecimalField ; libellé
# plafonné ; index nommés (≤ 30 chars). Le portail self-service lui-même n'a
# pas de modèle dédié : il agrège les données RH existantes par dossier lié.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0036_affectation_vehicule'),
    ]

    operations = [
        migrations.CreateModel(
            name='NoteDeFrais',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categorie', models.CharField(choices=[('transport', 'Transport'), ('repas', 'Repas'), ('hebergement', 'Hébergement'), ('fournitures', 'Fournitures'), ('autre', 'Autre')], default='autre', max_length=20, verbose_name='Catégorie')),
                ('montant', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Montant')),
                ('date_frais', models.DateField(blank=True, null=True, verbose_name='Date de la dépense')),
                ('libelle', models.CharField(max_length=255, verbose_name='Libellé')),
                ('statut', models.CharField(choices=[('soumise', 'Soumise'), ('approuvee', 'Approuvée'), ('remboursee', 'Remboursée'), ('refusee', 'Refusée')], default='soumise', max_length=20, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_notes_frais', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes_frais', to='rh.dossieremploye', verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Note de frais',
                'verbose_name_plural': 'Notes de frais',
                'ordering': ['-date_frais', '-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='notedefrais',
            index=models.Index(fields=['company', 'employe'], name='rh_frais_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='notedefrais',
            index=models.Index(fields=['company', 'statut'], name='rh_frais_comp_stat_idx'),
        ),
    ]
