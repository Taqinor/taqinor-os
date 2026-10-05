"""Lectures du module « Visites terrain » (``apps.visites``) — VTA3.

L'AGRÉGAT DE LA VISITE TECHNIQUE TERRAIN
----------------------------------------
``contexte_visite_terrain`` est la SOURCE DE VÉRITÉ de la forme servie par
``GET /api/django/visites/visites/<pk>/`` (contrat PACT10
``apps/visites/contract_samples/visite_terrain.json``). Les deux écrans —
wizard commercial mobile et revue bureau d'études — la lisent en UN appel.

LA COMPLÉTUDE EST CALCULÉE ICI, JAMAIS DANS LE NAVIGATEUR : le front AFFICHE
``completude.manquants``, il ne la reconstitue pas. Et cet agrégat n'émet
AUCUN verdict technique — il montre les mesures relevées ; c'est le bureau
d'études qui juge au moment du feu vert.

FRONTIÈRE M3 : toute lecture de ``crm``/``ventes`` passe par LEURS selectors,
en import PARESSEUX (fonction-local) — jamais par un import de leurs modèles.
"""

import re

# Ré-export M3 (revue Fable 15/09) — le VOCABULAIRE de qualification (module
# pur, zéro modèle) fait partie de la surface de LECTURE de l'app : les
# autres apps (crm) le consomment d'ICI, jamais du module interne.
from .qualification import (  # noqa: F401
    conseil, devis_a_reprendre, jours_avant_rappel, phrase, rappel_explicite,
)


def _visite_url_photo(attachment_id):
    """URL du proxy Django qui sert une pièce jointe (jamais MinIO direct)."""
    return f'/api/django/records/attachments/{attachment_id}/download/'


def _visite_decimal(valeur):
    """Un ``Decimal`` de coordonnée rendu en nombre JSON, ou ``None``."""
    return None if valeur is None else float(valeur)


def _visite_horodatage(valeur):
    """Un horodatage ISO, ou ``None`` — jamais une chaîne vide trompeuse."""
    return None if valeur is None else valeur.isoformat()


def _visite_photo(media):
    attachment = media.attachment
    return {
        'id': media.id,
        'url': _visite_url_photo(media.attachment_id),
        'filename': getattr(attachment, 'filename', '') or '',
        'gps_lat': _visite_decimal(media.gps_lat),
        'gps_lng': _visite_decimal(media.gps_lng),
        'commentaire': media.commentaire or '',
        'a_refaire': bool(media.a_refaire),
        'motif_refaire': media.motif_refaire or '',
    }


def _visite_etat_slot(declaration, photos):
    """``manquant`` / ``ok`` / ``a_refaire`` pour UN slot photo.

    Une photo marquée à refaire prime : tant qu'elle n'est pas remplacée, le
    slot n'est pas servi (peu importe le compte brut de photos).
    """
    if any(photo['a_refaire'] for photo in photos):
        return 'a_refaire'
    servies = [photo for photo in photos if not photo['a_refaire']]
    if len(servies) >= declaration['min_photos']:
        return 'ok'
    return 'manquant'


def _gabarit(visite):
    """AGR412 — le gabarit de LA visite (``toiture`` par défaut)."""
    return getattr(visite, 'gabarit', None) or 'toiture'


def _visite_checklist(visite, medias):
    from . import visite_checklist as checklist

    par_slot = {}
    for media in medias:
        par_slot.setdefault(media.slot_code, []).append(_visite_photo(media))
    blocs = []
    for cat in checklist.categories(_gabarit(visite)):
        slots = []
        for declaration in cat['slots']:
            photos = par_slot.get(declaration['code'], [])
            slots.append({
                'code': declaration['code'],
                'libelle': declaration['libelle'],
                'guide': declaration['guide'],
                'requis': declaration['requis'],
                'min_photos': declaration['min_photos'],
                'etat': _visite_etat_slot(declaration, photos),
                'photos': photos,
            })
        blocs.append({
            'categorie': cat['categorie'],
            'libelle': cat['libelle'],
            'slots': slots,
        })
    return blocs


def _visite_mesures(visite):
    """Les mesures DÉCLARÉES, remplies des valeurs saisies (``None`` sinon).

    Rendre la structure complète — et non le seul JSON stocké — garantit que
    l'écran affiche toujours les mêmes champs, dans le même ordre, qu'ils
    soient renseignés ou pas.
    """
    from . import visite_checklist as checklist

    saisies = visite.mesures if isinstance(visite.mesures, dict) else {}
    rendu = {}
    gabarit = _gabarit(visite)
    for cat in checklist.categories(gabarit):
        champs = cat['mesures']
        # CIQ600 — le contrat ``ci`` rend aussi les catégories sans mesure
        # (``general: {}``) ; les autres gabarits restent identiques.
        if not champs and gabarit != checklist.GABARIT_CI:
            continue
        valeurs = saisies.get(cat['categorie']) or {}
        rendu[cat['categorie']] = {
            champ['code']: valeurs.get(
                champ['code'],
                [] if champ['nature'] == checklist.LISTE else None)
            for champ in champs
        }
    return rendu


def zones_toiture_saisies(visite):
    """CIQ602 — les zones de toiture SAISIES d'une visite ``ci``, telles que
    stockées (liste de dicts) ; ``[]`` pour tout autre gabarit ou sans saisie.
    Fonction PURE sur l'objet reçu."""
    if _gabarit(visite) != 'ci':
        return []
    saisies = visite.mesures if isinstance(visite.mesures, dict) else {}
    bloc = saisies.get('toiture_ci') or {}
    zones = bloc.get('zones_toiture') if isinstance(bloc, dict) else None
    return [z for z in (zones or []) if isinstance(z, dict)]


