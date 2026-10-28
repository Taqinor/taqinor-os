"""CCAT15 (27/10/2026) — fiche commerciale des onduleurs hybrides Deye.

La description semée commençait par « Onduleur hybride Deye SUN-…SG » : les
points de suspension s'imprimaient sur chaque fiche produit Deye des PDF client
(devis 1348 une page, 1344 étude — critique Fable de la session RPDF). Le seeder
porte désormais le modèle réel (``seed_catalogue._PREMIERE_LIGNE_DEYE`` : modèle
cité seulement s'il est confirmé par le fondateur).

Le seeder ne réécrit jamais une valeur déjà saisie (ASTK176) : cette migration
ne touche QUE les produits dont la description commence encore par le préfixe
semé (« Onduleur hybride Deye SUN-…SG ») et n'en remplace que la PREMIÈRE ligne.
Deux variantes ont été semées : celle du 12/06 (« …SG, rendement max ≈ 97,6 % »)
et celle d'après le 20/08 (« …SG » seul) ; le reste de la fiche est gardé tel
quel. Une description saisie par le fondateur reste à lui.
"""
from django.db import migrations

PREFIXE = 'Onduleur hybride Deye SUN-…SG'
#: Première ligne de la variante semée le 12/06 (commit 2cac38216) ; sa suite
#: est la seule à porter « < 4 ms » — ce qui rend le retour arrière exact.
PREMIERE_LIGNE_1206 = PREFIXE + ', rendement max ≈ 97,6 %'
MARQUE_1206 = '< 4 ms'
_SUITE = ('Compatible batteries lithium 48 V (BMS CAN/RS485)\n'
          'Bascule secours (EPS/UPS) en cas de coupure réseau\n'
          'Monitoring Wi-Fi via Solarman Smart / Deye Cloud')
#: La variante semée après le 20/08.
ANCIENNE = PREFIXE + '\n' + _SUITE
PREMIERE_LIGNE = {
    'OND-H-DEY-5M': 'Onduleur hybride Deye monophasé (gamme SG05LP1)',
    'OND-H-DEY-10M': 'Onduleur hybride Deye monophasé',
    'OND-H-DEY-10T': 'Onduleur hybride Deye SUN-10K-SG05LP3-EU-SM2',
    'OND-H-DEY-15T': 'Onduleur hybride Deye SUN-15K-SG05LP3-EU-SM2',
    'OND-H-DEY-20T': 'Onduleur hybride Deye SUN-20K-SG05LP3-EU-SM2',
}


def _changer(apps, filtre, premiere):
    """Quelques dizaines de lignes au plus (SKU semés × sociétés) : sauvegarde
    ciblée, seule la première ligne change."""
    Produit = apps.get_model('stock', 'Produit')
    for sku, ligne in PREMIERE_LIGNE.items():
        qs = Produit.objects.filter(sku=sku, description__startswith=filtre(ligne))
        for p in qs.iterator():
            _ancienne, sep, reste = p.description.partition('\n')
            p.description = premiere(ligne, reste) + sep + reste
            p.save(update_fields=['description'])


def corriger(apps, schema_editor):
    _changer(apps, lambda _l: PREFIXE, lambda ligne, _reste: ligne)


def retablir(apps, schema_editor):
    _changer(apps, lambda ligne: ligne + '\n',
             lambda _l, reste: (PREMIERE_LIGNE_1206 if MARQUE_1206 in reste
                                else PREFIXE))


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0174_rpdf_garanties_maroc'),
    ]

    operations = [
        migrations.RunPython(corriger, retablir),
    ]
