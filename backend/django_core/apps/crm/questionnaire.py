"""L-QUEST (fondateur 25/08/2026) — « questionnaire envoyable au client ».

Règles MÉTIER du questionnaire, isolées ici pour être testables sans HTTP :
quelles sections existent, quels champs `Lead` chacune porte, laquelle est
MANQUANTE (le défaut des questions posées), quoi pré-remplir, et comment
enregistrer une section répondue.

Le contrat servi/consommé est figé dans
``apps/crm/contract_samples/questionnaire_lead.json`` (PACT10).

TROIS PRINCIPES NON NÉGOCIABLES :
  · **zéro chiffre inventé** — un pré-remplissage absent vaut ``None``, jamais
    un défaut forfaitaire ;
  · **on n'efface jamais** — une valeur déjà renseignée sur le lead n'est
    jamais remplacée par du vide, et une section n'écrit QUE ses propres
    champs (une réponse « contact » ne peut donc pas toucher le GPS) ;
  · **on ne REDEMANDE jamais** (ordre fondateur 25/08/2026) — une donnée que
    le lead porte DÉJÀ n'est jamais reposée à vide au client : elle revient
    pré-remplie (donc confirmable), et quand une AUTRE donnée déjà connue la
    couvre plus précisément, la question disparaît purement et simplement.
    Le cas qui a déclenché la règle : « you are adding the address while the
    client already have given its GPS position » — un repère GPS localise le
    toit au mètre ; redemander l'adresse postale, c'est refaire saisir au
    client, en MOINS précis, ce qu'il vient de donner. Le grain de cette
    décision est le CHAMP, pas la section : voir :func:`champs_a_poser`.
"""
import logging

from .models import Lead, LeadActivity, QuestionnaireLien

logger = logging.getLogger(__name__)

#: Whitelist des sections — source unique, portée par le modèle.
SECTIONS = QuestionnaireLien.SECTIONS_CLES

#: Colonnes `crm.Lead` que chaque section a le droit d'écrire ET de
#: pré-remplir. Une clé hors de cette table n'est jamais lue ni écrite.
CHAMPS_PAR_SECTION = {
    'contact': ('email', 'adresse', 'ville'),
    'gps': ('gps_lat', 'gps_lng'),
    # CAD149 — `objectif_projet` rejoint la section énergie : « pourquoi le
    # solaire » se répond aussi bien par écrit qu'au téléphone.
    'energie': ('facture_hiver', 'facture_ete', 'ete_differente',
                'conso_mensuelle_kwh', 'tranche_onee', 'raccordement',
                'objectif_projet'),
    # CAD149 — `type_bien` rejoint la section du bâtiment (celle qui porte
    # déjà l'âge du toit et le statut d'occupation).
    'toiture': ('type_toiture', 'surface_toiture_m2', 'roof_age', 'ownership',
                'type_bien'),
    # CAD154 — le nombre de personnes au foyer est LA donnée qui manquait au
    # chauffe-eau, et le chauffage d'hiver se répond par oui/non : les deux
    # se posent aussi bien par écrit.
    'occupation': ('occupation_jour', 'nb_personnes_foyer',
                   'chauffage_electrique_hiver'),
    'equipements': (
        'equip_piscine', 'equip_piscine_pompe_kw',
        'equip_piscine_heures_jour', 'equip_piscine_creneau',
        'equip_voiture_electrique', 'equip_ve_km_semaine',
        'equip_ve_chargeur_kw', 'equip_ve_creneau',
        'equip_clim', 'equip_clim_pieces', 'equip_clim_kw',
        'equip_clim_creneau',
        'equip_chauffe_eau_electrique', 'equip_chauffe_eau_kw',
        'equip_chauffe_eau_creneau',
        # CAD149 — « déjà là ou seulement prévu » se répond aussi bien par
        # écrit : c'est la précision qui décide de l'étiquette du devis.
        'equip_ve_statut',
    ),
    # CAD149 — `decideur` et `devis_concurrents` restent HORS de cette table :
    # ils ne se posent qu'à l'ORAL (décision fondateur du 21/09/2026).
    # AGR411 — la section POMPAGE (lead agricole seulement, filtre
    # ``sections_du_lead``) : les colonnes que le CLIENT écrit lui-même. Les
    # colonnes orales seulement (autorisation de prélèvement, aide FDA reçue,
    # décideur) n'y sont JAMAIS : elles ne se posent pas par écrit.
    'pompage': ('source_eau', 'niveau_statique_m', 'besoin_eau_m3j',
                'surface_irriguee_ha', 'culture', 'irrigation_methode',
                'pompe_alim_actuelle', 'butane_bouteilles_jour',
                'carburant_prix_unitaire_mad', 'depense_carburant_mad_mois',
                'mois_irrigation', 'compteur_eau'),
    # Sections PHOTO : aucune colonne — la réponse est une pièce jointe.
    'photo_facture': (),
    'photo_compteur': (),
    'photo_tableau': (),
    'photo_pompe': (),
    'photo_forage': (),
    # CIQ412 (contrat CIQ400 ``questionnaire_lead.json`` → ``exemple_pro``)
    # — sections du lead PRO : les colonnes du contrat CIQ1 que le CLIENT
    # écrit lui-même. Q21 tient : budget, délai, décideur et concurrents ne
    # sont JAMAIS demandés par écrit.
    'reseau': ('tension_raccordement', 'compteur_puissance_kva',
               'conso_mensuelle_kwh', 'releve_conso', 'cos_phi'),
    'activite': ('categorie_commerciale', 'reponses_categorie',
                 'secteur_industriel', 'export_ue_declare', 'regime_equipes',
                 'jours_ouverture', 'heure_debut', 'heure_fin',
                 'fermeture_mois', 'groupe_electrogene', 'groupe_kva',
                 'groupe_litres_mois', 'groupe_depense_mad_mois',
                 'pv_existant_kwc'),
    'site': ('type_surface', 'type_toiture', 'surface_toiture_m2'),
    'societe': ('societe', 'ice', 'rc', 'if_fiscal', 'adresse_siege',
                'fonction_contact', 'contact_secondaire_nom',
                'contact_secondaire_telephone', 'contact_secondaire_email',
                'contact_secondaire_fonction', 'tva_recuperable'),
    'photo_factures': (),
    'photo_poste': (),
}

