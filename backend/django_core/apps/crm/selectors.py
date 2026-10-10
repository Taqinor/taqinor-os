"""Sélecteurs LECTURE SEULE du domaine CRM exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les clients à travers ces
fonctions plutôt qu'en important `apps.crm.models` directement (voir CLAUDE.md,
règle de modularité). Comportement strictement identique aux requêtes inline
d'origine.
"""
import datetime  # noqa: F401 — façade : `datetime` reste exposé (golden SPL70)
from .portee_selectors import (  # noqa: F401
    MOTIF_CONTACT_REFUSE, peut_contacter, portee_leads, leads_visibles,
    leads_en_portee, lead_signe_q, est_lead_signe, cles_numeros_lead,
    lead_ids_du_responsable, lead_ids_anonymises, client_ids_anonymises,
)
from .cadence_selectors import (  # noqa: F401
    JOURS_OUVRES_JOINDRE, _minutes_ouvrees_de_5_jours, kpi_cadences,
    _STATUTS_CLOS_HUMAIN, LEADS_SANS_TOUCHE_MAX, _lundi, _pct, _mediane_decimale,
    _a_lheure, _a_lheure_ou_excusee, kpi_adherence, _conversion_par_stage,
    mes_stats_relance, CHAINE_COMMERCIALE_LIMITE, _chaine_bloc, _chaine_identite,
    _chaine_devis_partis, chaine_commerciale, _assigne_de_la_visite, SERIE_JOURS_MAX,
    _serie_jours_sans_retard, _mediane, relances_du_jour, relance_etapes_dues,
    file_du_cockpit, STATUT_EN_RETARD, STATUTS_SUIVI, SUIVI_JOURS_MAX,
    relance_etapes_periode, JOURNAL_TYPES, _JOURNAL_FENETRE, _JOURNAL_PREFIXES,
    _journal_cause_apres_deux_points, journal_relance, _journal_phrase,
    prochaine_touche_par_lead, devis_a_cadence_active, leads_chauds_non_contactes,
    devis_expirant_bientot, leads_rappel_demande, ma_file_commercial_items,
    CADENCES_CLOTURABLES, cadences_echues_a_clore, mesure_cadence, PRIORITE_RANG_FILE,
    PRIORITE_RANG_DEFAUT, trier_file_du_jour,
)
from .leads_selectors import (  # noqa: F401
    normalize_phone_key, normalize_email_key, normalize_name_key,
    find_lead_id_by_phone, leads_sla_depasse, CANAL_RAPPEL_SLA,
    leads_callback_sla_depasse, leads_meta_sla_depasse, leads_response_time_rows,
    HEURE_RAPPEL_DU_MATIN, _limite_rappel_du_matin, kpi_premier_contact,
    _objectif_premier_contact, lead_merge_fields, lead_contact_identifiers,
    existing_lead_emails, _PROGRESSIVE_PROFILING_STANDARD_FIELDS,
    lead_known_field_codes, lead_ids_by_contact, lead_ids_par_identifiant,
    doublons_foyer_probables,
)
from .clients_selectors import (  # noqa: F401
    client_base_qs, find_client_by_email, clients_pour_controle_ice,
    find_client_by_ice_or_libelle, find_client_by_phone, client_credit_warning,
    credit_hold_check, get_company_client, client_label, get_latest_lead_for_client,
    compute_attainment, _lignes_pipeline_ouvertes, _valeur_ponderee_leads,
    _activites_en_retard, _devis_compte_comme_signe, _ca_signe_mois, ca_signe_periode,
    nb_devis_envoyes_periode, stats_equipe, delai_paiement_client,
    clients_contact_identifiers, _tous_descendants, consolidation_client,
    forecast_rollup, revenu_pipeline_pondere_par_mois, resume_portail_partenaire,
    soumissions_partenaire_portail, partenaire_peut_soumettre,
    releve_commissions_partenaire, pipeline_pondere_par_entite,
    partenaire_pour_certification, partenaires_certifies_qs,
    specialites_partenaire_cles, certifications_expirantes, _as_date,
    portefeuille_commercial, comptes_dormants, salle_vente_analytics,
    salle_vente_summary_for_lead, _metric_count_for_owner, classement_defi,
    metrique_pipeline_pondere, register_metric_adapters, client_ids_par_identifiant,
)
from .devis_selectors import (  # noqa: F401
    lead_du_devis, ville_effective, _srm_deduite, lead_bills_for_devis,
    SITE_PROFILE_FIELDS, ALIAS_DEPRECIE_CV_ACTUELLE, site_profile_for_client,
    ENTREES_POMPAGE_CIBLES, _ENTREES_POMPAGE_SOURCES, _ENTREES_POMPAGE_INFORMATION,
    _LIBELLE_HEURES_ACTUELLES, FORMULE_VOLUME_DECLARE, _entree_valeur, _entree_vide,
    entrees_pompage_du_lead, entrees_pompage_pour_lead_id, _CI_DETAIL_SOURCE,
    _CI_COLONNE_SOURCE, _CI_INFORMATIONS, _CI_PHASES, _CI_REGISTRES_MT, _ci_nombre,
    entrees_ci_du_lead, entrees_ci_pour_lead_id, releve_declare_ci,
    site_location_for_devis, PROFILS_ACTIVITE, profil_activite_pour_devis,
    occupation_jour_pour_devis, equipements_pour_lead, equipements_pour_devis,
    lead_devis_ids_by_id, _kwh_positif, SEGMENTS_REPLI_KWH_SITE,
    conso_mensuelle_kwh_pour_devis,
)
from .roof_selectors import (  # noqa: F401
    conception_3d_du_lead, REPERE_SOURCE_ROOF_POINT, REPERE_SOURCE_GPS,
    _REPERE_TOLERANCE_DEG, _repere_nombre, _repere_pin, _repere_anneau,
    _repere_dans_anneau, repere_toit,
)
from .stock_selectors import (  # noqa: F401
    leads_utilisant_produit,
)


def signed_lead_phone_keys(company):
    """ADSDEEP25 — ``set`` des clés téléphone NORMALISÉES (QW10) des leads au
    stade SIGNÉ de la société.

    Point d'entrée cross-app SANCTIONNÉ pour ``apps.adsengine`` (métrique
    conversations-par-ad CTWA : rapproche une conversation WhatsApp entrante
    d'une signature par téléphone) — jamais un import de ``apps.crm.models``
    côté adsengine, et le stade SIGNÉ vient de ``STAGES.py`` (jamais codé en
    dur, règle #2). Lecture seule, scopée société ; ignore les numéros vides.
    Renvoie un ``set`` de clés non vides."""
    from .models import Lead

    keys = set()
    # ACRM33 — telephone ET whatsapp (helper partagé avec
    # ``find_lead_id_by_phone``).
    for lead in (Lead.objects
                 .filter(lead_signe_q(), company=company)
                 .only('id', 'telephone', 'whatsapp')):
        keys |= cles_numeros_lead(lead)
    return keys


def signed_leads_for_campaigns(company, utm_campaigns):
    """ENG10 — Leads SIGNÉS attribués par ``utm_campaign``, avec traçabilité.

    Point d'entrée cross-app SANCTIONNÉ pour ``apps.adsengine`` (métrique
    coût-par-signature) : lit le CRM UNIQUEMENT via ce sélecteur, jamais un
    import de ``apps.crm.models`` ni du stade « SIGNED » en dur — la clé de stade
    vient de la source de vérité ``STAGES.py`` (via ``apps.crm.stages``).

    Pour chaque valeur d'``utm_campaign`` demandée, renvoie le nombre de leads au
    stade SIGNÉ et la LISTE de leurs ids (chaque chiffre est donc cliquable
    jusqu'au lead réel — traçabilité Northbeam). Lecture seule, scopée société ;
    ne compte jamais un lead supprimé (``Lead.objects`` = vivants). Renvoie ::

        {utm_campaign: {'signed_count': int, 'signed_lead_ids': [int, ...]}}
    """
    from .models import Lead

    result = {}
    for key in utm_campaigns:
        if key in result:
            continue
        ids = list(
            Lead.objects
            .filter(lead_signe_q(), company=company, utm_campaign=key)
            .order_by('id')
            .values_list('id', flat=True))
        result[key] = {'signed_count': len(ids), 'signed_lead_ids': ids}
    return result


def attribution_lead_rows(company, qualifying_stage=None):
    """ADSENG6 — Lignes d'attribution PAR LEAD pour la jointure par variante.

    Point d'entrée cross-app SANCTIONNÉ pour ``apps.adsengine`` (attribution par
    variante) : le CRM est lu UNIQUEMENT via ce sélecteur, jamais un import de
    ``apps.crm.models``. Le stade « SIGNÉ » et le rang de qualification viennent
    de ``STAGES.py`` (via ``apps.crm.stages``) — jamais codés en dur côté
    adsengine (règle #2).

    Pour chaque lead vivant de la société, renvoie un dict portant les CLÉS
    d'attribution (``meta_ad_id`` d'ADSENG1, ``utm_content``/``utm_campaign``) +
    le canal (sous forme booléenne ``is_meta_channel`` pour ne pas exposer la
    taxonomie de canal crm à adsengine) + des drapeaux dérivés du funnel :

      * ``signed``    — le lead est au stade SIGNÉ ;
      * ``qualified`` — le lead a atteint AU MOINS ``qualifying_stage``
        (défaut : CONTACTED), hors COLD et hors perdu ;
      * ``junk``       — PUB28 : le lead est perdu (``perdu=True``) avec un
        motif marqué ``MotifPerte.est_junk=True`` (numéro invalide, spam/bot,
        hors zone, jamais répondu) — DISTINCT d'un lead simplement « non
        qualifié » (qui peut encore être vivant dans le funnel) ou perdu pour
        une raison commerciale réelle (prix, concurrent…). ``junk`` et
        ``qualified`` sont mutuellement exclusifs (un lead junk est perdu,
        donc jamais qualifié) ;
      * ``stage``     — PUB36 : l'étape courante (clé STAGES.py) du lead, pour
        l'entonnoir de décrochage par variante ; ``perdu`` — booléen « perdu ».

    Lecture seule, scopée société. Renvoie une LISTE de dicts (jamais un
    queryset de modèles — le contrat cross-app reste des données pures)."""
    from . import stages as stage_mod
    from .models import Lead, MotifPerte

    order = list(stage_mod.STAGES)
    qual_key = qualifying_stage or stage_mod.CONTACTED

    def _rank(key):
        try:
            return order.index(key)
        except ValueError:
            return -1

    qual_rank = _rank(qual_key)
    meta_channels = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    # PUB28 — motifs marqués « junk » de la société, comparés en minuscule/
    # strippé (Lead.motif_perte reste un texte libre, pas une FK vers
    # MotifPerte — même patron de rapprochement que le reste du CRM).
    junk_motifs = {
        (nom or '').strip().lower()
        for nom in MotifPerte.objects.filter(
            company=company, est_junk=True).values_list('nom', flat=True)}

    rows = []
    qs = (Lead.objects
          .filter(company=company, is_archived=False)
          .only('id', 'meta_ad_id', 'utm_content', 'utm_campaign', 'canal',
                'stage', 'perdu', 'motif_perte', 'is_archived'))
    for lead in qs:
        stage = lead.stage
        rank = _rank(stage)
        is_signed = est_lead_signe(lead)  # ACRM31
        is_qualified = (
            stage != stage_mod.COLD and not lead.perdu
            and rank >= qual_rank)
        is_junk = bool(lead.perdu) and (
            (lead.motif_perte or '').strip().lower() in junk_motifs)
        rows.append({
            'id': lead.id,
            'meta_ad_id': lead.meta_ad_id or '',
            'utm_content': lead.utm_content or '',
            'utm_campaign': lead.utm_campaign or '',
            'is_meta_channel': lead.canal in meta_channels,
            'signed': is_signed,
            'qualified': is_qualified,
            'junk': is_junk,
            # PUB36 — étape courante (clé STAGES.py) + perdu, pour l'entonnoir
            # de décrochage PAR VARIANTE (``adsengine.attribution
            # .variant_stage_funnel``). ``stage`` est une clé STAGES.py déjà
            # exposée à adsengine via ``pipeline_stage_order`` (règle #2) — pas
            # une nouvelle fuite de la taxonomie ; ``perdu`` est un booléen.
            'stage': stage,
            'perdu': bool(lead.perdu),
        })
    return rows


