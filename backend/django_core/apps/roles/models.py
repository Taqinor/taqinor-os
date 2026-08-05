import re

from django.db import models


# ───────────────────────────────────────────────────────────────────────────
# ODY26 — Axe « App visible » par rôle. DÉCISION : on RÉUTILISE
# ``Role.permissions``, sans nouveau champ ni migration.
#
# Vérifié avant de trancher : la visibilité d'une app ne dépendait jusqu'ici
# QUE du palier codé en dur dans les ``module.config.jsx`` (2 items de nav sur
# 44 modules portent un ``perm``) — rien d'administrable. ``Role.permissions``
# est le SEUL magasin par rôle, scopé société, éditable dans la matrice VX38 et
# déjà acheminé au front (``state.auth.permissions``, lu par
# ``useInstalledApps()``). Un champ dédié n'aurait rien apporté de plus et
# aurait coûté une migration + un 2ᵉ système à garder synchrone.
#
# Convention : un code ``app_<clé>_voir`` par app (préfixe ``app_`` : aucune
# collision avec les codes métier ``crm_voir``/``sav_voir``…).
#
# Sémantique : NARROWING OPT-IN, le patron déjà utilisé plus bas pour
# ``records_scope_equipe``/``records_scope_sous_arbre`` — un rôle SANS aucun
# marqueur voit tout (comportement historique préservé) ; dès qu'il en porte
# un, la liste devient une LISTE BLANCHE.
#
# Ces codes ne sont VOLONTAIREMENT pas dans ``ALL_PERMISSIONS`` (ci-dessous),
# pour deux raisons : (1) ``DIRECTEUR_PERMISSIONS``/``ADMIN_PERMISSIONS`` en
# dérivent — les y mettre restreindrait mécaniquement le Directeur à la liste
# gelée du jour ; (2) énumérer les 44 clés d'apps côté backend créerait un 2ᵉ
# REGISTRE de la liste d'apps, ce que le Groupe ODY interdit (l'unique registre
# reste ``moduleConfigs`` côté front, consommé par ``useInstalledApps()``). La
# validation se fait donc par FORME (``EST_PERMISSION_APP``) — ces codes ne
# donnent aucun droit, ils en RETIRENT : un code inconnu de trop n'ouvre rien.
#
# PORTÉE : restriction d'INTERFACE (quelles apps le porteur voit), jamais une
# frontière de sécurité — le gating serveur par viewset reste seul juge.
# ───────────────────────────────────────────────────────────────────────────
APP_VISIBILITY_PREFIX = 'app_'
APP_VISIBILITY_SUFFIX = '_voir'
EST_PERMISSION_APP = re.compile(r'^app_[a-z0-9][a-z0-9_]*_voir$')


def est_permission_app(code):
    """Vrai si ``code`` appartient à la famille ODY26 « app visible »."""
    return bool(EST_PERMISSION_APP.match(code or ''))


def permission_app(cle):
    """Code de permission « app visible » pour la clé de module ``cle``."""
    return f'{APP_VISIBILITY_PREFIX}{cle}{APP_VISIBILITY_SUFFIX}'


def cles_apps_autorisees(permissions):
    """Liste blanche d'apps portée par ``permissions``, ou ``None``.

    ``None`` (et non un ensemble vide) quand le rôle ne porte AUCUN marqueur :
    « pas de restriction » et « restreint à rien » sont deux états distincts,
    et seul le premier existe côté données (miroir exact de
    ``allowedAppKeys()`` dans ``frontend/src/lib/apps/useInstalledApps.js``).
    """
    codes = [c for c in (permissions or []) if est_permission_app(c)]
    if not codes:
        return None
    return {
        c[len(APP_VISIBILITY_PREFIX):-len(APP_VISIBILITY_SUFFIX)]
        for c in codes
    }


