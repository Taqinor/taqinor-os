"""Sélecteurs LECTURE SEULE de la relance et de l'engagement (« Action requise »
/ Relances du jour, déclencheurs CAD-K, engagement de la proposition) — sortis
de ``apps/ventes/selectors.py`` par SPL145 (déplacement pur, corps inchangés ;
propriétaire : lead).

Les autres apps continuent de lire ces fonctions par la FAÇADE
``apps.ventes.selectors`` (ré-export en fin de fichier) ; ce module est PLAT :
aucun import de ``.selectors`` en tête (cycle) — ``devis_a_facturer`` vient du
module FRÈRE ``.selectors_facturation``.
"""

import functools
import json
from pathlib import Path

from .selectors_facturation import devis_a_facturer


# ── QX29/QX30/PACT17 — « Relances du jour » : file d'action des devis ────────

#: APRF9 — le contrat partagé de « Relances du jour » (APRF1) : il DÉCLARE
#: ``details_par_panier``, lu ici — jamais un littéral recopié.
CONTRAT_ACTION_REQUISE = (Path(__file__).resolve().parent
                          / 'contract_samples' / 'devis_action_requise.json')


@functools.lru_cache(maxsize=1)
def details_par_panier():
    """APRF9 (contrat APRF1) — nombre de premiers ids (ordre ``id``
    croissant) de chaque panier dont ``devis`` porte la ligne d'affichage."""
    contrat = json.loads(CONTRAT_ACTION_REQUISE.read_text(encoding='utf-8'))
    return int(contrat['details_par_panier'])


#: ADEV64 — champs propriétaires qui ouvrent un devis à la portée d'un
#: utilisateur dans « Relances du jour » : son AUTEUR, ou le RESPONSABLE du
#: lead d'origine (string-FK ``crm.Lead.owner``, jamais un import crm).
_CHAMPS_PORTEE = ('created_by', 'lead__owner')


