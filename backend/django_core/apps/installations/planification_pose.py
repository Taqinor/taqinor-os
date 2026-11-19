"""Copilote vague 2 (CHTA5, D-W2-CHT-1) — « planifie la pose » en UN geste
confirmé : date de pose (et de fin) et technicien du CHANTIER, PUIS
l'intervention de pose (créée, ou la pose ouverte déplacée). Sans elle, une
date de pose ne met rien dans la journée de personne : « Ma journée » ne lit
que les interventions.

Route : ``POST chantiers/{id}/planifier-pose/`` (contrat
``contract_samples/chantier_planifier_pose.json``). Règles :

* le STATUT du chantier ne change JAMAIS ici (son seul écrivain reste
  ``services.changer_statut_chantier`` ; la date est posée d'abord, le
  passage à « Planifié » reste un geste de l'écran) ;
* la garde d'acompte de l'écran (YSERV1 / ACSV12 : une pose DATÉE pour la
  première fois sur un chantier dont l'acompte exigé n'est pas encaissé) est
  appliquée telle quelle, SANS passe-outre : aucun motif n'entre ici ;
* refus nommés (:class:`PoseRefusee`) : chantier annulé, clôturé ou déjà posé,
  date passée, fin avant début, technicien inconnu, pose déjà commencée ;
* tout est atomique, la ligne du chantier verrouillée ; les notifications
  partent après le commit (``on_commit`` des notifieurs existants).
"""
import copy
import datetime

from django.db import transaction

from . import activity, intervention_activity

MOTIF_ASSISTANT = "Planifiée par l'assistant"


class PoseRefusee(Exception):
    """Refus nommé : ``statut_http`` (400 ou 409), ``champ``, ``code``,
    ``detail`` (phrase française qui dit quoi faire)."""

    def __init__(self, statut_http, champ, code, detail):
        super().__init__(detail)
        self.statut_http, self.champ, self.code, self.detail = (
            statut_http, champ, code, detail)


def peut_assigner(user):
    """``technicien_assign`` comme ``HasPermissionOrLegacy`` le lit (rôle fin ;
    compte hérité sans rôle : responsable)."""
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'role', None):
        return user.has_erp_permission('technicien_assign')
    return bool(getattr(user, 'is_responsable', False))


def _verifier_chantier(inst, date_pose, date_fin, aujourdhui):
    from .models import Installation
    canon = Installation.canonical_statut(inst.statut)
    if inst.annule:
        raise PoseRefusee(409, 'chantier', 'chantier_annule',
                          'Ce chantier est annulé : sa pose ne se planifie plus.')
    if canon == Installation.Statut.CLOTURE:
        raise PoseRefusee(409, 'chantier', 'chantier_cloture',
                          'Ce chantier est clôturé : sa pose ne se planifie plus.')
    if canon in (Installation.Statut.INSTALLE, Installation.Statut.RECEPTIONNE):
        raise PoseRefusee(409, 'chantier', 'chantier_deja_pose',
                          'Ce chantier est déjà posé : rien à planifier.')
    if date_pose < aujourdhui:
        raise PoseRefusee(409, 'date_pose_prevue', 'date_passee',
                          "date_pose_prevue : la date est passée ; choisissez "
                          "aujourd'hui ou plus tard.")
    if date_fin is not None and date_fin < date_pose:
        raise PoseRefusee(400, 'date_pose_fin_prevue', 'fin_avant_debut',
                          'date_pose_fin_prevue : la fin précède le début de la pose.')


def _technicien(company_id, technicien_id):
    if technicien_id is None:
        return None
    from django.contrib.auth import get_user_model
    tech = (get_user_model().objects
            .filter(pk=technicien_id, company_id=company_id, is_active=True).first())
    if tech is None:
        raise PoseRefusee(400, 'technicien', 'technicien_inconnu',
                          "technicien : compte inconnu, inactif ou d'une autre société.")
    return tech


def _pose_ouverte(inst):
    """La pose ouverte (à préparer / prête) la plus tôt datée, verrouillée, ou
    ``None`` s'il n'y a aucune pose ; 409 si les poses existantes ont toutes
    commencé (elles se replanifient à l'écran, jamais par l'assistant)."""
    from django.db.models import F

    from .models import Intervention
    poses = list(Intervention.objects.select_for_update()
                 .filter(company_id=inst.company_id, installation_id=inst.pk,
                         type_intervention=Intervention.Type.POSE, annulee=False)
                 .order_by(F('date_prevue').asc(nulls_last=True), 'pk'))
    ouvertes = [p for p in poses if p.statut in (
        Intervention.Statut.A_PREPARER, Intervention.Statut.PRETE)]
    if ouvertes:
        return ouvertes[0]
    if poses:
        raise PoseRefusee(409, 'intervention_pose', 'pose_commencee',
                          "La pose de ce chantier a déjà commencé : elle se "
                          "replanifie depuis l'intervention, à l'écran.")
    return None


