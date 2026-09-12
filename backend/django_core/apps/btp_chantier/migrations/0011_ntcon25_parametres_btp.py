"""NTCON25 — réglages BTP par société (singleton par tenant).

Migration ADDITIVE : une table dans ``btp_chantier``. Tant qu'une société n'a
pas de ligne, ``services.config_btp`` applique les défauts du module — aucun
comportement ne change au déploiement.
"""
import apps.btp_chantier.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('btp_chantier', '0010_ntcon19_lot_checklist'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametresBtpChantier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('delai_reponse_rfi_defaut_jours', models.PositiveIntegerField(default=5, verbose_name='Délai de réponse RFI par défaut (jours ouvrés)')),
                ('delai_revue_visa_defaut_jours', models.PositiveIntegerField(default=10, verbose_name='Délai de revue de visa par défaut (jours ouvrés)')),
                ('guard_ppsps_bloquant', models.BooleanField(default=True, verbose_name='Bloquer le démarrage sans PPSPS signé (sinon avertir)')),
                ('guard_checklist_lot_bloquant', models.BooleanField(default=True, verbose_name='Bloquer la réception si la checklist du lot est incomplète')),
                ('lots_types_defaut', models.JSONField(blank=True, default=apps.btp_chantier.models.lots_types_defaut, verbose_name="Lots types suggérés par l'assistant")),
                ('taux_penalite_retard_defaut_pmil', models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name='Taux de pénalité de retard par défaut (‰/jour)')),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='btp_parametres', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Réglages BTP',
                'verbose_name_plural': 'Réglages BTP',
            },
        ),
    ]
