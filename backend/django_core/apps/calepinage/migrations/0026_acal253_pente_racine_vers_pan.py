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
#: Lot 3 critique #5 — la MARQUE posée par l'aller sur ``pitchSource`` : le
#: retour ne défait QUE les pans que cette migration a écrits.
MARQUE = 'migrationPenteRacine'

# Lot 3 critique #5 — l'empreinte IMPRIMÉE est RECALCULÉE par la même règle
# que l'app (``apps.ventes.domain.geometrie.layout_hash``), RECOPIÉE ici : une
# migration ne lit pas le code vivant, qui changera.
_CLES_IMPRIMEES_AJOUTEES = (
    'poseSurfaces', 'exclusionZones', 'modules', 'shading12x24',
    'environment', 'shadeObstructions', 'horizonProfile', 'modePoseDeclare',
)


def _vide(valeur):
    return valeur is None or valeur in ('', [], {})


def layout_hash(layout):
    """Copie figée de ``apps.ventes.domain.geometrie.layout_hash``."""
    import hashlib
    import json

    if not isinstance(layout, dict):
        return ''
    canonical = {
        'zones': (layout.get('zones') or layout.get('areas')
                  or layout.get('pans')),
        'result': layout.get('result'),
        'scenario': layout.get('scenario'),
        'panelWatt': layout.get('panelWatt') or layout.get('watt'),
        'battery': bool(layout.get('battery')),
    }
    for cle in _CLES_IMPRIMEES_AJOUTEES:
        valeur = layout.get(cle)
        if not _vide(valeur):
            canonical[cle] = valeur
    blob = json.dumps(canonical, sort_keys=True, separators=(',', ':'),
                      default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


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
            pan['pitchSource'] = {'mode': _mode(source), 'degres': pente,
                                  MARQUE: True}
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
            roof_layout=nouveau, layout_hash=layout_hash(nouveau))
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
        # Seuls les pans MARQUÉS par l'aller sont défaits : une pente saisie
        # dans l'onglet Pente après la migration n'est jamais remontée.
        if not isinstance(source, dict) or not source.get(MARQUE) \
                or source.get('degres') is None:
            continue
        document = dict(layout)
        pan = dict(zones[0])
        pan['pitchSource'] = {cle: valeur for cle, valeur in source.items()
                              if cle != MARQUE}
        document['zones'] = [pan]
        document['penteDeg'] = source['degres']
        document['penteSource'] = source.get('mode') or 'degres'
        Calepinage.objects.filter(pk=calepinage.pk).update(
            roof_layout=document, layout_hash=layout_hash(document))


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0025_acal247_pose_prevu_fige'),
        ('records', '0013_vx210_snooze_trigger_event'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(migrer_pente_racine, restaurer_pente_racine),
    ]
