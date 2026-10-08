"""Signaux du bus du cycle de vie du devis (propriétaire devis).

SPL287 — extrait de ``core/events/__init__.py`` (move only). Ré-exporté
par ``from .devis import *`` dans ``core/events/__init__.py`` :
les émetteurs et abonnés continuent d'importer ``core.events``.

Événements
----------

``devis_accepted``
    Émis quand un devis passe à « accepté » (action explicite ``accepter``).
    Arguments du signal :

    * ``devis`` — l'instance ``Devis`` acceptée ;
    * ``user`` — l'utilisateur qui accepte (peut être ``None``) ;
    * ``ancien_statut`` — le statut du devis avant l'acceptation.

``devis_acceptation_annulee``
    Émis quand l'acceptation d'un devis est ANNULÉE (« dés-acceptation ») :
    le lead sort de « Signé » par une action utilisateur (décision fondateur
    du 08/10/2026), le devis repasse « envoyé ». Émis DANS la transaction de
    ``apps.ventes.domain.cycle_vie.annuler_acceptation`` : les écritures des
    abonnés tiennent ou tombent avec elle. Abonnés : ``installations``
    (annule le chantier auto-créé), ``sav`` (désactive le contrat
    auto-créé), ``crm`` (commission, parrainage, notes de chatter).
    Arguments du signal :

    * ``devis`` — l'instance ``Devis`` désormais ``envoye`` ;
    * ``user`` — l'utilisateur à l'origine de l'annulation (peut être ``None``) ;
    * ``option_acceptee`` — l'option qui était acceptée (peut être vide) ;
    * ``date_acceptation`` — la date d'acceptation annulée (peut être ``None``) ;
    * ``motif`` — le motif libre de l'annulation.

``devis_sent``
    Émis quand un devis passe à « envoyé » suite à un partage client (U4), p.
    ex. la génération d'un lien WhatsApp. Abonné par ``crm`` pour avancer
    l'étape du lead vers QUOTE_SENT. Arguments du signal :

    * ``devis`` — l'instance ``Devis`` envoyée ;
    * ``user`` — l'utilisateur qui partage (peut être ``None``) ;
    * ``ancien_statut`` — le statut du devis avant l'envoi.

``devis_expired``
    Émis quand un devis ``envoyé`` bascule automatiquement en ``expiré``
    (QJ5, ``expire_stale_devis``) — YEVNT2. Jamais réémis pour un devis déjà
    ``expiré`` (no-op). Abonné dans ce repo : ``notifications`` (notifie le
    propriétaire du devis, ``EventType.DEVIS_EXPIRED``) ; ``crm`` continue
    d'avancer le funnel séparément (avancement direct dans le même appel,
    clés ``STAGES.py`` uniquement). Arguments du signal :

    * ``devis`` — l'instance ``Devis`` désormais ``expire`` ;
    * ``ancien_statut`` — toujours ``'envoye'``.

``document_pdf_generated``
    Émis quand un PDF de document de vente est généré (devis ou facture).
    Abonné par le satellite ``audit`` (journalise une entrée ``AuditLog.PDF``).
    Arguments du signal :

    * ``instance`` — l'objet ``Devis`` ou ``Facture`` concerné ;
    * ``kind`` — ``'devis'`` ou ``'facture'`` (sert au libellé d'audit).
"""
import django.dispatch


# Émis à l'acceptation d'un devis.
# Abonné dans ce repo : crm (avance l'étape du lead → SIGNED).
devis_accepted = django.dispatch.Signal()

# Émis à l'ANNULATION de l'acceptation d'un devis (décision fondateur du
# 08/10/2026 : un lead qui sort de « Signé » dés-accepte son devis).
# Arguments : devis, user, option_acceptee, date_acceptation, motif.
# Abonnés : installations, sav, crm (chacun défait SON effet d'acceptation).
devis_acceptation_annulee = django.dispatch.Signal()

# Émis à l'ENVOI d'un devis (U4) — passage brouillon → envoyé déclenché par un
# partage client (ex. lien WhatsApp). Arguments : devis, user, ancien_statut.
# Abonné dans ce repo : crm (avance l'étape du lead → QUOTE_SENT), exactement
# comme devis_accepted, pour que ventes n'importe jamais crm directement.
devis_sent = django.dispatch.Signal()

# Émis quand la conception 3D d'un devis est FINALISÉE (PV79) — création
# depuis un calepinage (``from-layout``) ou resynchronisation réussie
# (``sync-layout``). Arguments : devis, user.
# Ce n'est PAS un changement de statut : le devis reste où il est (règle #4) ;
# l'événement dit seulement que la toiture a été (re)dessinée et que les lignes
# suivent. Abonné dans ce repo : crm (pose une note au chatter du lead), ce qui
# évite que ventes importe crm directement.
layout_finalise = django.dispatch.Signal()

# ACAL91 (C-ACAL-115) — Émis quand « Réviser » a créé la V+1 d'un devis
# (``apps.ventes.domain.revision.reviser_devis``), APRÈS le commit de la
# transaction (``transaction.on_commit``), en best-effort (``send_robust`` :
# un abonné en échec ne casse jamais la révision). Arguments : ancien (la
# version remplacée), nouveau (la V+1), user. Ce n'est PAS un changement de
# statut : aucun statut de devis n'est écrit (règle #4) — seuls ``is_active`` /
# ``superseded_by`` de l'ancienne version ont bougé, par le service. Abonné
# prévu : le calepinage, qui re-lie sa conception à la V+1 (D-ACAL-3, ACAL92) ;
# d'ici là, réservé dans ``core.event_coverage.ALLOWED_UNCONSUMED``.
devis_revise = django.dispatch.Signal()

# Émis au refus d'un devis (FG44).
# Arguments : devis, user, motif_refus.
# Abonné optionnellement par crm pour marquer le lead perdu (→ COLD + perdu).
devis_refused = django.dispatch.Signal()

# Émis quand un devis envoyé bascule automatiquement en « expiré » (QJ5,
# ``expire_stale_devis``) — YEVNT2. Arguments : devis, ancien_statut='envoye'.
# Abonné dans ce repo : notifications (notifie le propriétaire).
devis_expired = django.dispatch.Signal()

# Émis à la génération d'un PDF de document de vente (devis/facture) — M4.
# Arguments : instance (Devis|Facture), kind ('devis'|'facture').
# Abonné par le satellite audit (journalise AuditLog.Action.PDF), ce qui évite
# que ventes importe apps.audit (suppression de l'arête montante ventes→audit).
document_pdf_generated = django.dispatch.Signal()

__all__ = [
    'devis_accepted',
    'devis_acceptation_annulee',
    'devis_sent',
    'layout_finalise',
    'devis_revise',
    'devis_refused',
    'devis_expired',
    'document_pdf_generated',
]