def devis_action_requise(company, *, user=None, today=None,
                         jours_sans_reponse=3, jours_avant_expiration=7,
                         jours_non_facture=7):
    """PACT17 — Regroupe les devis d'une société par ACTION ATTENDUE, miroir
    exact de ``apps.sav.selectors.file_action`` (ZSAV6, parité Odoo « Activity
    view »). C'est l'agrégat que ``DevisActionBoardPage`` consomme : il
    n'avait jamais été construit côté serveur, donc l'écran — pourtant publié
    au menu des rôles responsable/admin — était mort.

    Chaque devis tombe dans EXACTEMENT UN panier (le premier qui matche, dans
    l'ordre ci-dessous), pour qu'un même devis ne soit jamais compté deux
    fois :

      * ``acceptes_non_factures`` — accepté depuis plus de
        ``jours_non_facture`` jours sans aucune ``Facture`` liée (réutilise
        ``devis_a_facturer``, ZFAC12 — aucune logique dupliquée) ;
      * ``refuses_sans_motif``    — refusé sans ``motif_refus`` (QX26 : un
        refus sans motif est une information perdue pour toujours) ;
      * ``expirant_bientot``      — envoyé, ``date_validite`` dans les
        ``jours_avant_expiration`` jours (échéance non encore dépassée).
        CAD138 : ce panier passe DEVANT l'engagement — une date de validité
        qui tombe est une urgence datée ;
      * ``engagement_relance``    — envoyé et le moteur d'engagement (QX30be,
        ``ShareLink.engagement_triggers_fired``) a tiré au moins un
        déclencheur ENCORE actif (non ouvert 24 h / ouvert non signé 48 h /
        rouvert 3×). CAD138 : un déclencheur de plus de
        ``DECLENCHEUR_PEREMPTION_JOURS`` jours sort du panier ;
      * ``envoyes_sans_reponse``  — envoyé depuis plus de
        ``jours_sans_reponse`` jours sans aucun des signaux ci-dessus (palier
        de cadence).

    Les devis ``brouillon`` et ``expire`` ne sont JAMAIS dans un panier : le
    premier n'est pas encore parti, le second n'appelle plus de relance.

    Renvoie ``{'buckets': {clé: {'count': int, 'ids': [int, …]}, …},
    'wa_drafts': {devis_id: 'message'}, 'devis': {devis_id: {…}}}``.

      * ``wa_drafts`` ne porte QUE la file ``engagement_relance`` (le seul cas
        où le serveur sait quoi dire) ; l'écran retombe sur le lien wa.me nu
        partout ailleurs.
      * ``devis`` porte de quoi RENDRE chaque ligne (référence, client,
        téléphone, WhatsApp, total, CAD115 : ``prochaine_touche_crm``) pour
        les ``details_par_panier()`` premiers ids de chaque panier (APRF9,
        contrat APRF1 : ``count``/``ids`` restent complets). Sans lui l'écran devait re-télécharger la liste des
        devis et n'y trouvait ni ``client_telephone`` ni ``client_whatsapp``
        (``DevisSerializer`` ne les publie pas) : les raccourcis « Appeler » /
        WhatsApp ne s'affichaient JAMAIS, et une référence au-delà de la
        première page de 50 tombait sur « #42 ». Le serveur sert donc ce dont
        l'écran a besoin, en un seul appel.

    Lecture seule, bornée à ``company`` — jamais de fuite cross-société.
    Aucun prix d'achat ni marge n'est exposé (règle #4) : seul le total TTC,
    déjà visible du client, accompagne la ligne.

    ADEV64 (C-ADEV-025) — ``user`` fourni (la vue passe ``request.user``) :
    chaque panier est borné à SA portée (``core.scoping.scope_queryset`` sur
    ``_CHAMPS_PORTEE`` — auteur du devis OU responsable du lead) ; un
    Commercial de portée ``team`` ne voit ni les devis ni les téléphones des
    clients hors de sa portée. ``user=None`` (appel interne) : société
    entière, comme avant.
    """
    from datetime import timedelta

    from django.utils import timezone

    from .models import Devis
    # ADEV45 — import local (cycle évité, cf. en-tête) : une V1 remplacée par
    # sa révision n'entre dans AUCUN panier.
    from .selectors import devis_en_jeu

    today = today or timezone.localdate()
    now = timezone.now()

    envoyes_sans_reponse = []
    acceptes_non_factures = []
    refuses_sans_motif = []
    expirant_bientot = []
    engagement_relance = []
    wa_drafts = {}

    # ADEV64 — la portée de l'utilisateur borne TOUS les paniers (et donc
    # les lignes, téléphones et brouillons, tous dérivés des ids cités).
    devis_societe = Devis.objects.filter(company=company)
    if user is not None:
        from core.scoping import scope_queryset
        devis_societe = scope_queryset(devis_societe, user, _CHAMPS_PORTEE)

    # ── Acceptés non facturés : ZFAC12 tel quel (jamais recodé ici), relu
    # dans la portée (ordre ``id`` croissant, celui du contrat APRF1) ──
    acceptes_non_factures.extend(
        devis_societe
        .filter(pk__in=[d.id for d in devis_a_facturer(
            company, jours=jours_non_facture, today=today)])
        .order_by('id')
        .values_list('id', flat=True)
    )

    # ── Refusés sans motif (QX26) ──
    refuses_sans_motif.extend(
        devis_en_jeu(devis_societe.filter(statut=Devis.Statut.REFUSE))
        .exclude(motif_refus__gt='')
        .order_by('id')
        .values_list('id', flat=True)
    )

    # ── Devis ENVOYÉS : un seul panier par devis, priorité au signal le plus
    # fort (engagement mesuré > échéance qui approche > simple cadence).
    envoyes = (devis_en_jeu(devis_societe.filter(statut=Devis.Statut.ENVOYE))
               .select_related('client')
               .prefetch_related('share_links')
               .order_by('id'))
    limite_expiration = today + timedelta(days=jours_avant_expiration)

    for devis in envoyes:
        # CAD138 — L'EXPIRATION PASSE DEVANT L'ENGAGEMENT. Une date de
        # validité qui tombe dans trois jours est une urgence DATÉE ; un
        # drapeau de comportement ne l'est plus après trois semaines. L'ordre
        # inverse cachait le premier derrière le second.
        if (devis.date_validite is not None
                and today <= devis.date_validite <= limite_expiration):
            expirant_bientot.append(devis.id)
            continue
        # CAD138 — et les déclencheurs se PÉRIMENT : inscrits une fois pour
        # toutes, sans aucun code de remise à zéro, ils ne sortaient jamais du
        # panier.
        declencheurs = set()
        for link in devis.share_links.all():
            declencheurs |= declencheurs_actifs(link, devis=devis, now=now)
        if declencheurs:
            engagement_relance.append(devis.id)
            wa_drafts[devis.id] = _brouillon_relance_engagement(
                devis, declencheurs)
            continue
        envoye_le = devis.date_envoi
        if (envoye_le is not None
                and (now - envoye_le) >= timedelta(days=jours_sans_reponse)):
            envoyes_sans_reponse.append(devis.id)

    paniers = {
        'envoyes_sans_reponse': envoyes_sans_reponse,
        'acceptes_non_factures': acceptes_non_factures,
        'refuses_sans_motif': refuses_sans_motif,
        'expirant_bientot': expirant_bientot,
        'engagement_relance': engagement_relance,
    }
    # APRF9 (C-APRF-004/005) — lignes construites pour les SEULS
    # ``details_par_panier()`` premiers ids (déjà en ordre ``id`` croissant)
    # de chaque panier, totaux préchargés par ``devis_avec_totaux`` (APRF7) :
    # requêtes et octets de détail ne croissent plus avec les paniers.
    from .selectors import devis_avec_totaux
    n = details_par_panier()
    details = {i for ids in paniers.values() for i in ids[:n]}
    lignes = list(devis_avec_totaux(
        Devis.objects
        .filter(company=company, pk__in=details)
        .select_related('client', 'lead')))

    # CAD115 — SIG9 : « Action requise » (vue Ventes) et la file calendaire du
    # CRM pouvaient réclamer le même devis le même jour avec deux messages
    # différents, sans aucun arbitrage entre elles. Chaque ligne affiche donc
    # ici la prochaine touche CRM déjà programmée (``crm.RelanceEtape`` À
    # FAIRE) — lue via le selector CRM sanctionné (jamais un import de
    # ``apps.crm.models``), une seule requête pour tous les leads cités
    # (même patron que ``prochaine_touche_par_lead`` côté MRY5).
    from apps.crm.selectors import prochaine_touche_par_lead
    lead_ids = {d.lead_id for d in lignes if d.lead_id}
    touches = prochaine_touche_par_lead(company, lead_ids)

    return {
        'buckets': {
            cle: {'count': len(ids), 'ids': list(ids)}
            for cle, ids in paniers.items()
        },
        'wa_drafts': wa_drafts,
        'devis': {d.id: _ligne_action_requise(d, touches) for d in lignes},
    }


