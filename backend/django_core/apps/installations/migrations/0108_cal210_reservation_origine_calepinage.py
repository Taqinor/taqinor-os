"""CAL210 — trace la réservation de stock jusqu'au calepinage qui l'a
dimensionnée.

Ajoute ``StockReservation.origine_calepinage_id`` (nullable, défaut ``None``)
— un id OPAQUE vers un ``Calepinage`` du module autonome (jamais une FK :
même frontière inter-apps que ``lead_id`` sur ``Calepinage`` lui-même), posé
par ``apps.installations.services.seed_reservations`` via le sélecteur
cross-app ``apps.installations.selectors.calepinage_retenu_du_chantier``.
ADDITIF STRICT : une réservation existante sans calepinage garde
``origine_calepinage_id = None`` — aucune donnée existante modifiée, aucune
nouvelle mécanique de réservation.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0107_ntmob9_geofence_type_franchissement'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockreservation',
            name='origine_calepinage_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Calepinage d'origine"),
        ),
    ]
