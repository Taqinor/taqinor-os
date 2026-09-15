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


def _visite_checklist(visite, medias):
    from . import visite_checklist as checklist

    par_slot = {}
    for media in medias:
        par_slot.setdefault(media.slot_code, []).append(_visite_photo(media))
    blocs = []
    for cat in checklist.categories():
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
    for cat in checklist.categories():
        champs = cat['mesures']
        if not champs:
            continue
        valeurs = saisies.get(cat['categorie']) or {}
        rendu[cat['categorie']] = {
            champ['code']: valeurs.get(champ['code'], None)
            for champ in champs
        }
    return rendu


def _visite_manquants(blocs, mesures_rendues):
    from . import visite_checklist as checklist

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
    for cat in checklist.categories():
        valeurs = mesures_rendues.get(cat['categorie']) or {}
        for champ in cat['mesures']:
            if not checklist.mesure_requise(champ, valeurs):
                continue
            valeur = valeurs.get(champ['code'])
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
    return _visite_manquants(blocs, _visite_mesures(visite))


def contexte_visite_terrain(visite):
    """L'agrégat COMPLET d'une visite technique terrain (contrat VT0)."""
    medias = list(visite.medias.select_related('attachment').all())
    blocs = _visite_checklist(visite, medias)
    mesures_rendues = _visite_mesures(visite)
    manquants = _visite_manquants(blocs, mesures_rendues)
    commercial = visite.commercial
    return {
        'id': visite.id,
        'lead': visite.lead_id,
        'commercial': None if commercial is None else {
            'id': commercial.id,
            'nom_affiche': (commercial.get_full_name()
                            or commercial.username),
        },
        'statut': visite.statut,
        'date_prevue': (visite.date_prevue.isoformat()
                        if visite.date_prevue else None),
        'date_realisee': (visite.date_realisee.isoformat()
                          if visite.date_realisee else None),
        'notes': visite.notes or '',
        'modifiable': visite.modifiable,
        'raison_lecture_seule': visite.raison_lecture_seule,
        'photo_toit': {
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