def _ligne_action_requise(devis, touches=None):
    """PACT17 — de quoi RENDRE une ligne de « Relances du jour », rien de plus.

    Le WhatsApp vient du lead lié quand il existe (``crm.Lead.whatsapp``, lu
    par la relation string-FK déjà déclarée — jamais un import de
    ``apps.crm.models``, même motif que ``DevisSerializer.get_lead_nom``),
    sinon le téléphone du client fait office de numéro joignable. Le total est
    rendu en TEXTE décimal (jamais un flottant) — ``formatMAD`` le lit tel
    quel côté écran.

    CAD115 — ``touches`` est le dict ``{lead_id: (due_at, due_date, cadence,
    canal)}`` de ``apps.crm.selectors.prochaine_touche_par_lead`` : la ligne
    publie ``prochaine_touche_crm`` (``None`` quand le devis n'a pas de lead
    ou que le lead n'a aucune touche À FAIRE — jamais une valeur inventée).
    """
    client = getattr(devis, 'client', None)
    telephone = (getattr(client, 'telephone', '') or '') if client else ''
    whatsapp = ''
    if devis.lead_id:
        whatsapp = getattr(devis.lead, 'whatsapp', '') or ''
    total = devis.total_ttc
    touche = (touches or {}).get(devis.lead_id) if devis.lead_id else None
    prochaine_touche_crm = None
    if touche:
        due_at, due_date, cadence, canal = touche
        prochaine_touche_crm = {
            'due_at': due_at.isoformat() if due_at else None,
            'due_date': due_date.isoformat() if due_date else None,
            'cadence': cadence or '',
            'canal': canal or '',
        }
    return {
        'id': devis.id,
        'reference': devis.reference or '',
        'client_nom': (getattr(client, 'nom', '') or '') if client else '',
        'client_telephone': telephone,
        'client_whatsapp': whatsapp,
        'total_ttc': str(total) if total is not None else None,
        'prochaine_touche_crm': prochaine_touche_crm,
    }


