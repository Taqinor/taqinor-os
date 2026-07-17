"""Sélecteurs de lecture de l'app ESG (Groupe NTESG).

``agreger_indicateurs_periode`` (NTESG2) est le cœur de l'agrégation
cross-app : il appelle EXCLUSIVEMENT des sélecteurs déjà exposés par d'autres
apps (jamais leurs modèles), avec des imports FONCTION-LOCAUX (pattern
standard du dépôt pour éviter tout cycle d'import au chargement). Sources
appelées aujourd'hui :

* ``apps.qhse.selectors.export_esg`` — indicateurs ESG bruts (E/S/G),
  QHSE40 ;
* ``apps.flotte.selectors.consommation_annuelle_flotte`` — carburant flotte
  (scope 1 mobile), XQHS21 ;
* ``apps.rh.selectors.tableau_bord_hse`` — accidents du travail / taux de
  fréquence-gravité (FG181/FG185) ;
* ``apps.rh.selectors.kpi_effectifs_absences`` — effectif actif (ARC40).

Le bilan carbone (``qhse.BilanCarbone``, QHSE39) n'a PAS de sélecteur exposé
dans ``apps.qhse.selectors`` au moment de ce lane (seul un ``ViewSet`` existe
côté qhse) : cette source est donc marquée ``disponible=False`` avec une
``raison`` explicite plutôt que de contourner la frontière cross-app en
important ``qhse.models`` — un futur lane qhse peut ajouter ce sélecteur, ce
qui activera la source ici sans aucun autre changement.

RÈGLE CHECKED-FACTS-ONLY : chaque source manquante, absente, ou dont
l'agrégat réel est vide/nul est marquée ``disponible=False`` avec une
``raison`` — JAMAIS comblée par un zéro silencieux. Une exception levée par
une source (app absente, signature qui a changé…) est capturée et dégrade
elle aussi en ``disponible=False`` plutôt que de faire échouer toute
l'agrégation.
"""


def _safe(source_fn, *args):
    """Filet de sécurité DÉFENSE-EN-PROFONDEUR autour d'un appel de source.

    Chaque ``_source_*`` capture déjà ses propres erreurs d'import/appel
    (raisons précises) ; ce filet supplémentaire garantit qu'une régression
    future dans UNE source (bug non anticipé) ne fait jamais planter toute
    l'agrégation — elle dégrade simplement cette seule source en
    ``disponible=False`` plutôt que de propager l'exception à l'appelant."""
    try:
        return source_fn(*args)
    except Exception as exc:  # noqa: BLE001 - dégradation gracieuse globale
        return {'disponible': False,
                'raison': f"erreur inattendue ({exc.__class__.__name__})"}


def _source_indicateurs_esg(company, annee):
    """Indicateurs ESG bruts (E/S/G) de l'année via ``qhse.selectors``."""
    try:
        from apps.qhse.selectors import export_esg
    except Exception as exc:  # noqa: BLE001 - app absente/erreur d'import
        return {'disponible': False,
                'raison': f"qhse indisponible ({exc.__class__.__name__})"}
    try:
        data = export_esg(company, annee=annee)
    except Exception as exc:  # noqa: BLE001 - dégradation gracieuse
        return {'disponible': False,
                'raison': f"erreur qhse.selectors.export_esg "
                          f"({exc.__class__.__name__})"}
    total = data.get('total', 0)
    if not total:
        return {'disponible': False,
                'raison': "Aucun IndicateurESG saisi pour cette période."}
    return {
        'disponible': True,
        'annee': annee,
        'total': total,
        'piliers': data.get('piliers', {}),
    }


