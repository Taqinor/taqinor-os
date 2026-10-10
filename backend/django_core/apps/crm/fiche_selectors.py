"""Lectures « fiche » du lead (SPL89, scission de `selectors.py`) : lead de la
société, carte, provenance, segments, chatter, étapes, export.

Déplacement pur ; `apps.crm.selectors` ré-exporte chaque nom (frontière
inter-apps). N'importe jamais `.selectors` au niveau module.
"""
from .portee_selectors import (
    leads_visibles, lead_signe_q,
)


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