ALL_PERMISSIONS = [
    'stock_voir',
    'stock_creer',
    'stock_modifier',
    'stock_supprimer',
    'stock_mouvement',
    'stock_export',
    'crm_voir',
    'crm_creer',
    'crm_modifier',
    'crm_supprimer',
    'crm_export',
    'crm_reassign',
    'ventes_voir',
    'ventes_creer',
    'ventes_modifier',
    'ventes_supprimer',
    'ventes_valider',
    'ventes_pdf',
    'ventes_export',
    'ventes_reassign',
    'installation_voir',
    'installation_gerer',
    'installation_export',
    'intervention_gerer',
    'technicien_assign',
    'equipement_voir',
    'equipement_gerer',
    'sav_voir',
    'sav_gerer',
    'sav_export',
    'sav_reassign',
    'parametres_voir',
    'parametres_modifier',
    'users_voir',
    'users_gerer',
    'roles_gerer',
    'reporting_voir',
    'reporting_export',
    # ── Comptabilité — séparation des tâches (COMPTA40) ──
    # Trois actions DISJOINTES du flux comptable : saisir une écriture, la
    # valider (second regard) et clôturer une période/exercice. La règle
    # « le saisisseur ne valide pas sa propre écriture » est posée en dur côté
    # service (``compta.services.valider_ecriture``) ; ces codes gouvernent QUI
    # a le droit d'accéder à chaque action. ``compta_cloturer`` est une action
    # de gouvernance réservée par défaut au palier direction.
    'compta_saisir',
    'compta_valider',
    'compta_cloturer',
    # ── Paie (XPAI7) — follow-up explicite noté au DONE de PAIE1 ──
    # L'app ``paie`` était gatée uniquement par le grossier
    # ``IsResponsableOrAdmin`` (tout porteur de rôle passe). Deux codes
    # DISJOINTS : ``paie_voir`` (lecture bulletins/périodes/déclarations) et
    # ``paie_gerer`` (calcul/validation/clôture/paramètres/tout le reste en
    # écriture). Le coffre-fort employé (``CoffreFortBulletinViewSet``,
    # ``IsAnyRole``) reste scopé utilisateur, inchangé — hors périmètre.
    'paie_voir',
    'paie_gerer',
    # ── Données sensibles & gouvernance (Feature D, 2026-06) ──
    # Voir les prix d'achat et la marge interne (générateur, stock). Accordée à
    # Directeur + Administrateur par défaut ; jamais sur un document client.
    'prix_achat_voir',
    # Voir le Journal d'activité (audit). Directeur uniquement par défaut.
    'journal_activite_voir',
    # ── Rémunération RH (Feature G, 2026-06) ──
    # Lire ET écrire la rémunération de base d'un employé (salaire, périodicité,
    # historique). Donnée paie sensible : réservée au palier RH (Directeur +
    # Administrateur par défaut) ; ne fuit jamais dans une sortie client.
    'salaires_voir',
    # ── Données sensibles (FG20) — groupe « Données sensibles » curé ──
    # Permissions de LECTURE qui DÉMASQUENT une donnée sensible dans les
    # sérialiseurs ; absentes → la donnée est masquée. ÉLEVÉES (octroi réservé à
    # l'admin). Repli légacy : un compte SANS rôle fin garde l'accès historique
    # (jamais de régression pour les comptes hérités).
    # `client_pii_voir` : voir les coordonnées personnelles du client/lead
    # (téléphone, email, adresse, WhatsApp, GPS). `marge_voir` : voir la marge
    # interne calculée (indicateur générateur). Distinct de `prix_achat_voir`
    # (prix d'achat brut), qui reste la garde du prix d'achat lui-même.
    'client_pii_voir',
    'marge_voir',
    # XQHS22 — voir les montants du coût de la non-qualité (CoQ) QHSE (NCR/
    # CAPA/incident). Donnée financière interne, jamais client-facing (même
    # règle que `prix_achat`/`marge_voir`). Élevée (cf. ELEVATED_PERMISSIONS).
    'cout_non_qualite_voir',
    # ── ENG — Moteur de Publicités Meta (apps/adsengine) ──
    # Trois permissions DISJOINTES : lecture du moteur (adsengine_view),
    # gestion des campagnes (adsengine_manage), et approbation (propose → approuve).
    # L'approbation est réservée au palier direction/admin + responsable.
    'adsengine_view',
    'adsengine_manage',
    'adsengine_approve',
    # ── ADSENG47 — permissions FINES du moteur autonome (runner P6). Deux
    # pouvoirs DISTINCTS de l'approbation ENG19 : gérer les plans de vol
    # (``adsengine_flightplan_manage``, palier responsable+) et ACTIVER le mode
    # autonome (``adsengine_autonomy_toggle``). L'activation de l'autonomie est
    # admin-SEUL : elle n'est mappée sur AUCUN autre rôle ci-dessous, donc seuls
    # Directeur/Administrateur (qui héritent d'``ALL_PERMISSIONS``) la portent.
    'adsengine_flightplan_manage',
    'adsengine_autonomy_toggle',
    # ── Portée de visibilité des enregistrements (Feature F) ──
    # Marqueurs de RÔLE (pas des cases « action ») : narrowing OPT-IN. Un rôle
    # SANS l'un de ces marqueurs voit tous les enregistrements de sa société
    # (comportement historique préservé — légacy, rôles personnalisés, admins).
    # `records_scope_equipe` : ses propres enregistrements + ceux de ses pairs
    # (même superviseur direct). `records_scope_sous_arbre` : les siens + tout
    # son sous-arbre (toute personne lui remontant, récursivement).
    'records_scope_equipe',
    'records_scope_sous_arbre',
    # ── YRBAC3 — Fine-grainage des apps gatées seulement par
    # ``IsResponsableOrAdmin`` : qhse/gestion_projet/contrats/litiges/kb.
    # Chaque app reçoit deux codes DISJOINTS : ``<app>_voir`` (lecture — GET/
    # HEAD/OPTIONS) et ``<app>_gerer`` (écriture — POST/PUT/PATCH/DELETE +
    # actions custom). Compta a déjà ses propres codes fins (compta_saisir/
    # valider/cloturer, COMPTA40) — pas de doublon ici. Paie a déjà
    # paie_voir/paie_gerer (XPAI7) — pas de doublon ici non plus.
    'qhse_voir',
    'qhse_gerer',
    'projet_voir',
    'projet_gerer',
    'contrat_voir',
    'contrat_gerer',
    'litige_voir',
    'litige_gerer',
    'kb_voir',
    'kb_gerer',
    # ── AOF2 — Appels d'offres (apps/ao) : correction d'une régression de
    # confidentialité EXISTANTE. Les 8 ViewSets AO héritaient d'une base gardée
    # par le grossier ``IsResponsableOrAdmin`` : tout le palier Responsable
    # voyait l'intégralité d'un dossier d'appel d'offres, et il n'existait
    # AUCUNE permission ``ao_*``. Trois codes DISJOINTS :
    #   * ``ao_voir``   — lecture du dossier AO (GET/HEAD/OPTIONS) ;
    #   * ``ao_gerer``  — écriture (POST/PUT/PATCH/DELETE + actions métier) ;
    #   * ``ao_rentabilite_voir`` — voir l'ÉCONOMIE d'un AO (coût de revient,
    #     marge, bénéfice). Donnée financière interne, jamais client-facing —
    #     même palier que ``prix_achat_voir``/``marge_voir``, donc ÉLEVÉE (cf.
    #     ELEVATED_PERMISSIONS) et mappée dans AUCUNE liste de rôle ci-dessous :
    #     seuls Directeur et Administrateur la portent, par héritage
    #     d'ALL_PERMISSIONS.
    # ``ao_voir``/``ao_gerer`` ne sont eux non plus mappés sur aucun rôle
    # Responsable/Commercial/Technicien/Utilisateur : l'accès AO se RESSERRE
    # sur la direction, et reste INCHANGÉ pour Directeur/Administrateur.
    'ao_voir',
    'ao_gerer',
    'ao_rentabilite_voir',
]

