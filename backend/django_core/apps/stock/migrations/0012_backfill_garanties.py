"""Backfill des durées de garantie par catégorie / marque / type de produit.

Migration de DONNÉES uniquement : aucun changement de schéma.
Règles (fondateur, 2026-06-13), appliquées UNIQUEMENT aux champs encore vides
(jamais d'écrasement d'une valeur déjà saisie, aucune suppression) :

  - Batteries / stockage (toute marque) ........... garantie_mois = 120
    (PRÉCÉDENCE : un produit batterie gagne la règle batterie quelle que soit
    sa marque, avant toute règle onduleur.)
  - Onduleurs Huawei ............................... garantie_mois = 120
  - Onduleurs Deye (onduleurs seulement) ........... garantie_mois = 60
  - Panneaux / modules PV (toute marque) ........... garantie_mois = 144
                                              ET garantie_production_mois = 360
  - Pompes (OSP 30 / pompage) ...................... garantie_mois = 24
  - Variateurs / VEICHI (SI22, SI23, SI30, coffrets) garantie_mois = 24
  - Structures, câbles, transport, services, et tout
    ce qui n'est pas un équipement ................. laissés vides
  - Produit non classable avec certitude ........... laissé vide

garantie_production_mois n'est posé QUE sur les panneaux.
Le sens inverse est volontairement un no-op : on ne peut pas savoir quelles
valeurs étaient vides avant ce backfill.
"""
from django.db import migrations


def _norm(s):
    """Minuscule + accents usuels aplatis, pour des mots-clés robustes."""
    return (s or '').lower().replace('â', 'a').replace('é', 'e').replace('è', 'e')


def _classify(cat, marque, nom):
    """Retourne (garantie_mois, garantie_production_mois) ou (None, None) si
    le produit doit rester vide. cat/marque/nom sont déjà normalisés."""
    text = f'{cat} {nom}'

    # 1) Batteries / stockage — PRÉCÉDENCE absolue, avant la règle onduleur.
    if ('batterie' in text or 'battery' in text or 'stockage' in text
            or 'luna' in text):
        return 120, None

    # 2) Panneaux / modules PV (toute marque).
    if 'panneau' in text or 'module' in text:
        return 144, 360

    # 3) Onduleurs : Huawei = 120, Deye = 60, autres marques = non classable.
    if 'onduleur' in text:
        if 'huawei' in marque or 'huawei' in nom:
            return 120, None
        if 'deye' in marque or 'deye' in nom:
            return 60, None
        return None, None  # onduleur de marque inconnue → laissé vide

    # 4) Pompes (OSP 30 / pompage).
    if 'pompe' in text:
        return 24, None

    # 5) Variateurs / VEICHI / coffrets / afficheur variateur.
    if 'variateur' in text or 'veichi' in marque or 'afficheur' in nom:
        return 24, None

    # 6) Structures, câbles, transport, services, accessoires, etc. → vides.
    return None, None


def backfill_garanties(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    for p in Produit.objects.select_related('categorie').iterator(chunk_size=500):
        cat = _norm(p.categorie.nom) if p.categorie_id else ''
        marque = _norm(p.marque)
        nom = _norm(p.nom)
        gm, gp = _classify(cat, marque, nom)

        update_fields = []
        # On ne remplit QUE les champs vides : jamais d'écrasement.
        if gm is not None and p.garantie_mois in (None,):
            p.garantie_mois = gm
            update_fields.append('garantie_mois')
        if gp is not None and p.garantie_production_mois in (None,):
            p.garantie_production_mois = gp
            update_fields.append('garantie_production_mois')

        if update_fields:
            p.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0011_produit_garantie_mois_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_garanties, migrations.RunPython.noop),
    ]