def _source_bilan_carbone(company, annee):
    """Bilan carbone (QHSE39) — AUCUN sélecteur exposé par qhse pour l'instant.

    ``qhse.selectors`` ne porte pas encore de fonction de lecture pour
    ``BilanCarbone``/``LigneBilanCarbone`` (seul un ``ViewSet`` existe côté
    qhse) ; par respect strict de la frontière cross-app (jamais un import de
    ``qhse.models``), cette source reste ``disponible=False`` documentée
    jusqu'à ce qu'un lane qhse ajoute le sélecteur manquant.
    """
    return {
        'disponible': False,
        'raison': (
            "Aucun sélecteur qhse.selectors pour BilanCarbone au moment de "
            "ce lane (NTESG2) — nécessite un ajout côté apps/qhse/selectors.py, "
            "hors périmètre de cette app."),
    }


def _source_carburant_flotte(company, annee):
    """Carburant flotte (scope 1 mobile) via ``flotte.selectors``."""
    try:
        from apps.flotte.selectors import consommation_annuelle_flotte
    except Exception as exc:  # noqa: BLE001
        return {'disponible': False,
                'raison': f"flotte indisponible ({exc.__class__.__name__})"}
    try:
        conso = consommation_annuelle_flotte(company, annee)
    except Exception as exc:  # noqa: BLE001
        return {'disponible': False,
                'raison': f"erreur flotte.selectors."
                          f"consommation_annuelle_flotte "
                          f"({exc.__class__.__name__})"}
    gasoil = float(conso.get('gasoil_litres') or 0)
    essence = float(conso.get('essence_litres') or 0)
    kwh = float(conso.get('electrique_kwh') or 0)
    if not (gasoil or essence or kwh):
        return {'disponible': False,
                'raison': "Aucun plein carburant enregistré pour cette "
                          "année."}
    return {
        'disponible': True,
        'annee': annee,
        'gasoil_litres': gasoil,
        'essence_litres': essence,
        'electrique_kwh': kwh,
    }


def _source_social_hse(company, date_debut, date_fin):
    """AT/accidents-travail + heures travaillées via ``rh.selectors``."""
    try:
        from apps.rh.selectors import tableau_bord_hse
    except Exception as exc:  # noqa: BLE001
        return {'disponible': False,
                'raison': f"rh indisponible ({exc.__class__.__name__})"}
    within_days = 30
    if date_debut and date_fin:
        within_days = max((date_fin - date_debut).days, 0)
    try:
        hse = tableau_bord_hse(
            company, within_days=within_days, today=date_fin)
    except Exception as exc:  # noqa: BLE001
        return {'disponible': False,
                'raison': f"erreur rh.selectors.tableau_bord_hse "
                          f"({exc.__class__.__name__})"}
    a_des_donnees = bool(
        hse.get('accidents_total')
        or hse.get('presqu_accidents_total')
        or hse.get('heures_travaillees'))
    if not a_des_donnees:
        return {'disponible': False,
                'raison': "Aucun accident du travail, presqu'accident ni "
                          "heure travaillée enregistrés sur la période."}
    return {
        'disponible': True,
        'taux_frequence': hse.get('taux_frequence'),
        'taux_gravite': hse.get('taux_gravite'),
        'accidents_total': hse.get('accidents_total'),
        'accidents_avec_arret': hse.get('accidents_avec_arret'),
        'jours_arret_total': hse.get('jours_arret_total'),
        'presqu_accidents_total': hse.get('presqu_accidents_total'),
        'heures_travaillees': hse.get('heures_travaillees'),
    }


def _source_effectifs(company):
    """Effectif actif via ``rh.selectors.kpi_effectifs_absences``."""
    try:
        from apps.rh.selectors import kpi_effectifs_absences
    except Exception as exc:  # noqa: BLE001
        return {'disponible': False,
                'raison': f"rh indisponible ({exc.__class__.__name__})"}
    try:
        tuiles = kpi_effectifs_absences(company)
    except Exception as exc:  # noqa: BLE001
        return {'disponible': False,
                'raison': f"erreur rh.selectors.kpi_effectifs_absences "
                          f"({exc.__class__.__name__})"}
    effectif = 0
    for tuile in tuiles or []:
        if tuile.get('id') == 'rh_effectif_actif':
            effectif = tuile.get('valeur') or 0
            break
    if not effectif:
        return {'disponible': False,
                'raison': 'Aucun dossier employé actif.'}
    return {'disponible': True, 'effectif_actif': effectif}


