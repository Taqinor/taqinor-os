"""Lectures cross-app du domaine « Paramètres / Société ».

Point d'entrée UNIQUE pour les autres apps (ventes, crm, …) qui ont besoin de
l'identité société ou des repères tarifaires : elles passent par ces fonctions
plutôt que d'importer ``CompanyProfile`` directement, ce qui garde une seule
source de vérité et respecte la frontière cross-app.

Tout est en lecture seule. Aucun de ces accès n'écrit ni ne fabrique de valeur :
on lit le profil de la société (ou le profil pk=1 par défaut) et on renvoie ses
champs tels quels, avec un repli explicite quand le profil est absent.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

#: Rayon maximal (km) d'une preuve « ville voisine ». Au-delà, « une
#: installation comparable à la vôtre » ne serait plus vrai : mieux vaut
#: n'envoyer aucune preuve (la phrase est alors OMISE, MRY13) qu'en montrer
#: une à l'autre bout du pays.
RAYON_PREUVE_KM = 60


def _profile(company):
    """Profil société (ou pk=1 par défaut). Repli None si la table n'existe pas."""
    def _load():
        try:
            from apps.parametres.models import CompanyProfile
            return CompanyProfile.get(company=company)
        except Exception:  # noqa: BLE001 — un PDF/simulateur ne casse jamais ici
            return None

    # SCA43 / NTPLT16 — mémo PAR REQUÊTE (contextvar), MÊME clé que
    # ``ventes.utils.company_settings._profile`` : les deux accesseurs lisent le
    # MÊME ``CompanyProfile`` de la société, donc ils partagent un seul objet
    # mémorisé le temps d'une requête. Hors requête → cache inactif (inchangé).
    from core import request_cache
    return request_cache.memoize(
        ("parametres.company_profile", getattr(company, "id", None)), _load)


def company_identity(company) -> dict:
    """Identité légale + coordonnées d'une société pour les documents (devis/PDF).

    Renvoie un dict sérialisable JSON. Toutes les valeurs sont des chaînes
    (vides quand non renseignées) sauf ``couleur_principale`` qui porte le
    hex de la charte. Aucune valeur codée en dur d'un tenant particulier :
    quand aucun profil n'existe, tous les champs texte sont vides et le moteur
    PDF applique ses littéraux historiques par défaut.
    """
    p = _profile(company)
    if p is None:
        return {
            "nom": "", "adresse": "", "email": "", "telephone": "",
            "ice": "", "identifiant_fiscal": "", "rc": "", "patente": "",
            "cnss": "", "rib": "", "banque": "", "couleur_principale": "",
            "site_web": "",
        }
    return {
        "nom": p.nom or "",
        "adresse": p.adresse or "",
        "email": p.email or "",
        "telephone": p.telephone or "",
        "ice": p.ice or "",
        "identifiant_fiscal": p.identifiant_fiscal or "",
        "rc": p.rc or "",
        "patente": p.patente or "",
        "cnss": p.cnss or "",
        "rib": p.rib or "",
        "banque": p.banque or "",
        "couleur_principale": p.couleur_principale or "",
        # SCA27 — site web (pilote la ligne site + la base des liens fiches du
        # PDF résidentiel). Vide → littéraux historiques (taqinor.ma).
        "site_web": getattr(p, "site_web", "") or "",
    }


def adresse_affichage(company) -> str:
    """NTI18N22 — adresse « effective » d'une société pour un document (PDF).

    Priorité : si AU MOINS UN des champs structurés (`adresse_rue`,
    `adresse_code_postal`, `adresse_ville`, `adresse_pays`) est renseigné, on
    reconstruit une ligne d'adresse à partir d'eux ; sinon on retombe sur le
    TextField libre historique `adresse`, tel quel — NON-RÉGRESSION totale
    pour une société qui n'a jamais rempli les champs structurés (NTI18N22).
    Aucune exception : une société sans profil renvoie une chaîne vide.
    """
    p = _profile(company)
    if p is None:
        return ""
    parties_structurees = [
        (getattr(p, "adresse_rue", "") or "").strip(),
        (getattr(p, "adresse_code_postal", "") or "").strip(),
        (getattr(p, "adresse_ville", "") or "").strip(),
        (getattr(p, "adresse_pays", "") or "").strip(),
    ]
    if any(parties_structurees):
        rue, code_postal, ville, pays = parties_structurees
        ligne_ville = " ".join(x for x in (code_postal, ville) if x)
        return ", ".join(x for x in (rue, ligne_ville, pays) if x)
    return (p.adresse or "").strip()


