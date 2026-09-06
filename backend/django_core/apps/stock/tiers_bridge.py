"""ARC18 — Miroir one-way ``stock.Fournisseur`` → répertoire unifié
``tiers.Tiers``.

À la sauvegarde d'un Fournisseur, on rattache (dédup email/ICE company-scopée)
ou crée son ``Tiers`` miroir et on pose le drapeau ``is_fournisseur`` (ainsi
que ``is_soustraitant`` pour les fournisseurs de type service/mixte, DC34).
L'identité reste MAÎTRE côté Fournisseur ; ``tiers`` n'en est qu'un reflet
(pont réversible — bascule write-path = décision ARC21, OFF par défaut).

Découplage : ce module vit dans ``apps.stock`` (jamais dans ``apps.tiers`` qui
reste une couche fondation) et n'appelle ``apps.tiers.services`` que par un
import FONCTION-LOCAL. Best-effort : un échec du miroir ne fait JAMAIS échouer
la sauvegarde du Fournisseur.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _roles_pour_fournisseur(fournisseur):
    """Un fournisseur est toujours ``is_fournisseur`` ; s'il est de type
    service ou mixte (sous-traitance, DC34), il porte aussi
    ``is_soustraitant``."""
    roles = ['is_fournisseur']
    if fournisseur.type in ('service', 'mixte'):
        roles.append('is_soustraitant')
    return tuple(roles)


@receiver(post_save, sender='stock.Fournisseur',
          dispatch_uid='stock_fournisseur_mirror_tiers')
def mirror_fournisseur_to_tiers(sender, instance, **kwargs):
    fournisseur = instance
    if fournisseur.company_id is None:
        return  # pas de société — rien à miroiter (jamais cross-tenant).
    try:
        from apps.tiers import services as tiers_services

        # Un fournisseur avec un ICE est une entreprise ; sinon on laisse le
        # défaut « particulier » (rare, mais possible pour un artisan).
        type_tiers = 'entreprise' if (fournisseur.ice or '').strip() \
            else 'particulier'
        tiers, _cree = tiers_services.attacher_ou_creer_tiers(
            company=fournisseur.company,
            nom=fournisseur.nom or '',
            roles=_roles_pour_fournisseur(fournisseur),
            email=fournisseur.email or '',
            ice=fournisseur.ice or '',
            tiers_existant=(fournisseur.tiers
                            if fournisseur.tiers_id else None),
            type_tiers=type_tiers,
            raison_sociale=(fournisseur.nom or ''
                            if type_tiers == 'entreprise' else ''),
            telephone=fournisseur.telephone or '',
            adresse=fournisseur.adresse or '',
            rc=fournisseur.rc or '',
            identifiant_fiscal=fournisseur.identifiant_fiscal or '',
            rib=fournisseur.rib or '',
        )
        if fournisseur.tiers_id != tiers.id:
            sender.objects.filter(pk=fournisseur.pk).update(tiers=tiers)
            fournisseur.tiers = tiers
        # AUDV23 (ARC21) — LE HOOK D'ÉCRITURE, CÂBLÉ MAINTENANT. Voir le
        # jumeau `apps/crm/tiers_bridge.py` : le service existait sans aucun
        # appelant, donc activer `TIERS_SOURCE_ECRITURE` aurait été un
        # chantier et non un flip. Flag OFF (le défaut) = NO-OP strict.
        # L'identité SEULE est concernée : jamais un prix d'achat.
        from apps.stock.services import ecrire_identite_fournisseur
        ecrire_identite_fournisseur(fournisseur)
    except Exception:
        # CRX40 — le pont ne doit jamais casser une écriture Fournisseur, mais
        # il ne doit pas non plus échouer EN SILENCE : un `pass` nu rendait un
        # miroir cassé strictement invisible. L'exception reste avalée ; seule
        # la trace est ajoutée (même correctif que le jumeau crm).
        logger.exception(
            'ARC18: miroir Fournisseur → Tiers échoué (fournisseur #%s, '
            'société #%s) — le répertoire unifié peut diverger des achats.',
            getattr(fournisseur, 'pk', None), fournisseur.company_id)


def connect():
    """No-op explicite : le décorateur ``@receiver`` a déjà branché le signal
    à l'import du module (point d'accroche lisible depuis ``apps.py``)."""
    return None
