from django.db import migrations, models


class Migration(migrations.Migration):
    """ZFSM5 — devis d'upsell créé sur place depuis l'intervention.

    `devis_upsell_id` référence par ID (jamais un import de `ventes.models` —
    règle de modularité) le Devis brouillon d'upsell, DISTINCT de
    `Reserve.devis_repare_id` (XFSM18). Additive — nullable, aucune donnée
    existante affectée."""

    dependencies = [
        ('installations', '0088_zfsm4_intervention_facture_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='devis_upsell_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