def statut_libelle(company, domaine: str, cle: str, langue: str = 'fr') -> str:
    """NTI18N25 — libellé d'affichage d'un statut métier, langue-consciente.

    Ordre de priorité :
      1. surcharge société `StatutConfig` (N58) — TOUJOURS en français (un
         override manuel est un texte FR saisi par le tenant) : ne s'applique
         que si `langue == 'fr'`, jamais utilisée comme traduction EN/AR ;
      2. `i18n_labels.STATUT_LABELS` (NTI18N25) ;
      3. la clé canonique brute (jamais d'exception).

    Ne renomme ni ne réordonne jamais la clé canonique elle-même — ceci ne
    calcule qu'un LIBELLÉ, jamais une transition d'état.

    NTI18N51 — quand la langue demandée oblige à replier sur le français, le
    repli est COMPTÉ (``traductions_manquantes.enregistrer_repli``) pour que la
    lacune remonte d'elle-même à l'équipe une fois par semaine, au lieu
    d'attendre qu'un client la signale. Aucune écriture quand la traduction
    existe, et l'échec du compteur n'empêche jamais le libellé de sortir.
    """
    from .i18n_labels import statut_label, variante_absente
    from .models_statuses import StatutConfig

    if langue == 'fr' and company is not None:
        override = StatutConfig.objects.filter(
            company=company, domaine=domaine, cle=cle).first()
        if override is not None and override.libelle:
            return override.libelle
    if company is not None and variante_absente(domaine, cle, langue):
        from .traductions_manquantes import cle_statut, enregistrer_repli
        enregistrer_repli(company, langue, cle_statut(domaine, cle))
    return statut_label(domaine, cle, langue)


def langue_interface_verrouillee(company) -> bool:
    """NTI18N35 — société avec la langue d'interface verrouillée ?

    Point d'entrée cross-app PRÊT pour ``authentication.views.
    LangueInterfaceView`` (PATCH /auth/me/langue/, hors périmètre de cette
    lane) : cet endpoint devra appeler cette fonction et renvoyer 403 quand
    elle est vraie. Jamais d'exception — une société sans profil (ou hors
    requête) n'est jamais verrouillée."""
    p = _profile(company)
    return bool(p is not None and p.langue_interface_verrouillee)


def langue_par_defaut_effective(company) -> str | None:
    """NTI18N35 — langue à imposer si l'interface est verrouillée.

    Renvoie ``CompanyProfile.langue_repli`` quand
    ``langue_interface_verrouillee`` est vrai, sinon ``None`` (« pas
    d'imposition » — l'utilisateur garde sa préférence individuelle,
    comportement historique)."""
    p = _profile(company)
    if p is None or not p.langue_interface_verrouillee:
        return None
    return p.langue_repli


def tariff_for(company) -> dict:
    """Repères ROI/tarifaires CANONIQUES d'une société (source unique — DC5).

    CompanyProfile est la source de vérité déjà consommée ; tout lecteur (moteur
    de devis, simulateur) passe par ici plutôt que de dupliquer les constantes.
    Repli sur les défauts historiques du simulateur (1.75 MAD/kWh, 1600 kWh/kWc,
    rendement 0.8, TVA 20/10) quand aucun profil n'existe.
    """
    p = _profile(company)
    if p is None:
        return {
            "onee_tarif_kwh": 1.75,
            "productible_kwh_kwc": 1600.0,
            "rendement_global": 0.8,
            "tva_standard": 20.0,
            "tva_panneaux": 10.0,
        }

    def _f(val, default):
        try:
            return float(val)
        except (TypeError, ValueError):
            return float(default)

    return {
        "onee_tarif_kwh": _f(p.onee_tarif_kwh, Decimal("1.75")),
        "productible_kwh_kwc": _f(p.productible_kwh_kwc, Decimal("1600.0")),
        "rendement_global": _f(p.rendement_global, Decimal("0.8")),
        "tva_standard": _f(p.tva_standard, Decimal("20")),
        "tva_panneaux": _f(p.tva_panneaux, Decimal("10")),
    }


