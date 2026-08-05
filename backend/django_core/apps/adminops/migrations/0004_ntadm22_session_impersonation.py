import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.adminops.models


class Migration(migrations.Migration):
    """NTADM22 — table des sessions d'impersonation sous consentement.

    Purement additive : nouvelle table, aucun modèle existant modifié. Une
    ligne naît TOUJOURS `consentement_donne=False` — la table ne peut donc pas,
    à elle seule, ouvrir un accès.
    """

    dependencies = [
        ('adminops', '0003_ntadm7_seed_plans'),
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SessionImpersonation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('motif', models.TextField(help_text='Obligatoire — affiché tel quel au tenant dans la demande de consentement.', verbose_name='Motif')),
                ('consentement_donne', models.BooleanField(default=False, verbose_name='Consentement donné')),
                ('consentement_le', models.DateTimeField(blank=True, null=True)),
                ('refusee', models.BooleanField(default=False, verbose_name='Refusée')),
                ('refus_le', models.DateTimeField(blank=True, null=True)),
                ('expire_le', models.DateTimeField(default=apps.adminops.models.default_expiration_impersonation, verbose_name='Échéance de la demande')),
                ('demarree_le', models.DateTimeField(blank=True, null=True)),
                ('terminee_le', models.DateTimeField(blank=True, null=True)),
                ('expiree', models.BooleanField(default=False, verbose_name='Périmée')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('consentement_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='impersonations_consenties', to=settings.AUTH_USER_MODEL, verbose_name='Consentement donné par')),
                ('initiee_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='impersonations_initiees', to=settings.AUTH_USER_MODEL, verbose_name='Demandée par (support)')),
                ('utilisateur_cible', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='impersonations_subies', to=settings.AUTH_USER_MODEL, verbose_name='Utilisateur assisté')),
            ],
            options={
                'verbose_name': "Session d'impersonation",
                'verbose_name_plural': "Sessions d'impersonation",
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='sessionimpersonation',
            index=models.Index(
                fields=['company', 'consentement_donne'],
                name='adminops_imp_co_consent'),
        ),
    ]
