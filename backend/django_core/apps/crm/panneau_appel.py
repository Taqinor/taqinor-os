"""CAD148 — le PANNEAU D'APPEL GUIDÉ : ce que le serveur donne à l'écran d'appel.

Contrat servi : ``apps/crm/contract_samples/panneau_appel.json`` (CAD147).

CE QUE CE MODULE ASSEMBLE, ET POURQUOI IL N'INVENTE RIEN.

* Le SCRIPT vient de ``services.message_pour_etape`` — le rendu de gabarit est
  déjà CANAL-AGNOSTIQUE (il ne teste jamais le canal de la touche), donc un
  panneau d'appel n'a aucune raison d'écrire un second moteur de rendu. On
  retire seulement ``wa_url`` : un appel n'ouvre pas WhatsApp.
* Les QUESTIONS viennent de ``questionnaire.champs_encore_a_obtenir`` : une
  donnée que la fiche porte DÉJÀ n'est jamais reposée à l'oral. Elle n'est pas
  perdue pour autant — elle revient dans ``prefill``, pour que la commerciale
  voie ce qu'on sait sans le redemander.
* Le TEXTE de chaque question est le ``help_text`` du champ, lu à la source
  (« chaque champ EST le script d'appel ») : ce module ne formule aucune
  question, il les transporte.
* Les DRAPEAUX d'équipement viennent de
  ``apps.ventes.courbes_journalieres.composer_equipements`` — LA fonction qui
  décide vraiment ce qui compose une couche. Un équipement déclaré dont la
  grandeur manque est donc « pas compté », et le champ qui manque est NOMMÉ :
  c'est la question suivante à poser, pas une hypothèse à prendre.

ZÉRO CHIFFRE INVENTÉ : ``prefill`` ne contient que des valeurs réellement
portées par la fiche ; aucun défaut forfaitaire n'est jamais servi.
"""
import datetime
import decimal
import logging

from django.db import models

from . import questionnaire
from .models import Lead, RelanceEtape
from .segment_suggere import segment_suggere

logger = logging.getLogger(__name__)

#: CAD148 — `tranche_onee` ne se DEMANDE pas : c'est un texte libre qu'aucun
#: calcul ne lit (la grille tarifaire canonique vit dans `apps/ventes/pricing/`)
#: et qui se DÉRIVE de la facture et de la consommation. La poser à l'oral
#: ferait perdre une des cinq questions que l'appel 1 peut tenir.
CHAMPS_JAMAIS_DEMANDES = ('tranche_onee',)

#: CAD149 + décision fondateur du 21/09/2026 (Q21) — les questions qui ne se
#: posent QU'À L'ORAL : elles restent hors du questionnaire envoyé au client
#: (donc hors de ``CHAMPS_PAR_SECTION``), mais ce sont justement des questions
#: de CET appel. Sans cette liste, le panneau ne les proposerait jamais.
#: CAD154 ajoute le frein et le déclencheur : même vocabulaire que la
#: qualification de visite, et mêmes questions de découverte. `budget_client_mad`
#: reste HORS de cette liste — il ne se pose qu'APRÈS l'envoi du devis
#: (décision fondateur du 21/09/2026), une condition que ce panneau ne sait pas
#: encore lire sans interroger les devis du lead.
CHAMPS_ORAUX = ('decideur', 'devis_concurrents', 'frein_principal',
                'declencheur')

#: CAD148 — les colonnes NOT NULL à défaut non nul : leur valeur de départ ne
#: veut PAS dire « le client a répondu ». ``ete_differente`` vaut ``False`` dès
#: la création du lead (le module questionnaire le dit déjà : « sa colonne est
#: NOT NULL default False, donc elle vaut toujours Oui/Non ») — publier ce
#: ``False`` dans ``prefill`` reviendrait à servir un DÉFAUT pour une réponse,
#: exactement ce que ce panneau s'interdit. Tant qu'elle vaut ``False``, la
#: question reste posable et le pré-remplissage se tait ; à ``True``, c'est une
#: réponse, et elle cesse d'être une question.
CHAMPS_A_DEFAUT_NON_NUL = ('ete_differente',)

