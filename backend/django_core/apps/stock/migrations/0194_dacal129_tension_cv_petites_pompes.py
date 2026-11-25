"""D-ACAL-129 (fondateur 25/11/2026, « Yes: 220 V / 380 V ») — tension et CV des
petites pompes du lot POMPAGE du seeder (et de ``PMP-IMM-2M``, présente en
production), restés vides sur les bases existantes.

* ``tension_v`` : 220 V pour une pompe monophasée, 380 V pour une triphasée,
  la phase étant lue sur la ligne par la MÊME fonction que le kit
  (``core.pompage.selection.alimentation_produit`` : champ ``alimentation``,
  sinon nom) — importée seulement quand une ligne est à traiter ; phase
  illisible : rien n'est écrit ;
* ``pompe_cv`` : la valeur que le seeder déclare pour ce SKU (table FIGÉE
  ci-dessous ; rien pour ``PMP-IMM-2M``, que le seeder ne déclare pas).

Gardes : SKU comparé sans la casse (la production écrit ``Pmp-imm-2m``), dans
toute société ; chaque champ n'est écrit QUE s'il est vide ; ``pompe_kw`` n'est
jamais écrit (l'ERP le déduit des CV) ; aucun autre champ, aucun article créé ;
idempotente. Le retour vide les seuls champs qui portent encore EXACTEMENT la
valeur que la migration y écrirait.
"""
from decimal import Decimal

from django.db import migrations

#: SKU → CV déclarés par le seeder (``None`` = non déclaré).
POMPES_CV = {
    'PMP-IMM-1.5M': Decimal('1.5'),
    'PMP-IMM-3M': Decimal('3'),
    'PMP-IMM-4T': Decimal('4'),
    'PMP-IMM-5.5T': Decimal('5.5'),
    'PMP-IMM-7.5T': Decimal('7.5'),
    'PMP-IMM-10T': Decimal('10'),
    'PMP-SUR-1.5M': Decimal('1.5'),
    'PMP-SUR-3T': Decimal('3'),
    'PMP-IMM-2M': None,
}


def _tension_de_la_ligne(produit):
    from core.pompage.selection import (
        TENSION_MONO_V, TENSION_TRI_V, alimentation_produit)
    alimentation = alimentation_produit({
        'nom': produit.nom, 'alimentation': produit.alimentation,
        'tension_v': None})
    return {'mono': TENSION_MONO_V, 'tri': TENSION_TRI_V}.get(alimentation)


def _pompes(Produit, sku):
    return Produit.objects.filter(sku__iexact=sku)


def poser(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, cv in POMPES_CV.items():
        for produit in _pompes(Produit, sku):
            champs = {}
            if produit.tension_v is None:
                tension = _tension_de_la_ligne(produit)
                if tension:
                    champs['tension_v'] = tension
            if cv is not None and produit.pompe_cv is None:
                champs['pompe_cv'] = cv
            if champs:
                Produit.objects.filter(pk=produit.pk).update(**champs)


def retirer(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, cv in POMPES_CV.items():
        for produit in _pompes(Produit, sku):
            champs = {}
            if (produit.tension_v is not None
                    and produit.tension_v == _tension_de_la_ligne(produit)):
                champs['tension_v'] = None
            if cv is not None and produit.pompe_cv == cv:
                champs['pompe_cv'] = None
            if champs:
                Produit.objects.filter(pk=produit.pk).update(**champs)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0193_dacal129_fiches_variateurs_veichi'),
    ]

    operations = [
        migrations.RunPython(poser, retirer),
    ]
