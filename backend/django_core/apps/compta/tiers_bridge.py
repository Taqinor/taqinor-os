"""ARC19 — Miroir one-way ``compta.Partenaire`` → répertoire unifié
``tiers.Tiers``.

À la sauvegarde d'un Partenaire (apporteur / sous-revendeur / installateur),
on rattache (dédup email company-scopée) ou crée son ``Tiers`` miroir et on
pose le drapeau ``is_partenaire``. L'identité reste MAÎTRE côté Partenaire ;
``tiers`` n'en est qu'un reflet réversible.

ODX13-COMPATIBLE : le pont utilise un string-FK vers ``tiers`` (couche
fondation) et un signal câblé sur ``compta.Partenaire`` — le futur déplacement
du modèle vers ``crm`` par ``SeparateDatabaseAndState`` (non anticipé
autrement) laisse ce pont intact.

Découplage : ce module vit dans ``apps.compta`` et n'appelle
``apps.tiers.services`` que par un import FONCTION-LOCAL. Best-effort : un
échec du miroir ne fait JAMAIS échouer la sauvegarde du Partenaire.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='compta.Partenaire',
          dispatch_uid='compta_partenaire_mirror_tiers')
def mirror_partenaire_to_tiers(sender, instance, **kwargs):
    partenaire = instance
    if partenaire.company_id is None:
        return
    try:
        from apps.tiers import services as tiers_services

        tiers, _cree = tiers_services.attacher_ou_creer_tiers(
            company=partenaire.company,
            nom=partenaire.nom or '',
            roles=('is_partenaire',),
            email=partenaire.email or '',
            tiers_existant=(partenaire.tiers
                            if partenaire.tiers_id else None),
            # Un partenaire (apporteur/sous-revendeur/installateur) est une
            # entité commerciale → entreprise par défaut.
            type_tiers='entreprise',
            raison_sociale=partenaire.nom or '',
            telephone=partenaire.telephone or '',
        )
        if partenaire.tiers_id != tiers.id:
            sender.objects.filter(pk=partenaire.pk).update(tiers=tiers)
    except Exception:
        pass


def connect():
    """No-op explicite (le décorateur ``@receiver`` a déjà câblé le signal)."""
    return None