def residential_tranches_for(company) -> dict | None:
    """Barème résidentiel ONEE (paliers TTC) RÉGLÉ par une société — ordre
    fondateur 19/08/2026 (« correct all prices and keep them changable in the
    settings »). Renvoie ``None`` si aucune société n'est fournie ou si rien
    n'a été édité dans Paramètres → Tarification & ROI : l'appelant retombe
    alors sur les défauts 2026 codés en dur dans le moteur de devis (une seule
    source de vérité par défaut — jamais dupliquée ici).

    Lu par ``apps.ventes.quote_engine.builder`` (import paresseux/local, la
    frontière cross-app CLAUDE.md est respectée dans CE sens : ``ventes`` lit
    ``parametres`` via ce sélecteur ; ``parametres`` — app FONDATION — ne
    connaît JAMAIS ``ventes`` en retour). Renvoie donc un dict PUR (aucune
    classe de ``ventes.quote_engine.pricing`` importée ici) :
        {"pairs": [(plafond_kWh_nominal | None, prix_MAD_kWh_TTC), ...],
         "selective_threshold": int, "boundary_tolerance": int}
    prêt à reconstruire l'équivalent de ``pricing.TrancheTable`` côté appelant.

    ``TariffSettings.residential_tiers`` stocke des bornes déjà EFFECTIVES
    (210/310/510 = 200/300/500 + tolérance, cf. models_tariff.py) ; on les
    reconvertit ici en bornes NOMINALES (− tolérance, uniquement AU-DELÀ du
    seuil sélectif — la zone progressive n'est jamais décalée) pour rester
    compatible avec le format nominal+tolérance qu'attend ``TrancheTable``.
    """
    if company is None:
        return None
    try:
        from apps.parametres.models_tariff import TariffSettings
        settings = TariffSettings.get(company=company)
    except Exception:  # noqa: BLE001 — un PDF/une liste ne casse jamais ici
        return None
    if not settings.residential_tiers:
        return None
    seuil = int(settings.selective_threshold_kwh or 150)
    tol = int(settings.tolerance_kwh or 0)
    pairs = []
    for t in settings.effective_tiers():
        mk = t["max_kwh"]
        if mk is not None and mk > seuil:
            mk = mk - tol
        pairs.append((mk, float(t["prix_kwh_ttc"])))
    return {"pairs": pairs, "selective_threshold": seuil, "boundary_tolerance": tol}


def _reglages_tarif_existants(company):
    """``TariffSettings`` DÉJÀ enregistré pour ``company``, ou ``None``.

    Lecture pure (jamais de ``get_or_create`` : un sélecteur n'écrit pas) —
    une société qui n'a jamais ouvert l'écran Tarification n'a rien saisi.
    """
    if company is None:
        return None
    from apps.parametres.models_tariff import TariffSettings
    return TariffSettings.objects.filter(company=company).first()


def tou_pour(company) -> dict | None:
    """CALX274 — grille horaire (time-of-use) SAISIE par la société, ou ``None``.

    ``None`` tant que les tranches horaires, leurs tarifs, la SOURCE et sa
    DATE ne sont pas tous saisis dans Paramètres → Tarification & ROI :
    l'appelant publie alors l'économie horaire ``None`` avec
    ``apps.parametres.tariff.MOTIF_TOU_NON_SAISI`` — jamais un tarif supposé.
    Forme rendue : voir ``apps.parametres.tariff.tou_depuis_reglages``.

    CALX275 — ``heures`` est soit une liste de 24 libellés (toute l'année),
    soit ``{saison: [24 libellés]}`` (saisons ``tariff.SAISONS_TOU``) : le
    lecteur résout l'heure d'un mois donné par
    ``apps.ventes.solar_design.tranches_du_mois`` (saison saisie, sinon
    ``annuel``, sinon ``tranche: None`` + motif — jamais « pleine » supposée).
    """
    from apps.parametres.tariff import tou_depuis_reglages
    return tou_depuis_reglages(_reglages_tarif_existants(company))


# ── Catalogue « Réalisations » — la preuve de la touche J4 ─────────────────
# Ordre fondateur du 08/09/2026 : le message d'après-devis « Voici une
# installation comparable à la vôtre » ne se remplit plus à la main. Ces
# lectures choisissent l'installation RÉELLE à montrer. Tout est PUR : aucune
# écriture, et rien n'est fabriqué — sans candidate crédible on rend ``None``,
# et le rendu OMET la phrase (MRY13) au lieu d'inventer une preuve.


def _ville_canonique(texte):
    """Nom canonique du gazetier pour ``texte``, sinon le texte nettoyé.

    Même règle que ``villes_resolution.corriger_ville`` (VREF 07/09/2026) :
    seule une résolution CONFIANTE (``exacte``/``corrigee``) remplace le
    texte ; ``ambigue``/``inconnue`` le laissent intact — on ne devine pas
    une ville."""
    from .villes_resolution import corriger_ville
    return corriger_ville((texte or "").strip())


def _cle_recence(realisation):
    """Clé de tri « la plus récente d'abord » (mise en service, puis id).

    Une mise en service inconnue n'est jamais promue devant une date réelle :
    elle prend la date minimale."""
    return (realisation.mise_en_service or datetime.date.min,
            realisation.id or 0)


