"""Services du module Appels d'offres (``apps.ao``).

AOF1 — le CORPS des services AO vit désormais ICI (il vivait encore interleavé
dans ``apps.compta.services`` malgré la sortie ODX11 des modèles).
``apps.compta.services`` porte maintenant un shim de ré-export **INVERSE**
(``from apps.ao.services import …``) pour ne casser aucun import historique.

``ao`` ne lit crm/ventes QUE via leurs selectors/services ou par référence
opaque — jamais leurs ``models`` (le lead reste un ``lead_id`` opaque).
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from core import events
from core.numbering import create_with_reference

from .models import AppelOffre, EcheanceAO, ResultatAO

#: AOF5 — préfixe de NOTRE numérotation d'appels d'offres (``AO-YYYYMM-0001``).
#: La référence de l'acheteur vit dans ``AppelOffre.reference_acheteur`` et
#: n'entre JAMAIS dans cette séquence.
PREFIXE_REFERENCE_AO = 'AO'


# ── AOF5 — Numérotation des appels d'offres ────────────────────────────────

def creer_appel_offre_avec_reference(company, save_fn):
    """Crée un ``AppelOffre`` en lui attribuant une référence libre.

    Délègue à ``core.numbering.create_with_reference`` : plus-haut-numéro-
    utilisé + 1 par société et par mois, dans un savepoint, avec réessai sur
    une course. JAMAIS ``count() + 1`` ni un ``max + 1`` recalculé localement —
    ce motif a déjà coûté une collision de références en production (une
    suppression fait rétrécir le compte alors que le plus haut numéro utilisé,
    lui, reste).

    ``save_fn`` reçoit la référence générée et doit effectuer la création
    réelle (``serializer.save(...)`` ou ``AppelOffre.objects.create(...)``)
    puis retourner l'instance.
    """
    return create_with_reference(
        AppelOffre, PREFIXE_REFERENCE_AO, company, save_fn)


# ── AOF13 — Table de transitions DÉCLARATIVE + service de changement ───────
#
# La table est la seule description du cycle : aucune règle de statut n'est
# écrite « en dur » dans une vue ou un serializer. Les six valeurs historiques
# sont conservées ; ``en_preparation`` (le fourre-tout d'avant) reste un point
# de sortie vers CHACUNE des nouvelles étapes pour que les lignes déjà en base
# ne se retrouvent jamais coincées.

_S = AppelOffre.Statut

TRANSITIONS_AO = {
    _S.IDENTIFIE: (_S.ANALYSE_CPS, _S.EN_PREPARATION, _S.ABANDONNE),
    _S.ANALYSE_CPS: (_S.RELEVE, _S.ABANDONNE),
    _S.RELEVE: (_S.ETUDE, _S.ABANDONNE),
    _S.ETUDE: (_S.CHIFFRAGE, _S.ABANDONNE),
    _S.CHIFFRAGE: (_S.DOSSIER, _S.ABANDONNE),
    _S.DOSSIER: (_S.PRET_A_DEPOSER, _S.ABANDONNE),
    _S.PRET_A_DEPOSER: (_S.DEPOSE, _S.ABANDONNE),
    # Statut HISTORIQUE : rejoint n'importe quelle étape du nouveau cycle.
    _S.EN_PREPARATION: (
        _S.ANALYSE_CPS, _S.RELEVE, _S.ETUDE, _S.CHIFFRAGE, _S.DOSSIER,
        _S.PRET_A_DEPOSER, _S.DEPOSE, _S.ABANDONNE,
    ),
    _S.DEPOSE: (_S.GAGNE, _S.PERDU, _S.ABANDONNE),
    # États terminaux : plus aucune transition (l'issue d'un marché ne se
    # réécrit pas — un nouveau dossier serait un nouvel AO).
    _S.GAGNE: (),
    _S.PERDU: (),
    _S.ABANDONNE: (),
}

#: Statut → signal M6 à émettre EN SORTIE du service. Deux entrées, deux
#: abonnés réels (``apps/crm/receivers.py``) — on ne déclare jamais un signal
#: « pour plus tard » (``core.event_coverage`` le refuserait).
_SIGNAUX_PAR_STATUT = {
    _S.DEPOSE: events.ao_depose,
    _S.GAGNE: events.ao_gagne,
}


def transitions_possibles(statut):
    """Statuts atteignables depuis ``statut`` (tuple, éventuellement vide)."""
    return TRANSITIONS_AO.get(statut, ())


def changer_statut_ao(appel_offre, nouveau_statut, *, user=None, motif=''):
    """SEUL point de mutation du statut d'un appel d'offres (AOF13).

    Valide la transition contre ``TRANSITIONS_AO``, écrit le statut, journalise
    au chatter générique ``records`` (ARC8 — jamais une classe ``*Activity``
    maison) puis émet l'événement M6 correspondant s'il y en a un.

    Args:
        appel_offre: l'instance ``AppelOffre`` à faire avancer.
        nouveau_statut: valeur cible (clé de ``AppelOffre.Statut``).
        user: l'utilisateur qui décide (posé côté serveur, jamais lu du corps).
        motif: commentaire libre journalisé au chatter.

    Returns:
        L'instance mise à jour.

    Raises:
        ValidationError: transition inconnue ou interdite (message FR), à
        traduire en 400 par l'appelant HTTP.
    """
    ancien_statut = appel_offre.statut
    if nouveau_statut == ancien_statut:
        return appel_offre
    valides = dict(_S.choices)
    if nouveau_statut not in valides:
        raise ValidationError({'statut': f"Statut inconnu : « {nouveau_statut} »."})
    autorises = transitions_possibles(ancien_statut)
    if nouveau_statut not in autorises:
        libelles = ', '.join(f'« {valides[s]} »' for s in autorises) or 'aucun'
        raise ValidationError({'statut': (
            f"Transition interdite : « {valides[ancien_statut]} » → "
            f"« {valides[nouveau_statut]} ». Statuts atteignables : "
            f"{libelles}."
        )})

    appel_offre.statut = nouveau_statut
    setattr(appel_offre, AppelOffre.ATTR_STATUT_AUTORISE, True)
    try:
        appel_offre.save(update_fields=['statut', 'updated_at'])
    finally:
        setattr(appel_offre, AppelOffre.ATTR_STATUT_AUTORISE, False)

    _journaliser_statut(appel_offre, ancien_statut, nouveau_statut, user, motif)

    signal = _SIGNAUX_PAR_STATUT.get(nouveau_statut)
    if signal is not None:
        signal.send(
            sender='ao.AppelOffre', appel_offre=appel_offre,
            company=appel_offre.company, user=user,
            ancien_statut=ancien_statut)
    return appel_offre


def _journaliser_statut(appel_offre, ancien, nouveau, user, motif):
    """Trace le changement au chatter générique ``records`` (best-effort)."""
    from apps.records.models import Activity
    from apps.records.services import log_activity

    libelles = dict(_S.choices)
    log_activity(
        appel_offre, Activity.Kind.MODIFICATION, user=user,
        field='statut', field_label='Statut',
        old_value=libelles.get(ancien, ancien),
        new_value=libelles.get(nouveau, nouveau),
        body=motif or '', company=appel_offre.company)


# ── FG226 — Échéances d'AO dues (rappels) ──────────────────────────────────

def echeances_ao_dues(company, *, a_la_date=None):
    """Liste les échéances d'AO dont le rappel est dû (FG226), NON traitées.

    Une échéance est due quand ``date_echeance - rappel_jours <= a_la_date`` et
    qu'elle n'est pas encore traitée. Calcul pur (aucun envoi réseau) — sert au
    moteur d'alertes et aux tests.
    """
    a_la_date = a_la_date or timezone.now().date()
    dues = []
    qs = EcheanceAO.objects.filter(
        company=company, traitee=False).order_by('date_echeance')
    for ech in qs:
        seuil = ech.date_echeance - timezone.timedelta(days=ech.rappel_jours)
        if seuil <= a_la_date:
            dues.append(ech)
    return dues


# ── FG227 — Taux de réussite des appels d'offres ───────────────────────────

def taux_reussite_ao(company):
    """Taux de réussite gagné/perdu des AO (FG227).

    Compte les résultats par issue et calcule le taux = gagnés / (gagnés +
    perdus). Renvoie un dict d'agrégats. Lecture seule.
    """
    resultats = ResultatAO.objects.filter(company=company)
    gagnes = resultats.filter(issue=ResultatAO.Issue.GAGNE).count()
    perdus = resultats.filter(issue=ResultatAO.Issue.PERDU).count()
    total_decides = gagnes + perdus
    taux = Decimal('0.00')
    if total_decides > 0:
        taux = (Decimal(gagnes) / Decimal(total_decides) * Decimal('100')
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        'gagnes': gagnes,
        'perdus': perdus,
        'total_decides': total_decides,
        'total_resultats': resultats.count(),
        'taux_reussite_pct': taux,
    }
