"""Services (écriture/orchestration) du module ``apps.douane``.

Import local des modèles d'autres apps (jamais au niveau module) — toute
lecture d'un document d'une autre app se fait via son ``selectors.py`` ou en
recevant directement l'instance/l'id en paramètre (jamais un import direct de
``apps.<autre_app>.models`` depuis ce fichier).

Revue coordinateur (NTLOG14, post-fold) — deux motifs à ne JAMAIS réintroduire
sur un nouveau modèle numéroté :
  1. ``next_reference`` défaut ``field='reference'`` — un modèle dont le champ
     numéroté ne s'appelle pas littéralement ``reference`` (ici ``numero``)
     DOIT passer ``field=`` explicitement, sinon ``FieldError`` à CHAQUE appel
     (``DossierExport`` n'a pas de champ ``reference``).
  2. Le motif create-puis-numérote (``numero=''`` inséré, puis mis à jour)
     DOIT être enveloppé dans ``transaction.atomic()`` : sans ça, un échec de
     numérotation laisse une ligne ``numero=''`` committée, et
     ``unique_together (company, numero)`` empêche alors TOUTE création
     suivante pour cette société.
"""
from django.db import transaction

from core.numbering import next_reference


def attribuer_numero_dossier_export(dossier):
    """NTLOG14 — pose ``dossier.numero`` (anti-collision, plus-haut-utilisé+1
    par société) via ``core.numbering`` — jamais un ``count()+1`` (ARC6).
    No-op si déjà posé (idempotent). ``field='numero'`` explicite : le défaut
    de ``next_reference`` (``'reference'``) n'existe pas sur ce modèle."""
    if dossier.numero:
        return dossier

    from .models import DossierExport

    dossier.numero = next_reference(
        DossierExport, 'EXP', dossier.company, padding=4, period='monthly',
        field='numero')
    dossier.save(update_fields=['numero'])
    return dossier


def tracer_transition_statut_dossier_export(dossier, ancien_statut, *, user=None):
    """NTLOG49/50/51 — trace une transition de statut DÉJÀ ENREGISTRÉE (le
    ``save()`` a déjà eu lieu — voir ``DossierExportViewSet.perform_update``
    et ``cloturer_dossier_export`` ci-dessous, les deux seuls appelants).

    - NTLOG50 : écrit l'ancien/nouveau statut dans ``audit.AuditLog``
      (traçabilité réglementaire des actions douanières sensibles).
    - NTLOG49 : la MÊME écriture alimente le chatter générique
      ``records.Activity`` (entonnoir unique ``apps.audit.recorder.
      record_field_change`` — un seul appel écrit les deux, jamais deux
      journaux qui divergent) — visible du flux d'activité de tout
      ``records.Follower`` du dossier (voir ``apps/douane/platform.py``,
      ``record_targets``) — puis notifie ces followers (best-effort,
      ``apps.records.services.notify_followers``).
    - NTLOG51 : cette même trace d'audit (``AuditLog.changes``, filtrée sur
      ``field='statut'``) est la SOURCE lue par ``selectors.
      delai_moyen_dedouanement`` — aucune nouvelle colonne/migration sur
      ``DossierExport`` n'est nécessaire pour ce calcul.

    No-op silencieux si le statut n'a PAS réellement changé (appel
    défensif — jamais de bruit pour un « changement » identique)."""
    from .models import DossierExport

    if dossier.statut == ancien_statut:
        return dossier

    ancien_label = dict(DossierExport.Statut.choices).get(
        ancien_statut, ancien_statut)

    from apps.audit.recorder import record_field_change
    record_field_change(
        dossier, 'statut', ancien_label, dossier.get_statut_display(),
        user=user, field_label='Statut')

    from django.contrib.contenttypes.models import ContentType
    from apps.records.services import notify_followers
    notify_followers(
        content_type=ContentType.objects.get_for_model(DossierExport),
        object_id=dossier.pk,
        title=f'Dossier export {dossier.numero or dossier.pk} — nouveau statut',
        body=f'Nouveau statut : {dossier.get_statut_display()}.',
        exclude_user=user)
    return dossier