#: Mêmes questions, réservées au segment agricole : aucune section du
#: questionnaire client ne les porte, et elles n'ont de sens que pour un lead
#: de pompage. CAD175 — la seconde livraison du panneau y ajoute la pompe
#: elle-même (puissance, HMT, débit voulu : les trois entrées du générateur
#: en mode agricole, colonnes `pompe_*` déjà existantes), en tête. AGR401 —
#: la puissance posée est celle de la pompe ACTUELLE (`pompe_actuelle_cv`,
#: information) : la puissance retenue est une sortie du dimensionnement.
#: AGR407 — les CINQ étapes de l'appel agricole, dans l'ordre, chacune avec
#: les colonnes qui DIMENSIONNENT (contrat AGR1 ``lead_pompage.json``) :
#: (1) énergie actuelle, (2) eau, (3) besoin, (4) heures actuelles +
#: distance, (5) irrigation + électricité. ``pompe_actuelle_cv`` sort de
#: l'appel : elle se relève sur la PLAQUE, en visite. Aucune clé d'économie.
ETAPES_AGRICOLES = (
    ('energie_actuelle', ('pompe_alim_actuelle', 'butane_bouteilles_jour',
                          'carburant_litres_mois',
                          'carburant_prix_unitaire_mad',
                          'depense_carburant_mad_mois')),
    ('eau', ('source_eau', 'niveau_statique_m', 'debit_forage_m3h')),
    ('besoin', ('besoin_eau_m3j', 'surface_irriguee_ha', 'culture')),
    ('heures_distance', ('pompage_heures_jour', 'distance_forage_champ_m')),
    ('irrigation_electricite', ('irrigation_methode', 'mois_irrigation',
                                'electricite_sur_place')),
)
CHAMPS_ORAUX_AGRICOLE = tuple(
    champ for _etape, champs in ETAPES_AGRICOLES for champ in champs)

#: CIQ410 (D-CIQ-7) — les CINQ étapes du premier appel pro, dans l'ordre :
#: (1) la facture, (2) le raccordement, (3) l'activité et le rythme, (4) la
#: surface, (5) qui décide. Toutes les colonnes POSSIBLES ; celles qui
#: s'appliquent à CE lead (commercial/industriel, BT/MT) sont choisies par
#: :func:`_champs_pro_du_lead`. La puissance souscrite reste une question
#: PREMIÈRE (CAD175). Aucune clé d'économie.
ETAPES_PRO = (
    ('facture', ('conso_mensuelle_kwh', 'facture_hiver')),
    ('raccordement', ('tension_raccordement', 'compteur_puissance_kva',
                      'raccordement')),
    ('activite_rythme', ('categorie_commerciale', 'reponses_categorie',
                         'secteur_industriel', 'regime_equipes',
                         'jours_ouverture', 'heure_debut', 'heure_fin',
                         'fermeture_mois')),
    ('surface', ('type_surface', 'type_toiture', 'surface_toiture_m2')),
    ('decideur', ('decideur',)),
)
CHAMPS_ORAUX_PRO = tuple(
    champ for _etape, champs in ETAPES_PRO for champ in champs)

