"""ARC18 — Miroir one-way ``crm.Client`` → répertoire unifié ``tiers.Tiers``.

À la sauvegarde d'un Client, on rattache (dédup email/ICE company-scopée) ou
crée son ``Tiers`` miroir et on pose le drapeau ``is_client``. L'identité reste
MAÎTRE côté Client ; ``tiers`` n'en est qu'un reflet (pont réversible — la
bascule write-path est la décision ARC21, OFF par défaut).

Découplage : ce module vit dans ``apps.crm`` (jamais dans ``apps.tiers`` qui
reste une couche fondation) et n'appelle ``apps.tiers.services`` que par un
import FONCTION-LOCAL (motif d'évitement de cycle sanctionné). Best-effort :
un échec du miroir ne fait JAMAIS échouer la sauvegarde du Client.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _type_tiers_pour_client(client):
    """Traduit le ``type_client`` (particulier/entreprise) vers le
    ``type_tiers`` du répertoire (mêmes clés)."""
    return 'entreprise' if client.type_client == 'entreprise' else 'particulier'


@receiver(post_save, sender='crm.Client',
          dispatch_uid='crm_client_mirror_tiers')
def mirror_client_to_tiers(sender, instance, **kwargs):
    client = instance
    if client.company_id is None:
        return  # pas de société — rien à miroiter (jamais cross-tenant).
    try:
        from apps.tiers import services as tiers_services

        raison = client.nom if client.type_client == 'entreprise' else ''
        tiers, _cree = tiers_services.attacher_ou_creer_tiers(
            company=client.company,
            nom=client.nom or '',
            roles=('is_client',),
            email=client.email or '',
            ice=client.ice or '',
            tiers_existant=client.tiers if client.tiers_id else None,
            type_tiers=_type_tiers_pour_client(client),
            prenom=client.prenom or '',
            raison_sociale=raison,
            telephone=client.telephone or '',
            adresse=client.adresse or '',
            rc=client.rc or '',
            identifiant_fiscal=client.if_fiscal or '',
            cin=client.cin or '',
        )
        # Écrit le lien retour SANS re-déclencher ce signal (update direct).
        if client.tiers_id != tiers.id:
            sender.objects.filter(pk=client.pk).update(tiers=tiers)
    except Exception:
        # Le pont ne doit jamais casser une écriture Client existante — mais
        # CRX40 : il ne doit pas non plus échouer EN SILENCE. Le `pass` nu
        # rendait un miroir cassé strictement invisible : le répertoire unifié
        # divergeait du CRM sans qu'aucune trace n'existe nulle part, et le
        # premier symptôme était un `Tiers` manquant des mois plus tard.
        # `logger.exception` conserve la pile ; le comportement, lui, ne change
        # pas d'un iota (l'exception reste avalée).
        logger.exception(
            'ARC18: miroir Client → Tiers échoué (client #%s, société #%s) — '
            'le répertoire unifié peut diverger du CRM.',
            getattr(client, 'pk', None), client.company_id)


def connect():
    """No-op explicite : le décorateur ``@receiver`` a déjà branché le signal
    à l'import du module. Fournit un point d'accroche lisible depuis
    ``apps.py`` ``ready()`` (l'import du module suffit à câbler)."""
    return None