def lead_appointment_stats(company):
    """PUB37 — Statistiques de RDV (``crm.Appointment``) PAR LEAD, pour le
    signal qualité intermédiaire de l'attribution par variante (adsengine).

    Point d'entrée cross-app LECTURE SEULE (jamais un import de
    ``apps.crm.models`` côté adsengine) : une annonce qui génère des RDV
    fantômes (no-show) coûte cher avant que le coût-par-signature ne le
    montre. Renvoie ``{lead_id: {'total': int, 'no_show': int}}`` — un lead
    sans AUCUN rendez-vous est absent du dict (jamais une entrée 0/0
    fabriquée). Lecture seule, scopée société."""
    from .models import Appointment

    stats = {}
    qs = (Appointment.objects
          .filter(company=company)
          .values_list('lead_id', 'statut'))
    for lead_id, statut in qs:
        slot = stats.setdefault(lead_id, {'total': 0, 'no_show': 0})
        slot['total'] += 1
        if statut == Appointment.Statut.NO_SHOW:
            slot['no_show'] += 1
    return stats


def get_company_lead(company, lead_id, avec_corbeille=False):
    """B1 — Lead borné à la société, ou None. Point d'entrée cross-app pour que
    ventes résolve un lead par id sans importer ``apps.crm.models`` (un id d'une
    autre société renvoie None → l'appelant répond 404). Lecture seule.

    ACAL178 — ``avec_corbeille=True`` lit aussi les leads de la corbeille
    (``Lead.all_objects``) : une LECTURE d'un calepinage dont le lead a été
    supprimé retrouve son nom, sa ville, son pin ; les ÉCRITURES gardent le
    défaut (vivants seulement, un lead supprimé reste « introuvable »)."""
    if not lead_id:
        return None
    from .models import Lead
    gestionnaire = Lead.all_objects if avec_corbeille else Lead.objects
    return gestionnaire.filter(pk=lead_id, company=company).first()


def get_company_leads_by_ids(company, ids, avec_corbeille=False):
    """CALX407 — le batch de ``get_company_lead`` : plusieurs leads bornés
    société en UNE requête (``select_related('owner')`` inclus — l'appelant
    cross-app en a besoin pour un repli « responsable », jamais un import
    direct de ``authentication.CustomUser`` par lead). Un id hors société ou
    inconnu est simplement ABSENT du dict rendu, jamais une erreur : à
    l'appelant de traiter un id manquant comme il traite ``None`` côté
    ``get_company_lead``. Lecture seule."""
    if not ids:
        return {}
    from .models import Lead
    gestionnaire = Lead.all_objects if avec_corbeille else Lead.objects
    leads = gestionnaire.filter(
        company=company, pk__in=list(ids)).select_related('owner')
    return {lead.pk: lead for lead in leads}


def rechercher_leads_minimal(company, q, limit=10, *, user=None):
    """VTA16 — recherche de leads MINIMALE pour un consommateur cross-app.

    Renvoie une liste de dicts ``{id, nom, ville, telephone}`` — RIEN d'autre :
    ni email, ni étape de pipeline, ni montant. C'est l'unique surface qu'une
    app tierce (ici ``apps.visites``, pour choisir le client d'une visite à
    planifier) obtient du fichier leads ; elle ne remplace jamais la liste CRM
    et n'en est pas un raccourci.

    Bornée SOCIÉTÉ, corbeille exclue (``Lead.objects``), ``limit`` plafonnée.
    Une recherche vide ne renvoie RIEN — on n'énumère pas l'annuaire quand
    l'utilisateur n'a rien tapé.

    ACRM30 — ``user`` borne la recherche aux leads VISIBLES de l'appelant
    (``leads_visibles`` : portée propriétaire + périmètre d'entités) : la
    recherche ne rend jamais un lead qui lui répond 404. ``None`` (appel
    système sans utilisateur) = toute la société, comportement historique.
    """
    from django.db.models import Q

    from .models import Lead

    terme = (q or '').strip()
    if not terme:
        return []
    try:
        plafond = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        plafond = 10
    base = (leads_visibles(user, company) if user is not None
            else Lead.objects.filter(company=company))
    lignes = (base
              .filter(Q(nom__icontains=terme) | Q(telephone__icontains=terme))
              .order_by('nom', 'id')
              .values('id', 'nom', 'ville', 'telephone')[:plafond])
    return [{'id': ligne['id'], 'nom': ligne['nom'] or '',
             'ville': ligne['ville'] or '',
             'telephone': ligne['telephone'] or ''}
            for ligne in lignes]


def lead_touchpoints_attribution(lead, company=None):
    """FG204 — journal multi-touch ordonné + résumé d'attribution d'un lead.

    Renvoie la timeline des points de contact (PointContact) du lead, ordonnée
    (``ordre`` puis ``date_contact``), plus un résumé d'attribution simple :
    first-touch vs last-touch (canal + libellé), nombre de points et coût total
    des canaux payants. Lecture seule.

    Scopé société si ``company`` est fournie (jamais d'accès cross-tenant). Si le
    lead n'a aucun point de contact, ``timeline`` est vide et les champs
    first/last sont ``None`` (l'UI peut alors retomber sur ``Lead.canal``).

    Format::

        {
          'lead_id': int,
          'count': int,
          'timeline': [PointContact, ...],   # ordonné
          'first_touch': {'canal': str, 'canal_libelle': str} | None,
          'last_touch':  {'canal': str, 'canal_libelle': str} | None,
          'cout_total': Decimal,             # somme des coûts (canaux payants)
        }
    """
    from decimal import Decimal
    from .models import PointContact

    qs = PointContact.objects.filter(lead=lead)
    if company is not None:
        qs = qs.filter(company=company)
    # ordering du modèle (ordre, date_contact, id) → timeline chronologique.
    points = list(qs)

    def _touch(pc):
        if pc is None:
            return None
        return {
            'canal': pc.canal,
            'canal_libelle': pc.get_canal_display(),
        }

    cout_total = sum(
        (p.cout for p in points if p.cout is not None), Decimal('0'))

    return {
        'lead_id': lead.pk,
        'count': len(points),
        'timeline': points,
        'first_touch': _touch(points[0]) if points else None,
        'last_touch': _touch(points[-1]) if points else None,
        'cout_total': cout_total,
    }


def lead_card(lead_id, company):
    """S8 — fiche-carte LECTURE SEULE d'un lead pour le partage dans la
    messagerie. Scopée société : renvoie None si le lead n'appartient pas à la
    société (jamais d'accès cross-tenant). Format {label, subtitle, url}."""
    from .models import Lead
    lead = Lead.objects.filter(pk=lead_id, company=company).first()
    if lead is None:
        return None
    nom = ' '.join(p for p in [lead.nom, (lead.prenom or '')] if p).strip()
    label = nom or f'Lead #{lead.pk}'
    parts = []
    try:
        parts.append(lead.get_stage_display())
    except Exception:  # pragma: no cover - défensif
        pass
    if lead.ville:
        parts.append(lead.ville)
    return {
        'label': label,
        'subtitle': ' · '.join(parts),
        'url': f'/leads/{lead.pk}',
    }


# ── CAD150/CAD159 — la PROVENANCE des champs captés par le site ─────────────

#: La valeur « rien » telle que le chatter l'écrit (``activity._display``).
_VALEUR_CHATTER_VIDE = '—'


def provenance_site(lead):
    """CAD150/CAD159 — ``{champ: {valeur, le, ecrasee}}`` pour chaque champ de
    ``Lead.CHAMPS_SITE`` dont une valeur a été SAISIE PAR LE CLIENT (formulaire
    du site à la création, puis questionnaire du site).

    Décision fondateur du 21/09/2026 : ces champs sont toujours éditables,
    mais la valeur venue du site reste visible AVEC SA PROVENANCE, y compris
    après un écrasement fait en connaissance de cause. Rien n'est stocké en
    plus : tout se relit dans ce qui existe déjà —

      * un lead créé par le site (``source = site_web``) porte ses valeurs
        d'origine depuis ``date_creation`` ; si le champ a été modifié depuis,
        la valeur d'origine est l'ANCIENNE valeur de la première ligne de
        modification du chatter ;
      * une écriture SYSTÈME ultérieure (``user`` nul : questionnaire du
        client, nouvelle soumission du site) devient la nouvelle provenance ;
      * une écriture HUMAINE ne change jamais la provenance — elle la marque
        ``ecrasee``.

    ``valeur`` est la valeur LISIBLE (libellé du choix, comme le chatter) ;
    ``le`` l'horodatage ISO de la saisie. Un champ jamais saisi par le client
    est ABSENT, et un lead qui n'est pas venu du site rend ``{}`` SANS AUCUNE
    requête (le détail d'un lead manuel ne paie rien). UNE requête sinon (les
    lignes de modification de ces champs)."""
    from .activity import _display
    from .models import Lead, LeadActivity

    if lead is None or not getattr(lead, 'pk', None):
        return {}
    if getattr(lead, 'source', None) != Lead.Source.SITE_WEB:
        return {}
    champs = Lead.CHAMPS_SITE
    lignes = {}
    for ligne in (lead.activites
                  .filter(kind=LeadActivity.Kind.MODIFICATION, field__in=champs)
                  .order_by('created_at', 'pk')
                  .values('field', 'old_value', 'new_value', 'user_id',
                          'created_at')):
        lignes.setdefault(ligne['field'], []).append(ligne)

    def _renseignee(valeur):
        return bool(valeur) and valeur != _VALEUR_CHATTER_VIDE

    out = {}
    for champ in champs:
        historique = lignes.get(champ, [])
        valeur, le, ecrasee = None, None, False
        initiale = (historique[0]['old_value'] if historique
                    else _display(lead, champ, getattr(lead, champ, None)))
        if _renseignee(initiale):
            valeur, le = initiale, getattr(lead, 'date_creation', None)
        for ligne in historique:
            if ligne['user_id'] is None:
                if _renseignee(ligne['new_value']):
                    valeur, le = ligne['new_value'], ligne['created_at']
                    ecrasee = False
            elif valeur is not None:
                ecrasee = True
        if valeur is not None:
            out[champ] = {
                'valeur': valeur,
                'le': le.isoformat() if le is not None else None,
                'ecrasee': ecrasee,
            }
    return out