#: CIQ410 — la question PRO de chaque colonne, reprise MOT POUR MOT du
#: contrat CIQ1 (``lead_pro.json`` : ``questions_pro`` pour les variantes
#: par segment, ``colonnes_pro[].question`` sinon) — jamais une surcharge du
#: ``help_text`` résidentiel (« la photo du compteur », « votre maison »).
QUESTIONS_PRO = {
    'conso_mensuelle_kwh': {
        'commercial': "« Combien payez-vous d'électricité par mois, à peu "
                      "près ? Ou combien de kWh, si vous l'avez sous les "
                      "yeux ? »",
        'industriel': '« Combien de kWh consommez-vous par mois ? Ils sont '
                      'sur votre facture, avec les heures de pointe, pleines '
                      'et creuses. »'},
    'tension_raccordement': {
        'commercial': '« Votre site est-il raccordé en basse tension, avec '
                      'un compteur ordinaire, ou en moyenne tension, avec un '
                      'poste de transformation ? »',
        'industriel': '« Votre site a-t-il son propre poste de '
                      'transformation, en moyenne tension ? »'},
    'compteur_puissance_kva': '« Quelle est votre puissance souscrite, en '
                              'kVA ? Elle est écrite sur votre facture ou '
                              'votre contrat. »',
    'decideur': {
        'commercial': '« Qui prendra la décision pour ce projet ? »',
        'industriel': "« Qui décide d'un tel investissement chez vous : la "
                      'direction, un comité, le groupe ? »'},
    'raccordement': '« Votre compteur est-il monophasé ou triphasé ? »',
    'categorie_commerciale': '« Quelle est votre activité : hôtel, '
                             'restaurant ou café, commerce, bureaux, santé, '
                             'école, hammam, boulangerie, froid, ou autre '
                             'chose ? »',
    'reponses_categorie': "Les questions propres à l'activité, posées "
                          "juste après elle (une réponse par ligne).",
    'secteur_industriel': '« Que fabriquez-vous ou que transformez-vous sur '
                          'ce site ? »',
    'regime_equipes': '« Travaillez-vous en une équipe de jour, en deux '
                      'équipes, en trois équipes, ou en continu ? »',
    'jours_ouverture': '« Quels jours de la semaine êtes-vous ouverts ou en '
                       'production ? »',
    'heure_debut': '« À quelle heure commence votre journée de travail ? »',
    'heure_fin': '« Et à quelle heure se termine-t-elle ? »',
    'fermeture_mois': "« Fermez-vous certains mois de l'année, pour des "
                      'congés ou une saison creuse ? Lesquels ? »',
    'type_surface': '« Où pourrait-on poser les panneaux : sur la toiture, '
                    'sur une ombrière de parking, ou sur un terrain ? »',
    'type_toiture': '« Comment est faite votre toiture : terrasse béton, '
                    'tôle, tuiles, bac acier, fibrociment ? »',
    'surface_toiture_m2': '« Quelle surface est disponible pour les '
                          'panneaux, à peu près, en mètres carrés ? »',
}
# Même question pour la facture en dirhams : « en dirhams ou en kWh ».
QUESTIONS_PRO['facture_hiver'] = QUESTIONS_PRO['conso_mensuelle_kwh']

#: CIQ410 — préfixe commun des questions orales (même forme que les
#: ``help_text`` du modèle).
PREFIXE_QUESTION = "Question à l'appel : "

#: CIQ410 — choix PRO de « qui décide » : vocabulaire inchangé, seule la
#: présentation est filtrée (« avec le conjoint / la famille » n'a pas de
#: sens pour une entreprise).
DECIDEUR_PRO = ('seul', 'associe_direction', 'proprietaire_tiers')

#: CIQ410 — au plus TROIS questions propres à l'activité, prises dans
#: l'ordre de ``Lead.REPONSES_CATEGORIE_CLES``. Libellés : questions ajoutées
#: du contrat CIQ1 (``questions_ajoutees``), sinon les libellés du
#: générateur (``COMMERCIAL_CATEGORY_QUESTIONS``, frontend ventes/solar.js).
MAX_REPONSES_CATEGORIE = 3
LIBELLES_REPONSES_CATEGORIE = {
    'chambres': 'Nombre de chambres',
    'occupation_pct': "« Quel est votre taux d'occupation moyen sur "
                      "l'année, à peu près ? »",
    'piscine': 'Piscine chauffée',
    'heures_piscine': "« La piscine fonctionne combien d'heures par jour ? »",
    'blanchisserie': '« Lavez-vous le linge sur place ? »',
    'reception_24h': '« La réception est-elle ouverte 24 heures sur 24 ? »',
    'chambres_froides': 'Chambres froides',
    'horaires': 'Horaires',
    'cuisson': 'Cuisson',
    'ouvert_journee_ramadan': '« Pendant le Ramadan, êtes-vous ouverts en '
                              'journée ? »',
    'surface_vente_m2': 'Surface de vente (m²)',
    'effectif': 'Effectif',
    'clim': 'Climatisation centralisée',
    'lits': 'Nombre de lits',
    'garde_nuit': 'Garde de nuit',
    'internat': 'Internat',
    'fermeture_estivale': 'Fermeture estivale',
    'surface_m2': 'Surface (m²)',
    'chauffe': 'Chauffe eau',
    'four': 'Four',
    'cuisson_nocturne': 'Cuisson nocturne',
    'temperature_consigne': 'Température de consigne (°C)',
    'volume_m3': 'Volume froid (m³)',
    'saisonnalite_recolte': 'Pic saisonnier (récolte)',
}

