"""ARC19 — Miroir one-way (INTERNE) ``rh.DossierEmploye`` → ``tiers.Tiers``.

À la sauvegarde d'un dossier employé, on rattache (dédup email company-scopée)
ou crée son ``Tiers`` miroir. Le dossier est une partie prenante INTERNE :

  - AUCUN rôle client/fournisseur/partenaire n'est posé (le collaborateur
    n'est pas un tiers commercial) ;
  - PAS de fusion RIB ici (voir ARC25) — le miroir n'écrit que l'identité de
    contact (nom/prénom/CIN/téléphone/email), JAMAIS le RIB de paie.

L'identité reste MAÎTRE côté dossier ; ``tiers`` n'en est qu'un reflet
réversible. Découplage : import FONCTION-LOCAL de ``apps.tiers.services``.
Best-effort : un échec du miroir ne fait JAMAIS échouer la sauvegarde du
dossier.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='rh.DossierEmploye',
          dispatch_uid='rh_dossier_mirror_tiers')
def mirror_dossier_to_tiers(sender, instance, **kwargs):
    dossier = instance
    if dossier.company_id is None:
        return
    try:
        from apps.tiers import services as tiers_services

        tiers, _cree = tiers_services.attacher_ou_creer_tiers(
            company=dossier.company,
            nom=dossier.nom or '',
            # Aucun rôle commercial (partie interne) — voir docstring.
            roles=(),
            email=dossier.email or '',
            tiers_existant=dossier.tiers if dossier.tiers_id else None,
            type_tiers='particulier',
            prenom=dossier.prenom or '',
            telephone=dossier.telephone or '',
            cin=dossier.cin or '',
            # NB : JAMAIS de RIB miroité ici (fusion RIB = ARC25).
        )
        if dossier.tiers_id != tiers.id:
            sender.objects.filter(pk=dossier.pk).update(tiers=tiers)
    except Exception:
        pass


def connect():
    """No-op explicite (le décorateur ``@receiver`` a déjà câblé le signal)."""
    return None