#: AGR411 — sections du lead AGRICOLE seulement (jamais servies à un autre).
SECTIONS_AGRICOLES_SEULES = ('pompage', 'photo_pompe', 'photo_forage')
#: AGR411 — sections REFUSÉES (400 qui nomme la section) à un lead agricole :
#: plus jamais piscine, clim, toit ou facture d'électricité à un agriculteur.
SECTIONS_REFUSEES_AGRICOLE = ('occupation', 'equipements', 'energie',
                              'toiture', 'photo_facture', 'photo_tableau')
#: AGR411 — les sections que l'envoi SANS corps peut cocher pour un agricole.
SECTIONS_DEFAUT_AGRICOLE = ('pompage', 'photo_pompe', 'photo_forage', 'gps',
                            'contact')
#: CIQ412 — sections du lead PRO seulement (jamais servies à un autre).
SECTIONS_PRO_SEULES = ('reseau', 'activite', 'site', 'societe',
                       'photo_factures', 'photo_poste')
#: CIQ412 — les sections d'un lead commercial/industriel (ordre d'affichage
#: de la whitelist) : les sections pro, plus le GPS et les coordonnées.
SECTIONS_PRO = tuple(s for s in SECTIONS
                     if s in SECTIONS_PRO_SEULES or s in ('gps', 'contact'))
#: Le périmètre historique (avant AGR411) : celui que lit le panneau d'appel
#: et que sert tout lead résidentiel — inchangé à l'octet.
SECTIONS_HORS_POMPAGE = tuple(s for s in SECTIONS
                              if s not in SECTIONS_AGRICOLES_SEULES
                              and s not in SECTIONS_PRO_SEULES)


def est_agricole(lead) -> bool:
    return (getattr(lead, 'type_installation', None) or '') == \
        Lead.TypeInstallation.AGRICOLE


def est_pro(lead) -> bool:
    """CIQ412 — lead commercial ou industriel."""
    return (getattr(lead, 'type_installation', None) or '') in (
        Lead.TypeInstallation.COMMERCIAL, Lead.TypeInstallation.INDUSTRIEL)


def sections_du_lead(lead) -> tuple:
    """AGR411 — la whitelist des sections pour CE lead (filtre de segment).

    Agricole : tout sauf les sections refusées (et sans les sections pro) ;
    pro (CIQ412) : les sections pro + GPS + coordonnées ; sinon : le
    périmètre historique, sans les sections de pompage ni les sections pro."""
    if est_agricole(lead):
        return tuple(s for s in SECTIONS
                     if s not in SECTIONS_REFUSEES_AGRICOLE
                     and s not in SECTIONS_PRO_SEULES)
    if est_pro(lead):
        return SECTIONS_PRO
    return SECTIONS_HORS_POMPAGE


#: QJR596 — colonnes que CHAMPS_PAR_SECTION annonce mais que la page publique
#: ne pose JAMAIS (aucun contrôle dans [token].astro / lib/questionnaire.ts) :
#: elles ne se répondent qu'à l'ORAL, au panneau d'appel (qui lit toujours
#: CHAMPS_PAR_SECTION en entier). `conso_mensuelle_kwh` reste ÉCRITE (QJR632
#: lui donne un contrôle). Contrat : `colonnes_ecrites` de
#: questionnaire_lead.json.
CHAMPS_ORAUX_SEULEMENT = frozenset({
    'tranche_onee', 'objectif_projet', 'type_bien', 'nb_personnes_foyer',
    'chauffage_electrique_hiver', 'equip_ve_statut',
    # Détails d'équipements (kW / créneau / heures) : aucun contrôle dans
    # la page publique (0 occurrence dans [token].astro / questionnaire.ts).
    'equip_piscine_heures_jour', 'equip_piscine_creneau',
    'equip_ve_chargeur_kw', 'equip_ve_creneau',
    'equip_clim_kw', 'equip_clim_creneau',
    'equip_chauffe_eau_kw', 'equip_chauffe_eau_creneau',
})


def colonnes_ecrites(section) -> tuple:
    """Colonnes qu'une section du questionnaire PUBLIC sert, pré-remplit et
    écrit : CHAMPS_PAR_SECTION moins ce qui ne se pose qu'à l'oral."""
    return tuple(cle for cle in CHAMPS_PAR_SECTION.get(section, ())
                 if cle not in CHAMPS_ORAUX_SEULEMENT)


#: Libellé français d'une section (chatter + écran commercial).
LIBELLE_SECTION = {
    'contact': 'coordonnées',
    'gps': 'localisation GPS',
    'energie': 'énergie',
    'photo_facture': 'photo de la facture',
    'photo_compteur': 'photo du compteur',
    'photo_tableau': 'photo du tableau électrique',
    'toiture': 'toiture',
    'occupation': 'présence en journée',
    'equipements': 'équipements',
    # AGR411 — sections du lead agricole.
    'pompage': 'pompage et irrigation',
    'photo_pompe': 'photo de la plaque de la pompe',
    'photo_forage': 'photo de la tête de forage',
    # CIQ412 — sections du lead pro.
    'reseau': 'raccordement et consommation',
    'activite': 'activité et horaires',
    'site': 'surface disponible',
    'societe': 'société',
    'photo_factures': 'les 12 dernières factures',
    'photo_poste': 'compteur / poste de livraison',
}

#: Les trois booléens equip_* à TROIS ÉTATS : ``None`` = « jamais posée »,
#: ce qui est DIFFÉRENT de ``False`` (« le client a répondu non »). C'est ce
#: qui rend la section « équipements » manquante ou non.
_EQUIP_BOOLEENS = (
    'equip_piscine', 'equip_voiture_electrique', 'equip_clim',
    'equip_chauffe_eau_electrique',
)

