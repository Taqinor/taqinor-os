"""MRY11 — L'étiquette de clôture dit « Injoignable 6 appels ».

Le Protocole de rappel v3 compte SIX appels (plus cinq WhatsApp) sur 14 jours :
l'étiquette posée par ``cloturer_cadence`` annonçait « 7 tentatives », un
chiffre qui ne correspond à rien dans la cadence réelle. Meryem la lit dans sa
liste et dans ses filtres — elle doit dire ce que la cadence a fait.

Deux surfaces à reprendre, société par société :

  * ``crm.LeadTag`` — le référentiel d'étiquettes (suggestions + couleurs).
    Renommé SEULEMENT si la société ne porte pas déjà le nouveau nom : sinon
    ``unique_together (company, nom)`` sauterait, et un renommage aveugle
    écraserait une étiquette que le fondateur aurait déjà créée à la main.
    Dans ce cas l'ancienne ligne est laissée telle quelle (jamais supprimée —
    une étiquette peut être référencée dans des vues sauvegardées).
  * ``crm.Lead.tags`` — le champ LIBRE (texte séparé par des virgules) où
    ``poser_tag_lead`` écrit réellement. Sans cette moitié, les leads déjà
    parqués resteraient étiquetés à l'ancien nom et sortiraient des filtres.

Aucun `.update()` de masse : les lignes concernées sont peu nombreuses (elles
portent toutes la chaîne exacte) et sont reprises une par une, ce qui garde la
migration lisible et sans surprise sur une table peuplée.

Reverse : NO-OP assumé. Revenir en arrière rebaptiserait « 6 appels » en
« 7 tentatives » y compris sur des étiquettes créées après coup — on préfère
une migration non symétrique à une perte d'information.
"""
from django.db import migrations

ANCIEN = 'Injoignable 7 tentatives'
NOUVEAU = 'Injoignable 6 appels'


def _renommer_tags(apps, schema_editor):
    LeadTag = apps.get_model('crm', 'LeadTag')
    existants = set(
        LeadTag.objects.filter(nom=NOUVEAU).values_list('company_id',
                                                        flat=True))
    for tag in LeadTag.objects.filter(nom=ANCIEN).iterator():
        if tag.company_id in existants:
            continue  # la société porte déjà le nouveau nom : on ne touche pas
        tag.nom = NOUVEAU
        tag.save(update_fields=['nom'])
        existants.add(tag.company_id)


def _reecrire_leads(apps, schema_editor):
    Lead = apps.get_model('crm', 'Lead')
    for lead in Lead.objects.filter(tags__contains=ANCIEN).iterator():
        parts = [p.strip() for p in (lead.tags or '').split(',') if p.strip()]
        nouveaux = []
        for part in parts:
            part = NOUVEAU if part == ANCIEN else part
            if part not in nouveaux:
                nouveaux.append(part)
        lead.tags = ', '.join(nouveaux)[:500]
        lead.save(update_fields=['tags'])


def renommer(apps, schema_editor):
    _renommer_tags(apps, schema_editor)
    _reecrire_leads(apps, schema_editor)


def noop(apps, schema_editor):
    """Reverse assumé sans effet (cf. docstring du module)."""


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0092_relanceetape_index_concurrent'),
    ]

    operations = [
        migrations.RunPython(renommer, noop),
    ]
