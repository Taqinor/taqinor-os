"""CCAT (28/10/2026) — deux textes de fiche semés, imprimés tels quels au client.

* Huawei C&I (``OND-R-HUA-50T/100T/150T``) : « Garantie constructeur 5 ans
  (extensible jusqu'à 20 ans) » → « Garantie constructeur 5 ans ». Règle
  fondateur D-RES-2710-GAR (27/10) : une garantie client = UNE durée, la durée
  de base ; une extension payante non achetée ne s'imprime pas.
* Afficheur ``VEI-SI22-AFF`` : « … pour variateur VEICHI SI22 » s'imprimait
  sous un variateur SI23 (kit pompage, constat AGC) → « … pour variateur VEICHI ».

Même patron que 0174 : seule la valeur EXACTE semée change ; une saisie du
fondateur reste à lui. Réversible.
"""
from django.db import migrations

_SUITE_AFF = '\nLecture des paramètres et défauts au pied du coffret'
CHANGEMENTS = (
    ('garantie', ('OND-R-HUA-50T', 'OND-R-HUA-100T', 'OND-R-HUA-150T'),
     "Garantie constructeur 5 ans (extensible jusqu'à 20 ans)",
     'Garantie constructeur 5 ans'),
    ('description', ('VEI-SI22-AFF',),
     'Afficheur déporté pour variateur VEICHI SI22' + _SUITE_AFF,
     'Afficheur déporté pour variateur VEICHI' + _SUITE_AFF),
)


def _changer(apps, sens):
    """Quelques lignes au plus (SKU semés × sociétés) : sauvegarde ciblée."""
    Produit = apps.get_model('stock', 'Produit')
    for champ, skus, ancien, nouveau in CHANGEMENTS:
        de, vers = (ancien, nouveau) if sens else (nouveau, ancien)
        qs = Produit.objects.filter(sku__in=skus, **{champ: de})
        for p in qs.iterator():
            setattr(p, champ, vers)
            p.save(update_fields=[champ])


def corriger(apps, schema_editor):
    _changer(apps, True)


def retablir(apps, schema_editor):
    _changer(apps, False)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0175_ccat15_description_hybrides_deye'),
    ]

    operations = [
        migrations.RunPython(corriger, retablir),
    ]
