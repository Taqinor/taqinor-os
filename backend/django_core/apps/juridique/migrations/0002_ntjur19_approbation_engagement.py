"""NTJUR19 — workflow d'approbation des engagements de dépenses juridiques.

Ajoute le registre des cabinets (NTJUR9) et les mandats (NTJUR10) — prérequis
directs du critère d'acceptation NTJUR19 (« un mandat à 150 000 MAD au-dessus
du seuil reste bloqué en attente d'approbation avant activation ») — puis les
règles et étapes d'approbation elles-mêmes.

Migration ADDITIVE (4 nouvelles tables, aucune existante touchée).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('juridique', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CabinetAvocat',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(
                    max_length=200, verbose_name='Nom du cabinet')),
                ('barreau', models.CharField(
                    blank=True, default='', max_length=120,
                    verbose_name='Barreau')),
                ('specialites', models.TextField(
                    blank=True, default='',
                    help_text='Liste libre, une spécialité par ligne ou '
                              'séparée par des virgules.',
                    verbose_name='Spécialités')),
                ('contact_principal', models.CharField(
                    blank=True, default='', max_length=200,
                    verbose_name='Contact principal')),
                ('email', models.EmailField(
                    blank=True, default='', max_length=254,
                    verbose_name='E-mail')),
                ('telephone', models.CharField(
                    blank=True, default='', max_length=30,
                    verbose_name='Téléphone')),
                ('taux_horaire_moyen', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    verbose_name='Taux horaire moyen')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='juridique_cabinetavocat_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Cabinet d'avocats",
                'verbose_name_plural': "Cabinets d'avocats",
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RegleApprobationJuridique',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('libelle', models.CharField(
                    max_length=200, verbose_name='Libellé')),
                ('nature_dossier', models.CharField(
                    blank=True,
                    choices=[('contentieux', 'Contentieux'),
                             ('precontentieux', 'Précontentieux'),
                             ('consultatif', 'Consultatif'),
                             ('recouvrement', 'Recouvrement')],
                    default='', max_length=20,
                    verbose_name='Nature de dossier ciblée')),
                ('montant_min', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    verbose_name='Montant minimum')),
                ('montant_max', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    verbose_name='Montant maximum')),
                ('niveau_approbation', models.CharField(
                    choices=[('responsable', 'Responsable'),
                             ('administrateur', 'Administrateur'),
                             ('direction', 'Direction')],
                    default='responsable', max_length=20,
                    verbose_name="Niveau d'approbation requis")),
                ('nombre_approbateurs', models.PositiveIntegerField(
                    default=1, verbose_name="Nombre d'approbateurs requis")),
                ('priorite', models.PositiveIntegerField(
                    default=0, verbose_name='Priorité')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='juridique_regleapprobationjuridique_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Règle d'approbation juridique",
                'verbose_name_plural': "Règles d'approbation juridique",
                'ordering': ['-priorite', 'id'],
            },
        ),
        migrations.CreateModel(
            name='MandatAvocat',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_mandat', models.DateField(
                    verbose_name='Date du mandat')),
                ('mode_facturation', models.CharField(
                    choices=[('forfait', 'Forfait'), ('horaire', 'Horaire'),
                             ('resultat', 'Au résultat')],
                    default='forfait', max_length=15,
                    verbose_name='Mode de facturation')),
                ('montant_forfait', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    verbose_name='Montant du forfait')),
                ('taux_horaire', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    verbose_name='Taux horaire')),
                ('heures_estimees', models.PositiveIntegerField(
                    default=0, verbose_name='Heures estimées')),
                ('pourcentage_resultat', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=6, null=True,
                    verbose_name='Pourcentage au résultat')),
                ('statut', models.CharField(
                    choices=[('brouillon', 'Brouillon'),
                             ('en_approbation', "En attente d'approbation"),
                             ('actif', 'Actif'), ('clos', 'Clos')],
                    default='brouillon', max_length=20,
                    verbose_name='Statut')),
                ('cabinet', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='mandats', to='juridique.cabinetavocat',
                    verbose_name="Cabinet d'avocats")),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='juridique_mandatavocat_set',
                    to='authentication.company', verbose_name='Société')),
                ('dossier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mandats', to='juridique.dossierjuridique',
                    verbose_name='Dossier juridique')),
            ],
            options={
                'verbose_name': 'Mandat avocat',
                'verbose_name_plural': 'Mandats avocat',
                'ordering': ['-date_mandat', '-id'],
            },
        ),
        migrations.CreateModel(
            name='EtapeApprobationJuridique',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('niveau', models.PositiveIntegerField(
                    default=1, verbose_name="Niveau / rang de l'étape")),
                ('niveau_approbation', models.CharField(
                    choices=[('responsable', 'Responsable'),
                             ('administrateur', 'Administrateur'),
                             ('direction', 'Direction')],
                    default='responsable', max_length=20,
                    verbose_name="Niveau d'approbation requis")),
                ('statut', models.CharField(
                    choices=[('en_attente', 'En attente'),
                             ('approuve', 'Approuvé'), ('rejete', 'Rejeté')],
                    default='en_attente', max_length=20,
                    verbose_name='Statut')),
                ('decision_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Décidé le')),
                ('commentaire', models.TextField(
                    blank=True, default='', verbose_name='Commentaire')),
                ('approbateur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='juridique_etapes_approuvees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Approbateur')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='juridique_etapeapprobationjuridique_set',
                    to='authentication.company', verbose_name='Société')),
                ('mandat', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='etapes_approbation',
                    to='juridique.mandatavocat', verbose_name='Mandat')),
                ('regle', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='etapes_approbation',
                    to='juridique.regleapprobationjuridique',
                    verbose_name="Règle d'approbation source")),
            ],
            options={
                'verbose_name': "Étape d'approbation juridique",
                'verbose_name_plural': "Étapes d'approbation juridique",
                'ordering': ['mandat_id', 'niveau', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='regleapprobationjuridique',
            index=models.Index(fields=['company', 'actif'],
                               name='juridique_regleapp_co_act'),
        ),
        migrations.AddIndex(
            model_name='etapeapprobationjuridique',
            index=models.Index(fields=['mandat', 'niveau'],
                               name='juridique_etapeapp_ma_niv'),
        ),
    ]