def agreger_indicateurs_periode(company, date_debut, date_fin):
    """Agrégation cross-app EN LECTURE des indicateurs ESG d'une période
    (NTESG2).

    Appelle exclusivement des sélecteurs d'autres apps (jamais leurs
    modèles) ; chaque source dégrade en ``disponible=False`` (avec
    ``raison``) si elle est absente, vide, ou lève une exception — jamais
    d'exception propagée, jamais de zéro silencieux. Renvoie :

    ``{
        'periode': {'date_debut': iso|None, 'date_fin': iso|None,
                    'annee': int|None},
        'sources': {
            'indicateurs_esg': {...}, 'bilan_carbone': {...},
            'carburant_flotte': {...}, 'social_hse': {...},
            'effectifs': {...},
        },
    }``

    Sur une société sans AUCUNE donnée (aucun `company`, ou société vide),
    toutes les sources renvoient ``disponible=False`` sans lever d'exception.
    """
    annee = date_fin.year if date_fin else (
        date_debut.year if date_debut else None)
    periode = {
        'date_debut': date_debut.isoformat() if date_debut else None,
        'date_fin': date_fin.isoformat() if date_fin else None,
        'annee': annee,
    }
    if company is None:
        raison = 'Aucune société.'
        return {
            'periode': periode,
            'sources': {
                'indicateurs_esg': {'disponible': False, 'raison': raison},
                'bilan_carbone': {'disponible': False, 'raison': raison},
                'carburant_flotte': {'disponible': False, 'raison': raison},
                'social_hse': {'disponible': False, 'raison': raison},
                'effectifs': {'disponible': False, 'raison': raison},
            },
        }
    return {
        'periode': periode,
        'sources': {
            'indicateurs_esg': _safe(
                _source_indicateurs_esg, company, annee),
            'bilan_carbone': _safe(_source_bilan_carbone, company, annee),
            'carburant_flotte': _safe(
                _source_carburant_flotte, company, annee),
            'social_hse': _safe(
                _source_social_hse, company, date_debut, date_fin),
            'effectifs': _safe(_source_effectifs, company),
        },
    }


def donnees_effectives_periode(periode_esg):
    """Données ESG « effectives » d'une période (NTESG1/4/5).

    Une période FIGÉE (ou PUBLIÉE) relit son ``SnapshotESG`` gelé — jamais
    recalculé. Une période en BROUILLON calcule un aperçu LIVE via
    ``agreger_indicateurs_periode`` (utile pour le cockpit/wizard avant
    figeage, NTESG6/NTESG18) — cet aperçu n'est jamais persisté.
    """
    if periode_esg.est_figee:
        snapshot = getattr(periode_esg, 'snapshot', None)
        if snapshot is not None:
            return snapshot.donnees
    return agreger_indicateurs_periode(
        periode_esg.company, periode_esg.date_debut, periode_esg.date_fin)


# ── NTESG3 — couverture du catalogue GRI-lite ──────────────────────────────

