import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """YSERV1/YSERV9 — un chantier peut être créé sans devis lié (saisie
    manuelle). `client` devient nullable ; `create_installation_from_devis`
    continue de toujours le renseigner. Additive (relâche une contrainte,
    ne perd aucune donnée)."""

    dependencies = [
        ('installations', '0083_zstk10_lot_prelevement'),
    ]

    operations = [
        migrations.AlterField(
            model_name='installation',
            name='client',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='installations', to='crm.client'),
        ),
    ]
