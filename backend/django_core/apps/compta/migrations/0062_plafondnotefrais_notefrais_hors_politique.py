"""XACC27 — Politique de notes de frais : plafonds par catégorie + OCR.

Additif : ``PlafondNoteFrais`` (référentiel company-scopé) + ``NoteFrais.
hors_politique`` (flag warning posé côté serveur à la création, jamais
bloquant). L'OCR du justificatif (key-gated) n'a pas de modèle propre.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0061_provision'),
    ]

    operations = [
        migrations.AddField(
            model_name='notefrais',
            name='hors_politique',
            field=models.BooleanField(default=False, verbose_name='Hors politique (dépasse le plafond)'),
        ),
        migrations.CreateModel(
            name='PlafondNoteFrais',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categorie', models.CharField(choices=[('deplacement', 'Déplacement / transport'), ('carburant', 'Carburant'), ('repas', 'Repas / restauration'), ('hebergement', 'Hébergement'), ('fournitures', 'Petites fournitures'), ('peage', 'Péage / stationnement'), ('autre', 'Autre')], max_length=15, verbose_name='Catégorie')),
                ('montant_max', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Plafond (montant max)')),
                ('seuil_justificatif_obligatoire', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='Seuil au-delà duquel le justificatif est obligatoire')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plafonds_notes_frais', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Plafond de note de frais',
                'verbose_name_plural': 'Plafonds de notes de frais',
                'ordering': ['categorie'],
            },
        ),
        migrations.AddConstraint(
            model_name='plafondnotefrais',
            constraint=models.UniqueConstraint(fields=('company', 'categorie'), name='uniq_plafond_notefrais_categorie'),
        ),
    ]
