# ACAL267 (C-ACAL-051) — la pose réelle est référencée par l'identifiant
# STABLE du pan (``zone_id``) : renommer un pan ne détache plus le relevé.
#
# Schéma : colonne additive ``zone_id`` (défaut vide), puis l'unicité
# (calepinage, pan) devient (calepinage, zone_id) — deux pans de même libellé
# sont deux relevés indépendants.
#
# Données (rattrapage) : chaque relevé reçoit l'id de la zone dont l'ANCIENNE
# clé (label, sinon id, sinon PAN-<rang>) vaut son ``pan``. Rien n'est deviné :
# un libellé porté par deux pans, ou absent du document, garde son libellé
# comme ``zone_id`` (ligne ORPHELINE : hors totaux, retirable) et une note de
# chatter le dit. Les règles de clé sont RECOPIÉES ici (une migration ne lit
# pas le code vivant de l'app). Réversible : l'inverse retire la colonne et
# rétablit l'unicité par libellé (le libellé, lui, n'a jamais bougé).
from django.db import migrations, models

TAILLE_LOT = 200


def _cles(layout):
    """``({ancienne clé: nouvelle}, {ambiguës})`` du document — PUR."""
    zones = (layout.get('zones') if isinstance(layout, dict) else None) or []
    vues, ambigues = {}, set()
    for rang, zone in enumerate(zones if isinstance(zones, list) else [],
                                start=1):
        if not isinstance(zone, dict):
            continue
        ancienne = str(zone.get('label') or zone.get('id') or 'PAN-%d' % rang)
        if ancienne in vues:
            ambigues.add(ancienne)
        vues[ancienne] = str(zone.get('id') or 'PAN-%d' % rang)
    for ancienne in ambigues:
        vues.pop(ancienne, None)
    return vues, ambigues


def rattacher_zone_id(apps, schema_editor):
    PoseReelle = apps.get_model('calepinage', 'PoseReelle')
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Activity = apps.get_model('records', 'Activity')
    type_calepinage = ContentType.objects.filter(
        app_label='calepinage', model='calepinage').first()
    ids = (PoseReelle.objects.order_by().values_list('calepinage_id',
                                                     flat=True).distinct())
    for calepinage in (Calepinage.objects.filter(pk__in=list(ids))
                       .order_by('pk').iterator(chunk_size=TAILLE_LOT)):
        vues, _ambigues = _cles(calepinage.roof_layout)
        poses = list(PoseReelle.objects.filter(calepinage_id=calepinage.pk)
                     .order_by('pk'))
        prises, non_appariees = set(), []
        for pose in poses:
            cible = vues.get(pose.pan)
            if cible is None or cible in prises:
                non_appariees.append(pose)
                continue
            prises.add(cible)
            PoseReelle.objects.filter(pk=pose.pk).update(zone_id=cible)
        for pose in non_appariees:
            orpheline = pose.pan
            if orpheline in prises:
                orpheline = 'pan:%s' % pose.pan
            prises.add(orpheline)
            PoseReelle.objects.filter(pk=pose.pk).update(zone_id=orpheline)
        if non_appariees and type_calepinage is not None:
            Activity.objects.create(
                company_id=calepinage.company_id,
                content_type=type_calepinage, object_id=calepinage.pk,
                kind='note',
                body=('Pose réelle : pan ambigu ou absent du document pour %s '
                      '— relevé conservé (orphelin, hors totaux), à retirer '
                      'ou ressaisir.'
                      % ', '.join('« %s »' % p.pan for p in non_appariees)))


def dedoublonner_pan(apps, schema_editor):
    """Inverse (lot 3 critique #3) — AVANT de rétablir l'unicité par
    libellé : deux relevés d'un même calepinage peuvent désormais porter le
    même ``pan`` (deux pans de même libellé). Les suivants reçoivent un
    suffixe « (2) », « (3) »… pour que le retour arrière ne lève jamais
    ``IntegrityError``."""
    PoseReelle = apps.get_model('calepinage', 'PoseReelle')
    vus = {}
    for pose in PoseReelle.objects.order_by('calepinage_id', 'pk').iterator(
            chunk_size=TAILLE_LOT):
        pris = vus.setdefault(pose.calepinage_id, set())
        libelle, rang = pose.pan, 1
        while libelle in pris:
            rang += 1
            suffixe = ' (%d)' % rang
            libelle = pose.pan[:120 - len(suffixe)] + suffixe
        pris.add(libelle)
        if libelle != pose.pan:
            PoseReelle.objects.filter(pk=pose.pk).update(pan=libelle)


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0027_acal265_cles_de_pan_stables'),
        ('records', '0013_vx210_snooze_trigger_event'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='posereelle',
            name='zone_id',
            field=models.CharField(blank=True, default='', max_length=120,
                                   verbose_name='Identifiant du pan'),
        ),
        migrations.RunPython(rattacher_zone_id, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='posereelle',
            name='uniq_pose_reelle_par_pan',
        ),
        # Sans effet à l'aller ; au retour, s'exécute AVANT le rétablissement
        # de ``uniq_pose_reelle_par_pan`` (opérations inversées).
        migrations.RunPython(migrations.RunPython.noop, dedoublonner_pan),
        migrations.AddConstraint(
            model_name='posereelle',
            constraint=models.UniqueConstraint(
                fields=('calepinage', 'zone_id'),
                name='uniq_pose_reelle_par_zone'),
        ),
    ]