def _non_releves_plats(visite):
    """CIQ601 — les états « non relevé » d'une visite ``ci`` à plat :
    ``{'<categorie>.<clé>': motif}`` (forme du contrat ``exemple_ci``). Vide
    pour tout autre gabarit : l'état n'existe que pour un site professionnel."""
    from . import visite_checklist as checklist

    if _gabarit(visite) != checklist.GABARIT_CI:
        return {}
    saisies = visite.mesures if isinstance(visite.mesures, dict) else {}
    plats = {}
    for cat in checklist.categories(checklist.GABARIT_CI):
        bloc = saisies.get(cat['categorie']) or {}
        etats = bloc.get(checklist.CLE_NON_RELEVES) or {}
        if not isinstance(etats, dict):
            continue
        for cle, motif in etats.items():
            if motif in checklist.MOTIFS_NON_RELEVE:
                plats[f"{cat['categorie']}.{cle}"] = motif
    return plats


def _visite_manquants(blocs, mesures_rendues, gabarit=None,
                      non_releves=None):
    from . import visite_checklist as checklist

    # CIQ601 — une mesure « non relevée » AVEC son motif est traitée : elle
    # ne bloque pas « Terminer ».
    non_releves = non_releves or {}
    manquants = []
    for bloc in blocs:
        for slot in bloc['slots']:
            if slot['etat'] == 'a_refaire':
                manquants.append({
                    'type': checklist.MANQUE_PHOTO_A_REFAIRE,
                    'categorie': bloc['categorie'],
                    'code': slot['code'],
                    'libelle': slot['libelle'],
                })
            elif slot['requis'] and slot['etat'] == 'manquant':
                manquants.append({
                    'type': checklist.MANQUE_PHOTO,
                    'categorie': bloc['categorie'],
                    'code': slot['code'],
                    'libelle': slot['libelle'],
                })
    for cat in checklist.categories(gabarit):
        valeurs = mesures_rendues.get(cat['categorie']) or {}
        for champ in cat['mesures']:
            if champ['nature'] == checklist.LISTE:
                for code, libelle in checklist.liste_manquants(
                        champ, valeurs.get(champ['code'])):
                    if f"{cat['categorie']}.{code}" in non_releves:
                        continue
                    manquants.append({
                        'type': checklist.MANQUE_MESURE,
                        'categorie': cat['categorie'],
                        'code': code,
                        'libelle': libelle,
                    })
                continue
            if not checklist.mesure_requise(champ, valeurs):
                continue
            valeur = valeurs.get(champ['code'])
            if (valeur is None or valeur == '') and (
                    f"{cat['categorie']}.{champ['code']}" in non_releves):
                continue
            if valeur is None or valeur == '':
                manquants.append({
                    'type': checklist.MANQUE_MESURE,
                    'categorie': cat['categorie'],
                    'code': champ['code'],
                    'libelle': champ['libelle'],
                })
    return manquants


def _visite_client_panel(lead):
    """Panneau LECTURE SEULE du client — coordonnées du lead uniquement."""
    nom = ' '.join(
        part for part in [(lead.prenom or '').strip(), (lead.nom or '').strip()]
        if part)
    return {
        'lead_nom': nom or (lead.nom or ''),
        'telephone': lead.telephone or '',
        'whatsapp': lead.whatsapp or '',
        'adresse': lead.adresse or '',
        'ville': lead.ville or '',
        'gps_lat': _visite_decimal(lead.gps_lat),
        'gps_lng': _visite_decimal(lead.gps_lng),
    }


def _visite_devis(lead):
    """Devis du lead pour le panneau lecture seule — VT3.

    Frontière M3 : la lecture passe par le SELECTOR de ``apps.ventes``, jamais
    par un import de ses modèles. Cette porte ne laisse sortir aucun
    ``prix_achat`` ni aucune donnée de marge (garde testée côté VT4).
    """
    from apps.ventes.selectors import devis_lecture_seule_pour_lead

    try:
        return devis_lecture_seule_pour_lead(lead)
    except Exception:  # pragma: no cover - défensif : un devis illisible ne
        # doit jamais empêcher le commercial d'ouvrir sa visite sur le terrain.
        return []


def visite_terrain_manquants(visite):
    """La liste SERVEUR des manquants d'une visite (gate de terminaison)."""
    medias = list(visite.medias.select_related('attachment').all())
    blocs = _visite_checklist(visite, medias)
    return _visite_manquants(blocs, _visite_mesures(visite),
                             _gabarit(visite), _non_releves_plats(visite))


def contexte_visite_terrain(visite):
    """L'agrégat COMPLET d'une visite technique terrain (contrat VT0)."""
    medias = list(visite.medias.select_related('attachment').all())
    blocs = _visite_checklist(visite, medias)
    mesures_rendues = _visite_mesures(visite)
    non_releves = _non_releves_plats(visite)
    manquants = _visite_manquants(blocs, mesures_rendues, _gabarit(visite),
                                  non_releves)
    commercial = visite.commercial
    agregat = {
        'id': visite.id,
        'lead': visite.lead_id,
        'commercial': None if commercial is None else {
            'id': commercial.id,
            'nom_affiche': (commercial.get_full_name()
                            or commercial.username),
        },
        'statut': visite.statut,
        # AGR412 — la checklist servie est celle de CE gabarit.
        'gabarit': _gabarit(visite),
        'date_prevue': (visite.date_prevue.isoformat()
                        if visite.date_prevue else None),
        'date_realisee': (visite.date_realisee.isoformat()
                          if visite.date_realisee else None),
        'notes': visite.notes or '',
        'modifiable': visite.modifiable,
        'raison_lecture_seule': visite.raison_lecture_seule,
        # AGR412 — aucun toit à assembler sur un relevé du point d'eau ;
        # CIQ600 — ni sur un relevé de site professionnel (zones de toiture).
        'photo_toit': None if _gabarit(visite) in ('point_eau', 'ci') else {
            'assemblage_etat': visite.assemblage_etat,
            'assemblage_erreur': visite.assemblage_erreur or '',
            'url': (f'/api/django/visites/visites/{visite.id}/photo-toit/'
                    if visite.photo_toit_key else None),
            'texture_calage': visite.texture_calage,
        },
        'checklist': blocs,
        'mesures': mesures_rendues,
        'completude': {
            'complet': not manquants,
            'manquants': manquants,
        },
        'client_panel': _visite_client_panel(visite.lead),
        'devis': _visite_devis(visite.lead),
        # VTA6 — jalons de progression, horodatés SERVEUR. ``None`` tant que le
        # jalon n'est pas franchi : l'écran affiche « En route » ou « Arrivé »
        # à partir de CE fait, il ne le devine pas.
        'en_route_le': _visite_horodatage(visite.en_route_le),
        'arrivee_le': _visite_horodatage(visite.arrivee_le),
        # VISITE-CADENCE — la qualification de fin de visite, telle qu'elle a
        # été saisie. ``None`` tant que le terrain n'a rien rempli : l'écran
        # affiche alors le wizard vierge, il ne devine pas des valeurs.
        'qualification': visite.qualification,
    }
    if _gabarit(visite) == 'ci':
        # CIQ601 — les mesures « non relevées » et leur motif (contrat
        # ``exemple_ci._non_releves``) ; absent des autres gabarits.
        agregat['_non_releves'] = non_releves
        # CIQ606 — le relevé déclaré / constaté / écart (écran de revue) ;
        # la même fonction sert ``releve_ci_pour_lead`` (visite validée).
        agregat['releve_ci'] = releve_ci_de_visite(visite)
    return agregat


