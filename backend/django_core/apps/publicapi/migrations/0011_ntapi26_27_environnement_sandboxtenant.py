"""NTAPI26/27 — additif uniquement, aucune migration destructive.

* NTAPI26 — ``ApiKey.environnement`` (`test`/`live`, défaut `live`) : préfixe
  distinct, aucune conséquence sur les clés existantes (toutes migrent vers
  `live`, comportement historique inchangé).
* NTAPI27 — nouveau modèle ``SandboxTenant`` (bac à sable API) : mappe une
  société réelle à sa société-jumelle isolée portant les données de démo.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('publicapi', '0010_ntapi10_webhookdelivery_idempotency_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='apikey',
            name='environnement',
            field=models.CharField(
                blank=True,
                choices=[
                    ('test', 'Test (bac à sable, `tqk_test_…`)'),
                    ('live', 'Live (données réelles, `tqk_live_…`)'),
                ],
                default='live', max_length=4,
            ),
        ),
        migrations.CreateModel(
            name='SandboxTenant',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reset_at', models.DateTimeField(
                    blank=True, null=True,
                    help_text="Dernière remise à l'état initial "
                              "(POST sandbox/reset/).")),
                ('company', models.OneToOneField(
                    help_text='Société réelle propriétaire de ce bac à sable.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sandbox_tenant',
                    to='authentication.company')),
                ('sandbox_company', models.OneToOneField(
                    help_text='Société-jumelle isolée portant les données de démo.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sandbox_of',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': 'Bac à sable API',
                'verbose_name_plural': 'Bacs à sable API',
            },
        ),
    ]
