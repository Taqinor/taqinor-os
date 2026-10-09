"""ATOT5 — ``Facture.cle_tranche`` : la CLÉ de la tranche d'échéancier
facturée (la tranche suivante n'est plus choisie par position).

ADDITIF : une colonne texte à défaut vide. Rétro-remplissage best-effort des
factures de tranche ACTIVES existantes, devis par devis, dans l'ordre de
création (= l'ordre positionnel qui les a produites), depuis les clés de
l'échéancier du devis ; un devis dont l'échéancier ne se relit pas est laissé
vide (repli positionnel à l'exécution, comportement d'hier). Chaque devis est
traité sous un savepoint : un échec n'interrompt jamais la migration.
Réversible : ``python manage.py migrate facturation 0012`` (la colonne part).
"""
from django.db import migrations, models, transaction


def remplir_cles(apps, schema_editor):
    Facture = apps.get_model('facturation', 'Facture')
    Devis = apps.get_model('ventes', 'Devis')
    factures = (Facture.objects
                .filter(devis__isnull=False, bon_commande__isnull=True,
                        cle_tranche='')
                .exclude(type_facture='complete')
                .exclude(statut='annulee')
                .order_by('devis_id', 'id'))
    par_devis = {}
    for f in factures:
        par_devis.setdefault(f.devis_id, []).append(f)
    if not par_devis:
        return
    from apps.ventes.utils.echeancier import cles_tranches, tranches_normalisees
    for devis in Devis.objects.filter(pk__in=list(par_devis)):
        try:
            with transaction.atomic():
                cles = cles_tranches(tranches_normalisees(devis))
                for facture, cle in zip(par_devis[devis.pk], cles):
                    facture.cle_tranche = cle
                    facture.save(update_fields=['cle_tranche'])
        except Exception:  # noqa: BLE001 — best-effort, repli positionnel
            continue


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0012_ciq216_reference_commande_client'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='cle_tranche',
            field=models.CharField(
                blank=True, default='', max_length=60,
                verbose_name="Clé de tranche d'échéancier"),
        ),
        migrations.RunPython(remplir_cles, migrations.RunPython.noop),
    ]