# ── CIQ606 — RELEVÉ C&I : DÉCLARÉ / CONSTATÉ / ÉCART ─────────────────────────
#
# Le lead DÉCLARE (colonnes CIQ1, lues par ``crm.selectors``), la visite
# CONSTATE ; l'écart est montré à l'ingénieur, jamais corrigé automatiquement
# et jamais jugé (aucun seuil : égal ou différent, point). Aucune seconde
# saisie : le constaté vient des mesures déjà relevées par la visite.

def _mesure_ci(visite, categorie, code):
    """``(valeur, motif_non_releve)`` d'une mesure d'une visite ``ci`` :
    la valeur SAISIE (``None`` si vide) et le motif si elle est « non
    relevée »."""
    saisies = visite.mesures if isinstance(visite.mesures, dict) else {}
    bloc = saisies.get(categorie) or {}
    valeur = bloc.get(code) if isinstance(bloc, dict) else None
    if isinstance(valeur, str) and not valeur.strip():
        valeur = None
    etats = bloc.get('_non_releves') if isinstance(bloc, dict) else None
    motif = (etats or {}).get(code) if isinstance(etats, dict) else None
    return valeur, motif


def _surface_zone(zone):
    """La surface utile d'UNE zone (m²) : ``surface_utile_m2``, sinon
    longueur × largeur ; ``None`` si aucune des deux n'est saisie."""
    surface = zone.get('surface_utile_m2')
    if surface not in (None, ''):
        return float(surface)
    longueur, largeur = zone.get('longueur_m'), zone.get('largeur_m')
    if longueur in (None, '') or largeur in (None, ''):
        return None
    return float(longueur) * float(largeur)


def _ecart_ci(declare, constate, comparables=None):
    """``False`` égal, ``True`` différent, ``None`` non comparable (l'un des
    deux manque, ou une valeur n'est pas dans ``comparables``)."""
    if declare is None or constate is None:
        return None
    if comparables is not None and (declare not in comparables
                                    or constate not in comparables):
        return None
    if isinstance(declare, (int, float)) and isinstance(constate, (int, float)):
        return round(float(declare), 2) != round(float(constate), 2)
    return declare != constate


def releve_ci_de_visite(visite, declare=None):
    """CIQ606 — le bloc ``releve_ci`` (contrat CIQ5) d'UNE visite ``ci`` :
    ``{niveau_tension, puissance_souscrite_kva, type_toiture, surface_utile,
    statut_occupation}`` chacun ``{declare, constate, ecart}`` + ``validee_le``.

    ``declare`` est lu par ``crm.selectors`` (jamais ressaisi) sauf s'il est
    fourni. Une mesure « non relevée » donne ``constate`` ``None`` et son
    motif (clé ``non_releve``). Le type de toiture se compare via la table
    CIQ603 ; plusieurs couvertures différentes ou une zone sans surface = non
    comparable (les zones restent exposées telles que saisies). EN PLUS du
    contrat, pour le moteur C&I (CIQ2) : ``visite_id``, ``zones_toiture``,
    ``trajets`` et ``non_releves`` (états à plat). Lecture SEULE."""
    from apps.crm import selectors as crm_selectors

    from . import visite_checklist as checklist

    if declare is None:
        declare = crm_selectors.releve_declare_ci(visite.lead)
    zones = zones_toiture_saisies(visite)
    constate = {}
    non_releve = {}

    tension, motif = _mesure_ci(visite, 'comptage', 'niveau_tension_constate')
    constate['niveau_tension'] = None if motif else tension
    non_releve['niveau_tension'] = motif
    puissance, motif = _mesure_ci(
        visite, 'comptage', 'puissance_souscrite_kva_constatee')
    constate['puissance_souscrite_kva'] = (
        None if motif or puissance is None else float(puissance))
    non_releve['puissance_souscrite_kva'] = motif

    couvertures = {z.get('couverture') for z in zones if z.get('couverture')}
    types = {checklist.toiture_lead_depuis_visite(c) for c in couvertures}
    types.discard(None)
    constate['type_toiture'] = next(iter(types)) if len(types) == 1 else None
    surfaces = [_surface_zone(z) for z in zones]
    constate['surface_utile'] = (
        round(sum(surfaces), 2)
        if zones and all(s is not None for s in surfaces) else None)
    # Aucune mesure de la visite ne porte le statut d'occupation : il reste
    # au lead (``ownership``) — non comparable tant qu'un constat n'existe pas.
    constate['statut_occupation'] = None

    releve = {}
    for champ in ('niveau_tension', 'puissance_souscrite_kva', 'type_toiture',
                  'surface_utile', 'statut_occupation'):
        bloc = {
            'declare': declare.get(champ),
            'constate': constate[champ],
            'ecart': _ecart_ci(
                declare.get(champ), constate[champ],
                ('bt', 'mt') if champ == 'niveau_tension' else None),
        }
        if non_releve.get(champ):
            bloc['non_releve'] = non_releve[champ]
        releve[champ] = bloc
    releve['validee_le'] = _visite_horodatage(visite.validee_le)
    releve['visite_id'] = visite.id
    releve['zones_toiture'] = zones
    saisies = visite.mesures if isinstance(visite.mesures, dict) else {}
    trajets = (saisies.get('cheminement') or {}).get('trajets')
    releve['trajets'] = [t for t in (trajets or []) if isinstance(t, dict)]
    releve['non_releves'] = _non_releves_plats(visite)
    return releve