#: (clé de couche, libellé, booléen déclaratif du lead, grandeurs qui rendent
#: la couche composable). La clé de couche est celle que
#: ``composer_equipements`` renvoie : c'est elle qui tranche « compté ou non »,
#: pas cette table.
EQUIPEMENTS = (
    ('piscine', 'Piscine', 'equip_piscine',
     ('equip_piscine_pompe_kw',)),
    ('clim', 'Climatisation', 'equip_clim',
     ('equip_clim_kw', 'equip_clim_pieces')),
    ('ve', 'Véhicule électrique', 'equip_voiture_electrique',
     ('equip_ve_km_semaine',)),
    ('chauffe_eau', 'Chauffe-eau électrique', 'equip_chauffe_eau_electrique',
     ('equip_chauffe_eau_kw', 'equip_chauffe_eau_creneau')),
)


def _json(valeur):
    """Valeur du lead rendue JSON-safe, SANS jamais rien inventer."""
    if isinstance(valeur, decimal.Decimal):
        return float(valeur)
    if isinstance(valeur, (datetime.date, datetime.datetime)):
        return valeur.isoformat()
    if isinstance(valeur, str) and not valeur.strip():
        return None
    return valeur


def _vide(valeur) -> bool:
    """``None`` ou chaîne blanche. ``False`` et ``0`` sont des RÉPONSES."""
    if valeur is None:
        return True
    return isinstance(valeur, str) and not valeur.strip()


def _reponse_connue(lead, champ) -> bool:
    """La fiche porte-t-elle une VRAIE réponse pour ce champ ?

    ``False`` et ``0`` sont des réponses — sauf sur les colonnes de
    ``CHAMPS_A_DEFAUT_NON_NUL``, où le ``False`` de départ n'est que le défaut
    de la colonne (voir son commentaire)."""
    valeur = getattr(lead, champ, None)
    if _vide(valeur):
        return False
    if champ in CHAMPS_A_DEFAUT_NON_NUL and valeur is False:
        return False
    return True


#: CAD152 — un booléen EST un vocabulaire fermé (Oui/Non) : il est servi
#: comme tel, pour que l'écran d'appel rende deux boutons au lieu d'un champ
#: libre où « oui » serait refusé par le serveur. L'ordre (Oui d'abord) est
#: celui dans lequel la question se pose.
CHOIX_BOOLEEN = (
    {'valeur': True, 'libelle': 'Oui'},
    {'valeur': False, 'libelle': 'Non'},
)


#: AGR407 — les 12 mois, vocabulaire FERMÉ d'une liste d'entiers 1-12.
CHOIX_MOIS = tuple(
    {'valeur': numero, 'libelle': libelle} for numero, libelle in enumerate(
        ('Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet',
         'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'), start=1))

#: AGR407 / CIQ410 — colonnes JSON « liste d'entiers » servies en
#: ``choix_multiple`` (l'écran rend des boutons à cocher, jamais un champ
#: libre) : la clé est la colonne, la valeur son vocabulaire fermé.
#: CIQ410 — les 7 jours, 1 = lundi … 7 = dimanche (contrat CIQ1).
CHOIX_JOURS = tuple(
    {'valeur': numero, 'libelle': libelle} for numero, libelle in enumerate(
        ('Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi',
         'Dimanche'), start=1))

CHOIX_MULTIPLES = {
    'mois_irrigation': CHOIX_MOIS,
    'jours_ouverture': CHOIX_JOURS,
    'fermeture_mois': CHOIX_MOIS,
}


