# AUD820 — unicité DB du partage niveau enregistrement.
#
# `core.sharing.share_object` s'appuyait sur un `update_or_create` SANS aucune
# garde en base : deux requêtes de partage concurrentes sur le même (objet,
# principal) passaient toutes deux le SELECT et créaient DEUX lignes. Révoquer
# « le » partage en laissait une active — un accès fantôme invisible des écrans.
#
# La migration est en deux temps, dans cet ordre obligatoire :
#   1. DÉDOUBLONNAGE — on garde la ligne la plus RÉCENTE (pk max = dernier
#      partage accordé, donc le niveau/l'expiration les plus à jour) et on
#      supprime les autres. Aucun accès n'est retiré : la ligne conservée porte
#      exactement le même (company, objet, principal).
#   2. AddConstraint — l'unicité devient une garantie du moteur, pas une
#      intention applicative.
# Réversible : retirer la contrainte suffit (le dédoublonnage n'est pas rejoué
# à l'envers — on ne recrée jamais des doublons).

from django.db import migrations, models


def dedoublonner(apps, schema_editor):
    """Supprime les doublons (company, ct, object_id, principal) pré-existants.

    Traite par LOTS de clés dupliquées (jamais un balayage global non borné) :
    le volume attendu est nul ou marginal, mais la boucle reste bornée par le
    nombre de clés en doublon, pas par la taille de la table.
    """
    SharingRule = apps.get_model('core', 'SharingRule')
    champs = ['company_id', 'content_type_id', 'object_id',
              'principal_type', 'principal_id']
    doublons = (SharingRule.objects
                .values(*champs)
                .annotate(n=models.Count('id'))
                .filter(n__gt=1))
    for cle in doublons.iterator(chunk_size=200):
        cle.pop('n', None)
        ids = list(SharingRule.objects.filter(**cle)
                   .order_by('-id').values_list('id', flat=True))
        # ids[0] = la règle la plus récente : on la garde, on jette le reste.
        if len(ids) > 1:
            SharingRule.objects.filter(id__in=ids[1:]).delete()


def noop(apps, schema_editor):
    """Retour arrière : on ne recrée JAMAIS des doublons."""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0047_ntdata30_export_incremental'),
    ]

    operations = [
        migrations.RunPython(dedoublonner, noop),
        migrations.AddConstraint(
            model_name='sharingrule',
            constraint=models.UniqueConstraint(
                fields=('company', 'content_type', 'object_id',
                        'principal_type', 'principal_id'),
                name='core_sharingrule_unique_principal'),
        ),
    ]