def releve_ci_pour_lead(lead):
    """CIQ606 — le relevé C&I de la DERNIÈRE visite ``ci`` VALIDÉE du lead
    (bloc de ``releve_ci_de_visite``), ou ``None`` : une visite non validée
    n'est jamais reprise, une visite résidentielle non plus. La société est
    celle du lead. Lecture SEULE ; jamais mockée dans ses tests."""
    from .models import VisiteTerrain

    if lead is None:
        return None
    visite = (VisiteTerrain.objects
              .filter(lead=lead, company_id=lead.company_id,
                      gabarit=VisiteTerrain.Gabarit.CI,
                      statut=VisiteTerrain.Statut.VALIDEE)
              .select_related('lead').order_by('-id').first())
    if visite is None:
        return None
    return releve_ci_de_visite(visite)


def mesures_point_eau_pour_lead(visite):
    """AGR413 — les mesures SAISIES d'un relevé du point d'eau, ``{categorie:
    {code: valeur}}``, ou ``{}`` pour une visite toiture.

    Seules les valeurs réellement saisies sortent (``False`` et ``0``
    compris ; ``None`` et la chaîne vide jamais) : une mesure vide n'efface
    donc jamais rien côté lead. Voyage dans l'événement ``visite_validee``
    (kwarg ``mesures_point_eau``) ; le moteur agricole lit par ici les
    mesures sans colonne Lead (niveau dynamique, refoulement, conduite).
    Fonction PURE sur l'objet reçu (aucune requête)."""
    from . import visite_checklist as checklist

    if _gabarit(visite) != checklist.GABARIT_POINT_EAU:
        return {}
    saisies = visite.mesures if isinstance(visite.mesures, dict) else {}
    rendu = {}
    for cat in checklist.categories(checklist.GABARIT_POINT_EAU):
        valeurs = saisies.get(cat['categorie'])
        valeurs = valeurs if isinstance(valeurs, dict) else {}
        bloc = {champ['code']: valeurs[champ['code']]
                for champ in cat['mesures']
                if _releve_valeur_saisie(valeurs.get(champ['code']))}
        if bloc:
            rendu[cat['categorie']] = bloc
    return rendu


def visite_point_eau_validee_du_lead(lead):
    """AGR121 — la DERNIÈRE visite « relevé du point d'eau » VALIDÉE du lead,
    ou ``None``. Porte de lecture du moteur agricole ventes (jamais
    ``visites.models``) ; ses mesures se lisent ensuite par
    :func:`mesures_point_eau_pour_lead`. Société = celle du LEAD."""
    from . import visite_checklist as checklist
    from .models import VisiteTerrain

    if lead is None or getattr(lead, 'pk', None) is None:
        return None
    return (VisiteTerrain.objects
            .filter(lead=lead, company_id=lead.company_id,
                    statut=VisiteTerrain.Statut.VALIDEE,
                    gabarit=checklist.GABARIT_POINT_EAU)
            .order_by('-id')
            .first())


def texture_toit_pour_lead(lead):
    """VT12 — la texture de toit CALÉE d'un lead, ou des valeurs nulles.

    C'est la porte par laquelle le reste de l'ERP (atelier 3D/calepinage,
    carte de la fiche lead) lit le toit réaliste SANS rien connaître du module
    visite : il demande « la texture de ce lead », pas « la visite n° 7 ».

    Règles :

    * seule une visite **VALIDÉE** (feu vert du bureau d'études) compte — une
      visite encore en cours ou renvoyée ne doit jamais peindre un toit ;
    * la **dernière** validée gagne (``-id`` : déterministe, aucune horloge) ;
    * la société vient du LEAD, jamais de la requête — une visite d'une autre
      société ne peut structurellement pas sortir d'ici ;
    * sans visite validée, ou sans image assemblée, les MÊMES clés sortent à
      ``None`` — l'appelant n'a jamais à distinguer deux formes de réponse, et
      rien n'est inventé pour combler le vide.
    """
    from .models import VisiteTerrain

    vide = {'visite_id': None, 'url': None, 'texture_calage': None}
    if lead is None:
        return vide
    visite = (VisiteTerrain.objects
              .filter(lead=lead, company_id=lead.company_id,
                      statut=VisiteTerrain.Statut.VALIDEE)
              .exclude(photo_toit_key='')
              .order_by('-id')
              .first())
    if visite is None or not visite.photo_toit_key:
        return vide
    return {
        'visite_id': visite.id,
        'url': f'/api/django/visites/visites/{visite.id}/photo-toit/',
        'texture_calage': visite.texture_calage,
    }


