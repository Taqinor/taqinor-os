"""Écritures / orchestration du module ``apps.datarooms`` (groupe NTDOC, P2).

La société est TOUJOURS fournie par l'appelant (résolue côté serveur depuis
``request.user.company``) — jamais lue d'un corps de requête.
"""
from django.db import transaction
from django.utils import timezone

from .models import AccesSalleDonnees, SalleDeDonnees, SalleDeDonneesDocument

# NTDOC12 — issues de la résolution d'un jeton viewer PUBLIC. Introuvable et
# révoqué sont volontairement le MÊME code : un lien révoqué ne doit jamais
# révéler qu'il a existé.
ACCES_INTROUVABLE = 'introuvable'
ACCES_EXPIRE = 'expire'
ACCES_OK = 'ok'


class SalleFermee(ValueError):
    """Action impossible : la salle est fermée (message français)."""


@transaction.atomic
def ajouter_documents(salle, documents, *, visible=True):
    """NTDOC11 — Ajoute des documents GED à une salle (idempotent).

    ``documents`` est un itérable d'instances ``ged.Document`` DÉJÀ résolues et
    vérifiées côté appelant comme appartenant à la société de la salle (la vue
    le garantit ; ce service ne fait jamais confiance à un id brut de requête).

    Un document déjà présent n'est PAS dupliqué (contrainte d'unicité + ``
    get_or_create``) et son ordre existant est conservé. Renvoie la liste des
    lignes créées."""
    if not salle.est_ouverte:
        raise SalleFermee("Cette salle est fermée : son contenu est figé.")
    prochain = (SalleDeDonneesDocument.objects
                .filter(salle=salle)
                .order_by('-ordre')
                .values_list('ordre', flat=True)
                .first() or 0)
    creees = []
    for document in documents:
        prochain += 1
        ligne, cree = SalleDeDonneesDocument.objects.get_or_create(
            salle=salle, document=document,
            defaults={'company': salle.company, 'ordre': prochain,
                      'visible': visible})
        if cree:
            creees.append(ligne)
        else:
            prochain -= 1
    return creees


@transaction.atomic
def retirer_document(salle, document):
    """NTDOC11 — Retire un document de la salle SANS jamais toucher à la GED.

    Seule la ligne d'appartenance disparaît : le ``ged.Document`` reste intact,
    à sa place, avec ses versions. Renvoie True si une ligne a été retirée."""
    if not salle.est_ouverte:
        raise SalleFermee("Cette salle est fermée : son contenu est figé.")
    supprimees, _ = SalleDeDonneesDocument.objects.filter(
        salle=salle, document=document).delete()
    return bool(supprimees)


def creer_salle(*, company, nom, created_by=None, description='',
                deal_type='', dossier_source=None, expires_at=None):
    """NTDOC11 — Crée une salle de données (société posée côté serveur)."""
    return SalleDeDonnees.objects.create(
        company=company, nom=nom, description=description,
        deal_type=deal_type, dossier_source=dossier_source,
        expires_at=expires_at, created_by=created_by)


# ── NTDOC12 — Accès par viewer nommé ────────────────────────────────────────

def inviter_viewer(salle, *, nom, email='', expires_at=None, created_by=None):
    """NTDOC12 — Crée l'accès d'un viewer nommé (son lien lui est propre).

    La société vient TOUJOURS de la salle (jamais d'un corps de requête). Deux
    viewers de la même salle reçoivent deux jetons et deux expirations
    indépendants."""
    if not salle.est_ouverte:
        raise SalleFermee("Cette salle est fermée : aucun nouvel accès.")
    return AccesSalleDonnees.objects.create(
        company=salle.company, salle=salle, nom=nom, email=email,
        expires_at=expires_at, created_by=created_by)


def revoquer_acces(acces):
    """NTDOC12 — Révoque UN accès viewer (les autres ne bougent pas).

    Idempotent. Écriture ciblée : ne touche aucun autre champ."""
    if acces.revoque:
        return acces
    AccesSalleDonnees.objects.filter(pk=acces.pk).update(revoque=True)
    acces.revoque = True
    return acces


def resoudre_acces_public(token, *, now=None):
    """NTDOC12 — Résout un jeton viewer PUBLIC.

    Renvoie ``(statut, acces)`` où ``statut`` vaut ``ACCES_INTROUVABLE``
    (jeton inconnu OU révoqué — indistinct, pas de fuite), ``ACCES_EXPIRE``
    (expiration viewer ou salle dépassée, ou salle fermée) ou ``ACCES_OK``.

    Aucune identité ni société n'est lue de la requête : tout vient du jeton.
    Il n'existe AUCUN listing — seul un jeton exact résout quelque chose."""
    if not token:
        return ACCES_INTROUVABLE, None
    acces = (AccesSalleDonnees.objects
             .select_related('salle', 'salle__company', 'company')
             .filter(token=token)
             .first())
    if acces is None or acces.revoque:
        return ACCES_INTROUVABLE, None
    if not acces.salle.est_ouverte or acces.est_expire(now=now):
        return ACCES_EXPIRE, acces
    return ACCES_OK, acces


def lien_public_acces(acces):
    """NTDOC12 — Lien public d'un viewer (absolu si ``PUBLIC_SITE_URL`` posée).

    Réutilise LE réglage de base publique du projet — on n'en invente pas un
    second."""
    from django.conf import settings
    base = (getattr(settings, 'PUBLIC_SITE_URL', '') or '').rstrip('/')
    chemin = f'/api/django/datarooms/public/{acces.token}/'
    return f'{base}{chemin}' if base else chemin


def marquer_consultation(acces, *, now=None):
    """NTDOC12 — Horodate la dernière consultation d'un viewer (best-effort).

    Écriture ciblée, jamais bloquante : une panne d'écriture ne doit pas
    empêcher le viewer de consulter la salle."""
    horodatage = now or timezone.now()
    try:
        AccesSalleDonnees.objects.filter(pk=acces.pk).update(
            derniere_consultation=horodatage)
        acces.derniere_consultation = horodatage
    except Exception:  # pragma: no cover - défensif, jamais bloquant.
        pass
    return acces