def _choix(champ):
    """``[{valeur, libelle}]`` d'un champ à vocabulaire fermé, sinon ``None``.

    Un booléen est un vocabulaire fermé (Oui/Non, :data:`CHOIX_BOOLEEN`) ;
    une liste d'entiers de :data:`CHOIX_MULTIPLES` aussi."""
    if champ in CHOIX_MULTIPLES:
        return [dict(choix) for choix in CHOIX_MULTIPLES[champ]]
    meta = Lead._meta.get_field(champ)
    if isinstance(meta, models.BooleanField):
        return [dict(choix) for choix in CHOIX_BOOLEEN]
    brut = meta.choices
    if not brut:
        return None
    return [{'valeur': valeur, 'libelle': str(libelle)}
            for valeur, libelle in brut]


def _nature(champ):
    """CAD152 — la NATURE de la saisie : ``choix`` (vocabulaire fermé, dont
    Oui/Non), ``nombre`` (l'écran normalise la virgule décimale avant
    d'écrire) ou ``texte``. Lue sur le champ lui-même, jamais devinée.
    AGR407 — ``choix_multiple`` pour une liste d'entiers à vocabulaire
    fermé (:data:`CHOIX_MULTIPLES`)."""
    if champ in CHOIX_MULTIPLES:
        return 'choix_multiple'
    meta = Lead._meta.get_field(champ)
    if isinstance(meta, models.BooleanField) or meta.choices:
        return 'choix'
    if isinstance(meta, (models.DecimalField, models.IntegerField,
                         models.FloatField)):
        return 'nombre'
    return 'texte'


def _segment_pro(lead):
    """``'commercial'`` / ``'industriel'`` pour un lead pro, sinon ``None``."""
    segment = getattr(lead, 'type_installation', None) or ''
    if segment in (Lead.TypeInstallation.INDUSTRIEL,
                   Lead.TypeInstallation.COMMERCIAL):
        return str(segment)
    return None


def _cles_categorie_a_poser(lead):
    """CIQ410 — les (au plus 3) clés propres à l'activité encore sans
    réponse ; ``()`` tant que la catégorie n'est pas connue."""
    categorie = getattr(lead, 'categorie_commerciale', None) or ''
    cles = Lead.REPONSES_CATEGORIE_CLES.get(categorie, ())
    reponses = getattr(lead, 'reponses_categorie', None)
    reponses = reponses if isinstance(reponses, dict) else {}
    return tuple(c for c in cles[:MAX_REPONSES_CATEGORIE]
                 if reponses.get(c) is None)


def _question_pro(lead, champ, segment):
    """CIQ410 — la question PRO d'une colonne (``QUESTIONS_PRO``)."""
    texte = QUESTIONS_PRO[champ]
    if isinstance(texte, dict):
        texte = texte[segment]
    if champ == 'reponses_categorie':
        texte = '%s %s' % (texte, ' ; '.join(
            LIBELLES_REPONSES_CATEGORIE.get(c, c)
            for c in _cles_categorie_a_poser(lead)))
    return PREFIXE_QUESTION + texte


def _question(lead, champ, section):
    meta = Lead._meta.get_field(champ)
    choix = _choix(champ)
    nature = _nature(champ)
    # « Chaque champ EST le script d'appel » : le texte vient d'ici et de
    # nulle part ailleurs. Une formulation à améliorer se corrige dans le
    # `help_text` du modèle, jamais dans ce module. CIQ410 — un lead PRO lit
    # la question pro du contrat CIQ1, jamais la consigne résidentielle.
    question = str(meta.help_text or '')
    segment = _segment_pro(lead)
    if segment and champ in QUESTIONS_PRO:
        question = _question_pro(lead, champ, segment)
        if champ == 'decideur' and choix:
            choix = [c for c in choix if c['valeur'] in DECIDEUR_PRO]
        if champ == 'reponses_categorie':
            nature = 'objet'
    return {
        'champ': champ,
        'section': section,
        'libelle': str(meta.verbose_name),
        'question': question,
        'choix': choix,
        'nature': nature,
    }