def recap_visite_terrain(visite):
    """VT12 — le récap COURT (FR) écrit en retour sur ``Lead.visite_notes``.

    Ne contient QUE des valeurs réellement saisies : une mesure absente est
    OMISE de la phrase, jamais remplacée par un défaut forfaitaire (règle
    « zéro chiffre inventé »). Si rien n'a été relevé, seule la ligne de date
    sort — et si même la date manque, la phrase la tait aussi.
    """
    saisies = visite.mesures if isinstance(visite.mesures, dict) else {}

    def valeur(categorie, code):
        bloc = saisies.get(categorie) or {}
        brute = bloc.get(code)
        if brute is None or brute == '':
            return None
        return brute

    def nombre(categorie, code):
        brute = valeur(categorie, code)
        if brute is None:
            return None
        try:
            flottant = float(brute)
        except (TypeError, ValueError):
            return None
        entier = int(flottant)
        return str(entier) if flottant == entier else f'{flottant:g}'

    morceaux = []
    if _gabarit(visite) == 'point_eau':
        # AGR412 — relevé du point d'eau : les SEULES valeurs saisies, jamais
        # un défaut ni une mesure de toit.
        source = valeur('point_eau', 'source_eau')
        if source:
            morceaux.append(source)
        niveau = nombre('point_eau', 'niveau_statique_m')
        if niveau:
            morceaux.append(f'niveau statique {niveau} m')
        elif valeur('point_eau', 'niveau_non_mesurable') is True:
            morceaux.append('niveau non mesurable')
        debit = nombre('point_eau', 'debit_mesure_m3h')
        if debit:
            morceaux.append(f'débit {debit} m³/h')
        elif valeur('point_eau', 'debit_non_mesurable') is True:
            morceaux.append('débit non mesurable')
        profondeur = nombre('point_eau', 'profondeur_forage_m')
        if profondeur:
            morceaux.append(f'forage {profondeur} m')
        electricite = valeur('electricite', 'electricite_sur_place')
        if electricite:
            morceaux.append(f'électricité {electricite}')
        distance = nombre('site_pv', 'distance_forage_champ_m')
        if distance:
            morceaux.append(f'pose à {distance} m du forage')
        autorisation = valeur('administratif', 'autorisation_prelevement')
        if autorisation:
            morceaux.append(f'autorisation ABH {autorisation}')
        moment = visite.date_realisee or visite.date_prevue
        entete = "Relevé du point d'eau validé"
        if moment is not None:
            entete += f' — réalisé le {moment.strftime("%d/%m/%Y")}'
        if not morceaux:
            return entete + '.'
        return entete + ' : ' + ', '.join(morceaux) + '.'
    if _gabarit(visite) == 'ci':
        # CIQ600 — relevé d'un site professionnel : seules les valeurs
        # réellement saisies, jamais une mesure résidentielle ni un défaut.
        calibre = nombre('tableau_general', 'calibre_a')
        if calibre:
            morceaux.append(f"appareil de tête {calibre} A")
        tension = valeur('comptage', 'niveau_tension_constate')
        if tension:
            morceaux.append(f'tension {tension}')
        puissance = nombre('comptage', 'puissance_souscrite_kva_constatee')
        if puissance:
            morceaux.append(f'puissance souscrite {puissance} kVA')
        # CIQ602 — zones de toiture saisies ; le fibrociment pose le drapeau
        # (précaution : aucune réglementation citée).
        zones = zones_toiture_saisies(visite)
        if zones:
            morceaux.append(f'{len(zones)} zone(s) de toiture')
        fibro = [z.get('libelle') or z.get('id') or 'zone'
                 for z in zones if z.get('fibrociment')
                 or z.get('couverture') == 'fibrociment']
        if fibro:
            morceaux.append('amiante possible — diagnostic requis ('
                            + ', '.join(str(nom) for nom in fibro) + ')')
        # CIQ601 — une mesure « non relevée » se dit « non vérifié (motif) »,
        # jamais avec une valeur par défaut.
        from . import visite_checklist as checklist

        connus = {
            cat['categorie']: {m['code']: m for m in cat['mesures']}
            for cat in checklist.categories('ci')}
        for cle, motif in _non_releves_plats(visite).items():
            categorie_code, _, reste = cle.partition('.')
            libelle = checklist.libelle_cle_non_releve(
                connus.get(categorie_code, {}), reste)
            if libelle:
                morceaux.append(
                    f'{libelle} non vérifié '
                    f'({checklist.MOTIFS_NON_RELEVE[motif]})')
        moment = visite.date_realisee or visite.date_prevue
        entete = 'Relevé du site professionnel validé'
        if moment is not None:
            entete += f' — réalisé le {moment.strftime("%d/%m/%Y")}'
        if not morceaux:
            return entete + '.'
        return entete + ' : ' + ', '.join(morceaux) + '.'
    longueur = nombre('toiture', 'longueur_m')
    largeur = nombre('toiture', 'largeur_m')
    if longueur and largeur:
        morceaux.append(f'zone utile {longueur} × {largeur} m')
    if valeur('toiture', 'toit_plat') is True:
        morceaux.append('toit plat')
    else:
        pente = nombre('toiture', 'pente_deg')
        if pente:
            morceaux.append(f'pente {pente}°')
    orientation = valeur('toiture', 'orientation')
    if orientation:
        morceaux.append(f'orientation {orientation}')
    couverture = valeur('toiture', 'type_couverture')
    if couverture:
        morceaux.append(f'couverture {couverture}')
    calibre = nombre('tableau', 'calibre_disjoncteur_a')
    if calibre:
        morceaux.append(f'disjoncteur {calibre} A')
    alimentation = valeur('tableau', 'type_alimentation')
    if alimentation:
        morceaux.append(f'alimentation {alimentation}')

    moment = visite.date_realisee or visite.date_prevue
    entete = 'Visite technique validée'
    if moment is not None:
        entete += f' — réalisée le {moment.strftime("%d/%m/%Y")}'
    if not morceaux:
        return entete + '.'
    return entete + ' : ' + ', '.join(morceaux) + '.'


# ── VISITE-CADENCE — CE QUE LE CRM A LE DROIT DE LIRE DE LA VISITE ───────────
#
# Doctrine fondateur (15/09/2026) : la visite technique est une ÉTAPE DU SUIVI
# COMMERCIAL, placée APRÈS l'envoi du devis. La fiche lead doit donc montrer
# les visites du dossier, et le retour du terrain doit redescendre dans son
# historique.
#
# Ces deux lectures sont la PORTE de cette app vers le CRM (frontière M3) :
# ``apps.crm`` les appelle, il n'importe JAMAIS ``apps.visites.models``. Et
# elles ne portent aucune garde de visibilité : la portée dure « mes visites »
# (VTA6) est celle de l'APP TERRAIN, sur SES routes ; la fiche lead, elle, est
# déjà gardée par la portée CRM de l'appelant — la recopier ici masquerait à un
# responsable CRM les visites de son propre dossier.

