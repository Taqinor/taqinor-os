"""ENF18 — un seul ``ReconciliationSnapshot`` par (société, campagne, jour).

``reconciliation.run_daily_reconciliation`` upserte par
``update_or_create(company, campaign, date)`` : sans contrainte en base, deux runs
simultanés du même jour pouvaient créer deux instantanés. ADDITIVE : une contrainte
d'unicité (les lignes sans campagne — ``SET_NULL`` — ne sont pas concernées,
NULL != NULL).

Garde-fou : l'instantané est une donnée DÉRIVÉE (recalculée chaque jour par
``reconcile``) ; si une course passée en a laissé des doublons, le plus récent (id
le plus grand) est gardé, les autres supprimés AVANT la contrainte — sans quoi la
migration échouerait en prod. Revertable : le retour arrière retire la contrainte
(la suppression des doublons, sans objet sur une table saine, n'est pas rejouée).
"""
from django.db import migrations, models


def dedoublonner(apps, schema_editor):
    """Garde l'instantané le plus récent par (société, campagne, jour)."""
    ReconciliationSnapshot = apps.get_model('adsengine', 'ReconciliationSnapshot')
    vus = set()
    doublons = []
    lignes = ReconciliationSnapshot.objects.filter(
        campaign__isnull=False,
    ).order_by('-id').values_list('pk', 'company_id', 'campaign_id', 'date')
    for pk, company_id, campaign_id, jour in lignes:
        cle = (company_id, campaign_id, jour)
        if cle in vus:
            doublons.append(pk)
        else:
            vus.add(cle)
    if doublons:
        ReconciliationSnapshot.objects.filter(pk__in=doublons).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0060_aacq3_devise_seuils'),
    ]

    operations = [
        migrations.RunPython(dedoublonner, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='reconciliationsnapshot',
            constraint=models.UniqueConstraint(
                fields=('company', 'campaign', 'date'),
                name='uniq_adseng_recon_co_camp_dt'),
        ),
    ]