def _puissance_du_dernier_devis(lead):
    """kWc du dernier devis calepiné du lead, ou ``None``.

    Lecture cross-app par le SÉLECTEUR de ``ventes``
    (``conception_pour_lead``), jamais par ses modèles — frontière M3. Ce
    sélecteur ne regarde que les devis PORTANT UN CALEPINAGE (``roof_layout``)
    et retombe sur ``etude_params['puissance_kwc']`` : un lead sans conception
    3D rend donc ``None``, ce qui fait simplement tomber le départage par
    puissance sur « la plus récente ». Aucun chiffre n'est fabriqué ici."""
    try:
        from apps.ventes.selectors import conception_pour_lead
        kwc = (conception_pour_lead(lead, lead.company) or {}).get("kwc")
        return float(kwc) if kwc not in (None, "") else None
    except Exception:  # noqa: BLE001 — un message ne casse jamais sur ce point
        return None


def _repli(lignes, cible):
    """Repli fondateur (08/09/2026) : sans réalisation dans la ville ni dans le
    rayon, on montre quand même la DERNIÈRE installation de la société — celle
    dont la puissance est la plus proche de ``cible`` (kWc du devis du lead) si
    elle est connue, sinon la plus récente. ``lignes`` est trié « la plus
    récente d'abord »."""
    if not lignes:
        return None
    chiffrees = [r for r in lignes if r.puissance_kwc is not None]
    if cible is not None and chiffrees:
        return min(chiffrees,
                   key=lambda r: abs(float(r.puissance_kwc) - cible))
    return lignes[0]


def realisation_pour_lead(lead):
    """La réalisation à MONTRER à ce lead, ou ``None``.

    Ordre de choix, strictement :

    a. **même ville** (nom canonique du gazetier des deux côtés) — s'il y en a
       plusieurs, celle dont la puissance est la plus proche de celle du
       dernier devis du lead quand elle est connue, sinon la plus récente ;
    b. sinon la **plus proche** à vol d'oiseau (haversine sur les coordonnées
       du gazetier), dans la limite de ``RAYON_PREUVE_KM`` ;
    c. sinon (repli fondateur 08/09/2026, lead de Sidi Hashass à 400 km de
       tout chantier : « show our last installation… similar size ») la
       DERNIÈRE installation de la société — puissance la plus proche du
       devis du lead si elle est connue, sinon la plus récente. La ville
       affichée reste la SIENNE, vraie : « comparable » parle de la taille,
       jamais du lieu.

    La ville du lead est ``ville_reference`` (ville ERP de rattachement choisie
    sur l'écran « Vérifier la ville ») quand elle existe, sinon ``ville`` — le
    texte tapé par le client. Un lead SANS ville reçoit le repli (c).

    Lecture PURE (aucune écriture), scopée à ``lead.company``."""
    company = getattr(lead, "company", None) if lead is not None else None
    if company is None:
        return None

    from .models_realisations import Realisation
    from .villes_maroc import coordonnees_ville
    from .villes_resolution import _haversine_km  # même formule, une seule fois

    lignes = sorted(
        Realisation.objects.filter(company=company, actif=True),
        key=_cle_recence, reverse=True)
    if not lignes:
        return None

    ville_lead = _ville_canonique(
        (getattr(lead, "ville_reference", "") or "").strip()
        or (getattr(lead, "ville", "") or "").strip())
    if not ville_lead:
        return _repli(lignes, _puissance_du_dernier_devis(lead))

    # (a) Même ville. ``lignes`` est déjà trié du plus récent au plus ancien :
    # ``min`` renvoyant le PREMIER minimum, un ex æquo de puissance revient
    # naturellement à la réalisation la plus récente.
    memes = [r for r in lignes
             if _ville_canonique(r.ville).casefold() == ville_lead.casefold()]
    if memes:
        if len(memes) == 1:
            return memes[0]
        cible = _puissance_du_dernier_devis(lead)
        chiffrees = [r for r in memes if r.puissance_kwc is not None]
        if cible is not None and chiffrees:
            return min(chiffrees,
                       key=lambda r: abs(float(r.puissance_kwc) - cible))
        return memes[0]

    # (b) La plus proche, dans le rayon. Une ville absente du gazetier (des
    # deux côtés) n'a pas de coordonnées : elle ne participe pas au calcul
    # plutôt que d'être placée arbitrairement.
    origine = coordonnees_ville(ville_lead)
    if origine is None:
        return _repli(lignes, _puissance_du_dernier_devis(lead))
    meilleure, distance_min = None, None
    for realisation in lignes:
        coords = coordonnees_ville(realisation.ville)
        if coords is None:
            continue
        distance = _haversine_km(origine, coords)
        if distance > RAYON_PREUVE_KM:
            continue
        if distance_min is None or distance < distance_min:
            meilleure, distance_min = realisation, distance
    if meilleure is not None:
        return meilleure
    return _repli(lignes, _puissance_du_dernier_devis(lead))
