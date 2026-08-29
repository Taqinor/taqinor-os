"""Dé-doublonnage des produits SANS SKU homonymes (préalable à la contrainte).

Ordre fondateur 29/08/2026 — fermeture de la course pré-existante sur
``stock.Produit`` : ``apps.ventes.services._produit_frais_refactures`` faisait
un ``get_or_create(company=…, nom=…)`` alors qu'AUCUNE contrainte d'unicité ne
portait sur ``(company, nom)``. Deux requêtes concurrentes (webhook, tâche
Celery, double clic) pouvaient donc créer DEUX fiches « Frais refacturés » pour
la même société — la course documentée de ``get_or_create``.

PÉRIMÈTRE DE L'UNICITÉ (raisonnement, cf. ``stock.models.Produit.Meta``)
-----------------------------------------------------------------------
Un UNIQUE nu sur ``(company, nom)`` serait FAUX pour ce catalogue :

  * le seeder (``seed_catalogue``) ne saute un article que si un produit ACTIF
    porte déjà ce nom — « an archived demo product frees its name for the
    catalogue item » : un produit ARCHIVÉ doit pouvoir garder le nom d'un
    produit actif (les 6 coffrets variateurs placeholders sont ARCHIVÉS, jamais
    supprimés, autorisation fondateur) ;
  * deux SKU distincts peuvent légitimement porter le même nom ; l'unicité des
    produits SKUés est DÉJÀ assurée par ``unique_together ('company', 'sku')``.

La contrainte posée par la migration suivante (0135) ne couvre donc QUE la
surface réellement en course : produits ACTIFS et SANS SKU (NULL ou vide).
Cette migration nettoie EXACTEMENT ce même périmètre.

CE QUI EST FAIT AUX DOUBLONS
----------------------------
RIEN N'EST SUPPRIMÉ. Par société et par nom, la fiche la plus ANCIENNE (plus
petit ``pk``) est laissée STRICTEMENT INTACTE ; les suivantes sont RENOMMÉES
« <nom> (doublon N) » (N croissant, en évitant tout nom déjà pris dans la
société). Prix, quantités, stock, archivage : jamais touchés. Un résumé des
renommages est imprimé pendant le ``migrate`` (visible dans le log de déploiement).

RÉVERSIBILITÉ : oui, bornée. Le sens inverse retire le suffixe « (doublon N) »
d'un produit ACTIF SANS SKU dont le nom de base est encore porté par un autre
produit actif sans SKU de la même société — c'est-à-dire exactement la forme
que ce dé-doublonnage a créée, et rien d'autre (un produit que le fondateur
aurait lui-même nommé « … (doublon 2) » sans homonyme n'est jamais touché).
"""
import re

from django.db import migrations, models

#: Suffixe de désambiguïsation posé par ce dé-doublonnage.
_SUFFIXE_RE = re.compile(r'^(?P<base>.+) \(doublon (?P<n>\d+)\)$')

#: Longueur du champ ``Produit.nom`` — le nom renommé ne doit jamais déborder.
_NOM_MAX = 255


def _qs_sans_sku(Produit):
    """Produits ACTIFS et SANS SKU : le périmètre EXACT de la contrainte."""
    return Produit.objects.filter(is_archived=False).filter(
        models.Q(sku__isnull=True) | models.Q(sku=''))


def dedoublonner(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')

    vus = set()          # (company_id, nom) déjà attribués dans le périmètre
    renommes = []
    # ``pk`` croissant : la fiche la plus ancienne d'un nom est vue en premier
    # et reste intacte. ``iterator`` (jamais de ``.update()`` global) — patron
    # check_safe_migrations.
    for produit in _qs_sans_sku(Produit).order_by(
            'company_id', 'nom', 'pk').iterator(chunk_size=500):
        cle = (produit.company_id, produit.nom)
        if cle not in vus:
            vus.add(cle)
            continue

        ancien = produit.nom
        n = 2
        while True:
            candidat = f'{ancien} (doublon {n})'
            if len(candidat) > _NOM_MAX:
                # Nom déjà à la limite : on tronque la BASE, jamais le suffixe.
                marque = f' (doublon {n})'
                candidat = ancien[:_NOM_MAX - len(marque)] + marque
            libre = (produit.company_id, candidat) not in vus and not (
                Produit.objects.filter(
                    company_id=produit.company_id, nom=candidat)
                .exclude(pk=produit.pk).exists())
            if libre:
                break
            n += 1

        produit.nom = candidat
        produit.save(update_fields=['nom'])
        vus.add((produit.company_id, candidat))
        renommes.append((produit.pk, ancien, candidat))

    if renommes:
        print(f"\nstock.0134 — {len(renommes)} produit(s) sans SKU homonyme(s) "
              "renommé(s) (aucune suppression) :")
        for pk, ancien, nouveau in renommes:
            print(f"  produit #{pk} : « {ancien} » -> « {nouveau} »")
    else:
        print("\nstock.0134 — aucun doublon (company, nom) sans SKU trouvé.")


def restaurer(apps, schema_editor):
    """Sens inverse : retire le suffixe « (doublon N) » là où c'est sûr."""
    Produit = apps.get_model('stock', 'Produit')

    restaures = []
    for produit in _qs_sans_sku(Produit).order_by('-pk').iterator(
            chunk_size=500):
        m = _SUFFIXE_RE.match(produit.nom or '')
        if not m:
            continue
        base = m.group('base')
        # On ne restaure que si le nom de base est ENCORE porté par un autre
        # produit du même périmètre : c'est la signature du dé-doublonnage.
        if not _qs_sans_sku(Produit).filter(
                company_id=produit.company_id, nom=base).exists():
            continue
        produit.nom = base
        produit.save(update_fields=['nom'])
        restaures.append((produit.pk, base))

    if restaures:
        print(f"\nstock.0134 (inverse) — {len(restaures)} nom(s) restauré(s).")


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0133_bathomo_max_modules_par_banc_min1'),
    ]

    operations = [
        migrations.RunPython(dedoublonner, restaurer),
    ]