def couverture_catalogue(company):
    """% du catalogue GRI-lite (NTESG3) effectivement renseigné par pilier.

    Compare les ``code`` du ``CatalogueIndicateurESG`` de la société aux
    codes réellement utilisés par des ``qhse.IndicateurESG`` (tous, toutes
    années confondues — lu via ``qhse.selectors.export_esg``, jamais le
    modèle). Renvoie ``{'piliers': {pilier: {'total': N, 'couverts': M,
    'pct': float}}, 'global_pct': float}``. Société vide/absente → structure
    à zéro, jamais d'exception.
    """
    from .models import CatalogueIndicateurESG

    vide = {'piliers': {}, 'global_pct': 0.0}
    if company is None:
        return vide

    codes_utilises = set()
    try:
        from apps.qhse.selectors import export_esg
        data = export_esg(company)
        codes_utilises = {
            (ligne.get('code') or '').strip().upper()
            for ligne in data.get('lignes', [])
            if (ligne.get('code') or '').strip()
        }
    except Exception:  # noqa: BLE001 - dégradation gracieuse
        codes_utilises = set()

    piliers = {}
    total_catalogue = 0
    total_couvert = 0
    qs = CatalogueIndicateurESG.objects.filter(company=company)
    for pilier_key, _label in CatalogueIndicateurESG.Pilier.choices:
        entries = [e for e in qs if e.pilier == pilier_key]
        total = len(entries)
        couverts = sum(
            1 for e in entries if e.code.strip().upper() in codes_utilises)
        pct = round(couverts * 100.0 / total, 1) if total else 0.0
        piliers[pilier_key] = {
            'total': total, 'couverts': couverts, 'pct': pct}
        total_catalogue += total
        total_couvert += couverts

    global_pct = (
        round(total_couvert * 100.0 / total_catalogue, 1)
        if total_catalogue else 0.0)
    return {'piliers': piliers, 'global_pct': global_pct}


# ── NTESG7 — trajectoire vs réalisé ────────────────────────────────────────

def _valeur_indicateur_annee(company, code, annee):
    """Valeur réelle d'un ``qhse.IndicateurESG`` (par ``code``) pour une
    année donnée, via ``qhse.selectors.export_esg`` — ``None`` si absente."""
    try:
        from apps.qhse.selectors import export_esg
    except Exception:  # noqa: BLE001
        return None
    try:
        data = export_esg(company, annee=annee)
    except Exception:  # noqa: BLE001
        return None
    code_norm = (code or '').strip().upper()
    for ligne in data.get('lignes', []):
        if (ligne.get('code') or '').strip().upper() == code_norm:
            valeur = ligne.get('valeur')
            if valeur is None:
                continue
            try:
                return float(valeur)
            except (TypeError, ValueError):
                continue
    return None


def trajectoire_vs_realise(objectif):
    """Compare la trajectoire linéaire théorique d'un objectif ESG (NTESG7)
    aux valeurs RÉELLEMENT atteintes, année par année.

    Interpole linéairement entre (``annee_reference``, ``valeur_reference``)
    et (``annee_cible``, ``valeur_cible``). Pour chaque année de
    ``annee_reference`` à ``annee_cible`` inclus, lit la valeur réelle via
    ``qhse.selectors.export_esg`` (``apps.esg.selectors._valeur_indicateur_
    annee``) ; les années SANS donnée réelle disponible ne sont jamais
    extrapolées au-delà de la dernière année réelle connue — elles
    apparaissent avec ``reel=None`` et ``ecart_pct=None``.

    Renvoie une liste triée par année :
    ``[{'annee': int, 'theorique': float, 'reel': float|None,
        'ecart_pct': float|None}, ...]``.
    """
    annee_ref = objectif.annee_reference
    annee_cible = objectif.annee_cible
    val_ref = float(objectif.valeur_reference)
    val_cible = float(objectif.valeur_cible)
    span = annee_cible - annee_ref

    resultats = []
    for annee in range(annee_ref, annee_cible + 1):
        if span:
            theorique = val_ref + (val_cible - val_ref) * (
                (annee - annee_ref) / span)
        else:
            theorique = val_ref
        theorique = round(theorique, 4)

        reel = _valeur_indicateur_annee(
            objectif.company, objectif.indicateur_code, annee)
        ecart_pct = None
        if reel is not None and theorique:
            ecart_pct = round((reel - theorique) * 100.0 / abs(theorique), 2)
        elif reel is not None and not theorique:
            ecart_pct = None
        resultats.append({
            'annee': annee,
            'theorique': theorique,
            'reel': reel,
            'ecart_pct': ecart_pct,
        })
    return resultats