# Sections photo → mots-clés reconnus dans le LIBELLÉ du fichier joint.
#
# APPROXIMATION ASSUMÉE : le magasin générique ``records.Attachment`` ne porte
# aucun type métier ; on reconnaît donc la nature d'une photo à son nom de
# fichier (celui que pose ``intake_photo.attach_capture_photo`` pour les
# captures du site, et celui que pose ce module pour les réponses du
# questionnaire). En cas de doute, la section est déclarée MANQUANTE — on
# repose la question plutôt que de supposer qu'on a déjà la photo.
_PHOTO_MOTS_CLES = {
    'photo_facture': ('facture', 'bill'),
    'photo_compteur': ('compteur', 'meter'),
    'photo_tableau': ('tableau', 'disjoncteur'),
    # AGR411 — plaque de la pompe actuelle, tête de forage.
    'photo_pompe': ('pompe', 'plaque'),
    'photo_forage': ('forage', 'puits'),
    # CIQ412 — factures (jusqu'à 12) et compteur / poste de livraison.
    'photo_factures': ('factures', 'facture', 'bill'),
    'photo_poste': ('poste', 'livraison', 'compteur'),
}
_SECTIONS_PHOTO = tuple(_PHOTO_MOTS_CLES)

#: Extension retenue selon le type MIME annoncé par la data-URL du client.
#: Purement cosmétique (le nom affiché) : la vraie validation reste celle des
#: magic-bytes de ``records.storage``.
_EXT_PAR_MIME = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'application/pdf': '.pdf',
}


class SectionInconnue(ValueError):
    """Section hors whitelist (ou non demandée sur ce lien)."""


def _vide(valeur) -> bool:
    """Une valeur « pas renseignée » : ``None`` ou une chaîne blanche.

    ``False`` et ``0`` ne sont PAS vides — ce sont des réponses."""
    if valeur is None:
        return True
    return isinstance(valeur, str) and not valeur.strip()


def _gps_connu(lead) -> bool:
    return lead.gps_lat is not None and lead.gps_lng is not None


#: Colonnes qu'une AUTRE donnée déjà connue du lead rend inutiles à demander.
#: Clé = colonne du questionnaire ; valeur = prédicat « l'information est déjà
#: couverte, et plus précisément, par autre chose que le lead porte ».
#:
#: ``adresse`` ← GPS : ordre fondateur du 25/08/2026 (voir l'en-tête du
#: module). Un couple (lat, lng) désigne le toit ; l'adresse postale, elle, est
#: approximative au Maroc (quartiers sans numérotation) — la redemander à
#: quelqu'un qui a déjà posé son repère est une régression de précision ET une
#: question en double. La ville, elle, N'EST PAS couverte : rien ici ne
#: géocode à l'envers, donc une ville inconnue reste une vraie question.
_COUVERT_PAR = {
    'adresse': _gps_connu,
}


def _couverte_ailleurs(lead, cle) -> bool:
    predicat = _COUVERT_PAR.get(cle)
    return bool(predicat and predicat(lead))


def _encore_a_obtenir(lead, cle) -> bool:
    """La réponse à ``cle`` est-elle encore à obtenir DU CLIENT ?

    Non si le lead la porte déjà (elle sera pré-remplie), non plus si une
    autre donnée connue la couvre (``_COUVERT_PAR``)."""
    return (_vide(getattr(lead, cle, None))
            and not _couverte_ailleurs(lead, cle))


def _libelles_pieces_jointes(lead):
    """Noms de fichier des pièces jointes du lead (minuscules).

    Le lead est déjà company-scopé : le couple (content_type, object_id)
    désigne UNE fiche d'UNE société — aucune fuite inter-locataires."""
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment

    content_type = ContentType.objects.get_for_model(Lead)
    noms = Attachment.objects.filter(
        content_type=content_type, object_id=lead.pk,
    ).values_list('filename', flat=True)
    return [(nom or '').lower() for nom in noms]


def _photo_presente(section, libelles) -> bool:
    mots = _PHOTO_MOTS_CLES[section]
    return any(mot in nom for nom in libelles for mot in mots)


#: AGR411 — la section pompage est MANQUANTE tant que l'une de ces réponses
#: écrites manque.
_POMPAGE_ESSENTIELS = ('source_eau', 'niveau_statique_m', 'besoin_eau_m3j',
                       'surface_irriguee_ha', 'pompe_alim_actuelle')


def manquantes(lead) -> dict:
    """Carte ``{section: bool}`` — l'information de la section est-elle
    (encore) inconnue ? C'est le DÉFAUT des questions posées au client.

    Fonction PURE au sens métier (une seule requête, pour les pièces
    jointes) : aucun effet de bord, aucun chiffre inventé."""
    from .devis_auto import champs_manquants

    libelles = _libelles_pieces_jointes(lead)

    if est_pro(lead):
        return _manquantes_pro(lead, libelles)

    if est_agricole(lead):
        # AGR411 — un agriculteur ne reçoit JAMAIS factures, toit, piscine,
        # VE ni clim : le défaut ne coche que le pompage, ses deux photos, le
        # GPS et les coordonnées manquants.
        return {
            'pompage': any(_vide(getattr(lead, cle, None))
                           for cle in _POMPAGE_ESSENTIELS),
            'photo_pompe': not _photo_presente('photo_pompe', libelles),
            'photo_forage': not _photo_presente('photo_forage', libelles),
            'gps': not _gps_connu(lead),
            'contact': (_vide(lead.email)
                        or _encore_a_obtenir(lead, 'adresse')
                        or _vide(lead.ville)),
        }

    # Énergie : la règle serveur du devis automatique (source de vérité
    # UNIQUE, jamais dupliquée) + les deux champs tarifaires que le
    # générateur n'exige pas mais que le commercial veut toujours.
    # NB : `ete_differente` n'est PAS un signal de « jamais posée » — sa
    # colonne est NOT NULL default False, donc elle vaut toujours Oui/Non.
    # CAD148 — `tranche_onee` est SORTIE de cette condition : c'est un champ
    # texte libre qu'AUCUN calcul ne lit (la grille tarifaire canonique vit
    # dans `apps/ventes/pricing/`), et elle se DÉRIVE de la facture et de la
    # consommation. Tant qu'elle comptait comme « information manquante »,
    # elle rouvrait l'écran Énergie pour une question qu'on ne devrait pas
    # poser. Le champ reste : il n'est simplement plus un signal de manque.
    energie = bool(champs_manquants(lead))
    if not energie:
        energie = _vide(lead.raccordement)

    return {
        # `adresse` passe par `_encore_a_obtenir` : quand le GPS est déjà là,
        # elle ne compte PLUS comme une information manquante (sinon le
        # défaut des questions rouvrait un écran « Coordonnées » dont la
        # seule question restante était celle qu'on s'interdit de poser).
        'contact': (_vide(lead.email) or _encore_a_obtenir(lead, 'adresse')
                    or _vide(lead.ville)),
        'gps': not _gps_connu(lead),
        'energie': energie,
        'photo_facture': not _photo_presente('photo_facture', libelles),
        'photo_compteur': not _photo_presente('photo_compteur', libelles),
        'photo_tableau': not _photo_presente('photo_tableau', libelles),
        'toiture': (_vide(lead.type_toiture)
                    or lead.surface_toiture_m2 is None
                    or lead.roof_age is None
                    or _vide(lead.ownership)),
        'occupation': _vide(lead.occupation_jour),
        # Trois-états : AU MOINS UN booléen equip_* jamais posé (None).
        'equipements': any(getattr(lead, cle) is None
                           for cle in _EQUIP_BOOLEENS),
    }


