from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0015_xsav6_sla_pre_alerte_escalade'),
    ]

    operations = [
        migrations.AddField(
            model_name='contratmaintenance',
            name='sla_response_days',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Vide = pas de override contrat (SLA société standard).',
                verbose_name='SLA — délai de première réponse (jours, override)'),
        ),
        migrations.AddField(
            model_name='contratmaintenance',
            name='sla_resolution_days',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Vide = pas de override contrat (SLA société standard).',
                verbose_name='SLA — délai de résolution (jours, override)'),
        ),
    ]