def attribution_leads(company, debut=None, fin=None):
    """ZSAL6 — Rapport d'attribution des leads : par COMMERCIAL et par
    CANAL/SOURCE, croisés avec le résultat (conversion en SIGNED, CA signé).

    Croise ce que win/loss-par-source (QJ19) et le leaderboard commercial
    (FG93) exposent séparément. Lecture seule, aucune migration, jamais de
    ``prix_achat``. ``debut``/``fin`` (date, inclus) filtrent
    ``Lead.date_creation`` ; ``None`` = pas de borne sur ce côté.

    Renvoie ``{'par_commercial': [...], 'par_source': [...]}`` :
      - par_commercial: {commercial, nb_leads, par_canal: {canal: count},
        nb_signes, taux_conversion_pct, ca_signe}
      - par_source: {canal, canal_label, nb_leads, nb_signes,
        taux_conversion_pct, ca_signe}

    Toujours des gardes division-par-zéro (0.0, jamais une exception). Scopé
    société — jamais d'accès cross-tenant.
    """
    from decimal import Decimal
    from .models import Lead

    qs = Lead.objects.filter(company=company, is_archived=False)
    if debut is not None:
        qs = qs.filter(date_creation__date__gte=debut)
    if fin is not None:
        qs = qs.filter(date_creation__date__lte=fin)
    leads = list(qs.prefetch_related('devis').select_related('owner'))

    # Lead.Canal (TextChoices statique) : labels français prêts pour l'UI.
    # Un canal libre non listé (ex. valeur legacy) retombe sur sa propre clé.
    canal_labels = dict(Lead.Canal.choices)

    def _ca_signe_lead(lead):
        total = Decimal('0')
        for devis in lead.devis.all():
            if _devis_compte_comme_signe(devis):  # ACRM10
                try:
                    total += Decimal(str(devis.total_ttc or 0))
                except Exception:
                    continue
        return total

    par_commercial = {}
    par_source = {}

    for lead in leads:
        commercial_key = lead.owner_id or 0
        commercial_nom = getattr(lead.owner, 'username', None) or 'Non assigné'
        slot_com = par_commercial.setdefault(commercial_key, {
            'commercial': commercial_nom,
            'nb_leads': 0,
            'par_canal': {},
            'nb_signes': 0,
            'ca_signe': Decimal('0'),
        })
        slot_com['nb_leads'] += 1
        canal_key = lead.canal or 'inconnu'
        slot_com['par_canal'][canal_key] = slot_com['par_canal'].get(canal_key, 0) + 1

        slot_src = par_source.setdefault(canal_key, {
            'canal': canal_key,
            'canal_label': canal_labels.get(canal_key, canal_key),
            'nb_leads': 0,
            'nb_signes': 0,
            'ca_signe': Decimal('0'),
        })
        slot_src['nb_leads'] += 1

        est_signe = est_lead_signe(lead)  # ACRM31
        if est_signe:
            ca = _ca_signe_lead(lead)
            slot_com['nb_signes'] += 1
            slot_com['ca_signe'] += ca
            slot_src['nb_signes'] += 1
            slot_src['ca_signe'] += ca

    def _finalize_commercial(slot):
        taux = (
            round(slot['nb_signes'] / slot['nb_leads'] * 100, 1)
            if slot['nb_leads'] else 0.0
        )
        return {
            'commercial': slot['commercial'],
            'nb_leads': slot['nb_leads'],
            'par_canal': slot['par_canal'],
            'nb_signes': slot['nb_signes'],
            'taux_conversion_pct': taux,
            'ca_signe': str(slot['ca_signe']),
        }

    def _finalize_source(slot):
        taux = (
            round(slot['nb_signes'] / slot['nb_leads'] * 100, 1)
            if slot['nb_leads'] else 0.0
        )
        return {
            'canal': slot['canal'],
            'canal_label': slot['canal_label'],
            'nb_leads': slot['nb_leads'],
            'nb_signes': slot['nb_signes'],
            'taux_conversion_pct': taux,
            'ca_signe': str(slot['ca_signe']),
        }

    return {
        'par_commercial': sorted(
            (_finalize_commercial(s) for s in par_commercial.values()),
            key=lambda r: r['commercial']),
        'par_source': sorted(
            (_finalize_source(s) for s in par_source.values()),
            key=lambda r: r['canal']),
    }


# DC11 — provenance des valeurs énergie/toiture reprises du lead ──────────────

# Valeurs énergie + toiture du lead recopiées dans le devis. Une divergence sur
# l'une de ces clés (lead modifié APRÈS capture) déclenche la bannière
# « valeurs du lead modifiées depuis » côté générateur. Source unique pour que
# ``ventes`` n'ait pas à connaître la liste des champs du lead.
LEAD_PROVENANCE_FIELDS = (
    'facture_hiver', 'facture_ete', 'ete_differente', 'bill_kwh',
    'type_toiture', 'surface_toiture_m2', 'orientation', 'inclinaison_deg',
    'gps_lat', 'gps_lng',
    # ERR-QAC-PROVENANCE-CONSO-KWH — depuis CAD166 la conso mensuelle PILOTE
    # l'étude horaire (recopiée dans `etude_params`) : une dérive doit se voir.
    'conso_mensuelle_kwh',
    # QJR587 (contrat QJR506 ``lead_provenance_fields.json``) — les valeurs du
    # lead qui PILOTENT le devis : la taille souhaitée est SOUVERAINE, la
    # batterie souhaitée décide le scénario, le raccordement choisit phase et
    # onduleur, la structure dérive la ligne structure, le pompage est
    # re-saisi par l'écran agricole, le type choisit le marché et la ville
    # (de calcul, QJR586) le productible, le transport et le distributeur.
    'taille_souhaitee_kwc', 'batterie_souhaitee', 'raccordement',
    'structure_pref', 'structure_produit',
    'pompe_actuelle_cv', 'pompe_hmt_m', 'pompe_debit_m3h',
    'type_installation', 'ville', 'ville_reference',
    # AGR404 (ex-AGR215) — l'énergie de la pompe actuelle est lue par
    # `entrees_pompage` pour l'économie agricole : une dérive doit se voir.
    'pompe_alim_actuelle',
)


# ── QJR234 — LA GARDE : plus une seule omission SILENCIEUSE ──────────────────
#
# LE DÉFAUT. ``LEAD_PROVENANCE_FIELDS`` est une liste écrite à la main. Une
# valeur énergie/toiture ajoutée au modèle ``crm.Lead`` et oubliée ici sort de
# la bannière « valeurs du lead modifiées depuis » SANS QUE RIEN NE LE DISE :
# le commercial ne verra jamais que cette valeur a bougé depuis la capture. Ni
# test ni garde ne signalaient l'omission.
#
# LA RÈGLE. Tout champ concret de ``crm.Lead`` dont le NOM porte un marqueur
# énergie/toiture ci-dessous doit être, au choix : dans
# ``LEAD_PROVENANCE_FIELDS``, ou dans ``LEAD_PROVENANCE_EXCLUSIONS`` AVEC SA
# RAISON. Jamais par omission. Les marqueurs sont volontairement larges : un
# faux positif se règle en écrivant une ligne d'exclusion (trente secondes),
# un faux négatif se paye en chiffres périmés montrés à un client.
_LEAD_PROVENANCE_MARQUEURS = (
    'facture', 'ete_differente', 'conso_', 'kwh', 'bill_', 'tranche_onee',
    'raccordement', 'regularisation_', 'equip_', 'occupation_jour', 'pompe_',
    'toiture', 'roof_', 'orientation', 'inclinaison', 'ombrage', 'gps_',
    'nb_etages', 'structure_', 'kwc', 'batterie', 'distributeur',
    # QJR587 — la ville et le marché pilotent le devis : surveillés aussi.
    'ville', 'type_installation',
)


# Les raisons, mutualisées par famille : une seule phrase à relire, et un champ
# ajouté à une famille reste malgré tout un ROUGE tant qu'il n'est pas nommé
# ci-dessous (l'exclusion est par CHAMP, jamais par préfixe).
_RAISON_LU_EN_DIRECT = (
    "lu EN DIRECT sur le lead au moment du rendu, jamais recopié dans "
    "`Devis.etude_params` : une valeur qui n'a pas de copie ne peut pas "
    "diverger de sa copie. L'ajouter ferait clignoter la bannière sur un "
    "champ que le devis n'a jamais repris."
)


_RAISON_PROFIL_APPEL = (
    "profil d'équipements du script d'appel (L-BACK / L-WEBT2) : le devis ne "
    "le RECOPIE pas — il est lu sur le lead quand l'étude en a besoin. "
    "À déclarer le jour où l'écran générateur le re-saisit."
)


_RAISON_QUALIFICATION = (
    "donnée de QUALIFICATION du lead (ce que le prospect a déclaré au "
    "premier contact), pas une valeur d'étude re-saisie dans le devis : elle "
    "vit sa vie côté CRM et n'a pas de copie dans `etude_params`."
)


_RAISON_TRANCHE = (
    "valeur RE-DÉRIVÉE par l'étude à chaque rendu depuis la facture et la "
    "consommation (elles, sont estampillées) : l'estampiller en plus ferait "
    "signaler deux fois la même dérive."
)