def _tension_inconnue(lead) -> bool:
    return (_vide(lead.tension_raccordement)
            or lead.tension_raccordement == 'ne_sait_pas'
            or lead.tension_source == 'site_defaut_visible')


def _manquantes_pro(lead, libelles) -> dict:
    """CIQ412 — règles ``manquantes_pro`` (contrat CIQ400) : une section pro
    est MANQUANTE quand la tension, la puissance souscrite, le rythme, la
    surface ou l'identité restent inconnus. Jamais une section résidentielle."""
    if lead.type_installation == Lead.TypeInstallation.INDUSTRIEL:
        activite_connue = not _vide(lead.secteur_industriel)
    else:
        activite_connue = not _vide(lead.categorie_commerciale)
    return {
        'reseau': (_tension_inconnue(lead)
                   or lead.compteur_puissance_kva is None),
        'activite': (not activite_connue or not lead.jours_ouverture
                     or lead.heure_debut is None or lead.heure_fin is None),
        'site': lead.surface_toiture_m2 is None,
        'gps': not _gps_connu(lead),
        'photo_factures': not _photo_presente('photo_factures', libelles),
        'photo_poste': not _photo_presente('photo_poste', libelles),
        'societe': _vide(lead.societe) or _vide(lead.ice),
        'contact': (_vide(lead.email) or _encore_a_obtenir(lead, 'adresse')
                    or _vide(lead.ville)),
    }


#: CIQ412 — colonnes de la section activité propres à UN segment : un
#: commerce ne voit pas les questions d'usine, et l'inverse.
_ACTIVITE_INDUSTRIEL_SEULEMENT = ('secteur_industriel', 'export_ue_declare')
_ACTIVITE_COMMERCIAL_SEULEMENT = ('categorie_commerciale',
                                  'reponses_categorie')


def _colonnes_du_lead(lead, section) -> tuple:
    """Les colonnes écrites d'une section, filtrées par segment (CIQ412) ;
    hors lead pro, exactement :func:`colonnes_ecrites`."""
    colonnes = colonnes_ecrites(section)
    if section == 'activite':
        exclues = (_ACTIVITE_COMMERCIAL_SEULEMENT
                   if lead.type_installation == Lead.TypeInstallation.INDUSTRIEL
                   else _ACTIVITE_INDUSTRIEL_SEULEMENT)
        colonnes = tuple(c for c in colonnes if c not in exclues)
    if section == 'reseau' and \
            lead.type_installation != Lead.TypeInstallation.INDUSTRIEL:
        colonnes = tuple(c for c in colonnes if c != 'cos_phi')
    return colonnes


def champs_a_poser(lead, sections) -> dict:
    """``{section: [colonnes à AFFICHER]}`` — le grain FIN du questionnaire.

    La section dit QUEL écran s'ouvre ; cette carte dit quelles questions cet
    écran a encore le droit de poser. Une colonne est servie quand :

      · le lead la porte déjà → elle revient PRÉ-REMPLIE (le client confirme
        ou corrige, il ne ressaisit pas) ; ou
      · elle est réellement inconnue ET qu'aucune autre donnée connue ne la
        couvre (``_COUVERT_PAR``).

    Une colonne à la fois VIDE et COUVERTE (l'adresse d'un lead qui a déjà
    donné son GPS) est ABSENTE de la carte : la page ne la dessine pas. Rien
    n'est jamais inventé ici — on ne fabrique pas l'adresse depuis le GPS, on
    se contente de ne pas la redemander.

    Les sections photo n'ont aucune colonne : leur liste est vide, ce qui ne
    veut PAS dire « rien à demander » (la réponse y est une pièce jointe) —
    d'où :func:`sections_a_servir`, seul endroit qui tranche ce cas."""
    return {
        section: [cle for cle in _colonnes_du_lead(lead, section)
                  if not (_vide(getattr(lead, cle, None))
                          and _couverte_ailleurs(lead, cle))]
        for section in sections
    }


def sections_a_servir(lead, sections):
    """Sections actives DONT il reste quelque chose à afficher.

    Garde-fou d'écran mort : si le commercial coche une section dont toutes
    les colonnes sont vides ET couvertes ailleurs, la page n'a plus rien à
    dessiner — mieux vaut ne pas ouvrir l'écran du tout que d'en montrer un
    vide. Les sections photo, elles, restent TOUJOURS servies : leur réponse
    n'est pas une colonne."""
    # AGR411 — filtre de segment, même sur un lien ancien : un agriculteur ne
    # voit jamais un écran énergie/toiture/équipements.
    permises = sections_du_lead(lead)
    sections = [section for section in sections if section in permises]
    carte = champs_a_poser(lead, sections)
    return [section for section in sections
            if section in _SECTIONS_PHOTO or carte.get(section)]