# ── NTESG11 — comparateur multi-période (N vs N-1) ─────────────────────────

def comparer_periodes(periode_reference, periode_n):
    """Comparateur multi-période N vs N-1 (NTESG11).

    Compare, pilier par pilier puis indicateur par indicateur (code
    ``qhse.IndicateurESG``), les données effectives (NTESG1/2,
    ``donnees_effectives_periode`` — snapshot gelé si figée, aperçu live
    sinon) de deux périodes. Un indicateur présent dans une seule des deux
    périodes est signalé ``comparable=False`` (« non comparable ») — JAMAIS
    traité comme une variation de +100 %/-100 %.

    Renvoie ``{'periode_reference': {...}, 'periode_n': {...},
    'piliers': {pilier: [{'code', 'libelle', 'comparable', ...}, ...]}}``.
    """
    donnees_ref = donnees_effectives_periode(periode_reference)
    donnees_n = donnees_effectives_periode(periode_n)
    piliers_ref = (
        (donnees_ref.get('sources') or {}).get('indicateurs_esg') or {}
    ).get('piliers') or {}
    piliers_n = (
        (donnees_n.get('sources') or {}).get('indicateurs_esg') or {}
    ).get('piliers') or {}

    tous_piliers = sorted(set(piliers_ref) | set(piliers_n))
    resultat_piliers = {}
    for pilier in tous_piliers:
        lignes_ref = {
            ligne.get('code'): ligne
            for ligne in (piliers_ref.get(pilier) or {}).get('lignes', [])
            if ligne.get('code')
        }
        lignes_n = {
            ligne.get('code'): ligne
            for ligne in (piliers_n.get(pilier) or {}).get('lignes', [])
            if ligne.get('code')
        }
        codes = sorted(set(lignes_ref) | set(lignes_n))
        entrees = []
        for code in codes:
            ligne_ref = lignes_ref.get(code)
            ligne_n = lignes_n.get(code)
            libelle = (ligne_n or ligne_ref or {}).get('libelle')
            if ligne_ref is None or ligne_n is None:
                entrees.append({
                    'code': code, 'libelle': libelle, 'comparable': False,
                    'raison': "Indicateur absent d'une des deux périodes.",
                })
                continue
            try:
                valeur_ref = (
                    float(ligne_ref['valeur'])
                    if ligne_ref.get('valeur') is not None else None)
                valeur_n = (
                    float(ligne_n['valeur'])
                    if ligne_n.get('valeur') is not None else None)
            except (TypeError, ValueError):
                valeur_ref = valeur_n = None
            if valeur_ref is None or valeur_n is None:
                entrees.append({
                    'code': code, 'libelle': libelle, 'comparable': False,
                    'raison': 'Valeur manquante ou non numérique.',
                })
                continue
            variation_abs = round(valeur_n - valeur_ref, 4)
            variation_pct = (
                round((valeur_n - valeur_ref) * 100.0 / abs(valeur_ref), 2)
                if valeur_ref else None)
            entrees.append({
                'code': code, 'libelle': libelle, 'comparable': True,
                'valeur_reference': valeur_ref, 'valeur_n': valeur_n,
                'variation_abs': variation_abs,
                'variation_pct': variation_pct,
            })
        resultat_piliers[pilier] = entrees

    return {
        'periode_reference': {
            'id': periode_reference.pk, 'libelle': periode_reference.libelle},
        'periode_n': {'id': periode_n.pk, 'libelle': periode_n.libelle},
        'piliers': resultat_piliers,
    }


__all__ = [
    'agreger_indicateurs_periode',
    'donnees_effectives_periode',
    'couverture_catalogue',
    'trajectoire_vs_realise',
    'comparer_periodes',
]