# Permissions de portée : un rôle qui en porte une voit un sous-ensemble ; sans
# l'une d'elles, le rôle voit tout (par société). Source unique de vérité.
SCOPE_TEAM = 'records_scope_equipe'
SCOPE_SUBTREE = 'records_scope_sous_arbre'

# Permissions ÉLEVÉES (ERR5) : octroyer l'une d'elles donne le contrôle des
# rôles eux-mêmes (``roles_gerer`` = clé admin/escalade) ou l'accès aux données
# sensibles (prix d'achat/marge, journal d'audit). Un non-administrateur ne peut
# JAMAIS les ajouter à un rôle — sinon un Responsable s'auto-promeut
# Administrateur en cochant ``roles_gerer`` sur son propre rôle. Réservées au
# palier admin (porteur de ``roles_gerer``) côté serializer/vue.
ELEVATED_PERMISSIONS = frozenset({
    'roles_gerer',
    'prix_achat_voir',
    'journal_activite_voir',
    'salaires_voir',
    # FG20 — données sensibles : démasquer la marge interne est élevé (même
    # niveau que le prix d'achat). La PII client n'est PAS élevée : voir les
    # coordonnées d'un client est un besoin opérationnel courant (commercial),
    # donc ``client_pii_voir`` reste octroyable par un Responsable.
    'marge_voir',
    # XQHS22 — coût de la non-qualité : même palier que marge/prix d'achat.
    'cout_non_qualite_voir',
    # AOF2 — économie d'un appel d'offres (coût de revient, marge, bénéfice
    # net visé). Même palier que marge/prix d'achat : un non-administrateur ne
    # peut jamais l'octroyer, et aucun rôle non-direction ne la porte.
    'ao_rentabilite_voir',
})