_RAISON_POMPAGE_AGR = (
    "colonne de pompage agricole (AGR400, contrat AGR1) : le devis ne la "
    "RECOPIE pas encore dans `etude_params` — exclue jusqu'à ce que le "
    "moteur agricole serveur la recopie (D-AGR-1) ; à ce jour-là, la "
    "déclarer dans `LEAD_PROVENANCE_FIELDS`."
)


_RAISON_PRO_CIQ = (
    "colonne du lead pro (CIQ401, contrat CIQ1) : le devis C&I ne la "
    "RECOPIE pas encore dans `etude_params` — elle est lue par "
    "`entrees_ci` (CIQ405) au moment où le moteur serveur C&I (D-CIQ-0) "
    "compose l'étude ; à déclarer dans `LEAD_PROVENANCE_FIELDS` le jour où "
    "le devis en garde une copie."
)


LEAD_PROVENANCE_EXCLUSIONS = dict(
    [(champ, _RAISON_PROFIL_APPEL) for champ in (
        'equip_piscine', 'equip_piscine_pompe_kw', 'equip_piscine_heures_jour',
        'equip_piscine_creneau', 'equip_voiture_electrique',
        'equip_ve_km_semaine', 'equip_ve_chargeur_kw', 'equip_ve_creneau',
        'equip_clim', 'equip_clim_pieces', 'equip_clim_kw',
        'equip_clim_creneau', 'equip_chauffe_eau_electrique',
        'equip_chauffe_eau_kw', 'equip_chauffe_eau_creneau',
    )]
    + [(champ, _RAISON_QUALIFICATION) for champ in (
        'bill_range_bucket', 'roof_age', 'distributeur',
        'nb_etages', 'regularisation_8221',
    )]
    # ── CAD-L ── CAD149 — vague 1 du script d'appel guidé : deux des huit
    # champs portent un marqueur de provenance (`equip_`, `pompe_`) et
    # doivent donc être déclarés ICI, avec leur raison.
    + [
        ('equip_ve_statut',
         "précision du profil d'équipements posée à l'appel (CAD149) : elle "
         "dit si le véhicule électrique est DÉJÀ là ou seulement prévu, et "
         "le devis ne la RECOPIE pas dans `etude_params` — elle est relue "
         "sur le lead au moment où l'étude compose la couche véhicule et "
         "où le rendu décide de l'étiquette « avec votre future voiture ». "
         "Une valeur sans copie ne peut pas diverger de sa copie."),
        # AGR404 — `pompe_alim_actuelle` n'est PLUS exclue : `entrees_pompage`
        # la sert au moteur agricole (énergie actuelle de l'économie), elle
        # est donc déclarée dans `LEAD_PROVENANCE_FIELDS`.
    ]
    # AGR400 — colonnes de pompage du contrat AGR1 (``lead_pompage.json``).
    # Exclues AVEC LEUR RAISON (seules trois portent le marqueur `pompe_`,
    # toutes sont nommées pour qu'aucune ne sorte de la règle en silence).
    + [(champ, _RAISON_POMPAGE_AGR) for champ in (
        'source_eau', 'niveau_statique_m', 'niveau_statique_source',
        'profondeur_forage_m', 'debit_forage_m3h', 'debit_forage_source',
        'besoin_eau_m3j', 'besoin_eau_source', 'culture',
        'surface_irriguee_ha', 'irrigation_methode', 'region_agricole',
        'pompe_actuelle_type', 'pompe_actuelle_debit_m3h',
        'butane_bouteilles_jour', 'carburant_prix_unitaire_mad',
        'carburant_prix_declare_le', 'depense_carburant_mad_mois',
        'mois_irrigation', 'distance_forage_champ_m', 'electricite_sur_place',
        'autorisation_prelevement', 'autorisation_numero',
        'autorisation_debit_l_s', 'autorisation_volume_m3_an',
        'compteur_eau', 'projet_pompage', 'deja_beneficiaire_fda',
        'pompe_hmt_source',
    )]
    # CIQ401 — colonnes du lead pro (contrat CIQ1 ``lead_pro.json``) qui
    # portent un marqueur énergie : nommées une à une, avec leur raison.
    + [(champ, _RAISON_PRO_CIQ) for champ in (
        'tension_raccordement', 'releve_conso', 'facture_tranche_declaree',
        'pv_existant_kwc',
    )]
    + [
        ('occupation_jour', _RAISON_LU_EN_DIRECT),
        ('roof_point', _RAISON_LU_EN_DIRECT),
        ('roof_outline', _RAISON_LU_EN_DIRECT),
        ('ombrage', _RAISON_LU_EN_DIRECT),
        ('ombrage_notes',
         "note de terrain en TEXTE LIBRE : aucun chiffre d'étude n'en "
         "dérive, il n'y a rien à comparer."),
        ('tranche_onee', _RAISON_TRANCHE),
        ('roof_type',
         "colonne MORTE depuis QJR657 : le webhook du tunnel ne l'écrit plus "
         "(valeur fabriquée « autre ») et aucun écran ne l'affiche ; la seule "
         "source du type de toiture est `type_toiture`. Elle reste en base "
         "jusqu'à sa migration destructive séparée — à retirer d'ici ce "
         "jour-là."),
    ]
)


def _lead_champs_concrets():
    """Les noms des champs CONCRETS de ``crm.Lead`` (sans les relations inverses)."""
    from .models import Lead
    return [f.name for f in Lead._meta.get_fields()
            if getattr(f, 'concrete', False)]


def lead_provenance_champs_energie_toit(champs=None):
    """Les champs de ``crm.Lead`` que les marqueurs désignent énergie/toiture."""
    noms = _lead_champs_concrets() if champs is None else list(champs)
    return [nom for nom in noms
            if any(marqueur in nom for marqueur in _LEAD_PROVENANCE_MARQUEURS)]


def lead_provenance_omissions(champs=None):
    """QJR234 — [(champ, motif FR)] : tout ce qui rompt la règle ci-dessus.

    ``champs`` (facultatif) remplace la lecture du modèle : c'est ce qui permet
    de PROUVER la garde en simulant l'ajout d'un champ énergie au lead, sans
    migration et sans base de données. Liste vide = rien à signaler.
    """
    noms = _lead_champs_concrets() if champs is None else list(champs)
    connus = set(noms)
    energie_toit = lead_provenance_champs_energie_toit(noms)
    constats = []
    for champ in energie_toit:
        if champ in LEAD_PROVENANCE_FIELDS:
            continue
        raison = LEAD_PROVENANCE_EXCLUSIONS.get(champ)
        if raison:
            continue
        constats.append((
            champ,
            f"« {champ} » est un champ énergie/toiture de `crm.Lead` que "
            "`LEAD_PROVENANCE_FIELDS` ne déclare PAS : s'il change après la "
            "capture, la bannière « valeurs du lead modifiées depuis » ne le "
            "dira jamais. L'ajouter à `LEAD_PROVENANCE_FIELDS`, ou l'inscrire "
            "dans `LEAD_PROVENANCE_EXCLUSIONS` AVEC SA RAISON — jamais par "
            "omission."))
    for champ in LEAD_PROVENANCE_FIELDS:
        if champ not in connus:
            constats.append((
                champ,
                f"« {champ} » est déclaré dans `LEAD_PROVENANCE_FIELDS` mais "
                "n'existe plus sur `crm.Lead` : l'estampille porterait un "
                "champ fantôme (toujours None des deux côtés, donc une dérive "
                "invisible)."))
    for champ in LEAD_PROVENANCE_EXCLUSIONS:
        if champ not in connus:
            constats.append((
                champ,
                f"« {champ} » est exclu de la provenance alors qu'il n'existe "
                "plus sur `crm.Lead` : exclusion périmée, à retirer."))
    return constats


def _lead_provenance_valeurs(lead):
    """Snapshot {champ: valeur} des valeurs énergie/toiture d'un lead.

    Les Decimal sont rendus en str (JSON-safe + comparaison stable), les autres
    valeurs telles quelles. Lecture seule.
    """
    from decimal import Decimal
    valeurs = {}
    for f in LEAD_PROVENANCE_FIELDS:
        # QJR587 — une clé étrangère (``structure_produit``) est estampillée
        # par son id : JSON-safe et comparable.
        try:
            relation = lead._meta.get_field(f).is_relation
        except Exception:  # noqa: BLE001 — champ absent : None des deux côtés
            relation = False
        v = getattr(lead, f'{f}_id', None) if relation else getattr(lead, f, None)
        valeurs[f] = str(v) if isinstance(v, Decimal) else v
    return valeurs


def lead_provenance_stamp(lead, captured_at=None):
    """DC11 — estampille de provenance pour ``Devis.etude_params``.

    Renvoie ``{'source_lead_id', 'captured_at', 'valeurs'}`` ou None si pas de
    lead. ``captured_at`` (ISO) par défaut = maintenant. ``ventes`` appelle
    ceci à la création/maj du devis pour tracer d'où viennent les valeurs
    énergie/toiture re-saisies, sans importer ``apps.crm.models``.
    """
    if lead is None:
        return None
    from django.utils import timezone
    ts = captured_at or timezone.now().isoformat()
    return {
        'source_lead_id': lead.pk,
        'captured_at': ts,
        'valeurs': _lead_provenance_valeurs(lead),
    }


def lead_values_changed_since(stamp, company=None):
    """DC11 — le lead source a-t-il changé depuis la capture ?

    ``stamp`` = dict produit par :func:`lead_provenance_stamp` (typiquement
    ``devis.etude_params['provenance']``). Renvoie la liste des champs dont la
    valeur courante du lead diffère de la valeur estampillée (liste vide = rien
    n'a bougé). Renvoie ``[]`` si le stamp est absent/incomplet ou le lead
    introuvable (pas de fausse alerte). Scopé société si fournie. Lecture seule
    — alimente la bannière « valeurs du lead modifiées depuis ».
    """
    if not stamp:
        return []
    lead_id = stamp.get('source_lead_id')
    valeurs = stamp.get('valeurs') or {}
    if not lead_id or not valeurs:
        return []
    from .models import Lead
    qs = Lead.objects.filter(pk=lead_id)
    if company is not None:
        qs = qs.filter(company=company)
    lead = qs.first()
    if lead is None:
        return []
    courant = _lead_provenance_valeurs(lead)

    def _norm(x):
        # Compare les nombres par VALEUR : '800' (capture en mémoire) et
        # '800.00' (relu de la base, decimal_places appliqués) sont ÉGAUX,
        # sinon chaque champ décimal non modifié lèverait une fausse alerte.
        from decimal import Decimal, InvalidOperation
        if x is None or isinstance(x, bool):
            return x
        try:
            return Decimal(str(x))
        except (InvalidOperation, ValueError):
            return x

    return [f for f in LEAD_PROVENANCE_FIELDS
            if f in valeurs and _norm(courant.get(f)) != _norm(valeurs.get(f))]


