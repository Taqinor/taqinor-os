# Generated 2026-06-30 — FG196 Bulletin de paie (lecture seule)
#
# Entièrement additive : ``CreateModel`` (``BulletinPaie``) + contrainte
# d'unicité + index nommés — réversible. Dépôt mensuel du bulletin PDF (produit
# par le prestataire de paie) rattaché à un employé pour une période
# (annee/mois), en LECTURE SEULE : aucun calcul légal interne (décision FG196).
# Le fichier réutilise records.Attachment (MinIO) — aucun nouveau stockage. Le
# couple (employe, annee, mois) est unique. Société posée côté serveur.
# RUNTIME-SAFETY : note plafonnée ; contrainte + index nommés (≤ 30 chars).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('records', '0006_remove_tag_records_tag_company_nom_uniq_and_more'),
        ('rh', '0033_avance_salaire'),
    ]

    operations = [
        migrations.CreateModel(
            name='BulletinPaie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('annee', models.PositiveIntegerField(verbose_name='Année')),
                ('mois', models.PositiveSmallIntegerField(verbose_name='Mois')),
                ('note', models.CharField(blank=True, default='', max_length=255, verbose_name='Note')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('attachment', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='bulletin_paie', to='records.attachment', verbose_name='Pièce jointe')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_bulletins_paie', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bulletins_paie', to='rh.dossieremploye', verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Bulletin de paie',
                'verbose_name_plural': 'Bulletins de paie',
                'ordering': ['-annee', '-mois', 'employe'],
            },
        ),
        migrations.AddConstraint(
            model_name='bulletinpaie',
            constraint=models.UniqueConstraint(fields=('employe', 'annee', 'mois'), name='rh_bulletin_emp_an_mois_uniq'),
        ),
        migrations.AddIndex(
            model_name='bulletinpaie',
            index=models.Index(fields=['company', 'annee', 'mois'], name='rh_bulletin_comp_anmois_idx'),
        ),
        migrations.AddIndex(
            model_name='bulletinpaie',
            index=models.Index(fields=['company', 'employe'], name='rh_bulletin_comp_emp_idx'),
        ),
    ]