def questions_par_defaut(lead) -> dict:
    """Carte EXPLICITE des questions posées quand le commercial n'en choisit
    aucune : « DÉFAUT = les informations manquantes » (ordre fondateur).

    AGR411 — lead agricole : la carte nomme TOUTES ses sections permises ;
    celles que le défaut ne coche pas (``photo_compteur``) sont posées à
    False, sinon « clé absente → posée » (``question_posee``) les ouvrirait."""
    carte = dict(manquantes(lead))
    if est_agricole(lead) or est_pro(lead):
        for section in sections_du_lead(lead):
            carte.setdefault(section, False)
    return carte


def valider_questions(brut, lead=None) -> dict:
    """Normalise le corps ``questions`` du mint. Lève :class:`SectionInconnue`
    sur une clé hors whitelist — jamais un silence (une faute de frappe du
    commercial ne doit pas retirer une question sans le dire).

    AGR411 — avec ``lead`` : filtre de SEGMENT. Une section refusée à un lead
    agricole lève une erreur qui NOMME la section ; une section de pompage
    reste inconnue pour un lead non agricole (message historique)."""
    if brut is None:
        return None
    if not isinstance(brut, dict):
        raise SectionInconnue('« questions » doit être un objet {section: '
                              'true/false}.')
    permises = SECTIONS if lead is None else sections_du_lead(lead)
    out = {}
    for cle, valeur in brut.items():
        if cle not in permises:
            if lead is not None and est_agricole(lead) and cle in SECTIONS:
                if not valeur:
                    continue  # « ne pas poser » une section refusée : rien
                raise SectionInconnue(
                    f'Section « {cle} » non posée à un lead agricole : le '
                    'questionnaire pompage ne pose ni factures, ni toiture, '
                    'ni équipements de la maison.')
            if lead is not None and est_pro(lead) and cle in SECTIONS:
                if not valeur:
                    continue
                # CIQ412 — un hôtel ne reçoit jamais « Passez-vous la journée
                # à la maison ? » : refus qui NOMME la section.
                raise SectionInconnue(
                    f'Section « {cle} » non posée à un lead professionnel : '
                    'le questionnaire pro ne pose ni occupation, ni '
                    'équipements de la maison, ni toiture ou énergie '
                    'résidentielles.')
            raise SectionInconnue(f'Section inconnue : « {cle} ».')
        out[cle] = bool(valeur)
    return out


#: Types « pro » dont le kWh mensuel du site est repris (QJR592).
_TYPES_PRO = (Lead.TypeInstallation.INDUSTRIEL,
              Lead.TypeInstallation.COMMERCIAL)


def prefill(lead, sections) -> dict:
    """Valeurs ACTUELLES du lead pour les champs des sections actives.

    ZÉRO CHIFFRE INVENTÉ : une valeur absente vaut ``None`` — jamais un
    défaut forfaitaire. Les ``Decimal`` sont rendus en ``float`` (JSON)."""
    from decimal import Decimal

    out = {}
    for section in sections:
        for cle in _colonnes_du_lead(lead, section):
            valeur = getattr(lead, cle, None)
            # QJR592 — un lead PRO (industriel / commercial) a déjà donné son
            # kWh mensuel sur le site : il est rangé dans `bill_kwh` seulement.
            # On le PROPOSE (à confirmer) au lieu de le redemander ; jamais en
            # résidentiel (estimation possible) et aucune écriture serveur.
            if (cle == 'conso_mensuelle_kwh' and _vide(valeur)
                    and lead.type_installation in _TYPES_PRO):
                valeur = getattr(lead, 'bill_kwh', None)
            if isinstance(valeur, Decimal):
                valeur = float(valeur)
            elif isinstance(valeur, str) and not valeur.strip():
                valeur = None
            out[cle] = valeur
    return out


def _extension_photo(brut) -> str:
    """Extension d'affichage déduite de l'en-tête data-URL, sinon ``.jpg``."""
    if isinstance(brut, str) and brut.startswith('data:'):
        entete = brut[5:brut.find(',')] if ',' in brut else ''
        mime = entete.split(';')[0].strip().lower()
        return _EXT_PAR_MIME.get(mime, '.jpg')
    return '.jpg'


#: CRX31 — PLAFOND de photos acceptées par lien de questionnaire.
#: Le lien est PUBLIC et tokenisé : son porteur pouvait rejouer la même section
#: photo indéfiniment, chaque envoi stockant jusqu'à 10 Mo sur MinIO — un seul
#: lien suffisait donc à remplir le magasin de fichiers. Trois sections photo
#: existent (facture, compteur, tableau) ; le plafond laisse largement la place
#: aux reprises (photo floue, mauvaise section) tout en fermant la boucle.
PLAFOND_PHOTOS_PAR_LIEN = 12

#: Préfixe posé par ce module sur les fichiers qu'il joint (cf. `_enregistrer_photo`)
#: — c'est lui qui rend le plafond comptable sans nouvelle colonne.
PREFIXE_FICHIER_QUESTIONNAIRE = 'questionnaire-'


def _photos_deja_recues(lead) -> int:
    """Nombre de photos DÉJÀ jointes à ce lead par le questionnaire.

    Compté sur les pièces jointes réelles (le magasin qu'on veut borner), via
    le préfixe de nom posé par :func:`_enregistrer_photo` — aucune colonne
    ajoutée, aucun compteur à maintenir en cohérence. Le comptage est par LEAD :
    c'est un sur-ensemble du « par lien » (un lead a en pratique un lien
    questionnaire actif), donc une borne conservatrice, jamais permissive."""
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment

    return Attachment.objects.filter(
        company=lead.company,
        content_type=ContentType.objects.get_for_model(Lead),
        object_id=lead.pk,
        filename__startswith=PREFIXE_FICHIER_QUESTIONNAIRE,
    ).count()


