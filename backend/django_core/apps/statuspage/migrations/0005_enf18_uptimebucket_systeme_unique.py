"""ENF18 — un seul ``UptimeDayBucket`` SYSTÈME par (composant, région, jour).

``tasks._accumuler_uptime_jour`` n'écrit que des composants système (``company`` NULL) par
``get_or_create(company=None, composant, region, date)``. La contrainte existante
``statuspage_uptimebucket_jour`` porte sur ``company`` : en base NULL != NULL, elle n'épingle
RIEN pour ces lignes et deux ticks simultanés pouvaient créer deux buckets du même jour.
ADDITIVE : une contrainte d'unicité PARTIELLE (``company IS NULL``), les buckets par société
restent couverts par l'ancienne.

Garde-fou : le bucket est un agrégat de comptage (échantillons observés / opérationnels) ; si
une course passée en a laissé des doublons, celui qui a observé le plus d'échantillons est gardé
(à égalité, le plus ancien), les autres sont supprimés AVANT la contrainte — sans quoi la
migration échouerait en prod. Revertable : le retour arrière retire la contrainte (la
suppression des doublons, sans objet sur une table saine, n'est pas rejouée).
"""
from django.db import migrations, models


def dedoublonner(apps, schema_editor):
    """Garde, par (composant, région, jour) système, le bucket aux échantillons les plus nombreux."""
    UptimeDayBucket = apps.get_model('statuspage', 'UptimeDayBucket')
    vus = set()
    doublons = []
    lignes = UptimeDayBucket.objects.filter(
        company__isnull=True,
    ).order_by('-echantillons_total', 'id').values_list(
        'pk', 'composant', 'region', 'date')
    for pk, composant, region, jour in lignes:
        cle = (composant, region, jour)
        if cle in vus:
            doublons.append(pk)
        else:
            vus.add(cle)
    if doublons:
        UptimeDayBucket.objects.filter(pk__in=doublons).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('statuspage', '0004_ntobs33_componentstatuslog'),
    ]

    operations = [
        migrations.RunPython(dedoublonner, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='uptimedaybucket',
            constraint=models.UniqueConstraint(
                fields=('composant', 'region', 'date'),
                condition=models.Q(('company__isnull', True)),
                name='statuspage_uptimebucket_jour_systeme'),
        ),
    ]