RESPONSABLE_PERMISSIONS = [
    'stock_voir',
    # QG4 — `stock_creer` retiré : la création de produits est réservée aux
    # rôles Directeur + Commercial responsable (décision Reda).
    'stock_modifier',
    'stock_mouvement',
    'crm_voir',
    'crm_creer',
    'crm_modifier',
    'ventes_voir',
    'ventes_creer',
    'ventes_modifier',
    'ventes_valider',
    'ventes_pdf',
    # La Commerciale gère le flux chantier (création depuis devis, suivi,
    # interventions). L'admin garde le contrôle total (suppression).
    'installation_voir',
    'installation_gerer',
    'intervention_gerer',
    # SAV : la Commerciale consulte le parc d'équipements et ouvre/traite les
    # tickets après-vente. La GESTION du parc (ajout d'équipements) reste admin.
    'equipement_voir',
    'sav_voir',
    'sav_gerer',
    'parametres_voir',
    'users_voir',
    'reporting_voir',
    # COMPTA40 — le Responsable peut saisir ET valider des écritures (mais la
    # séparation des tâches empêche toujours de valider sa PROPRE saisie) ; la
    # clôture reste au palier direction/admin.
    'compta_saisir',
    'compta_valider',
    # XPAI7 — comportement historique préservé : le Responsable avait accès
    # complet à la paie via le grossier IsResponsableOrAdmin.
    'paie_voir',
    'paie_gerer',
    # FG20 — la Commerciale/Responsable voit les coordonnées client (besoin
    # opérationnel) ; comportement historique préservé.
    'client_pii_voir',
    # YRBAC3 — comportement historique préservé : le Responsable avait accès
    # complet (lecture + écriture) à qhse/gestion_projet/contrats/litiges/kb
    # via le grossier IsResponsableOrAdmin.
    'qhse_voir', 'qhse_gerer',
    'projet_voir', 'projet_gerer',
    'contrat_voir', 'contrat_gerer',
    'litige_voir', 'litige_gerer',
    'kb_voir', 'kb_gerer',
    # ENG — accès complet au moteur de publicités (y compris approbation).
    'adsengine_view', 'adsengine_manage', 'adsengine_approve',
]

UTILISATEUR_PERMISSIONS = [
    'stock_voir',
    'crm_voir',
    'ventes_voir',
    'installation_voir',
    'equipement_voir',
    'sav_voir',
    'parametres_voir',
    'reporting_voir',
    # FG20 — préserve l'accès historique aux coordonnées client.
    'client_pii_voir',
    # ENG19 — lecture du moteur publicitaire : `adsengine_view` est distribuée
    # à TOUS les rôles (manage/approve restent réservés aux paliers supérieurs).
    'adsengine_view',
]


# ── Les SEPT rôles (Feature D, 2026-06) ────────────────────────────────────
# Chacun reçoit les défauts ci-dessous ; TOUT reste éditable ensuite dans
# Paramètres (grille module × action). « Admin » = le rôle « Administrateur »
# existant (nom conservé pour la rétro-compatibilité données/tests). Les rôles
# système légacy « Responsable » et « Utilisateur » restent définis plus haut
# pour les comptes/données déjà en place ; ils voient tout (aucun marqueur de
# portée) — comportement historique préservé.

# Directeur : accès total, prix d'achat/marges, et le Journal d'activité.
# Aucun marqueur de portée → voit tous les enregistrements de la société.
DIRECTEUR_PERMISSIONS = [
    p for p in ALL_PERMISSIONS
    if p not in (SCOPE_TEAM, SCOPE_SUBTREE)
]