def _retour_commentaires_photos(visite):
    """Les commentaires de photos NON VIDES, avec le LIBELLÉ de leur slot.

    Le libellé (« Vue d'ensemble du toit ») plutôt que le code (``toit_vue``) :
    la phrase part dans le chatter du lead, lu par des commerciaux qui ne
    connaissent pas la nomenclature de la checklist. Un slot inconnu (photo
    d'une version antérieure de la checklist) garde son code plutôt que de
    disparaître — on ne perd jamais un commentaire du terrain.
    """
    from . import visite_checklist as checklist

    lignes = []
    for media in visite.medias.all().order_by('id'):
        commentaire = (media.commentaire or '').strip()
        if not commentaire:
            continue
        declaration = checklist.slot(media.slot_code)
        libelle = (declaration or {}).get('libelle') or media.slot_code
        lignes.append({'slot': libelle, 'commentaire': commentaire})
    return lignes


def retour_visite(visite):
    """Le RETOUR TERRAIN d'une visite — payload de ``visite_terminee``.

    ``{'notes': str, 'commentaires_photos': [{'slot', 'commentaire'}],
    'nb_photos': int}``. C'est le TEXTE LIBRE du technicien : exactement ce que
    ``recap_visite_terrain`` (mesures seules) ne transporte pas, et qui restait
    donc enfermé dans l'app terrain. Rien n'est inventé ni complété : un retour
    muet sort avec des valeurs vides, et l'abonné le dit tel quel.
    """
    return {
        'notes': (visite.notes or '').strip(),
        'commentaires_photos': _retour_commentaires_photos(visite),
        'nb_photos': visite.medias.count(),
    }


def ligne_visite_pour_lead(visite):
    """UNE ligne de l'onglet « Visites » de la fiche lead (côté CRM).

    ``retour_disponible`` dit s'il y a du TEXTE LIBRE à lire (notes du
    technicien ou commentaire sur au moins une photo) — jamais « il existe une
    visite » : l'écran s'en sert pour proposer d'ouvrir le retour, et une
    pastille qui ouvrirait sur du vide serait un mensonge d'interface.
    """
    commercial = visite.commercial
    nom = ''
    if commercial is not None:
        nom = (commercial.get_full_name() or commercial.username or '')
    return {
        'id': visite.id,
        'statut': visite.statut,
        'statut_libelle': visite.get_statut_display(),
        'date_prevue': (visite.date_prevue.isoformat()
                        if visite.date_prevue else None),
        'date_realisee': (visite.date_realisee.isoformat()
                          if visite.date_realisee else None),
        'commercial_nom': nom,
        'notes': visite.notes or '',
        'retour_disponible': bool(
            (visite.notes or '').strip()
            or _retour_commentaires_photos(visite)),
    }


def visites_recentes_par_lead(company, lead_ids):
    """D2 — la visite technique la PLUS RÉCENTE de CHAQUE lead de ``lead_ids``,
    en UNE requête (jamais une par lead : la file du jour coûtait 2 requêtes
    PAR lead ayant une visite — mesuré 11 requêtes pour 1 lead, 21 pour 6).

    Rend ``{lead_id: {'id', 'retour_disponible'}}`` — seuls les leads qui ONT
    au moins une visite y figurent ; un lead absent de ce ``dict`` n'en a
    aucune. Bornée par ``company`` (jamais une société lue d'une requête,
    même discipline que ``visites_pour_lead``).

    Tri IDENTIQUE à ``visites_pour_lead`` (« la plus récente d'abord ») mais
    écrit avec ``F('date_prevue').desc(nulls_last=True)`` — PAS le
    ``'-date_prevue'`` nu de Django : sous Postgres, un DESC nu met les NULL
    EN TÊTE, ce qui ferait passer une visite SANS date prévue devant une
    visite plus récente et RÉELLEMENT datée. ``-id`` départage ensuite les
    égalités (même stabilité que ``visites_pour_lead``).
    """
    from django.db.models import F

    from .models import VisiteTerrain

    lead_ids = [lid for lid in set(lead_ids) if lid is not None]
    if not lead_ids:
        return {}
    visites = (VisiteTerrain.objects
               .filter(company=company, lead_id__in=lead_ids)
               .select_related('commercial')
               .prefetch_related('medias')
               .order_by('lead_id', F('date_prevue').desc(nulls_last=True),
                         '-id'))
    resultat = {}
    for visite in visites:
        if visite.lead_id in resultat:
            # Déjà la plus récente de ce lead (premier rang de son groupe,
            # l'ordre ci-dessus le garantit) — les suivantes sont ignorées.
            continue
        ligne = ligne_visite_pour_lead(visite)
        resultat[visite.lead_id] = {
            'id': ligne['id'], 'retour_disponible': ligne['retour_disponible'],
        }
    return resultat


def nombre_visites_planifiees(company, lead_ids, *, depuis):
    """COCKPIT-CONTRÔLE (30/09/2026) — combien de visites techniques ont été
    PLANIFIÉES depuis ``depuis`` (instant aware) sur les leads ``lead_ids``
    (un itérable ou une sous-requête d'identifiants), pour le bloc
    « Contrôle du suivi » du CRM — un RÉSULTAT lu à côté de l'effort.

    Planifiée = créée sur la période avec une date prévue encore posée : un
    rendez-vous annulé (``annuler_rendez_vous`` vide ``date_prevue``, SUIVI
    E4) ne compte pas. Bornée par ``company`` ; lecture cross-app pour
    ``apps.crm`` (frontière M3 : il n'importe jamais ces modèles). UN COUNT."""
    from .models import VisiteTerrain

    return VisiteTerrain.objects.filter(
        company=company, lead_id__in=lead_ids, created_at__gte=depuis,
        date_prevue__isnull=False).count()


def visites_pour_lead(lead):
    """Les visites techniques d'un lead, de la PLUS RÉCENTE à la plus ancienne.

    Bornée par la SOCIÉTÉ DU LEAD (jamais une société lue d'une requête) : une
    visite d'un autre locataire ne peut structurellement pas sortir d'ici. Un
    lead absent rend une liste vide plutôt qu'une exception — l'onglet d'une
    fiche ne casse jamais la fiche.

    Tri : ``-date_prevue`` puis ``-id``, donc STABLE et déterministe même quand
    plusieurs visites partagent la même date (ou n'en ont aucune).
    """
    from .models import VisiteTerrain

    if lead is None:
        return []
    visites = (VisiteTerrain.objects
               .filter(lead=lead, company_id=lead.company_id)
               .select_related('commercial')
               .prefetch_related('medias')
               .order_by('-date_prevue', '-id'))
    return [ligne_visite_pour_lead(visite) for visite in visites]


