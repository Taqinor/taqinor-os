"""Récepteurs de persistance du module Portail (``apps.portail``).

WIR94 — dépôt GED canonique de l'upload portail. Cette orchestration
cross-app vivait d'abord dans ``DocumentClientPortail.save()`` ; elle est
REMONTÉE ici, hors de ``models.py``, parce qu'un modèle ne doit pas orchestrer
d'écriture cross-app : l'import ``portail.models -> ged.services`` tirait tout
le graphe ``ged → notifications → ventes/sav/stock`` dans le module de modèles
et cassait le contrat CI ``portail-models-decoupled`` (``.importlinter``, règle
« Cross-app boundary » de CLAUDE.md). Le contrat est JUSTE — c'était le code
qui était mal placé.

Patron : celui déjà en place dans ``apps/crm/tiers_bridge.py`` (récepteur
``post_save`` à ``sender`` STRING — aucun import de modèle — + import
FONCTION-LOCAL du ``services.py`` de l'app cible, dépôt best-effort). Câblé au
démarrage par ``PortailConfig.ready``.

Le comportement WIR94 est conservé À L'IDENTIQUE, y compris son séquencement :

* ``pre_save`` (émis AVANT que ``FileField.pre_save`` ne commite le fichier au
  stockage objet) lit les octets et le ``content_type`` sur le fichier ENCORE
  EN MÉMOIRE — aucun appel de stockage supplémentaire, et le mime de l'upload
  n'est pas perdu (il n'existe plus une fois le ``FieldFile`` recréé depuis le
  nom stocké) ;
* ``post_save`` (émis HORS du bloc atomique de ``save_base``, exactement là où
  l'ancien code appelait la GED après ``super().save()``) dépose les octets via
  ``ged.services.deposit_document`` puis lie ``document_ged``.

Garanties inchangées : dépôt BEST-EFFORT (un échec GED ne casse jamais
l'enregistrement du document portail), IDEMPOTENT (``source_type``/``source_id``
côté GED, plus le garde-fou ``document_ged_id`` déjà posé côté portail : un
second ``save()`` sans nouveau fichier ne redépose rien), et ``raw=True``
(chargement de fixtures) reste sans effet — comme avant, où ``loaddata``
court-circuitait ``save()``.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

#: Attribut transitoire porté par l'instance entre ``pre_save`` et
#: ``post_save`` (les octets ne sont plus lisibles après le commit du
#: ``FileField``). Jamais persisté.
_CONTENU_ATTR = '_wir94_upload_a_deposer'

SOURCE_TYPE = 'portail.documentclientportail'


@receiver(pre_save, sender='portail.DocumentClientPortail',
          dispatch_uid='portail_document_capture_upload_pour_ged')
def capturer_upload_pour_ged(sender, instance, raw=False, **kwargs):
    """Lit les octets de l'upload AVANT que le ``FileField`` ne soit commité.

    Même garde qu'avant : on ne capture que s'il y a un fichier ET qu'aucun
    document GED n'est encore lié (idempotence). Toute erreur de lecture
    annule silencieusement la capture — le dépôt est best-effort.
    """
    if raw:
        return
    setattr(instance, _CONTENU_ATTR, None)
    if not (instance.fichier and not instance.document_ged_id):
        return
    fichier = getattr(instance.fichier, 'file', None)
    if fichier is None:
        return
    try:
        fichier.seek(0)
        contenu = fichier.read()
        fichier.seek(0)
        mime = getattr(fichier, 'content_type', '') or ''
    except Exception:  # pragma: no cover - défensif (lecture best-effort)
        return
    if contenu:
        setattr(instance, _CONTENU_ATTR, (contenu, mime))


@receiver(post_save, sender='portail.DocumentClientPortail',
          dispatch_uid='portail_document_depot_ged')
def deposer_upload_dans_ged(sender, instance, raw=False, **kwargs):
    """Dépose l'upload capturé dans la GED canonique et lie ``document_ged``.

    Frontière cross-app : on passe par ``ged.services.deposit_document`` (import
    FONCTION-LOCAL, jamais ``apps.ged.models``/``views``). Best-effort : un
    échec GED laisse le document portail enregistré, sans document lié.
    """
    if raw:
        return
    capture = getattr(instance, _CONTENU_ATTR, None)
    # Consommé une seule fois : un save() ultérieur sans nouveau fichier ne
    # redépose rien.
    setattr(instance, _CONTENU_ATTR, None)
    if not capture:
        return
    contenu, mime = capture
    try:
        from apps.ged import services as ged_services

        nom = instance.libelle or instance.get_type_document_display()
        document, _created = ged_services.deposit_document(
            company=instance.company,
            nom=nom,
            source_type=SOURCE_TYPE,
            source_id=instance.pk,
            contenu_bytes=contenu,
            mime=mime,
            description=(
                'Document déposé par le client via le portail '
                f'(WIR94) — {nom}.'),
            cabinet_nom='Portail client',
            folder_nom='Documents clients',
            created_by=None,
        )
    except Exception:  # pragma: no cover - défensif (dépôt best-effort)
        return
    type(instance).objects.filter(pk=instance.pk).update(
        document_ged_id=document.pk)
    instance.document_ged_id = document.pk