def _garde_acompte(inst, pose):
    """YSERV1 / ACSV12 — une pose datée POUR LA PREMIÈRE FOIS (créée, ou pose
    ouverte sans date) : refus si l'acompte exigé n'est pas encaissé."""
    if pose is not None and pose.date_prevue is not None:
        return
    from .services import verifier_gate_acompte_planification
    raison = verifier_gate_acompte_planification(inst)
    if raison:
        raise PoseRefusee(409, 'date_prevue', 'acompte_non_encaisse',
                          f"{raison} Encaissez-le, ou un responsable passe outre "
                          "depuis la fiche du chantier.")


def _ecrire_chantier(inst, user, date_pose, date_fin, tech):
    """Date(s) et technicien du chantier, tracés au chatter ; le nouveau
    technicien responsable est notifié. Une fin devenue antérieure au début
    est effacée."""
    avant = copy.copy(inst)
    inst.date_pose_prevue = date_pose
    if date_fin is not None or (inst.date_pose_fin_prevue or date_pose) < date_pose:
        inst.date_pose_fin_prevue = date_fin
    champs = ['date_pose_prevue', 'date_pose_fin_prevue']
    nouveau = tech is not None and tech.pk != inst.technicien_responsable_id
    if nouveau:
        inst.technicien_responsable = tech
        champs.append('technicien_responsable')
    inst.save(update_fields=champs)
    activity.log_changes(avant, inst, user)
    if nouveau:
        from .services import _notifier_chantier_assigne
        _notifier_chantier_assigne(inst, tech)


def _ecrire_pose(inst, user, pose, date_pose, tech):
    """Déplace la pose ouverte (service unique ``replanifier`` : compteur de
    reports, confirmation du rendez-vous remise à zéro, trace) ou crée la pose
    (même effets que la création à l'écran). Le technicien affecté est
    notifié."""
    from .models import Intervention
    from .services import _notifier_intervention_assignee, replanifier
    if pose is not None:
        ancien = pose.technicien_id
        replanifier(pose, date_pose, MOTIF_ASSISTANT, user,
                    technicien_id=tech.pk if tech is not None else None)
        if tech is not None and tech.pk != ancien:
            _notifier_intervention_assignee(pose, user)
        return pose
    pose = Intervention.objects.create(
        company_id=inst.company_id, installation=inst,
        type_intervention=Intervention.Type.POSE, date_prevue=date_pose,
        technicien=tech, created_by=user)
    if tech is not None:
        _notifier_intervention_assignee(pose, user)
    elif inst.technicien_responsable_id:
        pose.equipe.add(inst.technicien_responsable_id)
    intervention_activity.log_creation(pose, user)
    activity.log_note(inst, user, f'Intervention ajoutée : '
                                  f'{pose.get_type_intervention_display()} ({MOTIF_ASSISTANT.lower()})')
    return pose


def planifier_pose(inst, user, *, date_pose, date_fin=None, technicien_id=None,
                   creer_intervention=True, aujourdhui=None):
    """Planifie la pose de ``inst`` (déjà lu dans la portée de ``user``) ;
    rend le chantier relu. Lève :class:`PoseRefusee` sans rien écrire.

    Technicien de la pose : celui donné ; sinon, pour une pose CRÉÉE, le
    technicien du chantier si ``user`` a le droit d'affecter
    (``technicien_assign``) — sinon personne, l'installateur entre dans
    l'équipe (comme à l'écran)."""
    from .models import Installation
    aujourdhui = aujourdhui or datetime.date.today()
    with transaction.atomic():
        inst = Installation.objects.select_for_update().get(pk=inst.pk)
        _verifier_chantier(inst, date_pose, date_fin, aujourdhui)
        tech = _technicien(inst.company_id, technicien_id)
        pose = _pose_ouverte(inst) if creer_intervention else None
        if creer_intervention:
            _garde_acompte(inst, pose)
        _ecrire_chantier(inst, user, date_pose, date_fin, tech)
        if creer_intervention:
            if pose is None and tech is None and peut_assigner(user):
                tech = inst.technicien_responsable
            _ecrire_pose(inst, user, pose, date_pose, tech)
    return inst
