"""NTP2P2 — plan d'approbation générique des demandes d'achat.

Additif pur : deux nouvelles tables (``RegleApprobationAchat`` /
``EtapeApprobationAchat``). Aucun champ existant modifié — sans règle active,
le cycle FG310 historique reste byte-identique.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('installations', '0100_photochecklistmeta_tenantmodel_timestamps'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegleApprobationAchat',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('libelle', models.CharField(
                    max_length=150, verbose_name='Libellé')),
                ('montant_min', models.DecimalField(
                    blank=True, decimal_places=2,
                    help_text='Borne basse incluse. Vide = pas de borne basse.',
                    max_digits=14, null=True,
                    verbose_name='Montant minimum (MAD)')),
                ('montant_max', models.DecimalField(
                    blank=True, decimal_places=2,
                    help_text='Borne haute incluse. Vide = pas de borne haute.',
                    max_digits=14, null=True,
                    verbose_name='Montant maximum (MAD)')),
                ('niveau_approbation', models.CharField(
                    choices=[('responsable', 'Responsable'),
                             ('administrateur', 'Administrateur'),
                             ('direction', 'Direction')],
                    default='responsable', max_length=20,
                    verbose_name="Niveau d'approbation requis")),
                ('nombre_approbateurs', models.PositiveIntegerField(
                    default=1,
                    verbose_name="Nombre d'approbateurs séquentiels")),
                ('autorise_depassement_budget', models.BooleanField(
                    default=False,
                    help_text='Quand actif, une demande hors budget part en '
                              "approbation au lieu d'être refusée (NTP2P4).",
                    verbose_name='Autorise le dépassement du budget '
                                 'départemental')),
                ('priorite', models.IntegerField(
                    default=0, verbose_name='Priorité (décroissante)')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Active')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('chantier', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='regles_approbation_achat',
                    to='installations.installation',
                    verbose_name='Chantier (optionnel)')),
                ('programme', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='regles_approbation_achat',
                    to='installations.projet',
                    verbose_name='Programme (optionnel)')),
            ],
            options={
                'verbose_name': "Règle d'approbation d'achat",
                'verbose_name_plural': "Règles d'approbation d'achat",
                'ordering': ['-priorite', 'id'],
            },
        ),
        migrations.CreateModel(
            name='EtapeApprobationAchat',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('niveau', models.PositiveIntegerField(
                    default=1, verbose_name='Rang séquentiel (1..N)')),
                ('niveau_approbation', models.CharField(
                    choices=[('responsable', 'Responsable'),
                             ('administrateur', 'Administrateur'),
                             ('direction', 'Direction')],
                    default='responsable', max_length=20,
                    verbose_name="Niveau d'approbation requis")),
                ('statut', models.CharField(
                    choices=[('en_attente', 'En attente'),
                             ('approuve', 'Approuvée'),
                             ('rejete', 'Rejetée')],
                    default='en_attente', max_length=20)),
                ('decision_le', models.DateTimeField(blank=True, null=True)),
                ('commentaire', models.TextField(blank=True, default='')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('demande', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='etapes_approbation',
                    to='installations.demandeachat',
                    verbose_name="Demande d'achat")),
                ('regle', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='etapes',
                    to='installations.regleapprobationachat',
                    verbose_name='Règle appliquée')),
                ('approbateur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='etapes_approbation_achat',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Approbateur')),
            ],
            options={
                'verbose_name': "Étape d'approbation d'achat",
                'verbose_name_plural': "Étapes d'approbation d'achat",
                'ordering': ['demande_id', 'niveau', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='regleapprobationachat',
            index=models.Index(fields=['company', 'actif'],
                               name='idx_regapa_co_actif'),
        ),
        migrations.AddIndex(
            model_name='regleapprobationachat',
            index=models.Index(fields=['company', 'chantier'],
                               name='idx_regapa_co_chant'),
        ),
        migrations.AddIndex(
            model_name='etapeapprobationachat',
            index=models.Index(fields=['company', 'statut'],
                               name='idx_etapa_co_statut'),
        ),
        migrations.AddIndex(
            model_name='etapeapprobationachat',
            index=models.Index(fields=['demande', 'niveau'],
                               name='idx_etapa_dem_niv'),
        ),
    ]
