# Generated 2026-06-29 — FG180 Émargement de remise EPI (accusé signé)
#
# Entièrement additive : ``AddField`` (marqueur d'accusé sur ``DotationEpi``) +
# ``CreateModel`` (``EmargementEpi``) + index nommé — réversible. L'émargement
# matérialise l'accusé de réception SIGNÉ d'une dotation EPI (exigible
# CNSS / accident du travail). Signature électronique IN-APP (loi 53-05), aucun
# prestataire externe. Société + utilisateur agissant posés côté serveur.
#
# RUNTIME-SAFETY (leçon FG136) : ``ip_adresse`` ≤ 45 (IPv6) ; ``user_agent`` est
# un ``TextField`` (potentiellement très long) ; l'index est nommé
# explicitement (≤ 30 chars) pour éviter la divergence d'auto-nommage Django.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rh", "0019_epi_peremption_controle"),
    ]

    operations = [
        migrations.AddField(
            model_name='dotationepi',
            name='accuse_remise',
            field=models.BooleanField(
                default=False, verbose_name='Remise émargée (accusée)'),
        ),
        migrations.AddField(
            model_name='dotationepi',
            name='date_accuse',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Date de l'accusé de remise"),
        ),
        migrations.CreateModel(
            name='EmargementEpi',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('signataire_nom', models.CharField(
                    max_length=255, verbose_name='Nom du signataire')),
                ('role_signataire', models.CharField(
                    choices=[
                        ('employe', 'Employé bénéficiaire'),
                        ('remettant', 'Remettant'),
                        ('temoin', 'Témoin'),
                    ],
                    default='employe', max_length=20,
                    verbose_name='Rôle du signataire')),
                ('date_signature', models.DateTimeField(
                    auto_now_add=True, verbose_name='Émargé le')),
                ('ip_adresse', models.CharField(
                    blank=True, default='', max_length=45,
                    verbose_name='Adresse IP')),
                ('user_agent', models.TextField(
                    blank=True, default='', verbose_name='User agent')),
                ('methode', models.CharField(
                    choices=[
                        ('typed', 'Nom dactylographié'),
                        ('draw', 'Signature dessinée'),
                    ],
                    default='typed', max_length=20,
                    verbose_name='Méthode de signature')),
                ('mention', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Mention')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_emargements_epi',
                    to='authentication.company',
                    verbose_name='Société')),
                ('dotation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='emargements',
                    to='rh.dotationepi',
                    verbose_name='Dotation EPI')),
                ('signataire', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='rh_emargements_epi',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur signataire')),
            ],
            options={
                'verbose_name': 'Émargement EPI',
                'verbose_name_plural': 'Émargements EPI',
                'ordering': ['-date_signature', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='emargementepi',
            index=models.Index(
                fields=['company', 'dotation'],
                name='rh_emepi_comp_dot_idx'),
        ),
    ]
