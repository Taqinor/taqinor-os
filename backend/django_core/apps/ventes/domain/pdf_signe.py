"""ERR-ACCEPTATION-PDF-SIGNE-SYNCHRONE (décision fondateur 28/10/2026, option a).

Le rendu de l'exemplaire SIGNÉ (moteur premium, 5 à 14 s mesurés) ne tourne
plus DANS la requête d'acceptation : il est mis en file Celery APRÈS le commit
(``transaction.on_commit``) et la requête répond dès l'acceptation écrite.

* La tâche (``ventes.rendre_pdf_signe``) re-vérifie d'abord le SCEAU posé à la
  signature (``identite_entreprise.verifier_empreinte_signature`` : lignes,
  en-tête, chiffres d'étude C&I scellés ``figures_scellees``). Contenu changé
  depuis la signature ⇒ REFUS bruyant (``logger.error``, état ``refuse``),
  jamais un document silencieusement différent de ce qui a été signé.
* Idempotente : ``signed_pdf_key`` déjà posée ⇒ aucun nouveau rendu
  (``cycle_vie._store_signed_pdf`` garde sa garde), confirmation envoyée une
  seule fois par acceptation (verrou de cache sur le jeton de mise en file :
  une ré-exécution Celery reprend le même jeton, une nouvelle acceptation en
  reçoit un neuf).
* La confirmation par e-mail (exemplaire signé joint, ADEV38/ADEV99) part
  depuis la tâche, APRÈS le rendu — sinon elle partirait sans l'exemplaire.
* Règle #4 : la tâche RENDRE seulement ; elle n'écrit aucun statut.

L'état « en préparation » est lisible (``etat_pdf_signe``) par les lecteurs qui
interrogent la signature avant que la tâche ait tourné.
"""
import logging

logger = logging.getLogger(__name__)

ETAT_CACHE_PREFIX = 'ventes:pdf_signe:'
ETAT_CACHE_TTL = 24 * 3600
CONFIRMATION_CACHE_PREFIX = 'ventes:pdf_signe_confirmation:'
EN_PREPARATION = 'en_preparation'
PRET = 'pret'
REFUSE = 'refuse'
ABSENT = 'absent'


def _cle_etat(devis_id):
    return f'{ETAT_CACHE_PREFIX}{devis_id}'


def _poser_etat(devis_id, etat):
    try:
        from django.core.cache import cache
        if etat is None:
            cache.delete(_cle_etat(devis_id))
        else:
            cache.set(_cle_etat(devis_id), etat, ETAT_CACHE_TTL)
    except Exception:  # noqa: BLE001 — état d'affichage seulement (D-ENF22-BLE001)
        logger.warning('PDF signé : état non consigné (devis %s)', devis_id,
                       exc_info=True)


def etat_pdf_signe(sig):
    """L'état LISIBLE de l'exemplaire signé d'une signature : ``pret`` (clé
    posée), ``en_preparation`` (tâche en file), ``refuse`` (contenu changé
    depuis la signature) ou ``absent``. Lecture seule, jamais d'exception."""
    if sig is None:
        return ABSENT
    if getattr(sig, 'signed_pdf_key', None):
        return PRET
    try:
        from django.core.cache import cache
        return cache.get(_cle_etat(sig.devis_id)) or ABSENT
    except Exception:  # noqa: BLE001 — lecture dégradée (D-ENF22-BLE001)
        logger.warning('PDF signé : état illisible', exc_info=True)
        return ABSENT


def planifier_pdf_signe(devis, *, user=None, envoyer_confirmation=False):
    """Met le rendu de l'exemplaire signé en file APRÈS le commit de
    l'acceptation. Appelée hors de toute écriture de statut (règle #4)."""
    import uuid
    from django.db import transaction
    devis_id = getattr(devis, 'pk', None)
    if not devis_id:
        return
    user_id = getattr(user, 'pk', None)
    jeton = uuid.uuid4().hex if envoyer_confirmation else ''
    _poser_etat(devis_id, EN_PREPARATION)
    transaction.on_commit(
        lambda: mettre_en_file_pdf_signe(
            devis_id, user_id=user_id,
            envoyer_confirmation=envoyer_confirmation, jeton=jeton))