# Administrateur (= « Admin ») : comme le Directeur, MAIS sans le Journal
# d'activité par défaut (réservé Directeur, octroyable dans Paramètres) et,
# depuis QG4, sans la création de produits (`stock_creer`) — réservée aux
# rôles Directeur + Commercial responsable (décision Reda).
ADMIN_PERMISSIONS = [
    p for p in DIRECTEUR_PERMISSIONS
    if p not in ('journal_activite_voir', 'stock_creer')
]

# Commercial responsable : CRM/Ventes/SAV complets, peut réassigner leads/
# devis/tickets dans l'équipe ; voit son sous-arbre ; pas de prix d'achat.
# QG4 — porte `stock_creer` : la création de produits est réservée aux rôles
# Directeur + Commercial responsable (décision Reda).
COMMERCIAL_RESP_PERMISSIONS = [
    'crm_voir', 'crm_creer', 'crm_modifier', 'crm_supprimer', 'crm_export',
    'crm_reassign',
    'ventes_voir', 'ventes_creer', 'ventes_modifier', 'ventes_supprimer',
    'ventes_valider', 'ventes_pdf', 'ventes_export', 'ventes_reassign',
    'stock_voir', 'stock_creer',  # QG4 — création de produits autorisée.
    'equipement_voir', 'sav_voir', 'sav_gerer', 'sav_export', 'sav_reassign',
    'parametres_voir', 'users_voir', 'reporting_voir', 'reporting_export',
    'client_pii_voir',  # FG20 — coordonnées client (besoin commercial).
    # YRBAC3 — comportement historique préservé (accès complet via l'ancien
    # IsResponsableOrAdmin, non-différencié lecture/écriture).
    'qhse_voir', 'qhse_gerer',
    'projet_voir', 'projet_gerer',
    'contrat_voir', 'contrat_gerer',
    'litige_voir', 'litige_gerer',
    'kb_voir', 'kb_gerer',
    # ENG — gestion des campagnes (l'approbation reste au palier admin).
    'adsengine_view', 'adsengine_manage',
    # ADSENG47 — gestion des plans de vol (palier responsable). L'ACTIVATION de
    # l'autonomie (``adsengine_autonomy_toggle``) reste admin-seul, non ici.
    'adsengine_flightplan_manage',
    SCOPE_SUBTREE,
]

# Commercial : l'accès de la « Commerciale » d'aujourd'hui ; voit son équipe
# (pairs) ; pas de prix d'achat, pas de réassignation.
COMMERCIAL_PERMISSIONS = [
    'crm_voir', 'crm_creer', 'crm_modifier', 'crm_export',
    'ventes_voir', 'ventes_creer', 'ventes_modifier', 'ventes_valider',
    'ventes_pdf', 'ventes_export',
    'stock_voir', 'equipement_voir', 'sav_voir',
    'parametres_voir', 'reporting_voir',
    'client_pii_voir',  # FG20 — coordonnées client (besoin commercial).
    # YRBAC3 — comportement historique préservé (accès complet via l'ancien
    # IsResponsableOrAdmin, non-différencié lecture/écriture).
    'qhse_voir', 'qhse_gerer',
    'projet_voir', 'projet_gerer',
    'contrat_voir', 'contrat_gerer',
    'litige_voir', 'litige_gerer',
    'kb_voir', 'kb_gerer',
    # ENG — gestion des campagnes (l'approbation reste au palier admin).
    'adsengine_view', 'adsengine_manage',
    SCOPE_TEAM,
]