def _brouillon_relance_engagement(devis, declencheurs):
    """PACT17/QX30 — message WhatsApp pré-rempli pour la file d'engagement.

    Le texte suit le déclencheur le plus parlant (jamais un message générique
    quand le serveur sait quoi dire) et ne cite AUCUN prix : un brouillon part
    tel quel dans WhatsApp, il doit rester une relance, pas une offre.
    """
    client = getattr(devis, 'client', None)
    # Prénom + nom, comme partout ailleurs dans ce fichier : « Bonjour Benali »
    # (le patronyme seul) ne se dit pas en français — on salue quelqu'un par
    # son prénom, ou par son nom complet. Un brouillon part TEL QUEL dans
    # WhatsApp : la salutation est la première chose que le client lit.
    prenom = (getattr(client, 'prenom', '') or '').strip() if client else ''
    patronyme = (getattr(client, 'nom', '') or '').strip() if client else ''
    nom = f'{prenom} {patronyme}'.strip()
    salutation = f'Bonjour {nom}' if nom else 'Bonjour'
    reference = getattr(devis, 'reference', '') or ''
    suffixe = f' (réf. {reference})' if reference else ''

    if 'reopened_3x' in declencheurs:
        corps = ('vous avez consulté votre proposition plusieurs fois'
                 f'{suffixe} — puis-je répondre à une question ?')
    elif 'opened_not_signed_48h' in declencheurs:
        corps = (f'avez-vous pu parcourir votre proposition{suffixe} ? '
                 'Je reste disponible pour en discuter.')
    else:
        corps = (f'votre proposition{suffixe} vous attend toujours — '
                 'souhaitez-vous que je vous la présente ?')
    return f'{salutation}, {corps}'


# ── CAD-K ── CAD138 — le panier « relance d'engagement » se vide enfin ──────
#
# Audit L3 du 21/09/2026. Un déclencheur allumé était inscrit UNE FOIS POUR
# TOUTES : deux sites d'écriture, tous deux additifs, aucun code de remise à
# zéro — et le panier engagement passait AVANT le test d'expiration. Un devis
# dont la validité tombait dans trois jours restait donc caché derrière un
# drapeau « non ouvert » vieux de trois semaines. (Les déclencheurs
# s'éteignaient de toute façon à l'expiration du LIEN, ce qui n'est pas la
# même chose qu'un traitement.)
#
# DEUX CORRECTIONS, ET RIEN D'AUTRE : les déclencheurs se PÉRIMENT, et
# l'expiration passe DEVANT l'engagement dans l'ordre des paniers — une date
# de validité qui tombe est une urgence datée, un drapeau de comportement ne
# l'est plus après trois semaines.

#: Durée au-delà de laquelle un déclencheur d'engagement sort du panier.
#: Elle vient du texte de la tâche CAD138 — « un drapeau de comportement ne
#: l'est plus après TROIS SEMAINES » — et non d'un réglage : la péremption
#: est automatique, préférée à un geste manuel de plus pour une équipe de
#: deux personnes.
DECLENCHEUR_PEREMPTION_JOURS = 21


def dates_declencheurs(link):
    """``{clé: date ISO ou None}`` des déclencheurs allumés sur un lien.

    Accepte les DEUX formes : la LISTE historique (aucune date connue → la
    valeur est ``None``) et le DICT daté écrit depuis CAD138. Aucune migration
    n'est nécessaire — le champ est un ``JSONField``.
    """
    brut = getattr(link, 'engagement_triggers_fired', None) or []
    if isinstance(brut, dict):
        return {str(cle): valeur for cle, valeur in brut.items()}
    return {str(cle): None for cle in brut}


def marquer_declencheur(link, cle, *, quand=None):
    """Allume un déclencheur DATÉ sans perdre les dates déjà connues.

    Écrit la forme DICT sur le lien (sans le sauvegarder — l'appelant décide
    quand) et la renvoie. Un déclencheur déjà allumé est RAFRAÎCHI : il vient
    de se reproduire, la péremption repart de là."""
    from django.utils import timezone

    dates = dates_declencheurs(link)
    dates[str(cle)] = (quand or timezone.now()).isoformat()
    link.engagement_triggers_fired = dict(sorted(dates.items()))
    return link.engagement_triggers_fired


def _date_declencheur_heritee(link, devis=None):
    """Date de repli d'un déclencheur SANS date (forme liste d'avant CAD138).

    La meilleure preuve disponible de QUAND le comportement a eu lieu : la
    dernière consultation du lien, sinon l'envoi du devis, sinon la création
    du lien. Rien n'est inventé — on lit ce qui existe déjà."""
    for valeur in (getattr(link, 'last_viewed_at', None),
                   getattr(devis, 'date_envoi', None),
                   getattr(link, 'created_at', None)):
        if valeur is not None:
            return valeur
    return None


