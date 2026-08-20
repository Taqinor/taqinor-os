"""PVLV (fondateur 21/08/2026) — la batterie HV « 16 kWh » est une Deye.

La facture fournisseur Solarex S26/001708 (27/07/2026) nomme le produit
« 16kWh BOS-B-Pro Battery Pack-deye » : c'est le module officiel Deye
BOS-B-Pack16-A3 (système BOS-B Pro-A3) — PAS une Dyness (c'est pourquoi
aucune configuration Dyness ne faisait 16 kWh). Le SKU historique
``BAT-DYN-HV-16`` NE CHANGE PAS (appariement par SKU, même règle que
Deyness→Dyness, migration 0121) ; cette migration corrige sur les bases
existantes ce que le seeder ne touche jamais après création :

  * ``nom``    : « Batterie Dyness haute tension — 16 kWh »
              →  « Batterie Deye BOS-B Pro haute tension — 16 kWh »
                 — UNIQUEMENT si le nom porte encore exactement l'ancien
                 libellé seedé (un nom retouché par le fondateur est à lui) ;
                 le mot-clé « haute tension » RESTE dans le nom (la garde
                 anti-composition basse tension s'appuie dessus) ;
  * ``marque`` : « Dyness » → « Deye » — même garde (seulement si encore
                 « Dyness » ou vide).

Le reste (description, garantie, fiche technique 16,08 kWh / 51,2 V / 314 Ah,
prix d'achat 28 000 HT) arrive par les canaux existants : ré-application des
fiches produit par le seeder au déploiement et migration 0125 (comble les
champs de fiche vides depuis ``FICHES_TECHNIQUES``).

RÉVERSIBLE : non — ``noop`` (un nom corrigé puis retouché par le fondateur ne
doit jamais être « détricoté » vers Dyness).
"""
from django.db import migrations

_SKU = 'BAT-DYN-HV-16'
_ANCIEN_NOM = 'Batterie Dyness haute tension — 16 kWh'
_NOUVEAU_NOM = 'Batterie Deye BOS-B Pro haute tension — 16 kWh'


def corriger_identite(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for produit in Produit.objects.filter(sku=_SKU).iterator():
        champs = []
        if produit.nom == _ANCIEN_NOM:
            produit.nom = _NOUVEAU_NOM
            champs.append('nom')
        if (produit.marque or '').strip() in ('', 'Dyness'):
            produit.marque = 'Deye'
            champs.append('marque')
        if champs:
            produit.save(update_fields=champs)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0126_pvlv_prix_deye_lv'),
    ]

    operations = [
        migrations.RunPython(corriger_identite, migrations.RunPython.noop),
    ]