# Champs Lead autorisés dans les règles JSON d'un segment marketing (XMKT6,
# module marketing de compta). Whitelist stricte — toute clé inconnue est
# rejetée côté validation, jamais évaluée à l'aveugle.
LEAD_SEGMENT_FIELDS = (
    'ville', 'type_installation', 'tags', 'canal', 'score', 'facture_energie',
)


def leads_matching_regles(company, regles):
    """XMKT6 — Renvoie le queryset de ``Lead`` correspondant aux règles JSON
    d'un segment marketing. LECTURE SEULE, point d'entrée cross-app pour le
    module marketing de compta (jamais d'import direct de
    ``apps.crm.models`` ailleurs).

    ``regles`` est un dict dont les clés viennent de ``LEAD_SEGMENT_FIELDS`` :

    * ``ville`` — égalité insensible à la casse ;
    * ``type_installation`` — égalité (valeur de choix) ;
    * ``tags`` — le tag apparaît dans la liste séparée par virgules ;
    * ``canal`` — égalité (valeur de choix) ;
    * ``score`` — dict ``{'gte': int, 'lte': int}`` (au moins une borne) ;
    * ``facture_energie`` — dict ``{'gte': num, 'lte': num}`` (sur
      ``facture_hiver``, la facture de référence du lead).

    Une clé absente de ``LEAD_SEGMENT_FIELDS`` lève ``ValueError`` — la
    validation stricte vit ici, appelée par le module marketing de compta
    avant tout enregistrement/évaluation.
    """
    from .models import Lead

    inconnues = set(regles or {}) - set(LEAD_SEGMENT_FIELDS)
    if inconnues:
        raise ValueError(f"Règle(s) de segment inconnue(s) : {sorted(inconnues)}")

    # ACRM56 (D-ACRM-5 (1)=(a)) — un lead « ne plus contacter » n'entre dans
    # AUCUN segment marketing.
    qs = Lead.objects.filter(company=company, is_archived=False, perdu=False,
                             ne_plus_contacter=False)
    if 'ville' in regles and regles['ville']:
        qs = qs.filter(ville__iexact=regles['ville'])
    if 'type_installation' in regles and regles['type_installation']:
        qs = qs.filter(type_installation=regles['type_installation'])
    if 'tags' in regles and regles['tags']:
        qs = qs.filter(tags__icontains=regles['tags'])
    if 'canal' in regles and regles['canal']:
        qs = qs.filter(canal=regles['canal'])
    if 'score' in regles and isinstance(regles['score'], dict):
        borne = regles['score']
        if borne.get('gte') is not None:
            qs = qs.filter(score__gte=borne['gte'])
        if borne.get('lte') is not None:
            qs = qs.filter(score__lte=borne['lte'])
    if 'facture_energie' in regles and isinstance(regles['facture_energie'], dict):
        borne = regles['facture_energie']
        if borne.get('gte') is not None:
            qs = qs.filter(facture_hiver__gte=borne['gte'])
        if borne.get('lte') is not None:
            qs = qs.filter(facture_hiver__lte=borne['lte'])
    return qs


def leads_ville_rows(company, canaux=None, date_start=None, date_end=None):
    """PUB62 — Une ligne par lead PORTANT une ville renseignée : id, ville,
    signé (stade SIGNED, jamais perdu — STAGES.py, jamais codé en dur).
    Scopé société, leads vivants. Un lead SANS ville est simplement ABSENT
    (jamais une ville vide fabriquée — règle checked-facts). Point d'entrée
    cross-app pour la carte chaleur ville d'``apps.adsengine.reporting``
    (jamais un import d'``apps.crm.models`` côté adsengine).

    AACQ10 — filtres OPTIONNELS (défaut = comportement d'avant) : ``canaux``
    (liste de clés ``Lead.Canal``) et ``date_start``/``date_end`` (dates
    incluses, sur la date de création du lead) — la carte chaleur peut ainsi
    ne demander que les leads Meta d'une fenêtre."""
    from .models import Lead

    rows = []
    qs = (Lead.objects
          .filter(company=company, is_archived=False)
          .exclude(ville__isnull=True).exclude(ville__exact='')
          .only('id', 'ville', 'stage', 'perdu', 'is_archived'))
    if canaux is not None:
        qs = qs.filter(canal__in=list(canaux))
    if date_start is not None:
        qs = qs.filter(date_creation__date__gte=date_start)
    if date_end is not None:
        qs = qs.filter(date_creation__date__lte=date_end)
    for lead in qs:
        rows.append({
            'id': lead.id,
            'ville': lead.ville.strip(),
            'signed': est_lead_signe(lead),  # ACRM31
        })
    return rows


# ── XMKT17 — Coût & ROI MAD par campagne (compta.Campagne) ─────────────────

def revenu_attribue_campagne(company, nom_campagne):
    """XMKT17 — Revenu attribué (dernier-touch) à une ``compta.Campagne`` :
    somme des devis ACCEPTÉS (TTC) des leads portant
    ``utm_campaign == nom_campagne``. Jamais d'import de ``apps.ventes``
    depuis ici — les devis sont lus via la relation ``lead.devis`` déjà
    dans le domaine crm (même pattern que ``attribution_leads``).

    Renvoie ``{'nb_leads': int, 'nb_signes': int, 'revenu_ttc': str}``.
    """
    from decimal import Decimal
    from .models import Lead

    if not nom_campagne:
        return {'nb_leads': 0, 'nb_signes': 0, 'revenu_ttc': '0'}

    leads = list(
        Lead.objects.filter(
            company=company, is_archived=False, utm_campaign=nom_campagne,
        ).prefetch_related('devis'))
    nb_signes = 0
    revenu = Decimal('0')
    for lead in leads:
        signe_pour_ce_lead = False
        # ACRM31 — seul un lead signé (prédicat unique) porte du CA attribué.
        if not est_lead_signe(lead):
            continue
        for devis in lead.devis.all():
            if _devis_compte_comme_signe(devis):  # ACRM10
                signe_pour_ce_lead = True
                try:
                    revenu += Decimal(str(devis.total_ttc or 0))
                except Exception:
                    continue
        if signe_pour_ce_lead:
            nb_signes += 1
    return {
        'nb_leads': len(leads),
        'nb_signes': nb_signes,
        'revenu_ttc': str(revenu),
    }


def leads_source_campagne(company, nom_campagne):
    """XMKT17 — Liste (drill-down) des leads portant l'utm_campaign de la
    campagne : id + nom + stage + signé (pour le drill-down ROI)."""
    from .models import Lead

    if not nom_campagne:
        return []
    leads = Lead.objects.filter(
        company=company, is_archived=False, utm_campaign=nom_campagne,
    ).only('id', 'nom', 'prenom', 'stage')
    return [
        {'id': lead.id, 'nom': f'{lead.nom} {lead.prenom or ""}'.strip(),
         'stage': lead.stage}
        for lead in leads
    ]


def lead_chatter_envelope(lead, user=None):
    """ARC9 — timeline chatter du lead dans l'ENVELOPPE UNIFORME.

    Étape 1 (additive) de la convergence des chatters historiques : projette
    ``crm.LeadActivity`` vers le format commun consommé par
    ``records.serializers.UniformChatterSerializer`` (un seul contrat de
    lecture pour le frontend, quel que soit le modèle source). Lecture seule —
    AUCUNE table modifiée. Le queryset est déjà borné par le lead (lui-même
    borné société par l'appelant).

    CRX19 — ``user`` optionnel : quand il est fourni, ``old_value``/
    ``new_value`` d'une entrée portant sur une PII du lead sont masqués par la
    MÊME règle que le sérialiseur d'activité (source unique
    ``serializers.masquer_valeurs_chatter``) — sinon cette troisième surface
    resservait en clair ce que les deux autres masquent. ``user=None`` (appel
    interne, ex. ``records.services`` qui ne lit que ``created_at``) laisse le
    rendu HISTORIQUE strictement inchangé. TOUTE surface HTTP qui exposera
    cette enveloppe DOIT passer l'utilisateur de la requête.
    """
    from .serializers import masquer_valeurs_chatter

    rows = lead.activites.select_related('user').all()
    sortie = []
    for a in rows:
        old_value, new_value = masquer_valeurs_chatter(
            a.field or '', a.old_value or '', a.new_value or '', user)
        sortie.append({
            'id': a.id,
            'kind': a.kind,
            'field': a.field or '',
            'field_label': a.field_label or '',
            'old_value': old_value,
            'new_value': new_value,
            'body': a.body or '',
            'user_username': a.user.username if a.user_id else None,
            'created_at': a.created_at,
            'source': 'crm.leadactivity',
        })
    return sortie


# ── CRX37 — Jalons devis dans l'historique du lead ───────────────────────────

#: CRX37 — ``kind`` renvoyé par ``ventes.selectors.devis_events_for_lead`` →
#: ``kind`` du chatter, celui que ``ChatterTimeline`` sait DÉJÀ rendre
#: (📤/👁️/✅/❌) et que ``matchesTimelineFilter`` range sous le filtre
#: « Devis ». Le rendu existait des deux côtés ; il ne manquait que la source.
_KIND_DEVIS_VERS_CHATTER = {
    'sent': 'devis_sent',
    'opened': 'devis_opened',
    'signed': 'devis_signed',
    'refused': 'devis_refused',
}


def lead_jalons_devis(lead):
    """CRX37 — jalons du cycle de vie des devis d'un lead, projetés dans la
    forme du chatter (contrat ``apps/crm/contract_samples/lead_jalons_devis.json``).

    Le sélecteur ``apps.ventes.selectors.devis_events_for_lead`` (QX32be) a été
    écrit pour ça et n'avait AUCUN appelant : le commercial ne voyait donc
    jamais « devis envoyé / proposition ouverte / signé / refusé » dans
    l'historique du lead, alors que ``ChatterTimeline`` sait rendre ces quatre
    ``kind`` depuis QX32 et que le filtre « Devis » de la timeline existe déjà.

    Lecture seule, cross-app par le SÉLECTEUR de l'app cible (jamais un import
    de ``apps.ventes.models``), bornée à la société du lead. Aucun montant :
    la timeline montre des JALONS, pas des prix (et jamais de ``prix_achat``).

    Chaque entrée porte la forme d'une ligne de chatter — ``id`` textuel et
    STABLE (aucune collision avec les ``id`` numériques de ``LeadActivity``,
    que le frontend fusionne dans la même liste), ``kind`` ``devis_*``,
    ``body`` lisible, ``created_at`` ISO.
    """
    from apps.ventes import selectors as ventes_selectors

    if lead is None or not getattr(lead, 'pk', None):
        return []
    evenements = ventes_selectors.devis_events_for_lead(lead.pk, lead.company)

    lignes = []
    for evenement in evenements:
        kind = _KIND_DEVIS_VERS_CHATTER.get(evenement.get('kind'))
        if kind is None:
            continue
        reference = evenement.get('reference') or ''
        lignes.append({
            'id': f"devis-{evenement.get('devis_id')}-{evenement.get('kind')}",
            'kind': kind,
            'body': reference,
            'created_at': evenement.get('at'),
            'devis_id': evenement.get('devis_id'),
            'reference': reference,
            'user_nom': None,
            'pinned': False,
        })
    return lignes