def _champs_pro_du_lead(lead, segment):
    """CIQ410 — les colonnes des cinq étapes qui s'appliquent à CE lead.

    (1) UNE question de facture : en kWh d'abord pour un industriel ou un
    site MT, en dirhams sinon ; (2) mono/tri seulement pour un commercial
    hors MT ; (3) catégorie + ses questions (commercial) ou secteur + équipes
    (industriel), puis le rythme ; (4) la surface ; (5) qui décide."""
    mt = (getattr(lead, 'tension_raccordement', None) or '') == 'mt'
    champs = []
    kwh_d_abord = segment == 'industriel' or mt
    champs.append('conso_mensuelle_kwh' if kwh_d_abord else 'facture_hiver')
    champs += ['tension_raccordement', 'compteur_puissance_kva']
    if segment == 'commercial' and not mt:
        champs.append('raccordement')
    if segment == 'commercial':
        champs.append('categorie_commerciale')
        if _cles_categorie_a_poser(lead):
            champs.append('reponses_categorie')
    else:
        champs += ['secteur_industriel', 'regime_equipes']
    champs += ['jours_ouverture', 'heure_debut', 'heure_fin',
               'fermeture_mois', 'type_surface', 'type_toiture',
               'surface_toiture_m2', 'decideur']
    return tuple(champs)


#: CIQ410 — l'étape « facture » est répondue dès qu'UNE de ces colonnes
#: porte une réponse (kWh, dirhams ou kWh du diagnostic).
CHAMPS_FACTURE_PRO = ('conso_mensuelle_kwh', 'facture_hiver', 'bill_kwh')


def _reponse_connue_panneau(lead, champ):
    """``_reponse_connue`` + les deux règles de groupe du pro (CIQ410)."""
    if _segment_pro(lead) and champ in ('conso_mensuelle_kwh',
                                        'facture_hiver'):
        return any(_reponse_connue(lead, c) for c in CHAMPS_FACTURE_PRO)
    if champ == 'reponses_categorie' and _segment_pro(lead):
        return not _cles_categorie_a_poser(lead)
    return _reponse_connue(lead, champ)


def champs_oraux_du_segment(lead):
    """Les questions orales qui s'appliquent à CE lead, dans l'ordre.

    AGR407 — agricole : les cinq étapes d'abord (l'ordre du script), puis
    les questions orales communes. CIQ410 — pro : de même, les cinq étapes
    de D-CIQ-7 d'abord."""
    segment = getattr(lead, 'type_installation', None)
    if segment == Lead.TypeInstallation.AGRICOLE:
        etapes = tuple(CHAMPS_ORAUX_AGRICOLE)
    elif _segment_pro(lead):
        etapes = _champs_pro_du_lead(lead, _segment_pro(lead))
    else:
        return tuple(CHAMPS_ORAUX)
    return etapes + tuple(c for c in CHAMPS_ORAUX if c not in etapes)


def _sections_du_panneau(lead):
    """Les sections du questionnaire que le panneau lit pour CE lead.

    AGR407 — un lead agricole ne reçoit AUCUNE section résidentielle
    (facture, toit, occupation, équipements : refusées par AGR411) : ses
    questions sont les cinq étapes orales. CIQ410 — un lead pro non plus
    (occupation, foyer, équipements, type_bien n'ont aucun sens pour une
    entreprise). Les autres gardent le périmètre historique, inchangé."""
    if questionnaire.est_agricole(lead) or _segment_pro(lead):
        return ()
    return questionnaire.SECTIONS_HORS_POMPAGE


def questions_a_poser(lead):
    """Les questions encore à poser sur CE lead — jamais une déjà répondue.

    Deux sources, une seule règle : les colonnes des sections du questionnaire
    dont la réponse est encore à obtenir, puis les questions ORALES (celles que
    le questionnaire client ne porte pas). ``tranche_onee`` est retirée : elle
    se dérive, on ne la demande pas.
    """
    sections = _sections_du_panneau(lead)
    carte = questionnaire.champs_encore_a_obtenir(lead, sections)
    questions, vus = [], set()
    for section in sections:
        a_obtenir = set(carte.get(section, ()))
        for champ in questionnaire.CHAMPS_PAR_SECTION.get(section, ()):
            if champ in CHAMPS_JAMAIS_DEMANDES or champ in vus:
                continue
            # Une colonne à défaut non nul n'apparaît jamais dans
            # `a_obtenir` (sa valeur n'est jamais « vide ») : elle reste une
            # question tant que ce défaut n'a pas été remplacé par un oui.
            a_poser = champ in a_obtenir or (
                champ in CHAMPS_A_DEFAUT_NON_NUL
                and not _reponse_connue(lead, champ))
            if not a_poser:
                continue
            vus.add(champ)
            questions.append(_question(lead, champ, section))
    for champ in champs_oraux_du_segment(lead):
        if champ in vus or _reponse_connue_panneau(lead, champ):
            continue
        vus.add(champ)
        questions.append(_question(lead, champ, None))
    return questions


