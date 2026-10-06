"""CIQ213 — ``Devis.tiers_payeur`` : l'organisme financeur qui règle les
tranches ``payeur: tiers`` de l'échéancier (string-FK ``crm.Client``).

ADDITIF : colonne nullable, aucun backfill, aucun devis existant modifié.
Réversible : ``python manage.py migrate ventes 0124``.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0001_initial'),
        ('ventes', '0124_adoc_sharelink_suivi_revocation'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='tiers_payeur',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='devis_finances', to='crm.client',
                verbose_name='Tiers payeur (organisme financeur)'),
        ),
    ]