# Technicien responsable : Chantiers/SAV/Stock complets, assigne les
# techniciens ; voit son sous-arbre ; pas de prix d'achat.
TECHNICIEN_RESP_PERMISSIONS = [
    'installation_voir', 'installation_gerer', 'installation_export',
    'intervention_gerer', 'technicien_assign',
    'equipement_voir', 'equipement_gerer', 'sav_voir', 'sav_gerer',
    'sav_export', 'sav_reassign',
    # QG4 — `stock_creer` retiré : la création de produits est réservée aux
    # rôles Directeur + Commercial responsable (décision Reda).
    'stock_voir', 'stock_modifier', 'stock_mouvement',
    'stock_export',
    'parametres_voir', 'users_voir', 'reporting_voir', 'reporting_export',
    'client_pii_voir',  # FG20 — coordonnées client (intervention terrain).
    # YRBAC3 — comportement historique préservé (accès complet via l'ancien
    # IsResponsableOrAdmin, non-différencié lecture/écriture).
    'qhse_voir', 'qhse_gerer',
    'projet_voir', 'projet_gerer',
    'contrat_voir', 'contrat_gerer',
    'litige_voir', 'litige_gerer',
    'kb_voir', 'kb_gerer',
    # ENG — gestion des campagnes (l'approbation reste au palier admin).
    'adsengine_view', 'adsengine_manage',
    # ADSENG47 — gestion des plans de vol (palier responsable). L'ACTIVATION de
    # l'autonomie (``adsengine_autonomy_toggle``) reste admin-seul, non ici.
    'adsengine_flightplan_manage',
    SCOPE_SUBTREE,
]

# Technicien : Chantiers/Installations et SAV pour le travail assigné, Stock en
# vue + mouvements ; pas d'édition Ventes ; voit son équipe (pairs).
TECHNICIEN_PERMISSIONS = [
    'installation_voir', 'installation_gerer', 'intervention_gerer',
    'equipement_voir', 'sav_voir', 'sav_gerer',
    'stock_voir', 'stock_mouvement',
    'parametres_voir', 'reporting_voir',
    'client_pii_voir',  # FG20 — coordonnées client (intervention terrain).
    # YRBAC3 — comportement historique préservé (accès complet via l'ancien
    # IsResponsableOrAdmin, non-différencié lecture/écriture).
    'qhse_voir', 'qhse_gerer',
    'projet_voir', 'projet_gerer',
    'contrat_voir', 'contrat_gerer',
    'litige_voir', 'litige_gerer',
    'kb_voir', 'kb_gerer',
    # ENG — gestion des campagnes (l'approbation reste au palier admin).
    'adsengine_view', 'adsengine_manage',
    SCOPE_TEAM,
]

# Viewer : lecture seule partout dans sa portée ; aucune création/édition/
# suppression/export ; pas de prix d'achat. Portée = sa position dans l'arbre.
VIEWER_PERMISSIONS = [
    'stock_voir', 'crm_voir', 'ventes_voir', 'installation_voir',
    'equipement_voir', 'sav_voir', 'parametres_voir', 'reporting_voir',
    'client_pii_voir',  # FG20 — préserve l'accès historique aux coordonnées.
    # YRBAC3 — nouvel accès en LECTURE SEULE (le Viewer n'avait aucun accès à
    # ces apps avant : IsResponsableOrAdmin bloquait tout porteur lecture
    # seule). Additif — jamais de _gerer pour ce rôle.
    'qhse_voir',
    'projet_voir',
    'contrat_voir',
    'litige_voir',
    'kb_voir',
    # ENG — accès en lecture seule (pas de gestion ni approbation).
    'adsengine_view',
    SCOPE_TEAM,
]

# ── NTPRT1 — Rôles système du Portail EXTERNE (self-service) ────────────────
# AXE DE PERMISSION SÉPARÉ du catalogue interne ``ALL_PERMISSIONS`` : ces codes
# ``portail_*_acces`` n'apparaissent JAMAIS dans la grille de rôles interne
# (Paramètres, module × action) ni dans la matrice RBAC interne
# (``core.rbac_matrix``). Ils bornent l'accès aux endpoints self-service
# ``/api/django/portail/*`` et RIEN d'autre. Un compte portail ne porte AUCUNE
# permission interne, donc n'a par construction accès à aucun endpoint interne
# (critère d'acceptation NTPRT1). Le préfixe ``portail_`` est exclu de
# ``CustomUser._role_grants_write`` : un compte portail n'est JAMAIS
# « responsable » interne. La classe de permission d'enforcement (accès borné à
# SON id) est posée par NTPRT5 ; ici on ne pose que la donnée (rôles + champs).
PORTAIL_CLIENT_PERMISSIONS = ['portail_client_acces']
PORTAIL_FOURNISSEUR_PERMISSIONS = ['portail_fournisseur_acces']
PORTAIL_PARTENAIRE_PERMISSIONS = ['portail_partenaire_acces']