# ── ADSENG31 — Réconciliation Meta-vs-ERP : lignes de lead par mécanisme ──────

def reconciliation_lead_rows(company, *, date_start=None, date_end=None):
    """ADSENG31 — Lignes d'un lead pour la RÉCONCILIATION Meta-vs-ERP (dd-
    attribution part b). Point d'entrée cross-app SANCTIONNÉ pour
    ``apps.adsengine`` (le CRM est lu UNIQUEMENT via ce sélecteur, jamais un
    import de ``apps.crm.models``).

    Chaque ligne porte de quoi classer le lead par MÉCANISME DE CAPTURE (les deux
    dénominateurs que la réconciliation ne fusionne jamais) et de quoi le
    rapprocher d'une campagne + le dédupliquer :

      * ``is_meta_form``      — formulaire Meta Lead Ads (``source=meta_lead_ads``,
        appariable 1:1 via leadgen_id) ;
      * ``is_site``           — lead du site (``source=site_web``) — Meta-attribué
        seulement si son canal/utm indique Meta (l'appelant tranche) ;
      * ``is_ctwa``           — canal WhatsApp/CTWA (auto-déclaré, JAMAIS confirmé
        côté Meta — montré à part) ;
      * ``is_meta_ads_canal`` — canal « Publicité Meta » ;
      * ``phone_key``/``email_key`` — clés NORMALISÉES QW10 (réutilise
        ``services.normalize_phone``/``normalize_email``) pour dédupliquer sans
        recompter un payload webhook brut (dd-attribution §3.3) ;
      * ``utm_campaign``/``meta_campaign_id`` — clés de rapprochement de campagne.

    Lecture seule, scopée société ; ne compte jamais un lead archivé.
    ``date_start``/``date_end`` (date, inclus) bornent ``date_creation`` ;
    ``None`` = pas de borne. Renvoie une LISTE de dicts (données pures)."""
    from . import services as crm_services
    from .models import Lead

    qs = Lead.objects.filter(company=company, is_archived=False)
    if date_start is not None:
        qs = qs.filter(date_creation__date__gte=date_start)
    if date_end is not None:
        qs = qs.filter(date_creation__date__lte=date_end)

    meta_form = Lead.Source.META_LEAD_ADS
    site_source = Lead.Source.SITE_WEB
    ctwa_canal = Lead.Canal.WHATSAPP_CTWA
    meta_canal = Lead.Canal.META_ADS

    rows = []
    for lead in qs.only(
            'id', 'utm_campaign', 'utm_source', 'meta_campaign_id',
            'source', 'canal', 'telephone', 'email', 'date_creation'):
        rows.append({
            'id': lead.id,
            'utm_campaign': lead.utm_campaign or '',
            'utm_source': (lead.utm_source or '').strip().lower(),
            'meta_campaign_id': lead.meta_campaign_id or '',
            'source': lead.source or '',
            'is_meta_form': lead.source == meta_form,
            'is_site': lead.source == site_source,
            'is_ctwa': lead.canal == ctwa_canal,
            'is_meta_ads_canal': lead.canal == meta_canal,
            'phone_key': crm_services.normalize_phone(lead.telephone),
            'email_key': crm_services.normalize_email(lead.email),
            'date': lead.date_creation.date() if lead.date_creation else None,
        })
    return rows


# ── ADSENG32 — Émetteur CAPI CRM-stage : contexte lead borné société ──────────

# Valeur d'``external_system`` d'un lead issu d'un formulaire Meta Lead Ads : son
# ``external_id`` EST alors le leadgen_id Meta (clé de match préférée, cf.
# services._META_LEAD_ADS_SYSTEM). Constante locale pour éviter d'importer les
# services CRM sur ce chemin de lecture.
_META_LEAD_ADS_SYSTEM = 'meta_lead_ads'


def pipeline_stage_order():
    """ADSENG32 — Ordre canonique des étapes + repères SIGNED/COLD, depuis
    ``STAGES.py`` (jamais codés en dur côté adsengine — règle #2). Point d'entrée
    cross-app pour que ``apps.adsengine`` détecte une transition AVANT (rang qui
    augmente) sans importer ``apps.crm.models`` ni ``STAGES.py`` directement.

    Renvoie ``{'stages': [...], 'funnel': [...], 'signed': str, 'cold': str,
    'quote_sent': str}`` où ``funnel`` = les étapes AVANT-ordonnées hors COLD
    (« Perdu » n'est pas une étape). PUB31 ajoute ``quote_sent`` (additif) :
    permet à ``adsengine.capi_crm`` de détecter la transition QUOTE_SENT sans
    jamais importer ``apps.crm.stages`` directement (règle #2)."""
    from . import stages as stage_mod
    order = list(stage_mod.STAGES)
    return {
        'stages': order,
        'funnel': [k for k in order if k != stage_mod.COLD],
        'signed': stage_mod.SIGNED,
        'cold': stage_mod.COLD,
        'quote_sent': stage_mod.QUOTE_SENT,
    }


def lead_current_stage(company, lead_id):
    """ADSENG32 — Étape COURANTE (clé STAGES.py) d'un lead borné société, ou
    None. Point d'entrée cross-app LECTURE SEULE : appelé en ``pre_save`` par
    l'émetteur CAPI CRM-stage pour capturer l'ANCIENNE étape (la base porte
    encore l'ancienne valeur) et n'émettre que sur une VRAIE transition."""
    if not lead_id:
        return None
    from .models import Lead
    return (Lead.objects
            .filter(pk=lead_id, company=company)
            .values_list('stage', flat=True)
            .first())


def lead_capi_identifiers(company, lead_id):
    """ADSENG32 — Identifiants de MATCH d'un lead borné société pour le CAPI
    CRM-stage (Conversion Leads), ou None si hors société. Point d'entrée cross-
    app LECTURE SEULE (jamais un import de ``apps.crm.models`` côté adsengine).

    Renvoie ``{'lead_id', 'leadgen_id', 'phone', 'email', 'fbclid',
    'is_meta_origin'}`` : ``leadgen_id`` = ``external_id`` quand
    ``external_system == 'meta_lead_ads'`` (clé de match Meta préférée) ; sinon
    ''. ``phone``/``email`` sont bruts (le HACHAGE SHA-256 se fait côté émetteur,
    jamais ici — on n'expose pas de PII hachée en dur). ``is_meta_origin`` =
    lead issu d'un canal/source Meta (éligible à l'intégration). Ne renvoie
    JAMAIS de donnée interne (aucun prix_achat n'existe côté lead)."""
    if not lead_id:
        return None
    from .dsr_provider import LEAD_NOM_ANONYMISE
    from .models import Lead
    lead = (Lead.objects
            .filter(pk=lead_id, company=company)
            .only('id', 'external_system', 'external_id', 'telephone', 'email',
                  'fbclid', 'canal', 'source', 'nom')
            .first())
    if lead is None:
        return None
    # AACQ20 — un lead EFFACÉ (DSR/rétention) ne fournit plus aucun
    # identifiant publicitaire : ``external_id`` est gardé en base pour la
    # dédup anti-résurrection, jamais renvoyé ici.
    is_erased = lead.nom == LEAD_NOM_ANONYMISE
    leadgen_id = ''
    if (not is_erased and lead.external_system == _META_LEAD_ADS_SYSTEM
            and lead.external_id):
        leadgen_id = str(lead.external_id)
    meta_canaux = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    is_meta_origin = (
        lead.canal in meta_canaux
        or lead.source == _META_LEAD_ADS_SYSTEM
        or bool(leadgen_id) or bool(lead.fbclid))
    return {
        'lead_id': lead.id,
        'leadgen_id': leadgen_id,
        'phone': lead.telephone or '',
        'email': lead.email or '',
        'fbclid': '' if is_erased else (lead.fbclid or ''),
        'is_meta_origin': is_meta_origin,
        'is_erased': is_erased,
    }


def meta_lead_match_coverage(company):
    """ADSENG32 — Couverture de MATCH des leads Meta de la société (moniteur EMQ
    LOCAL, sans appel réseau). Point d'entrée cross-app LECTURE SEULE : donne au
    moniteur EMQ d'``apps.adsengine`` une estimation de la qualité de match
    ATTENDUE (quelle proportion des leads Meta porte un identifiant fort :
    leadgen_id ou téléphone) sans exposer les modèles crm.

    Le score EMQ réel (0-10) exige l'API Dataset Quality de Meta (séparée) ; ce
    proxy local rend « visible » la qualité de match côté ERP en attendant.
    Renvoie ``{'meta_leads', 'with_leadgen_id', 'with_phone', 'strong_match'}``."""
    from .dsr_provider import LEAD_NOM_ANONYMISE
    from .models import Lead
    meta_canaux = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    # AACQ20 — un lead effacé ne compte plus dans la couverture de match.
    qs = (Lead.objects.filter(company=company, is_archived=False)
          .exclude(nom=LEAD_NOM_ANONYMISE)
          .only('external_system', 'external_id', 'telephone', 'canal',
                'source'))
    meta_leads = with_leadgen = with_phone = strong = 0
    for lead in qs:
        is_meta = (lead.canal in meta_canaux
                   or lead.source == _META_LEAD_ADS_SYSTEM)
        if not is_meta:
            continue
        meta_leads += 1
        has_leadgen = (lead.external_system == _META_LEAD_ADS_SYSTEM
                       and bool(lead.external_id))
        has_phone = bool(lead.telephone)
        if has_leadgen:
            with_leadgen += 1
        if has_phone:
            with_phone += 1
        if has_leadgen or has_phone:
            strong += 1
    return {
        'meta_leads': meta_leads,
        'with_leadgen_id': with_leadgen,
        'with_phone': with_phone,
        'strong_match': strong,
    }


# ── ADSENG33 — Drill-down reporting : lignes de lead (entonnoir + cohortes) ────

