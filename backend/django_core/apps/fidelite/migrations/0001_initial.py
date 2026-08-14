# NTRET9 — Programme de fidélité par points : ProgrammeFidelite,
# CompteFidelite, MouvementFidelite.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.fidelite.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
        ('crm', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProgrammeFidelite',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'nom',
                    models.CharField(
                        default='Programme fidélité', max_length=150),
                ),
                ('actif', models.BooleanField(default=False)),
                (
                    'points_par_mad',
                    models.DecimalField(
                        decimal_places=2, default='1.00', max_digits=6,
                        help_text='Points crédités par MAD TTC dépensé.'),
                ),
                (
                    'valeur_mad_par_point',
                    models.DecimalField(
                        decimal_places=4, default='0.10', max_digits=6,
                        help_text=(
                            "Valeur (MAD) d'un point à la dépense — affichage "
                            "seul, aucune dépense de points n'est câblée par "
                            "ce lot (NTRET9).")),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Programme de fidélité',
                'verbose_name_plural': 'Programmes de fidélité',
                'ordering': ['-actif', 'nom'],
            },
        ),
        migrations.CreateModel(
            name='CompteFidelite',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('solde_points', models.PositiveIntegerField(default=0)),
                # NTRET11 — créé DIRECTEMENT ici, jamais par un AddField(unique=True)
                # ultérieur : Django applique le défaut UNE SEULE FOIS pour toutes
                # les lignes existantes, ce qui viole l'unicité dès qu'une table est
                # peuplée (garde ADDFIELD_UNIQUE_ONESHOT de check_migration_safety).
                (
                    'code_qr',
                    models.CharField(
                        default=apps.fidelite.models.generer_code_qr, editable=False,
                        max_length=64, unique=True,
                        help_text=(
                            'Jeton opaque non séquentiel (carte dématérialisée '
                            'NTRET11) — globalement unique : résout LUI-MÊME LA '
                            'société, jamais réutilisable pour un autre tenant.')),
                ),
                (
                    'client',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='compte_fidelite', to='crm.client'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Compte de fidélité',
                'verbose_name_plural': 'Comptes de fidélité',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MouvementFidelite',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'type_mouvement',
                    models.CharField(
                        choices=[
                            ('gain', 'Gain'), ('depense', 'Dépense'),
                            ('ajustement', 'Ajustement manuel')],
                        max_length=12),
                ),
                (
                    'points',
                    models.IntegerField(
                        help_text=(
                            'Positif pour un gain, négatif pour une '
                            'dépense/reprise.')),
                ),
                (
                    'source_type',
                    models.CharField(
                        blank=True, default='', max_length=30,
                        help_text=(
                            "Origine du mouvement (ex. 'vente_comptoir', "
                            "'facture', 'parrainage', 'manuel').")),
                ),
                (
                    'source_id',
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        help_text=(
                            "Référence à l'objet source (id brut, jamais "
                            "une FK cross-app).")),
                ),
                (
                    'montant_source',
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12,
                        null=True,
                        help_text=(
                            'Montant TTC de la vente ayant généré ce gain '
                            '(sert au calcul du CA cumulé pour les paliers '
                            'NTRET10).')),
                ),
                ('motif', models.CharField(blank=True, default='', max_length=255)),
                (
                    'compte',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='mouvements', to='fidelite.comptefidelite'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='mouvements_fidelite_crees',
                        to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                'verbose_name': 'Mouvement de fidélité',
                'verbose_name_plural': 'Mouvements de fidélité',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='programmefidelite',
            constraint=models.UniqueConstraint(
                condition=models.Q(('actif', True)), fields=('company',),
                name='uniq_programmefidelite_company_actif'),
        ),
        migrations.AddIndex(
            model_name='mouvementfidelite',
            index=models.Index(
                fields=['compte', '-created_at'],
                name='fidelite_mvt_compte_date_idx'),
        ),
    ]