def cloturer_dossier_export(dossier, *, user=None):
    """NTLOG44 — clôture un ``DossierExport`` : bascule ``statut`` vers
    ``CLOTURE``, trace la transition (audit + chatter + followers — voir
    ``tracer_transition_statut_dossier_export`` ci-dessus), PUIS émet
    ``core.events.dossier_export_cloture`` sur le bus (aucun abonné câblé
    dans ce lot — voir ``core.event_coverage.ALLOWED_UNCONSUMED`` ; pose le
    crochet pour un futur abonné ``publicapi``/webhook sans que ``douane``
    importe cette app).

    Idempotente : reclôturer un dossier déjà clôturé est un no-op silencieux
    (statut inchangé, AUCUNE ligne d'audit/chatter/événement supplémentaire
    — évite le bruit d'un double clic)."""
    from .models import DossierExport

    ancien_statut = dossier.statut
    if ancien_statut == DossierExport.Statut.CLOTURE:
        return dossier

    dossier.statut = DossierExport.Statut.CLOTURE
    dossier.save(update_fields=['statut'])
    tracer_transition_statut_dossier_export(dossier, ancien_statut, user=user)

    from core.events import dossier_export_cloture
    dossier_export_cloture.send(
        sender=DossierExport, dossier=dossier, company=dossier.company,
        user=user, ancien_statut=ancien_statut)
    return dossier


def auditer_suppression_piece_validee(piece, *, user=None):
    """NTLOG50 — trace la suppression d'une ``PieceDossierExport`` déjà
    VALIDÉE dans ``audit.AuditLog`` (traçabilité réglementaire — motif
    NTLOG11, volet import ANALOGUE resté BLOCKED : voir
    ``apps/douane/apps.py``). Appelée JUSTE AVANT la suppression effective
    depuis ``PieceDossierExportViewSet.perform_destroy`` : l'instance n'est
    plus lisible une fois le ``DELETE`` exécuté.

    No-op silencieux si la pièce n'était PAS VALIDÉE (rien de sensible à
    tracer — évite de bruiter le journal pour une pièce encore manquante ou
    simplement déposée)."""
    from .models import PieceDossierExport

    if piece.statut_piece != PieceDossierExport.StatutPiece.VALIDEE:
        return

    from apps.audit.recorder import record
    from apps.audit.models import AuditLog

    record(
        AuditLog.Action.DELETE, instance=piece, user=user,
        detail=(
            "Suppression d'une pièce VALIDÉE du dossier export "
            f'{piece.dossier.numero or piece.dossier_id} : '
            f'{piece.get_type_piece_display()}.'))


def creer_dossier_export_depuis_facture(
        *, company, facture, pays_destinataire, incoterm='',
        port_embarquement='', port_debarquement='', devise='',
        valeur_marchandise_devise=0, created_by=None):
    """NTLOG14 — crée un ``DossierExport`` à partir d'une
    ``facturation.Facture`` (reçue en paramètre, jamais importée au niveau
    module). Le pays destinataire est capturé EXPLICITEMENT à l'appel : ni
    ``facturation.Facture`` ni ``crm.Client`` ne portent de champ pays
    structuré dans ce dépôt, donc « hérite du pays destinataire » se traduit
    ici par « le dossier créé depuis cette facture porte le pays donné au
    même appel », jamais une déduction magique d'un champ inexistant.
    Création + numérotation dans UNE SEULE transaction (sinon une ligne
    ``numero=''`` orpheline bloquerait la société — voir docstring module)."""
    from .models import DossierExport

    with transaction.atomic():
        dossier = DossierExport.objects.create(
            company=company, facture=facture, pays_destinataire=pays_destinataire,
            incoterm=incoterm, port_embarquement=port_embarquement,
            port_debarquement=port_debarquement, devise=devise,
            valeur_marchandise_devise=valeur_marchandise_devise,
            created_by=created_by)
        return attribuer_numero_dossier_export(dossier)
