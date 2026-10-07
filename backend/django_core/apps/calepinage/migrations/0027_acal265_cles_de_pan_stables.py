# ACAL265 (C-ACAL-051) — l'entrée électrique enregistrée passe aux clés
# STABLES : ``affectation_manuelle[].module`` '<libellé>#<rang>' devient
# '<zone.id>#<n>' (n = numéro stable du panneau, sinon le rang) et
# ``cheminement.pans[<libellé>]`` devient ``cheminement.pans[<zone.id>]``.
#
# Rien n'est deviné : un libellé porté par DEUX pans (ambigu) ou absent du
# document reste tel quel, et une note de chatter le dit (la ligne sera
# publiée « obsolète » et retirée par un geste nommé). Les règles de clé sont
# RECOPIÉES ici (une migration ne lit pas le code vivant de l'app, qui
# changera) : ancienne clé = label, sinon id, sinon PAN-<rang> ; nouvelle =
# id, sinon PAN-<rang>.
#
# DRY-RUN D'ABORD : ``inventaire_cles_de_pan(apps)`` liste (calepinage, clés
# avant → après, non appariées) SANS rien écrire — à soumettre au fondateur
# avant le merge. Réversible : l'inverse ramène les clés stables à l'ancien
# libellé.
from django.db import migrations

TAILLE_LOT = 200
CLE_ENTREE = 'entree_electrique'


def _zones(layout):
    zones = (layout.get('zones') if isinstance(layout, dict) else None) or []
    return [(rang, zone) for rang, zone in enumerate(zones, start=1)
            if isinstance(zone, dict)] if isinstance(zones, list) else []


def _numeros(zone):
    geometrie = zone.get('geometry')
    panneaux = (geometrie.get('panels') if isinstance(geometrie, dict)
                else None)
    if not isinstance(panneaux, list) or not panneaux:
        return ()
    numeros = []
    for panneau in panneaux:
        numero = panneau.get('n') if isinstance(panneau, dict) else None
        if isinstance(numero, bool) or not isinstance(numero, int) \
                or numero <= 0:
            return ()
        numeros.append(numero)
    return tuple(numeros) if len(set(numeros)) == len(numeros) else ()


def _correspondances(layout):
    """``({ancienne: (nouvelle, numéros)}, {ambiguës})`` — PUR."""
    vues, ambigues = {}, set()
    for rang, zone in _zones(layout):
        ancienne = str(zone.get('label') or zone.get('id') or 'PAN-%d' % rang)
        nouvelle = str(zone.get('id') or 'PAN-%d' % rang)
        if ancienne in vues:
            ambigues.add(ancienne)
        vues[ancienne] = (nouvelle, _numeros(zone))
    for ancienne in ambigues:
        vues.pop(ancienne, None)
    return vues, ambigues


def migrer_entree(entree, layout):
    """``(nouvelle_entree | None, non_appariees)`` — PUR. ``None`` : rien à
    changer."""
    if not isinstance(entree, dict):
        return None, []
    vues, ambigues = _correspondances(layout)
    # Les clés DÉJÀ stables (seconde passe, pan dont libellé = id) : gardées
    # sans bruit — la migration est idempotente.
    stables = {str(zone.get('id') or 'PAN-%d' % rang)
               for rang, zone in _zones(layout)}
    nouvelle = dict(entree)
    non_appariees = []
    change = False

    lignes = entree.get('affectation_manuelle')
    if isinstance(lignes, list):
        sorties = []
        for ligne in lignes:
            module = ligne.get('module') if isinstance(ligne, dict) else None
            if not isinstance(module, str) or '#' not in module:
                sorties.append(ligne)
                continue
            pan, _diese, rang = module.rpartition('#')
            cible = vues.get(pan)
            if cible is None or not rang.isdigit():
                if pan not in stables or pan in ambigues:
                    non_appariees.append(module)
                sorties.append(ligne)
                continue
            cle, numeros = cible
            rang = int(rang)
            numero = (numeros[rang - 1] if numeros
                      and 0 < rang <= len(numeros) else rang)
            nouveau = '%s#%d' % (cle, numero)
            if nouveau != module:
                change = True
                ligne = dict(ligne, module=nouveau)
            sorties.append(ligne)
        nouvelle['affectation_manuelle'] = sorties

    cheminement = entree.get('cheminement')
    if isinstance(cheminement, dict) and isinstance(
            cheminement.get('pans'), dict):
        pans = {}
        for ancienne, saisie in cheminement['pans'].items():
            cible = vues.get(str(ancienne))
            if cible is None:
                if str(ancienne) in ambigues or str(ancienne) not in stables:
                    non_appariees.append('cheminement:%s' % ancienne)
                pans[ancienne] = saisie
                continue
            if cible[0] != ancienne:
                change = True
            pans[cible[0]] = saisie
        nouvelle['cheminement'] = dict(cheminement, pans=pans)
    return (nouvelle if change else None), non_appariees


