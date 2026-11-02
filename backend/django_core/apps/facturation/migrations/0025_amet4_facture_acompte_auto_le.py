"""AMET4 (D-AMET4-PROVISOIRE, 01/11/2026) — ``Facture.acompte_auto_le``.

Colonne NULLABLE (aucune réécriture de table) qui marque le brouillon
d'acompte créé AUTOMATIQUEMENT à l'acceptation : la dés-acceptation ne retire
plus que lui (avant : toute facture d'acompte « BROUILLON-<id> », y compris un
brouillon saisi à la main).

Reprise : les brouillons d'acompte automatiques nés avant cette migration
(VNT62 : « BROUILLON-<id> », type acompte, devis accepté) reçoivent la marque,
par lots de pk — sinon leur dés-acceptation tomberait en 409. Réversible :
revenir à facturation 0023 retire la colonne.
"""
from django.db import migrations, models
from django.utils import timezone

LOT = 500


def marquer_acomptes_automatiques(apps, schema_editor):
    Facture = apps.get_model('facturation', 'Facture')
    pks = list(Facture.objects.filter(
        statut='brouillon', type_facture='acompte',
        reference__startswith='BROUILLON-', devis__statut='accepte',
        acompte_auto_le__isnull=True).values_list('pk', flat=True))
    maintenant = timezone.now()
    for debut in range(0, len(pks), LOT):
        batch = pks[debut:debut + LOT]
        Facture.objects.filter(pk__in=batch).update(acompte_auto_le=maintenant)


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0024_atot55_total_stocke'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='acompte_auto_le',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Acompte provisoire créé à l'acceptation le"),
        ),
        migrations.RunPython(marquer_acomptes_automatiques,
                             migrations.RunPython.noop),
    ]