def _enregistrer_photo(lead, section, photo):
    """Joint la photo d'une section photo_* au lead. Réutilise TEL QUEL le
    chemin de capture du site (``intake_photo.attach_capture_photo`` :
    base64/data-URL, magic-bytes, 10 Mo, MinIO, ``records.Attachment``
    company-scopé) — jamais un second magasin de fichiers.

    Le nom du fichier porte le mot-clé de la section pour que
    :func:`manquantes` la reconnaisse ensuite.

    CRX31 — au-delà de :data:`PLAFOND_PHOTOS_PAR_LIEN` photos déjà reçues, la
    photo est REFUSÉE (``None``, exactement comme une photo invalide : la
    section n'est simplement pas enregistrée). Le refus est journalisé côté
    serveur, jamais renvoyé en détail au porteur du lien."""
    from .intake_photo import attach_capture_photo

    if _photos_deja_recues(lead) >= PLAFOND_PHOTOS_PAR_LIEN:
        logger.warning(
            'questionnaire: plafond de %s photos atteint (lead #%s) — '
            'section %s refusée.',
            PLAFOND_PHOTOS_PAR_LIEN, lead.pk, section)
        return None

    mot = _PHOTO_MOTS_CLES[section][0]
    nom = f'{PREFIXE_FICHIER_QUESTIONNAIRE}{mot}{_extension_photo(photo)}'
    return attach_capture_photo(
        lead, {'photo': photo, 'photoFilename': nom})


#: Colonnes que ``Lead.save()`` RECALCULE à chaque écriture (dédup QW10) et
#: que ``date_modification`` (auto_now) suit. Un ``update_fields`` qui les
#: omet les laisserait rassir : le lead garderait l'e-mail normalisé de
#: l'ancienne adresse et la dédup cesserait de le retrouver. On les ajoute
#: donc dès que leur source est écrite.
_COLONNES_DERIVEES = {
    'email': ('email_normalise',),
    'telephone': ('phone_normalise',),
}


def _colonnes_a_ecrire(champs):
    """``update_fields`` complet : les champs de la section + ce que
    ``Lead.save()`` en dérive + l'horodatage de modification."""
    colonnes = list(champs)
    for source, derivees in _COLONNES_DERIVEES.items():
        if source in champs:
            colonnes.extend(derivees)
    colonnes.append('date_modification')
    return colonnes


def _sans_ecrasement_equipe(lead, section, champs, prefill_vu, ignorees):
    """QJR597 — retire de ``champs`` les réponses INCHANGÉES par rapport au
    pré-remplissage que le client a vu, quand l'équipe a modifié la valeur
    depuis l'ouverture du lien. Une correction VOLONTAIRE du client (valeur
    différente de ce qu'il a vu) passe toujours. Sans ``prefill_vu``
    exploitable, rien n'est retiré."""
    from .webhooks import champs_lead_depuis_reponses

    colonnes = colonnes_ecrites(section)
    vu = champs_lead_depuis_reponses(prefill_vu, colonnes)
    actuel_brut = prefill(lead, [section])
    gardes = {}
    for cle, valeur in champs.items():
        if cle in vu and valeur == vu[cle]:
            actuel = champs_lead_depuis_reponses(
                {cle: actuel_brut.get(cle)}, (cle,)).get(cle)
            if actuel != vu[cle]:
                if ignorees is not None:
                    ignorees.append(cle)
                LeadActivity.objects.create(
                    company=lead.company, lead=lead, user=None,
                    kind=LeadActivity.Kind.NOTE,
                    body=('Réponse client non appliquée : valeur modifiée '
                          "par l'équipe depuis l'ouverture du lien "
                          f'({cle})'))
                continue
        gardes[cle] = valeur
    return gardes


#: AGR411 — colonne de pompage écrite par le client → (colonne de provenance,
#: valeur posée). Mêmes valeurs que la saisie ERP (sérialiseur AGR400).
#: CIQ412 — idem pour les colonnes pro (sérialiseur CIQ401) : le client
#: DÉCLARE ; le cos φ se lit sur la facture.
_PROVENANCE_ECRITE = {
    'niveau_statique_m': ('niveau_statique_source', 'declare'),
    'besoin_eau_m3j': ('besoin_eau_source', 'client'),
    'tension_raccordement': ('tension_source', 'declare'),
    'compteur_puissance_kva': ('puissance_souscrite_source', 'declare'),
    'surface_toiture_m2': ('surface_source', 'declare'),
    'cos_phi': ('cos_phi_source', 'facture'),
}

#: CIQ412 — sections pro dont les réponses sont validées par le MODÈLE
#: (``Field.clean`` : type, choix fermés, validateurs CIQ401), colonne par
#: colonne — une valeur invalide est ignorée, jamais une erreur.
_SECTIONS_PRO_COLONNES = ('reseau', 'activite', 'site', 'societe')


def _champs_pro_depuis_reponses(lead, section, reponses) -> dict:
    """Réponses d'une section PRO → champs ``Lead`` propres (CIQ412).

    Seules les colonnes de la section (filtrées par segment) sont lues ;
    ``None``/chaîne vide = pas de réponse (on n'efface jamais). Le relevé de
    consommation est normalisé (au plus 12 mois) et porte la source
    ``declare``."""
    from django.core.exceptions import ValidationError

    from .models import normaliser_releve_conso

    if not isinstance(reponses, dict):
        return {}
    out = {}
    for cle in _colonnes_du_lead(lead, section):
        if cle not in reponses:
            continue
        brut = reponses[cle]
        if brut is None or (isinstance(brut, str) and not brut.strip()):
            continue
        if cle == 'releve_conso' and isinstance(brut, dict):
            brut = dict(brut, source='declare')
        try:
            valeur = Lead._meta.get_field(cle).clean(brut, lead)
        except (ValidationError, TypeError, ValueError):
            continue
        if cle == 'releve_conso':
            valeur = normaliser_releve_conso(valeur)
        if cle == 'reponses_categorie':
            categorie = (reponses.get('categorie_commerciale')
                         or lead.categorie_commerciale)
            permises = set(Lead.REPONSES_CATEGORIE_CLES.get(categorie, ()))
            if not isinstance(valeur, dict) or set(valeur) - permises:
                continue
        out[cle] = valeur
    if 'heure_debut' in out or 'heure_fin' in out:
        debut = out.get('heure_debut', lead.heure_debut)
        fin = out.get('heure_fin', lead.heure_fin)
        if debut is not None and fin is not None and debut >= fin:
            out.pop('heure_debut', None)
            out.pop('heure_fin', None)
    return out


