"""Récepteurs d'événements métier de l'app ``paie`` (M6, ``core/events.py``).

YHIRE2 — avant ce récepteur, passer un ``rh.DossierEmploye`` à SORTI ne
touchait JAMAIS ``ProfilPaie.actif`` : un salarié sorti restait éligible à un
bulletin de paie normal (``generer_bulletin`` ne regarde ni statut ni
date_sortie du dossier). ``rh.services.sortir_employe`` émet désormais
``employe_sorti`` sur le bus d'événements ; ce module s'y abonne pour couper
le profil de paie, SANS que ``rh`` importe jamais ``apps.paie`` (frontière
cross-app respectée — pattern identique à ``devis_accepted`` → ``crm``).
"""
import logging

from django.dispatch import receiver

from core.events import employe_sorti

logger = logging.getLogger(__name__)


@receiver(employe_sorti, dispatch_uid='paie_desactiver_profil_on_employe_sorti')
def _desactiver_profil_paie(sender, dossier, user, motif, **kwargs):
    """Coupe ``ProfilPaie.actif`` pour le dossier employé sorti (idempotent :
    un profil déjà inactif n'est pas re-sauvegardé)."""
    from .models import ProfilPaie

    try:
        profil = ProfilPaie.objects.filter(employe=dossier).first()
    except Exception:  # pragma: no cover - défensif
        logger.warning(
            'paie: échec lecture ProfilPaie pour dossier #%s',
            getattr(dossier, 'pk', None), exc_info=True)
        return
    if profil is None or not profil.actif:
        return
    profil.actif = False
    profil.save(update_fields=['actif'])