def ligne_visite_terrain(visite):
    """UNE ligne de la liste ``GET /visites/visites/`` (badge de complétude)."""
    manquants = visite_terrain_manquants(visite)
    lead = visite.lead
    nom = ' '.join(
        part for part in [(lead.prenom or '').strip(), (lead.nom or '').strip()]
        if part)
    return {
        'id': visite.id,
        'lead': visite.lead_id,
        'lead_nom': nom or (lead.nom or ''),
        'ville': lead.ville or '',
        'statut': visite.statut,
        'date_prevue': (visite.date_prevue.isoformat()
                        if visite.date_prevue else None),
        'complet': not manquants,
        'manquants_count': len(manquants),
    }


# -- VTA6 -- "MA JOURNEE" : L'ACCUEIL DE L'APP --------------------------------
#
# Recherche field-service : l'ecran d'accueil d'un terrain est SA JOURNEE, pas
# un tableau de bord. Le serveur compose la liste ; le front n'invente rien --
# ``complet`` et ``manquants_count`` viennent d'ici, comme dans la liste.
#
# Contrat : ``apps/visites/contract_samples/ma_journee.json``.

def ligne_ma_journee(visite):
    """UNE carte de "Ma journee" (contrat ``ma_journee.json``)."""
    lead = visite.lead
    nom = ' '.join(
        part for part in [(lead.prenom or '').strip(), (lead.nom or '').strip()]
        if part)
    manquants = visite_terrain_manquants(visite)
    return {
        'id': visite.id,
        'lead_nom': nom or (lead.nom or ''),
        'ville': lead.ville or '',
        'adresse': lead.adresse or '',
        'gps_lat': _visite_decimal(lead.gps_lat),
        'gps_lng': _visite_decimal(lead.gps_lng),
        'date_prevue': (visite.date_prevue.isoformat()
                        if visite.date_prevue else None),
        'statut': visite.statut,
        'en_route_le': _visite_horodatage(visite.en_route_le),
        'arrivee_le': _visite_horodatage(visite.arrivee_le),
        'complet': not manquants,
        'manquants_count': len(manquants),
    }


def ma_journee(visites, *, aujourdhui):
    """La journee d'un terrain : les visites DU JOUR + celles EN RETARD.

    ``visites`` est un queryset DEJA scope (societe + portee dure "mes
    visites") -- ce selector ne decide d'aucune permission, il compose.
    ``aujourdhui`` est une date passee par l'appelant (la vue la lit sur
    l'horloge serveur, dans le fuseau du projet) : aucune horloge n'est lue
    ici, ce qui rend la fonction testable sans dependre du jour ou le test
    tourne.

    EN RETARD = une visite dont la date prevue est PASSEE et qui n'est ni
    terminee, ni validee. Une visite SANS date prevue n'est jamais "en
    retard" : on ne peut pas etre en retard sur un rendez-vous qu'on n'a pas
    pris (elle reste visible dans la liste complete de l'app).
    """
    from .models import VisiteTerrain

    closes = (VisiteTerrain.Statut.TERMINEE, VisiteTerrain.Statut.VALIDEE)
    du_jour = visites.filter(date_prevue=aujourdhui)
    en_retard = (visites
                 .filter(date_prevue__lt=aujourdhui)
                 .exclude(statut__in=closes))
    lignes = sorted(
        list(en_retard) + list(du_jour),
        # Les retards d'abord (la dette la plus ancienne en tete), puis le
        # jour ; tri DETERMINISTE (l'id departage), jamais laisse au SGBD.
        key=lambda visite: (visite.date_prevue or aujourdhui, visite.id))
    return {
        'date': aujourdhui.isoformat(),
        'en_retard_count': en_retard.count(),
        'visites': [ligne_ma_journee(visite) for visite in lignes],
    }


# -- CALX363 -- LA PORTE VISITE TECHNIQUE -> CALEPINAGE ------------------------
#
# Jusqu'ici la seule porte de sortie de cette app vers le reste de l'ERP etait
# ``texture_toit_pour_lead`` (une image) : les MESURES que le commercial a
# relevees sur le toit et les PHOTOS de la checklist ne sortaient nulle part,
# et le concepteur du calepinage les ressaisissait. ``releve_pour_calepinage``
# est cette porte, sur le MEME patron de bornage : le calepinage demande « le
# releve de ce lead », il ne connait ni ``VisiteTerrain`` ni ``VisiteMedia``
# (``apps.calepinage`` n'importe jamais ``apps.visites.models``).
#
# Contrat partage (PACT10) : ``apps/calepinage/contract_samples/
# calepinage_releve_visite.json`` — cette lecture en sert ``visite_id``,
# ``validee_le``, ``mesures``, ``photos`` et ``motif_absence`` ; ``deja_repris``
# et ``releve`` appartiennent a l'action du calepinage (CALX364), qui seule
# sait si CE calepinage a deja repris la visite.

#: Les deux raisons d'absence, publiees TELLES QUELLES par l'onglet de reprise
#: (CALX365) : il nomme ce qui manque au lieu d'afficher un vide muet. La
#: seconde est recopiee mot pour mot dans ``exemple_vide`` du contrat.
MOTIF_AUCUNE_VISITE = (
    "Aucune visite technique n'a été faite pour ce lead : il n'y a ni mesure "
    'ni photo de terrain à reprendre.')
MOTIF_VISITE_NON_VALIDEE = (
    "La visite technique de ce lead n'est pas encore validée par le bureau "
    "d'études : ses mesures et ses photos ne sont pas reprises tant que le "
    'feu vert n\'est pas donné.')

