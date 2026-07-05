# XSAL6 — Plans de commission par commercial. Additive/reversible: one
# brand-new table, no changes to existing ones.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('ventes', '0070_xsal2_regleprix'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanCommission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('base', models.CharField(choices=[('ca_devis_signe', 'CA des devis signés'), ('marge_interne', 'Marge interne (admin uniquement)'), ('par_kwc', 'MAD par kWc installé')], max_length=20)),
                ('taux_pct', models.DecimalField(blank=True, decimal_places=2, help_text='% appliqué à la base (mode ca_devis_signe / marge_interne).', max_digits=5, null=True)),
                ('montant_par_kwc', models.DecimalField(blank=True, decimal_places=2, help_text='MAD par kWc installé (mode par_kwc).', max_digits=10, null=True)),
                ('paliers', models.JSONField(blank=True, null=True)),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plans_commission', to='authentication.company')),
                ('owner', models.ForeignKey(blank=True, help_text='Vide = plan par défaut de la société.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='plans_commission', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Plan de commission',
                'verbose_name_plural': 'Plans de commission',
                'ordering': ['-created_at'],
            },
        ),
    ]