def prefill_du_panneau(lead):
    """``{champ: valeur}`` de ce que la fiche porte DÉJÀ, parmi les questions
    du panneau. C'est l'exact complément de :func:`questions_a_poser` : ce qui
    est là ne se redemande pas, mais se RELIT — et rien n'y est inventé.
    """
    candidats = []
    for section in _sections_du_panneau(lead):
        candidats.extend(questionnaire.CHAMPS_PAR_SECTION.get(section, ()))
    candidats.extend(champs_oraux_du_segment(lead))
    if _segment_pro(lead):
        # CIQ410 — la facture se relit quelle que soit sa colonne.
        candidats.extend(CHAMPS_FACTURE_PRO)
    out = {}
    for champ in candidats:
        if champ in CHAMPS_JAMAIS_DEMANDES or champ in out:
            continue
        if not _reponse_connue(lead, champ):
            continue
        out[champ] = _json(getattr(lead, champ, None))
    return out


def _couches_composables(lead):
    """Clés de couches que l'étude sait VRAIMENT composer pour ce lead.

    Lecture cross-app par la façade publique de ``apps.ventes`` — jamais ses
    modèles. Best-effort : une étude illisible ne doit pas priver la
    commerciale de son panneau d'appel."""
    try:
        from apps.ventes.courbes_journalieres import composer_equipements

        from .selectors import equipements_pour_lead
        return set(composer_equipements(equipements_pour_lead(lead)) or {})
    except Exception:  # noqa: BLE001 — le panneau reste servi
        logger.warning('CAD148: couches d\'équipement illisibles (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return set()


def drapeaux_equipements(lead):
    """Par équipement : déclaré ? compté dans l'étude ? sinon, quoi manque.

    « Compté » n'est PAS « déclaré » : la clim déclarée sans sa puissance ni
    son nombre de pièces ne compose aucune couche — le chiffre montré au client
    ne la contient pas. Le dire à l'écran, avec le champ manquant NOMMÉ, c'est
    ce qui transforme un silence en question suivante."""
    composables = _couches_composables(lead)
    out = []
    for cle, libelle, booleen, grandeurs in EQUIPEMENTS:
        declare = getattr(lead, booleen, None) is True
        compte = cle in composables
        manquants = []
        if declare and not compte:
            manquants = [champ for champ in grandeurs
                         if _vide(getattr(lead, champ, None))]
        out.append({
            'cle': cle,
            'libelle': libelle,
            'declare': declare,
            'compte_dans_etude': compte,
            'champs_manquants': manquants,
        })
    return out


def _touche_en_cours(lead):
    """La prochaine touche À FAIRE du lead, ou ``None``.

    Même tri que ``services._prochaine_touche_a_faire`` (l'heure d'abord, les
    lignes sans heure en dernier) : le panneau d'appel et la file « Relances du
    jour » ne doivent jamais désigner deux touches différentes."""
    from django.db.models import F

    return (lead.relance_etapes
            .filter(statut=RelanceEtape.Statut.A_FAIRE)
            .order_by(F('due_at').asc(nulls_last=True), 'due_date', 'ordre')
            .first())


def _touche_servie(etape):
    if etape is None:
        return None
    return {
        'id': etape.pk,
        'rang': etape.ordre,
        'template_cle': etape.template_cle or '',
        'canal': etape.canal,
        'statut': etape.statut,
        'prevue_le': etape.due_date.isoformat() if etape.due_date else None,
        'heure_cible': (etape.due_at.astimezone().strftime('%H:%M')
                        if etape.due_at else None),
    }


def _script_servi(etape, *, request=None, user=None):
    """Le script de la touche, forme `relance_etape_message` SANS `wa_url`."""
    if etape is None:
        return None
    from . import services
    rendu = services.message_pour_etape(etape, request=request, user=user)
    return {
        'message': rendu.get('message') or '',
        'langue': rendu.get('langue') or 'fr',
        'placeholders_manquants': list(
            rendu.get('placeholders_manquants') or []),
    }


def _hhmm(heure):
    return heure.strftime('%H:%M') if heure is not None else None


def fenetre_du_jour_servie(lead, *, maintenant=None):
    """CAD155 — la fenêtre d'APPEL du jour, telle que le MOTEUR l'appliquera.

    Lue par ``apps.crm.horaires.fenetre_du_jour`` — l'unique autorité des
    touches de cadence (Ramadan SAISI par la société, pause de la prière du
    vendredi, jours ouvrés et fériés) — et jamais recopiée : sinon l'écran
    divergerait du moteur au premier réglage. Pendant le Ramadan, la fenêtre
    est commune à tous les canaux et AUCUN créneau du soir n'existe (décision
    fondateur du 21/09/2026, CAD39) : l'écran n'a donc rien d'autre à
    proposer que ce qui est servi ici.

    ``None`` quand la fenêtre est illisible (best-effort : le panneau reste
    servi, il ne dit simplement rien de l'horaire — jamais un horaire
    supposé). Le jour est celui de Casablanca, pas celui du serveur.
    """
    from django.utils import timezone

    from . import horaires

    try:
        instant = maintenant or timezone.now()
        jour = instant.astimezone(horaires.CASABLANCA).date()
        company = getattr(lead, 'company', None)
        fenetre = horaires.fenetre_du_jour(jour, company, canal='appel')
        ramadan = bool(horaires.est_en_ramadan(jour, company))
    except Exception:  # noqa: BLE001 — l'horaire n'empêche jamais l'appel
        logger.warning('CAD155: fenêtre d\'appel illisible (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return None
    if fenetre is None:
        return {'date': jour.isoformat(), 'appelable': False, 'debut': None,
                'fin': None, 'pause': None, 'ramadan': ramadan}
    debut, fin, pause = fenetre
    return {
        'date': jour.isoformat(),
        'appelable': True,
        'debut': _hhmm(debut),
        'fin': _hhmm(fin),
        'pause': ({'debut': _hhmm(pause[0]), 'fin': _hhmm(pause[1])}
                  if pause else None),
        'ramadan': ramadan,
    }


def profil_suppose_servi(lead):
    """CAD172 — le profil de journée de l'étude est-il SUPPOSÉ pour ce lead ?

    LE MÊME drapeau que la proposition (``apps.ventes.courbes_journalieres``
    ``profil_suppose_du_lead`` — même traducteur que le chemin sans devis) :
    vrai tant que ``occupation_jour`` n'a pas de réponse. C'est lui qui fait
    remonter la question EN TÊTE du panneau (décision Q5). Lecture de la
    façade publique d'``apps.ventes``, jamais ses modèles ; best-effort (un
    drapeau illisible vaut ``False`` : on ne crie jamais au loup)."""
    try:
        from apps.ventes.courbes_journalieres import profil_suppose_du_lead
        return bool(profil_suppose_du_lead(lead))
    except Exception:  # noqa: BLE001 — le panneau reste servi
        logger.warning('CAD172: drapeau de profil illisible (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return False


def panneau_appel(lead, *, request=None, user=None) -> dict:
    """Le panneau d'appel guidé d'UN lead — lecture seule, aucun effet de bord."""
    etape = _touche_en_cours(lead)
    segment = lead.type_installation or None
    return {
        'lead_id': lead.pk,
        'segment': segment,
        'segment_libelle': (lead.get_type_installation_display()
                            if segment else None),
        # AGR406 — segment SUGGÉRÉ (lecture seule, jamais écrit) : le bandeau
        # « Segment probable : … — à confirmer » de l'écran d'appel.
        'segment_suggere': segment_suggere(lead),
        'touche': _touche_servie(etape),
        'script': _script_servi(etape, request=request, user=user),
        'champs_a_poser': questions_a_poser(lead),
        'prefill': prefill_du_panneau(lead),
        'equipements': ([] if _segment_pro(lead) else drapeaux_equipements(lead)),
        'fenetre_du_jour': fenetre_du_jour_servie(lead),
        'profil_suppose': profil_suppose_servi(lead),
    }
