from django.db import migrations, models


class Migration(migrations.Migration):
    """ZFSM4 — facturation directe d'une intervention hors contrat/ticket.

    `facture_id` référence par ID (jamais un import de `ventes.models` —
    règle de modularité) la Facture brouillon générée depuis l'intervention.
    Additive — nullable, aucune donnée existante affectée."""

    dependencies = [
        ('installations', '0087_zfsm3_recurrence_intervention'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='facture_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
