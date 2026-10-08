"""Signaux du bus lead / visites (propriétaire lead).

SPL289 — extrait de ``core/events/__init__.py`` (move only). Ré-exporté
par ``from .lead import *`` dans ``core/events/__init__.py`` :
les émetteurs et abonnés continuent d'importer ``core.events``.
"""
import django.dispatch


# PUB100 — Émis quand un lead CRM est EFFACÉ (droit à l'oubli CNDP). Permet aux
# miroirs qui portent une référence STRING au lead (adsengine :
# ``MetaLeadMirror``/``CtwaReferral`` via ``crm_lead_id`` + ``phone_key``) de
# propager l'effacement (anonymisation best-effort) sans que ``crm`` importe
# ``apps.adsengine``. Arguments : company, crm_lead_id (int), phone_key (str,
# optionnel). Abonné dans ce repo : adsengine (apps/adsengine/receivers.py).
lead_erased = django.dispatch.Signal()

# NTGRC9 — Émis à la CRÉATION d'un lead CRM, quelle que soit la porte d'entrée
# (saisie, webhook site, import). Arguments : lead (crm.Lead), company.
# Émetteur dans ce repo : crm (apps/crm/receivers.py, post_save created=True).
# Abonné vivant (ALEA3 — docstring corrigée) : calepinage
# (apps/calepinage/receivers.py, reprise du tracé public CAL110) — `crm`
# n'importe jamais `apps.calepinage`. L'abonné historique `grc` (alerte DPO,
# NTGRC9) vit dans un module PARQUÉ (backend/parked/grc) : il ne reçoit rien.
lead_created = django.dispatch.Signal()

# VTA5 — Émis quand une visite technique terrain reçoit le FEU VERT du bureau
# d'études (``apps.visites.services.valider_visite``). Arguments : visite
# (visites.VisiteTerrain), lead_id (ENTIER, jamais l'instance — référence
# cross-app string), user (l'utilisateur AGISSANT, jamais déduit), recap
# (phrase FR courte PRÉ-CALCULÉE par ``visites.selectors.recap_visite_terrain``
# — le récepteur n'a rien à recalculer, et la règle « zéro chiffre inventé »
# reste tenue d'un seul côté).
# Ce n'est PAS un changement d'étape du funnel : ``STAGES.py`` n'est pas touché
# (le statut de visite est un layer DOCUMENT interne). Abonné dans ce repo :
# ``crm`` (``apps/crm/receivers.py``) — il pose ``Lead.visite_effectuee`` +
# le récap dans ``Lead.visite_notes`` et une note au chatter. C'est ce qui
# supprime le DERNIER écrit direct de ``visites`` vers ``crm.Lead`` : l'app
# visites ne connaît plus le lead que par un entier.
visite_validee = django.dispatch.Signal()

# VISITE-CADENCE (fondateur 15/09/2026) — LA VISITE TECHNIQUE EST UNE ÉTAPE DU
# SUIVI COMMERCIAL, PAS UN ÉVÉNEMENT ISOLÉ.
#
# Doctrine : la visite se place APRÈS l'envoi du devis, comme outil de closing
# pendant que le client est chaud. Le SUIVI doit donc RÉAGIR à la visite —
# suspendre les touches génériques quand un rendez-vous est pris, pousser le
# responsable à rappeler dans les 24-48 h une fois le technicien reparti.
# ``apps.visites`` ne sait RIEN de tout cela : elle ÉMET, ``apps.crm`` décide
# (même montage que ``visite_validee`` ci-dessus, frontière M3/M6 intacte).
#
# AUCUN de ces deux événements ne touche ``STAGES.py`` : le statut d'une visite
# reste un layer DOCUMENT interne, jamais une étape de funnel.

# Émis quand la DATE PRÉVUE d'une visite technique est posée ou CHANGÉE
# (création avec date, mise à jour, ou ``visites.services.planifier_visite``).
# Arguments : visite (visites.VisiteTerrain), lead_id (ENTIER — référence
# cross-app string), user (l'utilisateur AGISSANT), date_prevue (``date``),
# commercial_nom (texte déjà composé côté émetteur — le CRM n'a aucun
# utilisateur à aller relire).
# Abonné dans ce repo : ``crm`` — il synchronise ``Lead.visite_prevue_le``,
# pose la note de chatter, suspend la cadence après-devis en cours et programme
# les deux gestes du rendez-vous (confirmation la veille, débrief le lendemain).
visite_planifiee = django.dispatch.Signal()