def _a_examiner(apps):
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    return (Calepinage.objects.filter(resultat__has_key=CLE_ENTREE)
            .order_by('pk'))


def inventaire_cles_de_pan(apps):
    """DRY-RUN — ``[{calepinage, avant, apres, non_appariees}]``."""
    lignes = []
    for calepinage in _a_examiner(apps).iterator(chunk_size=TAILLE_LOT):
        entree = (calepinage.resultat or {}).get(CLE_ENTREE)
        nouvelle, non_appariees = migrer_entree(entree,
                                                calepinage.roof_layout)
        if nouvelle is None and not non_appariees:
            continue
        lignes.append({
            'calepinage': calepinage.pk,
            'avant': [ligne.get('module') for ligne in (entree or {}).get(
                'affectation_manuelle') or [] if isinstance(ligne, dict)],
            'apres': [ligne.get('module') for ligne in (nouvelle or entree or {}).get(
                'affectation_manuelle') or [] if isinstance(ligne, dict)],
            'non_appariees': non_appariees,
        })
    return lignes


def migrer_cles_de_pan(apps, schema_editor):
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Activity = apps.get_model('records', 'Activity')
    type_calepinage = ContentType.objects.filter(
        app_label='calepinage', model='calepinage').first()
    for calepinage in _a_examiner(apps).iterator(chunk_size=TAILLE_LOT):
        resultat = calepinage.resultat or {}
        nouvelle, non_appariees = migrer_entree(resultat.get(CLE_ENTREE),
                                                calepinage.roof_layout)
        if nouvelle is not None:
            Calepinage.objects.filter(pk=calepinage.pk).update(
                resultat=dict(resultat, **{CLE_ENTREE: nouvelle}))
        if non_appariees and type_calepinage is not None:
            Activity.objects.create(
                company_id=calepinage.company_id,
                content_type=type_calepinage, object_id=calepinage.pk,
                kind='note',
                body=('Clés de pan non appariées (libellé ambigu ou absent '
                      'du document), gardées telles quelles : %s'
                      % ', '.join(non_appariees)))


def restaurer_cles_de_pan(apps, schema_editor):
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    for calepinage in _a_examiner(apps).iterator(chunk_size=TAILLE_LOT):
        resultat = calepinage.resultat or {}
        entree = resultat.get(CLE_ENTREE)
        if not isinstance(entree, dict):
            continue
        inverse = {}
        for rang, zone in _zones(calepinage.roof_layout):
            stable = str(zone.get('id') or 'PAN-%d' % rang)
            ancienne = str(zone.get('label') or zone.get('id')
                           or 'PAN-%d' % rang)
            inverse[stable] = (ancienne, _numeros(zone))
        nouvelle = dict(entree)
        lignes = []
        for ligne in entree.get('affectation_manuelle') or []:
            module = ligne.get('module') if isinstance(ligne, dict) else None
            if isinstance(module, str) and '#' in module:
                pan, _d, numero = module.rpartition('#')
                cible = inverse.get(pan)
                if cible is not None and numero.isdigit():
                    numero = int(numero)
                    numeros = cible[1]
                    rang = (numeros.index(numero) + 1 if numero in numeros
                            else numero)
                    ligne = dict(ligne, module='%s#%d' % (cible[0], rang))
            lignes.append(ligne)
        if 'affectation_manuelle' in entree:
            nouvelle['affectation_manuelle'] = lignes
        cheminement = entree.get('cheminement')
        if isinstance(cheminement, dict) and isinstance(
                cheminement.get('pans'), dict):
            nouvelle['cheminement'] = dict(cheminement, pans={
                (inverse[c][0] if c in inverse else c): s
                for c, s in cheminement['pans'].items()})
        if nouvelle != entree:
            Calepinage.objects.filter(pk=calepinage.pk).update(
                resultat=dict(resultat, **{CLE_ENTREE: nouvelle}))


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0026_acal253_pente_racine_vers_pan'),
        ('records', '0013_vx210_snooze_trigger_event'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(migrer_cles_de_pan, restaurer_cles_de_pan),
    ]
