"""NTCON36 — opérations de capture TERRAIN hors-ligne du module BTP.

Enregistrées dans le moteur hors-ligne GÉNÉRIQUE du dépôt
(``apps.offlinesync``, NTMOB1) par ``registry.register`` depuis
``BtpChantierConfig.ready()`` : « Les autres modules s'ajoutent par un simple
``registry.register(...)`` — c'est le point d'extension, aucun code du moteur
n'est à toucher » (docstring de ``apps/offlinesync/handlers.py``). AUCUN second
mécanisme hors-ligne n'est introduit : ni file maison, ni endpoint de synchro
propre à ``btp_chantier``, ni journal parallèle.

MODULE DÉCLARÉ : ``installations`` — la valeur dont ``OfflineOperation.Module``
porte le libellé « Chantiers », et le modèle auquel le chantier BTP est
réellement rattaché (``btp_chantier`` référence ``installations.Installation``
par FK). Aucune valeur n'est ajoutée au catalogue fermé de ``offlinesync`` :
c'est son app, pas la nôtre.

LAST-WRITE-WINS (exigence du registre) : chaque handler POSE un état, jamais un
incrément. L'entrée de journal du jour est un ``update_or_create`` sur la clé
unique (chantier, date) — deux terminaux qui se reconnectent dans le désordre
convergent sur la dernière écriture, jamais sur un doublon refusé.

La PHOTO n'emprunte pas cette file : le moteur ``offlinesync`` transporte du
JSON, pas du binaire. L'écran terrain conserve donc la photo dans son brouillon
local et la téléverse par l'endpoint multipart EXISTANT
(``records.Attachment``) au retour du réseau — et il le DIT à l'utilisateur
plutôt que de faire disparaître la photo en silence.
"""
from __future__ import annotations


def _chantier(company, payload):
    """Chantier BORNÉ SOCIÉTÉ, ou ``OfflineOpError``.

    Lecture cross-app par le SÉLECTEUR d'``installations`` (jamais ses
    ``models``) : un id d'une autre société est indiscernable d'un id inconnu.
    """
    from apps.installations import selectors as installations_selectors
    from apps.offlinesync.registry import OfflineOpError

    chantier = installations_selectors.installation_scoped(
        company, payload.get('chantier'))
    if chantier is None:
        raise OfflineOpError('Chantier inconnu.')
    return chantier


def h_reserve_creer(company, user, payload):
    """``btp.reserve.creer`` — réserve posée sur un plan depuis le terrain.

    Le moteur dédoublonne par ``client_op_id`` : un lot rejoué deux fois ne
    crée jamais deux réserves. ``company`` et ``created_by`` sont posés
    SERVEUR, jamais lus du corps.
    """
    from apps.offlinesync.registry import OfflineOpError

    from . import services
    from .models import ReserveChantier

    chantier = _chantier(company, payload)
    description = (payload.get('description') or '').strip()
    if not description:
        raise OfflineOpError('Description de la réserve manquante.')
    gravite = payload.get('gravite') or ReserveChantier.Gravite.MINEURE
    if gravite not in {c for c, _ in ReserveChantier.Gravite.choices}:
        raise OfflineOpError(f'Gravité inconnue : « {gravite} ».')

    localisation = payload.get('localisation_plan') or {}
    if not isinstance(localisation, dict):
        raise OfflineOpError('Localisation sur le plan invalide.')

    reserve = ReserveChantier.objects.create(
        company=company, chantier=chantier,
        lot=(payload.get('lot') or '')[:100],
        localisation_plan=localisation,
        description=description, gravite=gravite, created_by=user)
    services.enregistrer_creation_reserve(reserve, created_by=user)
    return {'reserve_id': reserve.pk, 'statut': reserve.statut}


def h_journal_entree_du_jour(company, user, payload):
    """``btp.journal.entree_du_jour`` — entrée de journal du jour (NTCON6).

    LAST-WRITE-WINS assumé : ``update_or_create`` sur la clé unique
    (chantier, date) du modèle. Un second terminal qui se reconnecte écrase
    proprement au lieu de se heurter à la contrainte d'unicité et de perdre sa
    saisie.
    """
    from django.utils import timezone

    from apps.offlinesync.registry import OfflineOpError

    from .models import JournalChantier

    chantier = _chantier(company, payload)
    jour = payload.get('date')
    if jour:
        from django.utils.dateparse import parse_date
        jour = parse_date(str(jour))
        if jour is None:
            raise OfflineOpError(
                f'Date illisible : « {payload.get("date")} » '
                '(attendu AAAA-MM-JJ).')
    else:
        jour = timezone.localdate()

    champs = {'redacteur': user}
    for cle in ('meteo', 'materiel_present', 'evenements'):
        if payload.get(cle) is not None:
            champs[cle] = payload[cle]
    for cle in ('effectif_interne', 'effectif_sous_traitant', 'visiteurs'):
        valeur = payload.get(cle)
        if valeur is not None:
            if not isinstance(valeur, (dict, list)):
                raise OfflineOpError(f'Champ « {cle} » invalide.')
            champs[cle] = valeur

    entree, cree = JournalChantier.objects.update_or_create(
        company=company, chantier=chantier, date=jour, defaults=champs)
    return {'journal_id': entree.pk, 'cree': cree,
            'date': entree.date.isoformat()}


def connect():
    """Enregistre les op_types BTP. Appelé depuis ``BtpChantierConfig.ready()``.

    Best-effort : si ``apps.offlinesync`` n'est pas installé (édition allégée),
    la capture terrain fonctionne simplement en ligne seulement — jamais une
    erreur au démarrage.
    """
    try:
        from apps.offlinesync.models import OfflineOperation
        from apps.offlinesync.registry import register
    except Exception:  # noqa: BLE001 — module absent de cette édition
        return
    module = OfflineOperation.Module.INSTALLATIONS
    register('btp.reserve.creer', module, h_reserve_creer)
    register('btp.journal.entree_du_jour', module, h_journal_entree_du_jour)
