# AMET23 (D-PROVENANCE, C-AMET-025) — colonne ``Lead.saisies_humaines`` (JSON,
# liste des champs saisis par un humain) + rattrapage depuis ``LeadActivity`` :
# toute modification journalisée AVEC utilisateur marque sa clé. Additive,
# idempotente (union triée, rejouable), réversible (l'inverse du rattrapage est
# un no-op : la colonne est simplement retirée).

from django.db import migrations, models


def rattraper_saisies_humaines(apps, schema_editor):
    Lead = apps.get_model('crm', 'Lead')
    LeadActivity = apps.get_model('crm', 'LeadActivity')
    champs_lead = {f.name for f in Lead._meta.concrete_fields}
    champs_lead.discard('saisies_humaines')
    par_lead = {}
    activites = (LeadActivity.objects
                 .filter(kind='modification', user__isnull=False,
                         field__isnull=False)
                 .exclude(field='')
                 .values_list('lead_id', 'field').distinct())
    for lead_id, champ in activites.iterator():
        if champ in champs_lead:
            par_lead.setdefault(lead_id, set()).add(champ)
    for lead_id, champs in par_lead.items():
        lead = Lead.objects.filter(pk=lead_id).only('id', 'saisies_humaines').first()
        if lead is None:
            continue
        valeurs = sorted(set(lead.saisies_humaines or []) | champs)
        if valeurs != list(lead.saisies_humaines or []):
            Lead.objects.filter(pk=lead_id).update(saisies_humaines=valeurs)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0132_acrm32_lead_whatsapp_normalise_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='saisies_humaines',
            field=models.JSONField(
                blank=True, default=list,
                verbose_name='Champs saisis par un humain'),
        ),
        migrations.RunPython(rattraper_saisies_humaines, noop_reverse),
    ]
