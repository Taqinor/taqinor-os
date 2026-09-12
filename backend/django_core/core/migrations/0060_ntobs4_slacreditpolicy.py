# NTOBS4 — barème de crédits SLA. Migration écrite à la main (INTERDIT
# manage.py sur cette lane) ; state Django équivalent à ce que
# `makemigrations` produirait pour `core.sla.SlaCreditPolicy` + les 3 champs
# crédit ajoutés à `SlaSnapshot`.
import django.db.models.deletion
from django.db import migrations, models

import core.sla


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('core', '0059_ntobs3_slasnapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='SlaCreditPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('paliers', models.JSONField(default=core.sla._default_paliers, help_text='Liste de {"seuil_uptime_pct": .., "credit_pct_facture": ..} : un palier s\'applique si uptime_pct < seuil_uptime_pct.', verbose_name='Paliers')),
                ('valide', models.BooleanField(default=False, help_text="False = valeurs d'exemple, pas encore un engagement réel.", verbose_name='Barème validé par le fondateur')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, help_text='NULL = politique par défaut système.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sla_credit_policies', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Barème de crédits SLA',
                'verbose_name_plural': 'Barèmes de crédits SLA',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='slasnapshot',
            name='credit_du_pct',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Crédit dû (%)'),
        ),
        migrations.AddField(
            model_name='slasnapshot',
            name='credit_du_montant',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='None si le montant facturé du mois est inconnu.', max_digits=12, null=True, verbose_name='Crédit dû (montant)'),
        ),
        migrations.AddField(
            model_name='slasnapshot',
            name='credit_statut',
            field=models.CharField(choices=[('non_applicable', 'Non applicable'), ('a_emettre', 'À émettre'), ('emis', 'Émis'), ('refuse', 'Refusé')], default='non_applicable', max_length=15, verbose_name='Statut du crédit'),
        ),
    ]
