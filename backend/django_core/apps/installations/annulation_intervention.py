"""ACSV4 — annulation d'UNE intervention (drapeau ``annulee`` YSERV6, motif
gardé). Module à part : ``services.py`` et ``views/intervention.py`` sont des
murs (garde C20). ``annuler_intervention`` est l'unique implémentation du geste,
réutilisée par la boucle ``services._annuler_interventions`` (chantier ou ticket
annulé) et par l'action « Annuler l'intervention »."""


def annuler_intervention(interv, user, motif, note):
    """Pose ``annulee`` + ``motif_annulation`` (le ``statut`` reste FIGÉ, AUD317),
    note au chatter de l'intervention et notifie technicien et équipe."""
    from . import intervention_activity
    from .services import _notifier_intervention_annulee
    interv.annulee = True
    interv.motif_annulation = motif[:255]
    interv.save(update_fields=['annulee', 'motif_annulation'])
    intervention_activity.log_note(interv, user, note)
    _notifier_intervention_annulee(interv, user)


def annuler_intervention_motivee(interv, user, motif):
    """« Annuler l'intervention » : motif obligatoire (400), refus d'état (409)
    sur une intervention déjà annulée, terminée ou validée ; note aussi au
    chatter du chantier. Rend l'intervention."""
    from rest_framework.exceptions import ValidationError

    from core.conflit_etat import ConflitEtat

    from . import activity
    from .models import Intervention
    if not motif:
        raise ValidationError({'motif': ["Indiquez le motif de l'annulation."]})
    if interv.annulee:
        raise ConflitEtat('Intervention déjà annulée.')
    if interv.statut in (Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE):
        raise ConflitEtat(f'Intervention {interv.get_statut_display().lower()} : '
                          'elle ne peut plus être annulée.')
    annuler_intervention(interv, user, motif, f'Intervention annulée — motif : {motif}.')
    if interv.installation_id:
        activity.log_note(interv.installation, user,
                          f'Intervention annulée : {interv.get_type_intervention_display()} — {motif}')
    return interv
