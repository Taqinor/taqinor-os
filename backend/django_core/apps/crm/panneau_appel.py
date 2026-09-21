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

from . import questionnaire
from .models import Lead, RelanceEtape

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
#: de pompage.
CHAMPS_ORAUX_AGRICOLE = (
    'pompage_heures_jour', 'pompe_alim_actuelle', 'carburant_litres_mois',
)

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


def _choix(champ):
    """``[{valeur, libelle}]`` d'un champ à vocabulaire fermé, sinon ``None``."""
    brut = Lead._meta.get_field(champ).choices
    if not brut:
        return None
    return [{'valeur': valeur, 'libelle': str(libelle)}
            for valeur, libelle in brut]


def _question(lead, champ, section):
    meta = Lead._meta.get_field(champ)
    return {
        'champ': champ,
        'section': section,
        'libelle': str(meta.verbose_name),
        # « Chaque champ EST le script d'appel » : le texte vient d'ici et de
        # nulle part ailleurs. Une formulation à améliorer se corrige dans le
        # `help_text` du modèle, jamais dans ce module.
        'question': str(meta.help_text or ''),
        'choix': _choix(champ),
    }


def champs_oraux_du_segment(lead):
    """Les questions orales qui s'appliquent à CE lead, dans l'ordre."""
    champs = list(CHAMPS_ORAUX)
    if getattr(lead, 'type_installation', None) == Lead.TypeInstallation.AGRICOLE:
        champs += list(CHAMPS_ORAUX_AGRICOLE)
    return tuple(champs)


def questions_a_poser(lead):
    """Les questions encore à poser sur CE lead — jamais une déjà répondue.

    Deux sources, une seule règle : les colonnes des sections du questionnaire
    dont la réponse est encore à obtenir, puis les questions ORALES (celles que
    le questionnaire client ne porte pas). ``tranche_onee`` est retirée : elle
    se dérive, on ne la demande pas.
    """
    carte = questionnaire.champs_encore_a_obtenir(
        lead, questionnaire.SECTIONS)
    questions, vus = [], set()
    for section in questionnaire.SECTIONS:
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
        if champ in vus or _reponse_connue(lead, champ):
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
    for section in questionnaire.SECTIONS:
        candidats.extend(questionnaire.CHAMPS_PAR_SECTION.get(section, ()))
    candidats.extend(champs_oraux_du_segment(lead))
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


def panneau_appel(lead, *, request=None, user=None) -> dict:
    """Le panneau d'appel guidé d'UN lead — lecture seule, aucun effet de bord."""
    etape = _touche_en_cours(lead)
    segment = lead.type_installation or None
    return {
        'lead_id': lead.pk,
        'segment': segment,
        'segment_libelle': (lead.get_type_installation_display()
                            if segment else None),
        'touche': _touche_servie(etape),
        'script': _script_servi(etape, request=request, user=user),
        'champs_a_poser': questions_a_poser(lead),
        'prefill': prefill_du_panneau(lead),
        'equipements': drapeaux_equipements(lead),
    }
