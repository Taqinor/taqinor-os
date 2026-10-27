"""CCAT15 (27/10/2026) — fiche commerciale des onduleurs hybrides Deye.

La description semée commençait par « Onduleur hybride Deye SUN-…SG » : les
points de suspension s'imprimaient sur chaque fiche produit Deye des PDF client
(devis 1348 une page, 1344 étude — critique Fable de la session RPDF). Le seeder
porte désormais le modèle réel (``seed_catalogue._PREMIERE_LIGNE_DEYE`` : modèle
cité seulement s'il est confirmé par le fondateur).

Le seeder ne réécrit jamais une valeur déjà saisie (ASTK176) : cette migration
ne touche QUE les produits qui portent encore EXACTEMENT l'ancienne description
semée — une description saisie par le fondateur reste à lui.
"""
from django.db import migrations

_SUITE = ('Compatible batteries lithium 48 V (BMS CAN/RS485)\n'
          'Bascule secours (EPS/UPS) en cas de coupure réseau\n'
          'Monitoring Wi-Fi via Solarman Smart / Deye Cloud')
ANCIENNE = 'Onduleur hybride Deye SUN-…SG\n' + _SUITE
PREMIERE_LIGNE = {
    'OND-H-DEY-5M': 'Onduleur hybride Deye monophasé (gamme SG05LP1)',
    'OND-H-DEY-10M': 'Onduleur hybride Deye monophasé',
    'OND-H-DEY-10T': 'Onduleur hybride Deye SUN-10K-SG05LP3-EU-SM2',
    'OND-H-DEY-15T': 'Onduleur hybride Deye SUN-15K-SG05LP3-EU-SM2',
    'OND-H-DEY-20T': 'Onduleur hybride Deye SUN-20K-SG05LP3-EU-SM2',
}


def _changer(apps, avant, apres):
    """Quelques dizaines de lignes au plus (SKU semés × sociétés) : sauvegarde
    ciblée, seule la valeur semée connue change."""
    Produit = apps.get_model('stock', 'Produit')
    for sku, ligne in PREMIERE_LIGNE.items():
        de, vers = avant(ligne), apres(ligne)
        for p in Produit.objects.filter(sku=sku, description=de).iterator():
            p.description = vers
            p.save(update_fields=['description'])


def corriger(apps, schema_editor):
    _changer(apps, lambda _l: ANCIENNE, lambda ligne: ligne + '\n' + _SUITE)


def retablir(apps, schema_editor):
    _changer(apps, lambda ligne: ligne + '\n' + _SUITE, lambda _l: ANCIENNE)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0174_rpdf_garanties_maroc'),
    ]

    operations = [
        migrations.RunPython(corriger, retablir),
    ]