def appliquer_section(lien, section, reponses=None, photo=None,
                      prefill_vu=None, ignorees=None):
    """Enregistre UNE section répondue par le client. Retourne la liste des
    clés réellement enregistrées (vide si rien d'exploitable).

    Garanties :
      · seule la section demandée est écrite (whitelist par section) ;
      · une valeur déjà renseignée n'est JAMAIS remplacée par du vide ;
      · l'historique du lead reçoit une note de section + une ligne
        ancienne→nouvelle valeur par champ suivi (mécanisme existant) ;
      · la progression du client est mémorisée sur le lien (reprise) ;
      · QJR597 — une réponse restée au pré-remplissage VU par le client
        (``prefill_vu``) n'écrase pas une valeur que l'équipe a corrigée
        depuis : la clé est sautée et ajoutée à ``ignorees`` (liste
        facultative remplie en place).
    """
    from django.utils import timezone

    from . import activity
    from .webhooks import champs_lead_depuis_reponses

    if section not in SECTIONS:
        raise SectionInconnue(f'Section inconnue : « {section} ».')
    if not lien.question_posee(section):
        raise SectionInconnue(
            f'Section non demandée sur ce lien : « {section} ».')

    lead = lien.lead
    if section not in sections_du_lead(lead):
        # AGR411 — filtre de segment (lien ancien, ou type changé depuis).
        raise SectionInconnue(
            f'Section non demandée sur ce lien : « {section} ».')
    enregistrees = []

    if section in _SECTIONS_PHOTO:
        if _enregistrer_photo(lead, section, photo) is not None:
            enregistrees.append('photo')
    else:
        if section in _SECTIONS_PRO_COLONNES:
            champs = _champs_pro_depuis_reponses(lead, section, reponses)
        else:
            champs = champs_lead_depuis_reponses(
                reponses, colonnes_ecrites(section))
        if champs and isinstance(prefill_vu, dict):
            champs = _sans_ecrasement_equipe(
                lead, section, champs, prefill_vu, ignorees)
        if champs:
            # Instantané AVANT écriture : le chatter compare l'ancien au
            # nouveau via le mécanisme existant (activity.log_changes).
            avant = Lead.objects.get(pk=lead.pk)
            for cle, valeur in champs.items():
                setattr(lead, cle, valeur)
            # AGR411 — une valeur de pompage écrite par le client porte sa
            # provenance (« déclarée ») ; le prix du carburant est DATÉ (Q17).
            serveur = []
            for cle, (source, origine) in _PROVENANCE_ECRITE.items():
                if cle in champs and getattr(avant, cle) != champs[cle]:
                    setattr(lead, source, origine)
                    serveur.append(source)
            if ('carburant_prix_unitaire_mad' in champs
                    and avant.carburant_prix_unitaire_mad
                    != champs['carburant_prix_unitaire_mad']):
                from core.dates import aujourd_hui_local
                lead.carburant_prix_declare_le = aujourd_hui_local()
                serveur.append('carburant_prix_declare_le')
            lead.save(update_fields=_colonnes_a_ecrire(
                list(champs) + serveur))
            enregistrees = list(champs)
            activity.log_changes(avant, lead, None)

    if not enregistrees:
        return []

    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=('Questionnaire — section '
              f'{LIBELLE_SECTION[section]} répondue par le client'),
    )

    repondues = lien.sections_repondues
    if not isinstance(repondues, dict):
        repondues = {}
    repondues[section] = True
    lien.sections_repondues = repondues
    lien.derniere_reponse_at = timezone.now()
    lien.save(update_fields=['sections_repondues', 'derniere_reponse_at'])
    # CRX33 — le questionnaire écrit exactement les champs qui NOURRISSENT le
    # score (facture, surface, orientation, toiture, raccordement, maturité
    # d'achat…). Sans recalcul APRÈS écriture, un prospect qui vient de tout
    # remplir restait « froid » dans la file du commercial jusqu'à une édition
    # manuelle — l'inverse de ce que le questionnaire sert à provoquer.
    # ``recompute_lead_score`` est best-effort : il n'échoue jamais l'appelant.
    # Le recalcul est posé ICI, APRÈS l'horodatage du lien : depuis CAD133 le
    # score compte « questionnaire répondu » d'après `derniere_reponse_at`, et
    # recalculer AVANT de l'écrire persistait un score périmé de 4 points —
    # deux valeurs différentes pour le même lead (la colonne triée d'un côté,
    # le calcul de l'autre), ce que CRX22 interdit.
    from .services import recompute_lead_score
    recompute_lead_score(lead)
    # CAD136 (audit L3 du 21/09/2026) — le responsable est PRÉVENU. Jusqu'ici
    # répondre au questionnaire enrichissait le lead, recalculait le score et
    # écrivait une note — sans aucune notification, et `derniere_reponse_at`
    # n'était relu par personne dans tout le dépôt. Le client vient pourtant
    # de passer cinq minutes sur NOTRE formulaire.
    from .services import (
        SIGNAL_QUESTIONNAIRE, notifier_signal_client, poser_touche_signal)
    notifier_signal_client(
        lead, SIGNAL_QUESTIONNAIRE,
        detail=f'Section « {LIBELLE_SECTION[section]} » renseignée.')
    # CAD136 × CAD130 — et la cadence BOUGE : une touche « Questionnaire
    # complété — appeler » dans la file, par la mécanique de CAD130 (UNE
    # touche même si le client répond à neuf sections, jamais hors fenêtre,
    # jamais sur un lead qu'on ne relance plus). Best-effort par construction.
    poser_touche_signal(lead, SIGNAL_QUESTIONNAIRE)
    return enregistrees


