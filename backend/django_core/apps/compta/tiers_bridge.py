"""ARC19 — Miroir one-way ``crm.Partenaire`` → répertoire unifié
``tiers.Tiers``.

À la sauvegarde d'un Partenaire (apporteur / sous-revendeur / installateur),
on rattache (dédup email company-scopée) ou crée son ``Tiers`` miroir et on
pose le drapeau ``is_partenaire``. L'identité reste MAÎTRE côté Partenaire ;
``tiers`` n'en est qu'un reflet réversible.

ODX13 — le modèle ``Partenaire`` a été rapatrié de ``compta`` vers ``crm``
(``SeparateDatabaseAndState``, aucune donnée déplacée). Le string-FK vers
``tiers`` (couche fondation) survit tel quel au move ; le sender du signal
ci-dessous est re-pointé sur ``crm.Partenaire`` (l'app_label suit désormais
la classe, physiquement dans ``apps.crm.models``) pour que le pont continue
de se déclencher.

Découplage : ce module reste dans ``apps.compta`` (câblé par
``ComptaConfig.ready()``) et n'appelle ``apps.tiers.services`` que par un
import FONCTION-LOCAL. Best-effort : un échec du miroir ne fait JAMAIS
échouer la sauvegarde du Partenaire.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='crm.Partenaire',
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
