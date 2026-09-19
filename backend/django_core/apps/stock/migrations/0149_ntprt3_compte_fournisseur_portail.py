# NTPRT3 — compte portail fournisseur RÉEL (CustomUser rattaché à un
# Fournisseur). Additive : une nouvelle table, aucune colonne existante
# touchée. Le jeton XPUR22 (PortailFournisseurToken) reste inchangé.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('stock', '0148_stkcat27_recherche_unaccent_trgm'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CompteFournisseurPortail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('derniere_connexion', models.DateTimeField(blank=True, null=True, verbose_name='Dernière connexion')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comptes_portail', to='stock.fournisseur', verbose_name='Fournisseur')),
                ('utilisateur', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='compte_fournisseur_portail', to=settings.AUTH_USER_MODEL, verbose_name='Compte utilisateur')),
            ],
            options={
                'verbose_name': 'Compte portail fournisseur',
                'verbose_name_plural': 'Comptes portail fournisseur',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='comptefournisseurportail',
            index=models.Index(fields=['company', 'actif'],
                               name='idx_cptfourn_por_co_actif'),
        ),
        migrations.AddConstraint(
            model_name='comptefournisseurportail',
            constraint=models.UniqueConstraint(
                fields=('company', 'fournisseur'),
                name='uniq_cptfourn_portail_co_fou'),
        ),
    ]