# ── Cycle de vie du lien (mint côté commercial, résolution côté public) ────

class LienIndisponible(Exception):
    """Jeton inconnu ou expiré (la vue publique traduit en 404 générique)."""


def url_publique(token, *, request=None) -> str:
    """URL complète de la page questionnaire pour un jeton donné.

    TOUJOURS construite sur l'origine du SITE PUBLIC (``PUBLIC_SITE_URL``),
    JAMAIS sur l'hôte de la requête. Revue critique du 25/08/2026, finding
    #6 : la page ``/questionnaire/<token>/`` vit dans ``apps/web`` (le site
    Astro) — l'ERP ne la sert nulle part. Le mint étant appelé depuis l'écran
    commercial, donc depuis l'hôte de l'API, ``build_absolute_uri`` fabriquait
    un lien sur l'API : le client recevait une URL MORTE.

    ``request`` est accepté et IGNORÉ : la signature reste celle des appelants
    existants, mais aucun hôte entrant ne peut plus décider où pointe un lien
    envoyé à un client (c'est aussi ce qui empêche un ``Host:`` forgé de
    fabriquer une URL de questionnaire sur un domaine tiers)."""
    from django.conf import settings

    base = (getattr(settings, 'PUBLIC_SITE_URL', '')
            or getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    return f'{base}/questionnaire/{token}/'


def mint_lien(lead, *, questions=None, user=None):
    """Crée — ou RÉUTILISE — le lien questionnaire d'un lead.

    IDEMPOTENT : tant qu'un lien non expiré existe pour ce lead, c'est LUI
    qui est renvoyé (ses ``questions`` sont simplement remises à jour) —
    jamais un second jeton, donc jamais deux liens vivants chez le client.

    ``questions=None`` (le commercial n'a rien coché) → les informations
    MANQUANTES, ordre fondateur. Multi-tenant : la société vient TOUJOURS du
    lead, jamais du corps de requête.

    Retourne ``(lien, change)`` — ``change`` est vrai quand le lien vient
    d'être créé OU que les questions posées ont réellement bougé (c'est ce
    qui mérite une trace dans l'historique ; un re-POST identique n'en
    laisse aucune)."""
    from django.utils import timezone

    maintenant = timezone.now()
    lien = (
        QuestionnaireLien.objects
        .filter(lead=lead, company=lead.company, expires_at__gt=maintenant)
        .order_by('-created_at')
        .first()
    )
    cree = lien is None
    if cree:
        lien = QuestionnaireLien(
            company=lead.company, lead=lead, created_by=user)
        avant = None
    else:
        avant = lien.questions if isinstance(lien.questions, dict) else {}

    lien.questions = (questions if questions is not None
                      else questions_par_defaut(lead))
    if cree:
        lien.save()
    else:
        lien.save(update_fields=['questions'])
    # Recalage fold 25/08 : troisième valeur ``cree`` — le dialogue ERP mint
    # SILENCIEUSEMENT à l'ouverture (pour lire manquantes/questions), et le
    # chatter ne doit jamais dire « envoyé » sur une simple ouverture ; le
    # libellé de la trace distingue donc création et mise à jour (l'envoi
    # WhatsApp réel n'est pas observable côté serveur — on ne l'affirme pas).
    return lien, cree or lien.questions != avant, cree


def resoudre(token):
    """Résout un jeton PUBLIC → ``(lien, interne)``.

    ``interne`` vaut True quand le jeton est celui du COMMERCIAL (aperçu) —
    l'appelant doit alors ne RIEN écrire ni journaliser. Lève
    :class:`LienIndisponible` si le jeton est inconnu ou expiré ; le lien
    n'est jamais « consommé » (magic-link : il se rouvre autant de fois que
    le client en a besoin, jusqu'à expiration)."""
    if not token:
        raise LienIndisponible('Introuvable.')
    lien = (QuestionnaireLien.objects
            .select_related('lead', 'company')
            .filter(token=token).first())
    interne = False
    if lien is None:
        lien = (QuestionnaireLien.objects
                .select_related('lead', 'company')
                .filter(token_interne=token).first())
        interne = lien is not None
    if lien is None or lien.is_expired:
        raise LienIndisponible('Introuvable.')
    # Un lead SUPPRIMÉ (soft-delete) ferme son lien : sans cette garde, la
    # page s'ouvrirait encore et l'écriture planterait plus loin
    # (``Lead.objects`` masque la corbeille). Un lead simplement ARCHIVÉ
    # reste ouvert — l'archivage est un rangement réversible du pipeline,
    # pas une raison de bloquer le client qui répond.
    if getattr(lien.lead, 'is_deleted', False):
        raise LienIndisponible('Introuvable.')
    return lien, interne


# ── CAD-L ── CAD148 — le grain « encore à OBTENIR » (panneau d'appel guidé)
#
# :func:`champs_a_poser` sert le questionnaire ENVOYÉ AU CLIENT : une donnée
# déjà portée y revient PRÉ-REMPLIE, à confirmer. Le panneau d'appel, lui, a
# besoin de l'autre moitié de la règle « on ne redemande jamais » : la liste
# des colonnes dont la réponse est encore à obtenir, pour ne JAMAIS faire
# poser à l'oral une question dont la fiche porte déjà la réponse. Les deux
# lisent la MÊME table (``CHAMPS_PAR_SECTION``) et le MÊME prédicat
# (:func:`_encore_a_obtenir`) — il n'y a pas deux règles.
def champs_encore_a_obtenir(lead, sections) -> dict:
    """``{section: [colonnes dont la réponse est encore à obtenir]}``."""
    return {
        section: [cle for cle in CHAMPS_PAR_SECTION.get(section, ())
                  if _encore_a_obtenir(lead, cle)]
        for section in sections
    }
