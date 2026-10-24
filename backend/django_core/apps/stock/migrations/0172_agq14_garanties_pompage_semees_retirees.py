"""AGQ14 (D-AGQ-4, 23/10/2026) — retire les 24 mois de garantie SEMÉS sur
les pompes et variateurs du seeder, sans garantie écrite fournisseur (AGRM22
ouvert).

Les 24 mois lus en production sur les OSP / VEICHI viennent de la migration de
données ``0012_backfill_garanties`` (règles « Pompes … = 24 », « Variateurs /
VEICHI … = 24 »), pas du seeder. Décision fondateur : sans durée structurée, le
PDF imprime « garantie : selon fiche fournisseur » et l'omission est nommée
(rendu livré par AGQ14 dans le moteur).

Migration de DONNÉES, destructive mais RÉVERSIBLE, ciblée au plus étroit :
  * ``role_pompage`` ∈ {pompe, variateur_pompage, afficheur_variateur} ;
  * ``garantie_mois == 24`` (la valeur semée, jamais une autre) ;
  * SKU du seeder ``seed_catalogue`` : ``VEI-*`` (variateurs VEICHI et leur
    afficheur) et ``PMP-OSP-*`` (pompes OSP 30) — aucun journal old→new
    propre à ``Produit`` n'existe dans ``apps/stock`` ;
  * EN PLUS, jamais un produit dont ``garantie_mois`` a été modifié par un
    humain : le Journal d'activité (``audit.AuditLog``, diff structuré
    ``changes`` — Produit est un modèle suivi) ne doit porter aucune ligne de
    modification de ce champ pour ce produit (0012 tournait hors requête, donc
    sans ligne de journal).

Retour : remet 24 sur les mêmes SKU / rôles quand ``garantie_mois`` est vide.
"""
from django.db import migrations

ROLES = ('pompe', 'variateur_pompage', 'afficheur_variateur')
PREFIXES = ('VEI-', 'PMP-OSP-')
SEMEE = 24


def _candidats(apps):
    from django.db.models import Q

    Produit = apps.get_model('stock', 'Produit')
    filtre = Q()
    for prefixe in PREFIXES:
        filtre |= Q(sku__startswith=prefixe)
    return Produit.objects.filter(filtre, role_pompage__in=ROLES)


def _edites_par_un_humain(apps, ids):
    """Ids de produits dont ``garantie_mois`` figure dans un diff du Journal."""
    if not ids:
        return set()
    ContentType = apps.get_model('contenttypes', 'ContentType')
    AuditLog = apps.get_model('audit', 'AuditLog')
    ct = ContentType.objects.filter(app_label='stock', model='produit').first()
    if ct is None:
        return set()
    lignes = AuditLog.objects.filter(
        content_type_id=ct.pk, object_id__in=[str(i) for i in ids],
        changes__contains=[{'field': 'garantie_mois'}])
    return {int(o) for o in lignes.values_list('object_id', flat=True)
            if str(o).isdigit()}


#: Mise à jour par paquets de pk (quelques dizaines de SKU en pratique).
TAILLE_CHUNK = 200


def _poser_par_chunk(apps, ids, valeur):
    Produit = apps.get_model('stock', 'Produit')
    for debut in range(0, len(ids), TAILLE_CHUNK):
        chunk = ids[debut:debut + TAILLE_CHUNK]
        Produit.objects.filter(pk__in=chunk).update(garantie_mois=valeur)


def retirer_garanties_semees(apps, schema_editor):
    ids = list(_candidats(apps).filter(garantie_mois=SEMEE)
               .values_list('pk', flat=True))
    garder = _edites_par_un_humain(apps, ids)
    _poser_par_chunk(apps, [i for i in ids if i not in garder], None)


def retablir_garanties_semees(apps, schema_editor):
    ids = list(_candidats(apps).filter(garantie_mois__isnull=True)
               .values_list('pk', flat=True))
    _poser_par_chunk(apps, ids, SEMEE)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0171_alter_imputationavoirfournisseur_avoir_and_more'),
        ('audit', '0009_asec8_caviardage_secrets'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(retirer_garanties_semees,
                             retablir_garanties_semees),
    ]