def mettre_en_file_pdf_signe(devis_id, *, user_id=None,
                             envoyer_confirmation=False, jeton=''):
    """Confie la tâche à Celery ; courtier injoignable ⇒ rendu EN LIGNE (déjà
    après le commit) plutôt qu'un exemplaire signé silencieusement perdu."""
    from apps.ventes.tasks import task_rendre_pdf_signe
    try:
        task_rendre_pdf_signe.delay(
            devis_id, user_id=user_id,
            envoyer_confirmation=envoyer_confirmation, jeton=jeton)
        return
    except Exception as exc:  # noqa: BLE001 — courtier indisponible (D-ENF22-BLE001)
        logger.warning('PDF signé : file Celery indisponible (%s) — rendu en '
                       'ligne pour le devis %s', exc, devis_id)
    rendre_pdf_signe(devis_id, user_id=user_id,
                     envoyer_confirmation=envoyer_confirmation, jeton=jeton)


def sceau_concorde(devis):
    """Le contenu du devis reproduit-il ENCORE le sceau de sa signature ?
    ``False`` seulement quand l'empreinte scellée ne se reproduit plus (une
    signature sans empreinte — très ancienne — n'est pas « falsifiée »)."""
    from apps.ventes.domain.identite_entreprise import (
        verifier_empreinte_signature)
    return verifier_empreinte_signature(devis).get('intacte') is not False


def _rendre_si_scelle(devis, sig):
    """Rend l'exemplaire signé si le sceau concorde ; sinon refus journalisé.
    Rend l'état final (``pret`` / ``refuse`` / ``absent``)."""
    from apps.ventes.domain import cycle_vie
    if sig.signed_pdf_key:
        return PRET  # idempotent : l'exemplaire signé existe déjà
    if not sceau_concorde(devis):
        logger.error(
            'PDF signé REFUSÉ pour le devis %s : le contenu ne reproduit plus '
            'le sceau de la signature (aucun document différent de celui '
            'signé n\'est rendu).', devis.reference)
        return REFUSE
    # Nom lu sur ``cycle_vie`` : les tests le bouchonnent à cet endroit.
    cycle_vie._store_signed_pdf(devis=devis)
    sig.refresh_from_db(fields=['signed_pdf_key'])
    return PRET if sig.signed_pdf_key else ABSENT


def _confirmer_une_fois(devis, user_id, jeton):
    """La confirmation d'acceptation (exemplaire joint), UNE fois par
    acceptation (``jeton``) même si la tâche est rejouée. Sans signature
    enregistrée, elle part quand même : elle n'affirme alors ni signature ni
    exemplaire (QJR134 / ES11)."""
    from django.core.cache import cache
    from apps.ventes.domain import cycle_vie
    garde = f'{CONFIRMATION_CACHE_PREFIX}{devis.pk}:{jeton}'
    if not cache.add(garde, 1, ETAT_CACHE_TTL):
        return
    user = None
    if user_id:
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.filter(pk=user_id).first()
    cycle_vie._send_acceptance_emails(devis=devis, user=user)


def rendre_pdf_signe(devis_id, *, user_id=None, envoyer_confirmation=False,
                     jeton=''):
    """Le corps de la tâche : rendu scellé puis, si demandé, confirmation.
    N'écrit AUCUN statut (règle #4). Rend l'état final."""
    from apps.ventes.models import Devis, DevisSignature
    devis = (Devis.objects.select_related('company', 'client')
             .filter(pk=devis_id).first())
    if devis is None:
        _poser_etat(devis_id, None)
        return ABSENT
    sig = DevisSignature.objects.filter(devis_id=devis_id).first()
    etat = ABSENT
    if sig is not None:
        try:
            etat = _rendre_si_scelle(devis, sig)
        except Exception:  # noqa: BLE001 — rendu best-effort, journalisé (D-ENF22-BLE001)
            logger.exception('PDF signé : rendu échoué (devis %s)',
                             devis.reference)
    _poser_etat(devis_id, REFUSE if etat == REFUSE else None)
    if envoyer_confirmation:
        try:
            _confirmer_une_fois(devis, user_id, jeton)
        except Exception:  # noqa: BLE001 — best-effort, journalisé (D-ENF22-BLE001)
            logger.exception('PDF signé : confirmation non partie (devis %s)',
                             devis.reference)
    return etat
