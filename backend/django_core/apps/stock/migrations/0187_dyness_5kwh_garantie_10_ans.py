"""Dyness DL5.0C d'origine (BAT-DEY-5) — garantie remise à 10 ans.

Décision fondateur du 24/11/2026 : les batteries Dyness 5 kWh posées sont des
DL5.0C d'ORIGINE (aucun « V2 » sur l'étiquette). Conditions de garantie
officielles Dyness, version Afrique V2-202502
(https://dyness.com/Public/Uploads/uploadfile/files/20251022/
DynessWarrantyTermsDL5.0Cfeizhouban2.pdf) : la DL5.0C d'origine est garantie
10 ans ; seule la DL5.0C V2 a 7 ans de base. Le 7 ans posé par 0174 (27/10,
« à la place du fondateur, à revoir ») est donc retiré.

Même prudence que 0174 : seul un produit qui porte EXACTEMENT le texte semé
« 7 ans » change, et ``garantie_mois`` 84 → 120 seulement s'il vaut encore 84.
Une valeur saisie par le fondateur n'est jamais écrasée. Réversible.
"""
from django.db import migrations

ANCIEN_TEXTE = ('Garantie constructeur 7 ans · '
                '6 000 cycles (0,2C, 25 °C, DoD 90 %)')
NOUVEAU_TEXTE = ('Garantie constructeur 10 ans · '
                 '6 000 cycles (0,2C, 25 °C, DoD 90 %)')


def _changer(qs, regles):
    """Quelques lignes au plus (un SKU × sociétés) : parcours par
    ``.iterator()`` et sauvegarde ciblée, jamais un update global.
    ``regles`` = {champ: {ancienne valeur: nouvelle}}."""
    for p in qs.iterator():
        champs = []
        for champ, table in regles.items():
            actuel = getattr(p, champ)
            if actuel in table:
                setattr(p, champ, table[actuel])
                champs.append(champ)
        if champs:
            p.save(update_fields=champs)


def corriger(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    _changer(Produit.objects.filter(sku='BAT-DEY-5'), {
        'garantie': {ANCIEN_TEXTE: NOUVEAU_TEXTE},
        'garantie_mois': {84: 120}})


def retablir(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    _changer(Produit.objects.filter(sku='BAT-DEY-5'), {
        'garantie': {NOUVEAU_TEXTE: ANCIEN_TEXTE},
        'garantie_mois': {120: 84}})


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0186_acal816_fiche_bus_dc_redresse'),
    ]

    operations = [
        migrations.RunPython(corriger, retablir),
    ]
