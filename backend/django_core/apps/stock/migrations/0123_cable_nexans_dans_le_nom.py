"""Le câble solaire porte la marque Nexans dans son NOM, pas seulement sa
fiche — décision fondateur du 20/08/2026 (constat proposition publique : la
ligne du devis disait « Câble solaire 6mm² (au mètre) », sans nulle part la
marque, alors que le fondateur ne pose QUE du Nexans).

MÊME PATRON que la migration 0121 (« la marque batterie s'écrit Dyness —
renommage systémique sans réécrire l'histoire ») : une migration de DONNÉES,
pas de schéma, parce que ``seed_catalogue`` (rule du docstring du module :
« existing products are NEVER modified ») ne renomme JAMAIS un produit déjà
seedé — seul un ``RunPython`` peut rattraper une base de production.

PÉRIMÈTRE — CINQ SKU, ``Produit.nom`` UNIQUEMENT, RIEN D'AUTRE :
  * CAB-6MM-M       : « Câble solaire 6mm² (au mètre) »
                        → « Câble solaire Nexans 6 mm² (au mètre) »
  * CAB-H1Z2Z2-4-M  : « Câble solaire H1Z2Z2-K 4 mm² (au mètre) »
                        → « Câble solaire Nexans H1Z2Z2-K 4 mm² (au mètre) »
  * CAB-H1Z2Z2-6-M, CAB-H1Z2Z2-10-M, CAB-H1Z2Z2-16-M : même patron (6/10/16).
CAB-NEX-DC-6 et CAB-NEX-TER-6 ne bougent pas : leur nom porte déjà « Nexans »
(règle fondateur du 18/08). Aucun prix, aucune quantité, aucun SKU touché —
``Produit.marque`` reste hors périmètre ici : elle est déjà 'Nexans' sur les
7 SKU câble depuis a002d459 (2026-08-19), réappliquée par le seeder à chaque
déploiement (comblage de champ vide, jamais d'écrasement).

APPARIEMENT PAR SKU + ANCIEN NOM EXACT (pas un simple remplacement de mot
comme la migration 0121) : on est en train d'INSÉRER « Nexans » dans un nom
figé, pas de corriger l'orthographe d'un jeton qui apparaît partout. Ne
touche donc QUE la ligne dont le nom est EXACTEMENT l'ancien libellé — un
nom déjà personnalisé par le fondateur (ou déjà migré) est laissé intact,
et rejouer la migration n'écrit rien de plus (idempotent).

CE QUI N'EST **PAS** TOUCHÉ — LES DOCUMENTS HISTORIQUES : les désignations
figées des lignes de devis (``ventes.DevisLigne.designation``) et les PDF
déjà générés gardent leur texte d'origine, exactement comme pour Dyness ;
c'est la resynchronisation habituelle du devis qui fera suivre les rendus
futurs. La classification par mots-clés (« cable » substring — solar.js,
apps/ventes/services.py, apps/stock/management/commands/seed_catalogue.py::
classify_categorie) matche par sous-chaîne : insérer « Nexans » au milieu
d'un nom qui contient déjà « câble »/« solaire »/« mètre » ne casse aucun
classifieur (vérifié — aucun changement requis là-bas).

RÉVERSIBILITÉ : ``reverse`` réapplique l'ancien libellé sur les mêmes cinq
lignes (matchées cette fois par le NOUVEAU nom exact).
"""
from django.db import migrations

# (sku, ancien nom exact, nouveau nom)
_RENOMMAGES = (
    ('CAB-6MM-M',
     'Câble solaire 6mm² (au mètre)',
     'Câble solaire Nexans 6 mm² (au mètre)'),
    ('CAB-H1Z2Z2-4-M',
     'Câble solaire H1Z2Z2-K 4 mm² (au mètre)',
     'Câble solaire Nexans H1Z2Z2-K 4 mm² (au mètre)'),
    ('CAB-H1Z2Z2-6-M',
     'Câble solaire H1Z2Z2-K 6 mm² (au mètre)',
     'Câble solaire Nexans H1Z2Z2-K 6 mm² (au mètre)'),
    ('CAB-H1Z2Z2-10-M',
     'Câble solaire H1Z2Z2-K 10 mm² (au mètre)',
     'Câble solaire Nexans H1Z2Z2-K 10 mm² (au mètre)'),
    ('CAB-H1Z2Z2-16-M',
     'Câble solaire H1Z2Z2-K 16 mm² (au mètre)',
     'Câble solaire Nexans H1Z2Z2-K 16 mm² (au mètre)'),
)


def _renommer(apps, mapping):
    """Renomme chaque ligne dont le SKU ET le nom ACTUEL correspondent
    exactement à ``mapping`` — idempotent (aucune écriture si déjà renommé),
    jamais de doublon créé, jamais de prix/quantité/SKU touché."""
    Produit = apps.get_model('stock', 'Produit')
    for sku, ancien, nouveau in mapping:
        Produit.objects.filter(sku=sku, nom=ancien).update(nom=nouveau)


def marquer_nexans(apps, schema_editor):
    _renommer(apps, _RENOMMAGES)


def demarquer_nexans(apps, schema_editor):
    _renommer(apps, tuple((sku, nouveau, ancien)
                          for sku, ancien, nouveau in _RENOMMAGES))


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0122_pvondh_onduleur_batterie_demarrage_isc'),
    ]

    operations = [
        migrations.RunPython(marquer_nexans, demarquer_nexans),
    ]
