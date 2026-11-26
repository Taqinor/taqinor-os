"""D-ACAL-129 (fondateur 25/11/2026, « Yes: 220 V / 380 V ») — tension et CV des
petites pompes du lot POMPAGE du seeder (et de ``PMP-IMM-2M``, présente en
production), restés vides sur les bases existantes.

* ``tension_v`` : 220 V pour une pompe monophasée, 380 V pour une triphasée ;
  la phase de chaque SKU est FIGÉE ci-dessous (jamais d'import du code vivant :
  la migration doit se rejouer sur une base neuve dans des années). Un test
  sans base vérifie qu'elle égale aujourd'hui ce que lit le kit
  (``core.pompage.selection.alimentation_produit``) sur la désignation ;
* ``pompe_cv`` : la valeur que le seeder déclare pour ce SKU (rien pour
  ``PMP-IMM-2M``, que le seeder ne déclare pas).

Gardes : SKU comparé sans la casse (la production écrit ``Pmp-imm-2m``), dans
toute société ; chaque champ n'est écrit QUE s'il est vide ; ``pompe_kw`` n'est
jamais écrit (l'ERP le déduit des CV) ; aucun autre champ, aucun article créé ;
idempotente. Le retour vide les seuls champs qui portent encore EXACTEMENT la
valeur que la migration y écrirait.
"""
from decimal import Decimal

from django.db import migrations

#: SKU (comparé sans la casse) → (phase, CV déclarés par le seeder ou ``None``).
POMPES = {
    'PMP-IMM-1.5M': ('mono', Decimal('1.5')),
    'PMP-IMM-3M': ('mono', Decimal('3')),
    'PMP-IMM-4T': ('tri', Decimal('4')),
    'PMP-IMM-5.5T': ('tri', Decimal('5.5')),
    'PMP-IMM-7.5T': ('tri', Decimal('7.5')),
    'PMP-IMM-10T': ('tri', Decimal('10')),
    'PMP-SUR-1.5M': ('mono', Decimal('1.5')),
    'PMP-SUR-3T': ('tri', Decimal('3')),
    'PMP-IMM-2M': ('mono', None),
}
#: Phase → tension (V).
TENSIONS = {'mono': 220, 'tri': 380}
#: Lignes lues par lots (garde check_safe_migrations) : chaque ligne est mise à
#: jour par sa seule clé primaire.
TAILLE_BATCH = 500


def poser(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, (phase, cv) in POMPES.items():
        tension = TENSIONS[phase]
        for produit in Produit.objects.filter(sku__iexact=sku).order_by('pk').iterator(chunk_size=TAILLE_BATCH):
            champs = {}
            if produit.tension_v is None:
                champs['tension_v'] = tension
            if cv is not None and produit.pompe_cv is None:
                champs['pompe_cv'] = cv
            if champs:
                Produit.objects.filter(pk=produit.pk).update(**champs)


def retirer(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for sku, (phase, cv) in POMPES.items():
        tension = TENSIONS[phase]
        for produit in Produit.objects.filter(sku__iexact=sku).order_by('pk').iterator(chunk_size=TAILLE_BATCH):
            champs = {}
            if produit.tension_v == tension:
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