def reporting_lead_rows(company, *, date_start=None, date_end=None):
    """ADSENG33 — Lignes de lead pour les drill-downs de reporting (entonnoir par
    campagne + cohortes de signature). Point d'entrée cross-app SANCTIONNÉ pour
    ``apps.adsengine`` (le CRM est lu UNIQUEMENT via ce sélecteur, jamais un
    import de ``apps.crm.models``).

    Chaque ligne porte l'étape courante (clé STAGES.py), le drapeau ``perdu``, la
    clé de campagne (``meta_campaign_id``/``utm_campaign``), la date de création,
    et — pour le lag de signature (dd-attribution §5.3) — la DATE de signature :
    la plus ANCIENNE ``date_acceptation`` parmi les devis ACCEPTÉS du lead (lus
    via la relation ``lead.devis`` déjà dans le domaine crm, JAMAIS un import de
    ``apps.ventes.models`` — même patron que ``attribution_leads``). None si le
    lead n'a pas de devis accepté (un lead au stade SIGNÉ sans devis n'a pas
    d'horodatage de signature → lag indéterminé, jamais fabriqué).

    PUB38 — ``ville`` (brute, non normalisée) est incluse pour le harnais
    d'incrémentalité geo-holdout d'``apps.adsengine`` (zone tenue vs zones
    actives) ; additif, ignoré des consommateurs existants (entonnoir/cohortes).

    Lecture seule, scopée société ; jamais un lead archivé. ``date_start``/
    ``date_end`` (date, inclus) bornent ``date_creation``. Renvoie une LISTE de
    dicts (données pures)."""
    from .models import Lead

    qs = Lead.objects.filter(company=company, is_archived=False)
    if date_start is not None:
        qs = qs.filter(date_creation__date__gte=date_start)
    if date_end is not None:
        qs = qs.filter(date_creation__date__lte=date_end)

    meta_canaux = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    rows = []
    for lead in qs.prefetch_related('devis'):
        accept_dates = [
            d.date_acceptation for d in lead.devis.all()
            if getattr(d, 'statut', None) == 'accepte' and d.date_acceptation]
        signature_date = min(accept_dates) if accept_dates else None
        rows.append({
            'id': lead.id,
            'utm_campaign': lead.utm_campaign or '',
            'meta_campaign_id': lead.meta_campaign_id or '',
            'stage': lead.stage,
            'perdu': bool(lead.perdu),
            'is_meta_channel': lead.canal in meta_canaux,
            'created_date': (lead.date_creation.date()
                             if lead.date_creation else None),
            'signature_date': signature_date,
            'ville': lead.ville or '',
        })
    return rows


# ── PUB72 — Mine d'objections (motif_perte + notes chatter) ──────────────────

def objection_mining_rows(company):
    """PUB72 — Lignes texte-libre PAR LEAD pour la mine d'objections
    (``apps.adsengine.comment_mining.mine_ad_objections``) : ``motif_perte`` +
    le corps des activités de chatter texte-libre (notes/appels/e-mails —
    JAMAIS les entrées structurées création/modification, qui ne portent pas
    d'objection), avec les MÊMES clés d'attribution que
    ``attribution_lead_rows`` (``meta_ad_id``/``utm_content``/
    ``utm_campaign``) pour permettre la résolution PAR VARIANTE d'annonce en
    aval. Point d'entrée cross-app SANCTIONNÉ pour ``apps.adsengine`` (le CRM
    est lu UNIQUEMENT via ce sélecteur, jamais un import de
    ``apps.crm.models``). Lecture seule, scopée société ; jamais un lead
    archivé. Renvoie une LISTE de dicts (jamais un queryset de modèles)."""
    from .models import Lead, LeadActivity

    qs = (Lead.objects
          .filter(company=company, is_archived=False)
          .only('id', 'meta_ad_id', 'utm_content', 'utm_campaign', 'canal',
                'motif_perte'))
    leads = list(qs)
    lead_ids = [lead.id for lead in leads]

    notes_by_lead = {}
    if lead_ids:
        text_kinds = (LeadActivity.Kind.NOTE, LeadActivity.Kind.APPEL,
                      LeadActivity.Kind.EMAIL)
        activities = (LeadActivity.objects
                      .filter(lead_id__in=lead_ids, kind__in=text_kinds)
                      .only('lead_id', 'body'))
        for act in activities:
            if act.body:
                notes_by_lead.setdefault(act.lead_id, []).append(act.body)

    meta_channels = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    rows = []
    for lead in leads:
        rows.append({
            'id': lead.id,
            'meta_ad_id': lead.meta_ad_id or '',
            'utm_content': lead.utm_content or '',
            'utm_campaign': lead.utm_campaign or '',
            'is_meta_channel': lead.canal in meta_channels,
            'motif_perte': lead.motif_perte or '',
            'notes': notes_by_lead.get(lead.id, []),
        })
    return rows


def organic_referral_lead_series(company, *, date_start=None, date_end=None):
    """PUB95 — Comptes QUOTIDIENS de leads par CATÉGORIE de canal, pour la
    détection de cannibalisation par ``apps.adsengine`` (« les pubs créent-elles
    des leads ou déplacent-elles l'organique ? »). Point d'entrée cross-app
    LECTURE SEULE (jamais un import de ``apps.crm.models`` côté adsengine).

    Ne renvoie que des COMPTES par catégorie — ``paid`` (Meta/CTWA, piloté par la
    dépense pub), ``referral`` (parrainage / référence), ``organic`` (tout le reste
    non payant) — jamais la taxonomie de canal crm brute (même discipline que
    ``attribution_lead_rows``). Scopé société ; jamais un lead archivé.
    ``date_start``/``date_end`` (date, inclus) bornent ``date_creation``. Renvoie
    ``{'YYYY-MM-DD': {'paid': int, 'organic': int, 'referral': int}}``."""
    from .models import Lead

    qs = Lead.objects.filter(company=company, is_archived=False)
    if date_start is not None:
        qs = qs.filter(date_creation__date__gte=date_start)
    if date_end is not None:
        qs = qs.filter(date_creation__date__lte=date_end)

    paid_canaux = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA, Lead.Canal.GOOGLE_ADS}
    referral_canaux = {Lead.Canal.REFERENCE}

    series = {}
    for lead in qs.only('canal', 'date_creation'):
        if not lead.date_creation:
            continue
        key = lead.date_creation.date().isoformat()
        slot = series.setdefault(key, {'paid': 0, 'organic': 0, 'referral': 0})
        if lead.canal in paid_canaux:
            slot['paid'] += 1
        elif lead.canal in referral_canaux:
            slot['referral'] += 1
        else:
            slot['organic'] += 1
    return series


def lead_criteria_for_territoire(company, lead_id):
    """NTCRM1 — Contexte plat de matching territoire pour un lead réel,
    exposé aux AUTRES apps (historiquement le module territoires) au lieu
    d'un import direct de ``apps.crm.models`` — jamais cross-tenant : ``None``
    si le lead n'existe pas ou appartient à une autre société."""
    from .models import Lead

    try:
        lead = Lead.objects.get(pk=lead_id, company=company)
    except (Lead.DoesNotExist, ValueError, TypeError):
        return None
    return {
        'ville': lead.ville,
        'type_installation': lead.type_installation,
        'montant_estime': lead.montant_estime,
        'canal': lead.canal,
    }


def leads_recents_pour_couverture(company, jours=30):
    """NTCRM25 — Leads récents (``jours`` derniers jours) de ``company``, avec
    leur contexte plat de matching territoire (même forme que
    ``lead_criteria_for_territoire``), exposés au module territoires pour le
    rapport de couverture — jamais un import direct de ``apps.crm.models``
    depuis l'appelant."""
    from django.utils import timezone

    from .models import Lead

    depuis = timezone.now() - timezone.timedelta(days=jours)
    leads = Lead.objects.filter(company=company, date_creation__gte=depuis)
    return [
        {
            'id': lead.id,
            'nom': getattr(lead, 'nom', '') or getattr(lead, 'prenom', '') or f'Lead #{lead.id}',
            'ville': lead.ville,
            'type_installation': lead.type_installation,
            'montant_estime': lead.montant_estime,
            'canal': lead.canal,
        }
        for lead in leads
    ]


# ── PUB64 — Calculateur recyclage COLD (aide à la décision, pas une action) ──

# Buckets d'âge-au-COLD (jours). Le dernier segment est ouvert (180j+).
COLD_AGE_BUCKETS = (
    (0, 30, '0-30j'), (30, 90, '30-90j'), (90, 180, '90-180j'),
    (180, None, '180j+'),
)


# Jamais un taux de reconversion calculé sur un échantillon minuscule (bruit
# statistique) — sous ce seuil, ``rate`` reste ``None``.
MIN_SAMPLE_COLD_BUCKET = 3


def cold_reactivation_by_age_bucket(company):
    """PUB64 — Taux de reconversion RÉEL des leads passés COLD, par
    ÂGE-AU-COLD (date de création → PREMIÈRE entrée en COLD, lue dans le
    chatter ``LeadActivity`` field='stage' — les valeurs stockées sont les
    LIBELLÉS FR de ``STAGES.STAGE_LABELS``, jamais les clés brutes). Un lead
    sans trace d'entrée COLD explicite (créé directement COLD, activité non
    journalisée) est EXCLU — jamais un âge inventé. « Reconverti » = a
    quitté COLD au moins une fois ET est ACTUELLEMENT au stade SIGNED (non
    perdu).

    Un bucket avec <``MIN_SAMPLE_COLD_BUCKET`` leads renvoie ``rate=None``
    (bruit statistique, jamais un taux fabriqué). Renvoie une liste ordonnée
    ``[{'bucket', 'total', 'reconverted', 'rate'}, ...]``."""
    from . import stages as stage_mod
    from .models import Lead, LeadActivity

    cold_label = stage_mod.STAGE_LABELS[stage_mod.COLD]

    # Première entrée en COLD par lead (âge-au-COLD).
    first_cold_at = {}
    for row in (LeadActivity.objects
                .filter(lead__company=company,
                        kind=LeadActivity.Kind.MODIFICATION,
                        field='stage', new_value=cold_label)
                .order_by('lead_id', 'created_at')
                .values('lead_id', 'created_at')):
        first_cold_at.setdefault(row['lead_id'], row['created_at'])

    if not first_cold_at:
        return [{'bucket': label, 'total': 0, 'reconverted': 0, 'rate': None}
                for (_, _, label) in COLD_AGE_BUCKETS]

    # A quitté COLD au moins une fois (old_value=cold_label -> autre étape).
    left_cold_ids = set(
        LeadActivity.objects.filter(
            lead__company=company, kind=LeadActivity.Kind.MODIFICATION,
            field='stage', old_value=cold_label,
            lead_id__in=list(first_cold_at))
        .values_list('lead_id', flat=True))
    # Repli : certaines écritures historiques peuvent porter la clé brute
    # (jamais supposé, mais couvert honnêtement) — union, jamais un ET.
    left_cold_ids |= set(
        LeadActivity.objects.filter(
            lead__company=company, kind=LeadActivity.Kind.MODIFICATION,
            field='stage', old_value=stage_mod.COLD,
            lead_id__in=list(first_cold_at))
        .values_list('lead_id', flat=True))

    signed_now = set(
        Lead.objects.filter(
            id__in=list(first_cold_at), stage=stage_mod.SIGNED, perdu=False)
        .values_list('id', flat=True))
    reconverted_ids = left_cold_ids & signed_now

    creation_by_id = dict(
        Lead.objects.filter(id__in=list(first_cold_at))
        .values_list('id', 'date_creation'))

    buckets = {label: {'total': 0, 'reconverted': 0}
               for (_, _, label) in COLD_AGE_BUCKETS}
    for lead_id, cold_at in first_cold_at.items():
        created = creation_by_id.get(lead_id)
        if created is None or cold_at is None:
            continue
        age_days = (cold_at - created).days
        if age_days < 0:
            continue
        for lo, hi, label in COLD_AGE_BUCKETS:
            if age_days >= lo and (hi is None or age_days < hi):
                buckets[label]['total'] += 1
                if lead_id in reconverted_ids:
                    buckets[label]['reconverted'] += 1
                break

    result = []
    for (_, _, label) in COLD_AGE_BUCKETS:
        b = buckets[label]
        rate = (round(b['reconverted'] / b['total'], 4)
                if b['total'] >= MIN_SAMPLE_COLD_BUCKET else None)
        result.append({
            'bucket': label, 'total': b['total'],
            'reconverted': b['reconverted'], 'rate': rate,
        })
    return result