#: L'unite DECLAREE par le libelle d'une mesure de la checklist — la
#: parenthese finale (« Longueur de la zone utile (m) » -> « m »). La
#: checklist reste la seule autorite : aucune unite n'est ecrite ici.
_UNITE_DU_LIBELLE = re.compile(r'\(([^()]+)\)\s*$')


def _releve_unite(champ):
    """L'unite d'une mesure NOMBRE, lue dans son libelle — ``None`` sinon.

    Un choix, un booleen, un texte ou un nombre sans unite declaree (le
    nombre d'emplacements libres) n'a PAS d'unite : ``None`` le dit, rien
    n'est suppose.
    """
    from . import visite_checklist as checklist

    if champ.get('nature') != checklist.NOMBRE:
        return None
    trouve = _UNITE_DU_LIBELLE.search(champ.get('libelle') or '')
    return trouve.group(1).strip() if trouve else None


def _releve_valeur_saisie(valeur):
    """Vrai si la valeur a REELLEMENT ete saisie (``False`` et ``0`` compris).

    ``None``, la chaine vide ou une chaine d'espaces = « non relevee » :
    la mesure est alors OMISE, jamais servie a ``None``.
    """
    if valeur is None:
        return False
    if isinstance(valeur, str) and not valeur.strip():
        return False
    return True


def _releve_mesures_saisies(mesures_json):
    """Les mesures SAISIES d'une visite, dans l'ordre de la checklist.

    ``mesures_json`` est le JSON stocke (``{categorie: {code: valeur}}``).
    Chaque mesure DECLAREE et reellement saisie sort en
    ``{code, libelle, valeur, unite}`` ; une mesure vide est OMISE (jamais
    ``valeur: None``) et une cle inconnue de la checklist n'est pas servie
    (la checklist est la seule autorite sur ce qui est une mesure). Aucune
    valeur n'est convertie ni completee : l'orientation reste le choix saisi,
    jamais un azimut devine. Fonction PURE (aucune base).
    """
    from . import visite_checklist as checklist

    saisies = mesures_json if isinstance(mesures_json, dict) else {}
    rendu = []
    for cat in checklist.categories():
        valeurs = saisies.get(cat['categorie'])
        valeurs = valeurs if isinstance(valeurs, dict) else {}
        for champ in cat['mesures']:
            valeur = valeurs.get(champ['code'])
            if not _releve_valeur_saisie(valeur):
                continue
            rendu.append({
                'code': champ['code'],
                'libelle': champ['libelle'],
                'valeur': valeur,
                'unite': _releve_unite(champ),
            })
    return rendu


def _releve_photos_retenues(medias):
    """Les photos RETENUES d'une visite : ``[{slot_code, libelle,
    attachment_id}]``, dans l'ordre des medias recus.

    Une photo marquee « a refaire » n'est pas une prise de vue acceptee : elle
    ne sort pas. Le libelle est celui du slot de la checklist ; un slot
    inconnu (photo d'une version anterieure de la checklist) garde son code
    plutot que de disparaitre. La piece jointe n'est PAS copiee : seul son
    identifiant sort. Fonction PURE sur des objets deja lus.
    """
    from . import visite_checklist as checklist

    photos = []
    for media in medias:
        if getattr(media, 'a_refaire', False):
            continue
        declaration = checklist.slot(media.slot_code)
        photos.append({
            'slot_code': media.slot_code,
            'libelle': (declaration or {}).get('libelle') or media.slot_code,
            'attachment_id': media.attachment_id,
        })
    return photos


def releve_pour_calepinage(lead):
    """CALX363 — le releve de terrain d'un lead, pour le calepinage.

    Regles (memes que ``texture_toit_pour_lead``) :

    * seule une visite **VALIDEE** (feu vert du bureau d'etudes) sort — une
      visite en cours, terminee ou renvoyee n'est jamais reprise ;
    * la **derniere** validee gagne (``-id`` : deterministe, aucune horloge) ;
    * la societe vient du LEAD, jamais d'une requete : une visite d'une autre
      societe ne peut structurellement pas sortir d'ici ;
    * sans visite validee, les MEMES cles sortent a ``None`` — jamais une
      seconde forme de reponse — et ``motif_absence`` NOMME ce qui manque
      (aucune visite, ou visite pas encore validee) ;
    * LECTURE SEULE : rien n'est ecrit, ni ici ni sur le lead.

    ``validee_le`` (CIQ604) est l'horodatage ISO que
    ``services.valider_visite`` pose cote serveur ; il sort a ``None`` pour une
    visite validee AVANT cette tache (aucune reprise des anciennes) — aucune
    autre date (``date_realisee``, ``updated_at``) n'est presentee a sa place,
    ce serait une date inventee.

    Returns:
        dict — ``{visite_id, validee_le, mesures, photos, motif_absence}``.
    """
    from .models import VisiteTerrain

    vide = {
        'visite_id': None,
        'validee_le': None,
        'mesures': None,
        'photos': None,
        'motif_absence': MOTIF_AUCUNE_VISITE,
    }
    if lead is None:
        return vide
    visites = VisiteTerrain.objects.filter(lead=lead,
                                           company_id=lead.company_id)
    visite = (visites.filter(statut=VisiteTerrain.Statut.VALIDEE)
              .order_by('-id').first())
    if visite is None:
        if visites.exists():
            return dict(vide, motif_absence=MOTIF_VISITE_NON_VALIDEE)
        return vide
    medias = visite.medias.filter(company_id=lead.company_id).order_by('id')
    releve = {
        'visite_id': visite.id,
        # CIQ604 — la date du feu vert, posée par ``valider_visite`` ; ``None``
        # pour une visite validée avant la tâche (aucune date inventée).
        'validee_le': _visite_horodatage(visite.validee_le),
        'mesures': _releve_mesures_saisies(visite.mesures),
        'photos': _releve_photos_retenues(medias),
        'motif_absence': None,
    }
    if getattr(visite, 'gabarit', None) == 'ci':
        # CIQ602 — site professionnel : le relevé expose la LISTE des zones
        # (une visite résidentielle garde exactement la forme historique).
        releve['zones_toiture'] = zones_toiture_saisies(visite)
    return releve
