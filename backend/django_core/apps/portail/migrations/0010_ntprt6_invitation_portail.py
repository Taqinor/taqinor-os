"""NTPRT6 — Invitation & gestion de l'équipe du portail client.

Migration STRICTEMENT ADDITIVE : une nouvelle table (``InvitationPortail`),
aucun champ touché sur les modèles existants, aucune donnée déplacée. Aucun
compte portail existant n'est affecté : sans ligne d'invitation, un compte
reste traité comme l'admin (accès plein), exactement le comportement
d'aujourd'hui.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
        ('portail', '0009_ntprt34_preference_portail'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InvitationPortail',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('email', models.EmailField(
                    max_length=254, verbose_name='Email invité')),
                (
                    'role',
                    models.CharField(
                        choices=[
                            ('lecture', 'Lecture seule'),
                            ('ecriture', 'Lecture et écriture'),
                        ],
                        default='lecture', max_length=10,
                        verbose_name='Rôle portail'),
                ),
                (
                    'statut',
                    models.CharField(
                        choices=[
                            ('en_attente', 'En attente'),
                            ('acceptee', 'Acceptée'),
                            ('revoquee', 'Révoquée'),
                        ],
                        default='en_attente', max_length=12,
                        verbose_name='Statut'),
                ),
                (
                    'token_invitation',
                    models.CharField(
                        db_index=True, max_length=64, unique=True,
                        verbose_name="Token d'invitation"),
                ),
                ('expire_le', models.DateTimeField(verbose_name='Expire le')),
                (
                    'date_acceptation',
                    models.DateTimeField(
                        blank=True, null=True,
                        verbose_name='Acceptée le'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company',
                        verbose_name='Société'),
                ),
                (
                    'compte_portail_client',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='invitations',
                        to='portail.compteportailclient',
                        verbose_name='Compte portail client'),
                ),
                (
                    'utilisateur_cree',
                    models.OneToOneField(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='invitation_portail_acceptee',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Compte utilisateur créé'),
                ),
            ],
            options={
                'verbose_name': 'Invitation portail (équipe client)',
                'verbose_name_plural': 'Invitations portail (équipe client)',
                'ordering': ['-created_at'],
            },
        ),
    ]
