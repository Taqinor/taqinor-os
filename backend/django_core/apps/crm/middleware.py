"""QJEQUIPE4 (fondateur 17/10/2026) — mémorise l'IP des utilisateurs ERP connectés.

Nouveau fichier car : un middleware se déclare par chemin pointé dans
``settings.MIDDLEWARE`` et ``apps/crm`` n'en avait aucun.

Après chaque appel API authentifié (``/api/django/…``), le triplet (société,
plateforme, IP d'origine déclarée) de l'utilisateur est retenu dans le cache
pour ``visites.EQUIPE_IP_TTL_S`` (2 h). ``crm.visites.requete_marquee_equipe``
lit ce même triplet sur les ouvertures PUBLIQUES de proposition : un téléphone
qui vient d'utiliser l'ERP et ouvre le vrai lien client depuis le navigateur
intégré WhatsApp (jamais de cookie, jamais d'identifiant d'appareil) est reconnu
comme un appareil de l'équipe — ni compteur, ni note, ni notification.

Pourquoi APRÈS la vue : l'ERP s'authentifie par JWT DRF, que le middleware
Django ne voit pas ; c'est la vue DRF qui pose ``request.user`` (le ``Request``
DRF recopie l'utilisateur authentifié sur la requête Django sous-jacente). Un
point public (``AllowAny``, sans authentificateur) laisse l'utilisateur anonyme
→ rien n'est mémorisé : un client n'est jamais confondu avec l'équipe.

Best-effort absolu : jamais d'exception, jamais une réponse modifiée.
"""
import logging

logger = logging.getLogger(__name__)

#: Seuls les appels de l'API interne portent un utilisateur ERP.
PREFIXE_API = '/api/django/'


class EquipeIpMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._memoriser(request)
        return response

    @staticmethod
    def _memoriser(request):
        try:
            if not (getattr(request, 'path', '') or '').startswith(PREFIXE_API):
                return
            user = getattr(request, 'user', None)
            if user is None or not getattr(user, 'is_authenticated', False):
                return
            company = getattr(user, 'company', None)
            if company is None:
                return
            from .visites import memoriser_ip_equipe
            memoriser_ip_equipe(company, request, user=user)
        except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
            logger.warning('QJEQUIPE4: EquipeIpMiddleware échoué : %s', exc)
