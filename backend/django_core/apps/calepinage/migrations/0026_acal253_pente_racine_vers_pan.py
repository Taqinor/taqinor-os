# ACAL253 (C-ACAL-022) — la pente RACINE ``penteDeg`` (ancien onglet Pente)
# devient la pente du PAN quand le document n'a qu'un pan ; sinon rien n'est
# deviné : la clé est retirée et une note de chatter dit « pente saisie X° non
# attribuée (plusieurs pans) ». Après migration, AUCUN document ne porte plus
# ``penteDeg`` / ``penteSource`` à la racine (schéma roof_layout_v2, ACAL2).
#
# DRY-RUN D'ABORD (founder) : ``inventaire_pente_racine(apps)`` liste, sans
# rien écrire, (calepinage, devis lié et son statut, pente avant → après) —
# à soumettre au fondateur AVANT le merge ; un calepinage lié à un devis
# ENVOYÉ n'est pas modifié sans son accord. Le devis lui-même n'est JAMAIS
# réécrit ici (son ``roof_layout`` figé reste tel quel).
#
# Lot par lot (``iterator``), une ligne mise à jour par document. Réversible :
# l'inverse restaure ``penteDeg`` / ``penteSource`` depuis le ``pitchSource``
# du pan unique (une note de chatter n'est pas défaite : elle est l'histoire).
from django.db import migrations

TAILLE_LOT = 200
MODES = ('degres', 'pourcentage', 'cotes')


def _nombre(valeur):
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    if isinstance(valeur, str):
        try:
            return float(valeur.replace(',', '.').strip())
        except ValueError:
            return None
    return None


def _mode(pente_source):
    if isinstance(pente_source, str) and pente_source in MODES:
        return pente_source
    if isinstance(pente_source, dict) and pente_source.get('mode') in MODES:
        return pente_source['mode']
    return 'degres'


def _texte_degres(valeur):
    return ('%g' % valeur).replace('.', ',')


def migrer_document(layout):
    """``(nouveau_layout, note | None)`` — PUR. ``nouveau_layout`` est
    ``None`` quand le document ne porte pas de pente racine."""
    if not isinstance(layout, dict) or (
            'penteDeg' not in layout and 'penteSource' not in layout):
        return None, None
    document = dict(layout)
    pente = _nombre(document.pop('penteDeg', None))
    source = document.pop('penteSource', None)
    zones = document.get('zones')
    zones = zones if isinstance(zones, list) else []
    if len(zones) == 1 and isinstance(zones[0], dict):
        if pente is not None:
            pan = dict(zones[0])
            pan['pitchDeg'] = pente
            pan['pitchSource'] = {'mode': _mode(source), 'degres': pente}
            document['zones'] = [pan]
        return document, None
    if pente is None:
        return document, None
    motif = 'plusieurs pans' if len(zones) > 1 else 'aucun pan'
    return document, ('pente saisie %s° non attribuée (%s)'
                      % (_texte_degres(pente), motif))


def _a_migrer(apps):
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    from django.db.models import Q

    return (Calepinage.objects
            .filter(Q(roof_layout__has_key='penteDeg')
                    | Q(roof_layout__has_key='penteSource'))
            .order_by('pk'))


def inventaire_pente_racine(apps):
    """DRY-RUN — ``[{calepinage, devis, statut_devis, pente_avant,
    pitch_avant, pitch_apres, note}]``, AUCUNE écriture."""
    Devis = apps.get_model('ventes', 'Devis')
    lignes = []
    for calepinage in _a_migrer(apps).iterator(chunk_size=TAILLE_LOT):
        layout = calepinage.roof_layout
        nouveau, note = migrer_document(layout)
        zones_avant = layout.get('zones') if isinstance(layout, dict) else None
        zones_apres = (nouveau or {}).get('zones')
        avant = (zones_avant[0].get('pitchDeg')
                 if isinstance(zones_avant, list) and len(zones_avant) == 1
                 and isinstance(zones_avant[0], dict) else None)
        apres = (zones_apres[0].get('pitchDeg')
                 if isinstance(zones_apres, list) and len(zones_apres) == 1
                 and isinstance(zones_apres[0], dict) else None)
        statut = (Devis.objects.filter(pk=calepinage.devis_id)
                  .values_list('statut', flat=True).first()
                  if calepinage.devis_id else None)
        lignes.append({
            'calepinage': calepinage.pk, 'devis': calepinage.devis_id,
            'statut_devis': statut, 'pente_avant': layout.get('penteDeg'),
            'pitch_avant': avant, 'pitch_apres': apres, 'note': note})
    return lignes


def migrer_pente_racine(apps, schema_editor):
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Activity = apps.get_model('records', 'Activity')
    type_calepinage = ContentType.objects.filter(
        app_label='calepinage', model='calepinage').first()
    for calepinage in _a_migrer(apps).iterator(chunk_size=TAILLE_LOT):
        nouveau, note = migrer_document(calepinage.roof_layout)
        if nouveau is None:
            continue
        Calepinage.objects.filter(pk=calepinage.pk).update(
            roof_layout=nouveau)
        if note and type_calepinage is not None:
            Activity.objects.create(
                company_id=calepinage.company_id,
                content_type=type_calepinage, object_id=calepinage.pk,
                kind='note', body=note)


def restaurer_pente_racine(apps, schema_editor):
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    for calepinage in (Calepinage.objects.order_by('pk')
                       .iterator(chunk_size=TAILLE_LOT)):
        layout = calepinage.roof_layout
        if not isinstance(layout, dict) or 'penteDeg' in layout:
            continue
        zones = layout.get('zones')
        if not (isinstance(zones, list) and len(zones) == 1
                and isinstance(zones[0], dict)):
            continue
        source = zones[0].get('pitchSource')
        if not isinstance(source, dict) or source.get('degres') is None:
            continue
        document = dict(layout)
        document['penteDeg'] = source['degres']
        document['penteSource'] = source.get('mode') or 'degres'
        Calepinage.objects.filter(pk=calepinage.pk).update(
            roof_layout=document)


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0025_acal247_pose_prevu_fige'),
        ('records', '0013_vx210_snooze_trigger_event'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(migrer_pente_racine, restaurer_pente_racine),
    ]
