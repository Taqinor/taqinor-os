"""ATOT32 — référence de facture de licence UNIQUE par société.

1. Dédoublonnage d'abord : pour chaque (société, référence non vide) portée
   par plusieurs lignes, la plus ancienne (plus petit id) garde sa référence ;
   les suivantes reçoivent ``<référence>-D<id>`` (tronqué à 40), visible et
   traçable — aucune ligne supprimée.
2. Puis ``UniqueConstraint(company, reference)`` hors brouillons (référence
   vide).

Retour arrière : la contrainte est retirée ; le dédoublonnage n'est pas annulé
(no-op documenté — réintroduire un doublon n'a pas de sens).
"""
from django.db import migrations, models
from django.db.models import Count


def dedoublonner(apps, schema_editor):
    FactureLicence = apps.get_model('adminops', 'FactureLicence')
    doublons = (FactureLicence.objects.exclude(reference='')
                .values('company_id', 'reference')
                .annotate(n=Count('id')).filter(n__gt=1))
    for d in doublons:
        lignes = list(FactureLicence.objects.filter(
            company_id=d['company_id'], reference=d['reference'])
            .order_by('id'))
        for ligne in lignes[1:]:
            ligne.reference = f"{d['reference']}-D{ligne.pk}"[:40]
            ligne.save(update_fields=['reference'])


def rien(apps, schema_editor):
    """No-op documenté."""


class Migration(migrations.Migration):

    dependencies = [
        ('adminops', '0008_sol9_plan_solaire_choice'),
    ]

    operations = [
        migrations.RunPython(dedoublonner, rien),
        migrations.AddConstraint(
            model_name='facturelicence',
            constraint=models.UniqueConstraint(
                condition=models.Q(('reference', ''), _negated=True),
                fields=('company', 'reference'),
                name='adminops_facturelicence_reference_uniq'),
        ),
    ]