# Les 3 rôles système du portail (nom → permissions). Créés/synchronisés par le
# seeder ``init_roles`` (idempotent, additif) exactement comme les rôles
# internes ci-dessus, avec ``est_systeme=True``.
# NTPRT2 — noms CANONIQUES des 3 rôles système portail, extraits en constantes
# pour que le provisionnement d'un compte portail (services de ``portail``/
# ``stock``/``compta``) rattache le compte au MÊME rôle que celui semé par
# ``init_roles`` — jamais une chaîne magique dupliquée qui divergerait.
ROLE_PORTAIL_CLIENT = 'Portail client'
ROLE_PORTAIL_FOURNISSEUR = 'Portail fournisseur'
ROLE_PORTAIL_PARTENAIRE = 'Portail partenaire'

CANONICAL_PORTAIL_ROLES = [
    (ROLE_PORTAIL_CLIENT, PORTAIL_CLIENT_PERMISSIONS),
    (ROLE_PORTAIL_FOURNISSEUR, PORTAIL_FOURNISSEUR_PERMISSIONS),
    (ROLE_PORTAIL_PARTENAIRE, PORTAIL_PARTENAIRE_PERMISSIONS),
]


# Registre canonique : (nom, permissions). Les trois premiers conservent les
# noms système historiques. Ordre = ordre d'affichage souhaité. Le seeder crée/
# met à jour ces rôles système pour chaque société (idempotent, additif).
CANONICAL_SYSTEM_ROLES = [
    ('Directeur', DIRECTEUR_PERMISSIONS),
    ('Administrateur', ADMIN_PERMISSIONS),
    ('Commercial responsable', COMMERCIAL_RESP_PERMISSIONS),
    ('Commercial', COMMERCIAL_PERMISSIONS),
    ('Technicien responsable', TECHNICIEN_RESP_PERMISSIONS),
    ('Technicien', TECHNICIEN_PERMISSIONS),
    ('Viewer', VIEWER_PERMISSIONS),
    # Rôles légacy conservés pour les comptes/données déjà en place.
    ('Responsable', RESPONSABLE_PERMISSIONS),
    ('Utilisateur', UTILISATEUR_PERMISSIONS),
    # NTPRT1 — rôles système du Portail externe (client/fournisseur/partenaire).
    # Un même axe que les rôles internes pour le SEEDING (est_systeme=True,
    # idempotent), mais des permissions portail-seules (jamais internes).
    *CANONICAL_PORTAIL_ROLES,
]


class Role(models.Model):
    company = models.ForeignKey(
        'authentication.Company',  # app_label.ModelName
        # on_delete: un rôle n'existe que dans SA société — supprimer la
        # société supprime ses rôles (aucun rôle orphelin ne doit survivre,
        # sans quoi il resterait porteur de permissions sans locataire).
        on_delete=models.CASCADE,
        related_name='roles',
    )
    nom = models.CharField(max_length=100)
    permissions = models.JSONField(default=list)
    est_systeme = models.BooleanField(default=False)
    # ── NTADM3 — Périmètre de DONNÉES par entité ────────────────────────────
    # Narrowing OPT-IN, exactement le patron déjà utilisé pour
    # ``records_scope_*`` (portée par propriétaire) et ``app_<clé>_voir``
    # (visibilité d'app) : VIDE = aucune restriction, le rôle voit toutes les
    # entités — c'est l'état de TOUS les rôles existants, donc zéro
    # régression. Dès qu'au moins une entité est cochée, la liste devient une
    # LISTE BLANCHE (cf. ``core.entite_scoping``) : les lignes « non
    # affectées » (``entite IS NULL``) restent visibles de tous, celles d'une
    # entité hors périmètre disparaissent et ne peuvent plus être créées.
    # FK-STRING cross-app : jamais d'import de ``apps.entites.models`` ici.
    entites_visibles = models.ManyToManyField(
        'entites.Entite',
        blank=True,
        related_name='roles_visibles',
        verbose_name='Entités visibles',
        help_text="Vide = toutes les entités sont visibles (défaut).",
    )

    class Meta:
        unique_together = [('company', 'nom')]
        verbose_name = 'Rôle'
        verbose_name_plural = 'Rôles'
        ordering = ['company', 'nom']

    def __str__(self):
        return f'{self.company.nom} — {self.nom}'