def new_leads_by_mode_meta(company, *, date_start, date_end):
    """PUB64 — Nombre de leads NOUVEAUX (créés sur ``[date_start, date_end]``)
    par ``type_installation``, restreint au canal Meta (META_ADS/
    WHATSAPP_CTWA) — le dénominateur du CAC-par-mode courant du calculateur
    de recyclage COLD. Un mode absent de la fenêtre est simplement absent du
    dict (jamais un 0 fabriqué). Renvoie ``{type_installation_ou_'': count}``."""
    from django.db.models import Count

    from .models import Lead

    meta_channels = [Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA]
    rows = (Lead.objects
            .filter(company=company, canal__in=meta_channels,
                    date_creation__date__gte=date_start,
                    date_creation__date__lte=date_end)
            .values('type_installation')
            .annotate(n=Count('id')))
    return {(r['type_installation'] or ''): r['n'] for r in rows}


def leads_export_rows(company, lead_ids):
    """NTMKT40 — lignes d'export (nom/prenom/email/telephone/ville) des leads
    d'un segment marketing, par ids OPAQUES. Lecture seule, scopé société (un
    id hors société est ignoré) — snapshot d'audit RGPD/CNDP, aucune donnée
    interne (score/notes)."""
    from .models import Lead

    if not lead_ids:
        return []
    rows = Lead.objects.filter(
        company=company, id__in=list(lead_ids),
    ).values('id', 'nom', 'prenom', 'email', 'telephone', 'ville')
    return list(rows)


def dernier_contact_lead(company, lead_id):
    """NTMKT34 — date/heure du dernier point de contact (``PointContact``,
    FG204) d'un lead, ou ``None``. Lecture seule, par id OPAQUE pour un
    appelant cross-app (``marketing``)."""
    from .models import PointContact

    pc = (PointContact.objects
          .filter(company=company, lead_id=lead_id)
          .order_by('-date_contact')
          .first())
    return pc.date_contact if pc else None


# ── NTMKT20 — Modèles d'attribution configurables sur PointContact (FG204) ──
# Complète ``revenu_attribue_campagne`` (XMKT17, implicitement dernier-touche
# par nom de campagne) SANS le modifier : ceci répartit le revenu d'UN devis
# signé entre les points de contact de son parcours, pour les 4 modèles
# standards — une aide à la décision, jamais un recalcul persistant.

ATTRIBUTION_MODELES = (
    'dernier_touche', 'premier_touche', 'lineaire', 'pondere_temporel',
)


# Demi-vie (jours) du modèle « pondéré temporel » — formule de dégradation
# temporelle standard (poids = 2^(-jours_avant_la_dernière_touche / demi_vie)).
_ATTRIBUTION_DEMI_VIE_JOURS = 7


def _attribution_part(point_contact, montant):
    return {
        'point_contact_id': point_contact.pk,
        'canal': point_contact.canal,
        'canal_libelle': point_contact.get_canal_display(),
        'date_contact': point_contact.date_contact,
        'revenu_attribue': str(montant),
    }


def _repartir_attribution(points, modele, total_revenu):
    """NTMKT20 — répartit ``total_revenu`` (Decimal) entre ``points``
    (``PointContact`` triés chronologiquement) selon ``modele``. Lecture
    pure : aucune écriture, aucun état modifié. La somme des montants
    répartis reste TOUJOURS égale à ``total_revenu`` au centime près."""
    from decimal import ROUND_HALF_UP, Decimal

    n = len(points)
    if n == 0 or not total_revenu:
        return []

    if modele == 'premier_touche':
        montants = [Decimal('0')] * n
        montants[0] = total_revenu
    elif modele == 'lineaire':
        part = (total_revenu / n).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        montants = [part] * n
        # Ajuste le DERNIER point pour que la somme reste exacte au centime
        # (l'arrondi par ligne peut sinon dériver de quelques centimes).
        montants[-1] = total_revenu - part * (n - 1)
    elif modele == 'pondere_temporel':
        derniere_date = points[-1].date_contact
        poids = [
            Decimal(str(2 ** (
                -max((derniere_date - p.date_contact).days, 0)
                / _ATTRIBUTION_DEMI_VIE_JOURS)))
            for p in points
        ]
        total_poids = sum(poids) or Decimal('1')
        montants = [
            (total_revenu * w / total_poids).quantize(Decimal('0.01'))
            for w in poids
        ]
        ecart = total_revenu - sum(montants)
        montants[-1] = montants[-1] + ecart
    else:  # 'dernier_touche' — défaut, comportement historique XMKT17.
        montants = [Decimal('0')] * n
        montants[-1] = total_revenu

    return [_attribution_part(p, m) for p, m in zip(points, montants)]


def attribution_comparaison_devis(devis):
    """NTMKT20 — pour un devis ACCEPTÉ, la répartition de son ``total_ttc``
    entre les points de contact (``PointContact``, FG204) du lead lié, pour
    les 4 modèles d'attribution côte à côte. ``None`` si le devis n'a pas de
    lead lié ou n'est pas accepté. Lecture seule, aide à la décision — ne
    modifie JAMAIS ``PointContact`` ni le devis."""
    from decimal import Decimal

    from .models import PointContact

    lead = getattr(devis, 'lead', None)
    if lead is None or getattr(devis, 'statut', None) != 'accepte':
        return None
    points = list(
        PointContact.objects.filter(company=lead.company_id, lead=lead))
    try:
        total_revenu = Decimal(str(devis.total_ttc or 0))
    except Exception:
        total_revenu = Decimal('0')
    return {
        'devis_id': devis.pk,
        'lead_id': lead.pk,
        'total_revenu': str(total_revenu),
        'nb_points_contact': len(points),
        'modeles': {
            modele: _repartir_attribution(points, modele, total_revenu)
            for modele in ATTRIBUTION_MODELES
        },
    }


# ── QA-COHERENCE — « signé fantôme », en LECTURE SEULE pour l'auditeur ──────
#
# Point d'entrée cross-app de l'auditeur de cohérence nocturne
# (``apps/ventes/coherence``) : même définition que
# ``services.lead_signe_sans_devis_actif`` (lead à SIGNED sans AUCUN devis au
# statut DOCUMENT « accepté »), mais en UNE requête par société au lieu d'une
# par lead. Exclusions assumées pour ne pas crier au loup :
#   * lead perdu ou archivé — le funnel n'y bouge plus, rien à décider ;
#   * lead importé d'Odoo — signé dans Odoo, il n'a en général AUCUN devis
#     dans l'ERP ; l'absence de devis n'y est pas une incohérence.
# L'étape vient de ``stages`` (STAGES.py, règle #2) ; le statut « accepte » est
# celui du DOCUMENT (couche séparée), déclaré une fois dans ``services``.
def leads_signes_sans_devis_accepte(company):
    """Leads SIGNED (natifs, vivants, non perdus) sans devis accepté.

    Renvoie une liste de dicts ``{'id', 'stage', 'source'}`` — aucune donnée
    personnelle (le nom n'est pas lu). Scopé à ``company``."""
    from .models import Lead
    from .services import _DEVIS_STATUT_ACCEPTE
    return list(
        Lead.objects
        .filter(lead_signe_q(), company=company)
        .exclude(source=Lead.Source.ODOO_IMPORT_TEST)
        .exclude(devis__statut=_DEVIS_STATUT_ACCEPTE)
        .order_by('pk')
        .values('id', 'stage', 'source'))


def champs_devis_auto_manquants(lead):
    """AGR124 — ``[{champ, label}]`` des groupes « devis automatique prêt »
    sans aucun champ rempli (``devis_auto.champs_manquants_detail``, AGR403) :
    point d'entrée cross-app du devis automatique serveur (``ventes``), qui
    ne lit jamais ``crm.devis_auto`` directement. Lecture seule."""
    from .devis_auto import champs_manquants_detail
    if lead is None:
        return []
    return champs_manquants_detail(lead)


def lead_en_attente_ou_veille(lead_id, today, *, company):
    """CIQ523 — le lead ``lead_id`` (de ``company`` seulement) attend-il une
    décision déclarée ?

    Vrai si le lead porte une étiquette d'attente POSÉE par la réponse
    « En attente d'un accord » (une par raison, CIQ508/AGR520), OU une étape
    de relance encore À FAIRE datée APRÈS ``today`` (manuelle, ou veille
    datée par ``rappel_le``). Lu par le beat nocturne QJ5 de ``ventes`` pour
    ne jamais parquer au Froid un lead qui attend. Lecture seule ; un lead
    d'une autre société n'est jamais lu (``False``)."""
    from .models import Lead, RelanceEtape
    from .services import ETIQUETTES_RAISON_ATTENTE, _lead_porte_tag

    if not lead_id or company is None:
        return False
    lead = Lead.objects.filter(pk=lead_id, company=company).first()
    if lead is None:
        return False
    if any(_lead_porte_tag(lead, tag) for tag in ETIQUETTES_RAISON_ATTENTE):
        return True
    return RelanceEtape.objects.filter(
        lead=lead, statut=RelanceEtape.Statut.A_FAIRE, due_date__gt=today,
    ).exists()