def declencheurs_actifs(link, *, devis=None, now=None):
    """Les déclencheurs d'engagement ENCORE actionnables sur ce lien.

    Un déclencheur de plus de ``DECLENCHEUR_PEREMPTION_JOURS`` jours sort du
    panier : il ne dit plus rien d'utile au commercial, et il masquait des
    devis dont la validité tombe. Un déclencheur sans date connue est daté par
    ``_date_declencheur_heritee`` ; sans aucune date exploitable, il est
    GARDÉ — on ne jette pas un signal faute de savoir le dater.
    """
    import datetime as _dt

    from django.utils import timezone

    now = now or timezone.now()
    limite = _dt.timedelta(days=DECLENCHEUR_PEREMPTION_JOURS)
    actifs = set()
    for cle, iso in dates_declencheurs(link).items():
        quand = None
        if iso:
            try:
                quand = _dt.datetime.fromisoformat(str(iso))
            except (TypeError, ValueError):
                quand = None
        if quand is None:
            quand = _date_declencheur_heritee(link, devis)
        if quand is None or (now - quand) < limite:
            actifs.add(cle)
    return actifs


# ── CAD-K ── CAD133 — engagement du client sur SA proposition ───────────────
def engagement_proposition_du_lead(lead_id, company):
    """CAD133 — ce que le client a FAIT de sa proposition (lecture seule).

    Point d'entrée cross-app UNIQUE pour que le score du CRM compte un
    COMPORTEMENT sans importer ``apps.ventes.models``. Multi-tenant : borné à
    la société fournie. Aucun montant, aucun prix d'achat, aucune marge — ce
    sont des faits de lecture, jamais du chiffrage.

    Renvoie ``{ouverte, vues, lue_en_detail, derniere_vue}`` :
      * ``ouverte``       — la proposition a été ouverte au moins une fois ;
      * ``vues``          — total des consultations (``ShareLink.view_count``) ;
      * ``lue_en_detail`` — un ``deep_engagement_logged_at`` existe ;
      * ``derniere_vue``  — le plus récent instant connu, ou ``None``.
    """
    from django.db.models import Max, Sum

    from .models import ShareLink

    vide = {'ouverte': False, 'vues': 0, 'lue_en_detail': False,
            'derniere_vue': None}
    if not lead_id or company is None:
        return vide
    agregat = (ShareLink.objects
               .filter(devis__lead_id=lead_id, devis__company=company)
               .aggregate(vues=Sum('view_count'),
                          premiere=Max('first_viewed_at'),
                          profond=Max('deep_engagement_logged_at')))
    vues = int(agregat.get('vues') or 0)
    premiere = agregat.get('premiere')
    profond = agregat.get('profond')
    instants = [i for i in (premiere, profond) if i is not None]
    return {
        'ouverte': premiere is not None or vues > 0,
        'vues': vues,
        'lue_en_detail': profond is not None,
        'derniere_vue': max(instants) if instants else None,
    }


def annotations_engagement_proposition():
    """CAD133 — les MÊMES faits, posés en ANNOTATIONS sur un queryset de leads.

    ``engagement_proposition_du_lead`` coûte une agrégation ``ShareLink`` PAR
    LEAD : sur la liste du CRM (qui calcule le score de chaque ligne) cela
    faisait repartir la base une fois par ligne — un N+1 franc. Les mêmes
    trois faits sont ici des sous-requêtes corrélées : la liste les obtient
    dans la requête qui charge déjà les leads, sans une requête de plus.

    À greffer par ``qs.annotate(**annotations_engagement_proposition())`` sur
    un queryset de ``crm.Lead``. Les trois attributs posés
    (``sig_vues_proposition``, ``sig_premiere_vue_proposition``,
    ``sig_lecture_profonde_at``) sont relus par ``apps.crm.signaux`` — la
    frontière M3 tient : ``apps.crm`` n'importe toujours pas
    ``apps.ventes.models``, il appelle ce sélecteur.
    """
    from django.db.models import (
        DateTimeField, IntegerField, Max, OuterRef, Subquery, Sum,
    )

    from .models import ShareLink

    base = (ShareLink.objects
            .filter(devis__lead=OuterRef('pk'),
                    devis__company=OuterRef('company'))
            .order_by()
            .values('devis__lead'))
    return {
        'sig_vues_proposition': Subquery(
            base.annotate(valeur=Sum('view_count')).values('valeur')[:1],
            output_field=IntegerField()),
        'sig_premiere_vue_proposition': Subquery(
            base.annotate(valeur=Max('first_viewed_at')).values('valeur')[:1],
            output_field=DateTimeField()),
        'sig_lecture_profonde_at': Subquery(
            base.annotate(
                valeur=Max('deep_engagement_logged_at')).values('valeur')[:1],
            output_field=DateTimeField()),
    }