# Émis à la fin de l'action ``terminer`` d'une visite technique (le technicien
# a fini sur place). Arguments : visite, lead_id (ENTIER), user, retour —
# ``{'notes': str, 'commentaires_photos': [{'slot': str, 'commentaire': str}],
# 'nb_photos': int}``, PRÉ-COMPOSÉ par ``visites.selectors.retour_visite`` :
# c'est le TEXTE LIBRE du terrain, celui que ``visite_validee`` ne transporte
# justement pas (son récap ne porte que des mesures). Sans lui, les remarques
# du technicien mouraient dans l'app terrain.
# …et ``qualification`` : la LECTURE COMMERCIALE du terrain, à vocabulaire
# FERMÉ (``apps.visites.qualification``) — température, sort du devis,
# décideur, frein, déclencheur, moment du rappel, conseil de closing. ``None``
# tant que rien n'a été saisi (jamais un dict de défauts, qui ferait croire à
# une qualification faite). Elle voyage À CÔTÉ du retour parce qu'elle n'est
# pas du texte : le CRM la rend en une phrase et cale le débrief dessus.
# Abonné dans ce repo : ``crm`` — note de chatter portant la qualification puis
# les commentaires, ``Lead.visite_effectuee``, recalage du débrief et
# notification au RESPONSABLE du lead (« rappeler sous 24-48 h »).
visite_terminee = django.dispatch.Signal()

# NTCRM12 — Émis quand ``crm.Lead.stage`` change (à N'IMPORTE quel point
# d'entrée : avance auto premier contact, avance auto devis envoyé/accepté,
# réactivation YLEAD11, avance manuelle depuis l'écran lead). Arguments :
# lead, old_stage, new_stage, user (peut être None — transitions système).
# Abonné dans ce repo : crm lui-même (``apps/crm/receivers.py``) — génère la
# progression des tâches du playbook actif de la nouvelle étape
# (``LeadPlaybookProgress``), même patron émetteur=abonné que
# ``incident_declared``/``contrat_signe`` (preuve de visibilité cross-app
# sans import direct).
lead_stage_changed = django.dispatch.Signal()

# NTCRM22 — commission due d'un ``DealEnregistre``. ALEA3 (D-ALEA-3) : n'est
# PLUS émis (aucun abonné ; la commission due se lit par
# ``deals-enregistres/a-payer/``). Déclaration conservée (golden SPL283),
# réservée dans ``core.event_coverage`` pour le retour du module compta.
# Arguments historiques : company, deal_id, apporteur_id, montant (Decimal).
deal_commission_due = django.dispatch.Signal()

# PUB30 — Émis quand un ``crm.Appointment`` (RDV terrain) bascule vers EFFECTUE
# (transition GÉNUINE — un save sans changement de statut ne réémet jamais).
# Câblé par ``crm`` lui-même (``apps/crm/receivers.py``, un pre_save/post_save
# intra-app comme le récepteur QJ7 sur ``LeadActivity`` juste au-dessus), même
# patron émetteur=abonné-ailleurs que ``ticket_resolu``. Permet à ``adsengine``
# de pousser un événement CAPI CRM-stage dédié (« visite technique effectuée »,
# même famille/gating que ADSENG32 — ``apps/adsengine/capi_crm.py``) sans que
# ``crm`` importe jamais ``apps.adsengine``. Arguments : ``appointment``
# (instance ``crm.Appointment``), ``company``, ``user`` (toujours None
# aujourd'hui — transition détectée par signal modèle, pas par une action
# utilisateur explicite), ``ancien_statut`` (str|None).
appointment_effectue = django.dispatch.Signal()

# ``salle_vente_signal_interet``
#     Une salle de vente (``crm.SalleVente``) a reçu ≥3 consultations
#     (``crm.SalleVenteVue``) en moins de 48h alors que le lead lié est en
#     stage QUOTE_SENT — signal d'intérêt fort, purement informationnel
#     (JAMAIS un changement de stage automatique). Émis par
#     ``apps.crm.services.detecter_signal_interet_salle_vente`` (appelé en
#     best-effort depuis ``apps.crm.public_views.public_salle_vente`` à chaque
#     nouvelle vue), au plus UNE fois par jour local et par salle. La note de
#     chatter (``LeadActivity``) est écrite EN LIGNE par ce même service.
#     Abonné dans ce repo (ALEA3) : ``crm`` (``apps/crm/receivers.py``)
#     notifie le responsable du lead (``apps.notifications``).
#     Arguments : ``lead``, ``salle``, ``company``.
salle_vente_signal_interet = django.dispatch.Signal()

__all__ = [
    'lead_erased',
    'lead_created',
    'visite_validee',
    'visite_planifiee',
    'visite_terminee',
    'lead_stage_changed',
    'deal_commission_due',
    'appointment_effectue',
    'salle_vente_signal_interet',
]
