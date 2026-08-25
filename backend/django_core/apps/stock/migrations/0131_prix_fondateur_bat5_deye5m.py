"""Prix fondateur 25/08/2026 — Batterie Dyness 5 kWh et Deye 5 kW mono.

Décision fondateur (session du 25/08/2026) : « correct battery price to
14000dh ttc and deye 5kw mono to 15000dh ».

  * BAT-DEY-5   (Batterie Dyness 5 kWh)          : 17 000 → 14 000 TTC
  * OND-H-DEY-5M (Onduleur hybride Deye 5kW Mono) : 17 000 → 15 000 TTC

Le catalogue stocke le HT (TVA 20 % sur batteries/onduleurs, l'ancre est le
TTC — même doctrine que le seeder) : 14 166,67 HT → 11 666,67 HT pour la
batterie, 14 166,67 HT → 12 500,00 HT pour l'onduleur. Même patron que les
migrations 0126/0127 : le recalage n'écrase le prix QUE s'il porte encore
l'ancienne valeur seedée — une saisie fondateur divergente n'est JAMAIS
touchée. ``prix_achat`` et quantités intacts. Le seeder porte les mêmes TTC
pour les bases neuves.

RÉVERSIBLE : non — ``noop`` (même doctrine que 0125/0126/0127 : impossible de
distinguer après coup un prix recalé d'une saisie postérieure).
"""
from decimal import Decimal

from django.db import migrations

#: sku -> (ancien prix_vente HT seedé, nouveau prix_vente HT)
_RECALAGES_PRIX = {
    'BAT-DEY-5': (Decimal('14166.67'), Decimal('11666.67')),
    'OND-H-DEY-5M': (Decimal('14166.67'), Decimal('12500.00')),
}


def recaler_prix(apps, schema_editor):
    # Volume minuscule (2 SKU × N sociétés), mais itéré par lots via
    # .iterator() plutôt qu'un .update() global : jamais de verrou long
    # (patron check_safe_migrations), et la garde par l'ancienne valeur
    # reste évaluée ligne à ligne.
    Produit = apps.get_model('stock', 'Produit')
    for sku, (ancien, nouveau) in _RECALAGES_PRIX.items():
        for produit in Produit.objects.filter(
                sku=sku, prix_vente=ancien).iterator(chunk_size=200):
            produit.prix_vente = nouveau
            produit.save(update_fields=['prix_vente'])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0130_ldech_puissances_decharge'),
    ]

    operations = [
        migrations.RunPython(recaler_prix, migrations.RunPython.noop),
    ]
