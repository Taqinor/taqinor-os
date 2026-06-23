"""Couche d'événements métier (M6) — petit bus d'événements interne basé sur
les signaux Django, pour découpler les apps du cœur métier.

Une app émettrice (ex. ``ventes``) envoie un événement ; les apps intéressées
(``crm``, ``installations``, ``audit``…) s'y abonnent via un récepteur câblé
dans leur ``apps.py`` (``ready()``). Cela évite qu'une app importe directement
les ``models`` / ``services`` d'une autre uniquement pour réagir à un changement
d'état : l'émetteur ne connaît pas ses abonnés.

``core`` est une app de fondation : elle ne dépend d'aucune app métier, donc
placer le bus ici n'introduit aucun cycle d'import.

Carte des trois couches (M4)
----------------------------

Le repo est organisé en trois couches, chacune ne dépendant QUE de couches en
dessous d'elle ; les réactions inter-app montantes passent par ce bus, jamais
par un import direct des ``models`` / ``views`` d'une autre app :

* **Fondation** — ``authentication``, ``roles``, ``records``, ``customfields``,
  ``core`` (dont ce bus). Ne dépend d'aucune app métier.
* **Cœur métier** — ``crm``, ``stock``, ``ventes``, ``installations``, ``sav``.
  Se parlent via ``services.py`` / ``selectors.py`` (jamais les ``models`` /
  ``views`` d'une autre), et réagissent aux autres via ce bus.
* **Satellites** — ``reporting``, ``automation``, ``monitoring``,
  ``notifications``, ``publicapi``, ``audit``, ``documents``, ``dataimport``,
  ``contact``. Observent le cœur métier ; le cœur métier ne les importe pas.

M4 a supprimé la dernière arête montante ``ventes → audit`` : ``ventes`` émet
désormais ``document_pdf_generated`` et le satellite ``audit`` s'y abonne
(``apps/audit/receivers.py``) pour journaliser le PDF, sans que ``ventes``
importe ``apps.audit``.

Événements disponibles
----------------------

``devis_accepted``
    Émis quand un devis passe à « accepté » (action explicite ``accepter``).
    Arguments du signal :

    * ``devis`` — l'instance ``Devis`` acceptée ;
    * ``user`` — l'utilisateur qui accepte (peut être ``None``) ;
    * ``ancien_statut`` — le statut du devis avant l'acceptation.

``devis_sent``
    Émis quand un devis passe à « envoyé » suite à un partage client (U4), p.
    ex. la génération d'un lien WhatsApp. Abonné par ``crm`` pour avancer
    l'étape du lead vers QUOTE_SENT. Arguments du signal :

    * ``devis`` — l'instance ``Devis`` envoyée ;
    * ``user`` — l'utilisateur qui partage (peut être ``None``) ;
    * ``ancien_statut`` — le statut du devis avant l'envoi.

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

# Émis à l'ENVOI d'un devis (U4) — passage brouillon → envoyé déclenché par un
# partage client (ex. lien WhatsApp). Arguments : devis, user, ancien_statut.
# Abonné dans ce repo : crm (avance l'étape du lead → QUOTE_SENT), exactement
# comme devis_accepted, pour que ventes n'importe jamais crm directement.
devis_sent = django.dispatch.Signal()

# Émis au refus d'un devis (FG44).
# Arguments : devis, user, motif_refus.
# Abonné optionnellement par crm pour marquer le lead perdu (→ COLD + perdu).
devis_refused = django.dispatch.Signal()

# Émis à la génération d'un PDF de document de vente (devis/facture) — M4.
# Arguments : instance (Devis|Facture), kind ('devis'|'facture').
# Abonné par le satellite audit (journalise AuditLog.Action.PDF), ce qui évite
# que ventes importe apps.audit (suppression de l'arête montante ventes→audit).
document_pdf_generated = django.dispatch.Signal()
