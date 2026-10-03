"""AGR402 — reprise de l'existant : les réponses agricoles du site restées
dans ``web_questionnaire`` passent dans leurs colonnes AGR400.

DONNÉES seulement (aucun changement de schéma), patron 0117 (QJR595). Une clé
n'est déplacée que si sa colonne est VIDE et que la valeur tient dans la
colonne ; la clé déplacée est RETIRÉE du sac, celle qui ne l'est pas y reste.
Idempotente (une clé déplacée n'est plus dans le sac ; une colonne remplie
n'est plus vide). Retour arrière : no-op. Prod 02/10/2026 : aucune clé de ce
type, donc aucun effet en prod.

La table est COPIÉE ici (jamais importée du code de l'app : une migration ne
doit pas changer de sens quand le code évolue).
"""
from decimal import Decimal, InvalidOperation

from django.db import migrations

LOT = 500

#: clé du sac → (colonne, colonne de provenance posée à « site_web » ou None,
#: borne stricte de la colonne ou None, vocabulaire fermé ou None).
PROMOTIONS = (
    ('water_source', 'source_eau', None, None,
     ('puits', 'forage', 'bassin', 'riviere')),
    ('profondeur_m', 'niveau_statique_m', 'niveau_statique_source',
     Decimal('100000'), None),
    ('besoin_m3j', 'besoin_eau_m3j', 'besoin_eau_source',
     Decimal('10000000'), None),
    ('irrigation', 'irrigation_methode', None, None,
     ('goutte', 'aspersion', 'gravitaire')),
    ('culture', 'culture', None, None, None),
    ('surface_ha', 'surface_irriguee_ha', None, Decimal('10000000'), None),
    ('region_agricole', 'region_agricole', None, None,
     ('souss-massa', 'doukkala', 'tadla', 'saiss', 'oriental',
      'draa-tafilalet', 'gharb-loukkos', 'haouz')),
    ('fuel_spend_mad', 'depense_carburant_mad_mois', None,
     Decimal('100000000'), None),
)

CLES = tuple(p[0] for p in PROMOTIONS)


def _dec(raw):
    if isinstance(raw, bool) or raw in (None, ''):
        return None
    try:
        val = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    return val if val.is_finite() and val >= 0 else None


def _valeur(raw, borne, choix):
    if choix is not None:
        return raw if raw in choix else None
    if borne is not None:
        val = _dec(raw)
        return val if val is not None and val < borne else None
    texte = str(raw).strip()[:120] if raw not in (None, '') else ''
    return texte or None


def deplacer(apps, schema_editor):
    Lead = apps.get_model('crm', 'Lead')
    pks = list(
        Lead.objects.exclude(web_questionnaire=None)
        .exclude(web_questionnaire={})
        .order_by('pk').values_list('pk', flat=True))
    for i in range(0, len(pks), LOT):
        for lead in Lead.objects.filter(pk__in=pks[i:i + LOT]):
            sac = lead.web_questionnaire
            if not isinstance(sac, dict) or not any(c in sac for c in CLES):
                continue
            champs = []
            for cle, colonne, source, borne, choix in PROMOTIONS:
                if cle not in sac:
                    continue
                if getattr(lead, colonne) not in (None, ''):
                    continue
                valeur = _valeur(sac.get(cle), borne, choix)
                if valeur is None:
                    continue
                setattr(lead, colonne, valeur)
                champs.append(colonne)
                if source:
                    setattr(lead, source, 'site_web')
                    champs.append(source)
                sac = {k: v for k, v in sac.items() if k != cle}
            if champs:
                lead.web_questionnaire = sac
                champs.append('web_questionnaire')
                lead.save(update_fields=champs)


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0119_agr401_pompe_actuelle_cv'),
    ]

    operations = [
        migrations.RunPython(deplacer, migrations.RunPython.noop),
    ]
