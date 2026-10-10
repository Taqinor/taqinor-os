"""Retour de visite vers le lead (crochet visite, relevés, récapitulatif) (SPL7, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import re as _re

from . import activity
from .models import Lead, LeadActivity


# ── VT1 — CHATTER AUTOMATIQUE DE LA VISITE TECHNIQUE TERRAIN ─────────────────
#
# Le chatter du lead (``LeadActivity``) est le journal COMMUN de tout ce qui
# arrive à un lead : la visite technique y écrit ses quatre moments — création,
# terminaison, feu vert, renvoi — plutôt que d'ouvrir un second historique.
# L'auteur et la société viennent TOUJOURS du serveur (jamais du corps de
# requête), comme le reste du chatter.


#: Moment de la visite → phrase FR posée au chatter.
_VISITE_CHATTER = {
    'creation': 'Visite technique créée.',
    'terminee': 'Visite technique terminée par le commercial.',
    'validee': "Visite technique validée par le bureau d'études (feu vert).",
    'a_refaire': 'Visite technique renvoyée au commercial.',
}


def journaliser_visite(visite, user, moment, detail=''):
    """Pose UNE note de chatter sur le lead pour ``moment``.

    Best-effort : un chatter indisponible ne doit jamais faire échouer la
    transition métier qui vient d'aboutir (même prudence qu'ailleurs dans ce
    module). Renvoie l'activité créée, ou ``None``.
    """
    from . import activity

    phrase = _VISITE_CHATTER.get(moment)
    if phrase is None:
        return None
    corps = f'{phrase} {detail}'.strip() if detail else phrase
    try:
        return activity.log_note(visite.lead, user, corps)
    except Exception:  # pragma: no cover - défensif, jamais bloquant
        return None


# ── VT3/VT12/VTA5 — RETOUR DU FEU VERT SUR LA FICHE LEAD ─────────────────────
#
# VTA5 — l'app ``visites`` n'appelle PLUS ce retour : elle ÉMET
# ``visite_validee`` (bus ``core.events``) et c'est ``apps/crm/receivers.py``
# qui s'abonne et appelle cette fonction avec le récap DÉJÀ calculé par le
# selector de l'app visites. Le CRM n'a donc plus rien à recalculer, et
# ``visites`` ne fait plus aucun écrit sur ``crm.Lead``.


#: ALEA28 — balises du bloc de récap PAR VISITE dans ``Lead.visite_notes``.
_RECAP_DEBUT = '[Récap visite n°{}]'
_RECAP_FIN = '[/Récap visite n°{}]'
_RE_BLOC_RECAP = _re.compile(
    r'\[Récap visite n°(\d+)\]\n.*?\n\[/Récap visite n°\1\]', _re.S)


def _bloc_recap_visite(visite_id, recap):
    return (f'{_RECAP_DEBUT.format(visite_id)}\n{recap}\n'
            f'{_RECAP_FIN.format(visite_id)}')


def _notes_avec_recap(existantes, recap, visite_id):
    """ALEA28 — ``existantes`` où le récap de ``visite_id`` est REMPLACÉ.

    * la visite a déjà son bloc → son contenu est remplacé (R1 → R2), le
      reste du texte (saisie manuelle, blocs des autres visites) est intact ;
    * pas encore de bloc, mais le même récap présent HORS bloc (écrit avant
      ALEA28) → cette occurrence est balisée en place, jamais dupliquée ;
    * le même récap déjà porté par le bloc d'une AUTRE visite → rien
      (même phrase, aucune information de plus) ;
    * sinon le bloc est ajouté à la fin.
    """
    bloc = _bloc_recap_visite(visite_id, recap)
    for trouve in _RE_BLOC_RECAP.finditer(existantes):
        if trouve.group(1) == str(visite_id):
            return (existantes[:trouve.start()] + bloc
                    + existantes[trouve.end():])
    blocs = [(m.start(), m.end()) for m in _RE_BLOC_RECAP.finditer(existantes)]
    debut = existantes.find(recap)
    while debut != -1:
        if not any(a <= debut < b for a, b in blocs):
            return (existantes[:debut] + bloc
                    + existantes[debut + len(recap):])
        debut = existantes.find(recap, debut + 1)
    if recap in existantes:
        return existantes
    return f'{existantes}\n{bloc}'.strip() if existantes else bloc


def ecrire_retour_lead_visite(lead, recap, visite_id=None):
    """VT12 — le feu vert REDESCEND sur la fiche lead.

    Le lead est la fiche que tout le monde ouvre : après le feu vert, il porte
    lui-même ``visite_effectuee=True`` et un récap COURT dans ``visite_notes``
    (uniquement des mesures RÉELLEMENT saisies — jamais un défaut inventé ;
    c'est ``visites.selectors.recap_visite_terrain`` qui compose la phrase,
    unique source de vérité, et elle arrive ici toute faite).

    ALEA28 — le récap vit dans un bloc balisé PAR VISITE
    (``[Récap visite n°<id>]`` … ``[/Récap visite n°<id>]``) : une
    revalidation après renvoi REMPLACE le récap de cette visite (un seul récap
    courant), une autre visite du même lead a son propre bloc, et le texte
    écrit à la main autour n'est JAMAIS écrasé. Revalider sans changement
    laisse ``visite_notes`` octet-identique. Sans ``visite_id`` (appel
    historique), le récap est seulement ajouté s'il est absent. Rien de tout
    ceci ne double le chatter : la note ``journaliser_visite(..., 'validee')``
    reste l'unique trace d'historique.
    """
    if lead is None:
        return None
    existantes = (lead.visite_notes or '').strip()
    champs = []
    if not lead.visite_effectuee:
        lead.visite_effectuee = True
        champs.append('visite_effectuee')
    if recap:
        if visite_id is not None:
            nouvelles = _notes_avec_recap(existantes, recap, visite_id)
        elif recap not in existantes:
            nouvelles = (f'{existantes}\n{recap}'.strip()
                         if existantes else recap)
        else:
            nouvelles = existantes
        if nouvelles != existantes:
            lead.visite_notes = nouvelles
            champs.append('visite_notes')
    if champs:
        lead.save(update_fields=champs)
    return lead


# ── AGR413 — LA MESURE DU POINT D'EAU REMPLACE LA DÉCLARATION ───────────────
#
# Contrat AGR5 (``visites/contract_samples/visite_terrain.json`` →
# ``retour_lead_point_eau``), recopié ici mot pour mot (garde de test) :
# mesure de la visite (``categorie.code``) → colonne Lead, + la provenance
# « mesure_visite » posée sur la colonne ``*_source`` quand elle existe.
# Une mesure sans colonne Lead (niveau dynamique, refoulement, conduite,
# tension, alimentation) n'est PAS recopiée : le moteur la lit par
# ``visites.selectors.mesures_point_eau_pour_lead``.
RETOUR_LEAD_POINT_EAU = (
    ('point_eau', 'source_eau', 'source_eau', None),
    ('point_eau', 'niveau_statique_m', 'niveau_statique_m',
     ('niveau_statique_source', 'mesure_visite')),
    ('point_eau', 'debit_mesure_m3h', 'debit_forage_m3h',
     ('debit_forage_source', 'mesure_visite')),
    ('point_eau', 'profondeur_forage_m', 'profondeur_forage_m', None),
    ('pompe_existante', 'pompe_actuelle_type', 'pompe_actuelle_type', None),
    ('pompe_existante', 'pompe_actuelle_cv', 'pompe_actuelle_cv', None),
    ('electricite', 'electricite_sur_place', 'electricite_sur_place', None),
    ('site_pv', 'distance_forage_champ_m', 'distance_forage_champ_m', None),
    ('administratif', 'autorisation_prelevement', 'autorisation_prelevement',
     None),
    ('administratif', 'autorisation_numero', 'autorisation_numero', None),
    ('administratif', 'autorisation_debit_l_s', 'autorisation_debit_l_s',
     None),
    ('administratif', 'autorisation_volume_m3_an',
     'autorisation_volume_m3_an', None),
    ('administratif', 'compteur_eau', 'compteur_eau', None),
)


def _valeur_colonne_lead(colonne, brute):
    """La valeur saisie convertie au type de la colonne Lead, ou None si elle
    n'y tient pas (jamais tronquée en silence pour un nombre)."""
    from decimal import Decimal, InvalidOperation

    from django.core.exceptions import ValidationError

    champ = Lead._meta.get_field(colonne)
    if champ.get_internal_type() == 'DecimalField':
        try:
            valeur = Decimal(str(brute))
        except (InvalidOperation, ValueError, TypeError):
            return None
        limite = Decimal(10) ** (champ.max_digits - champ.decimal_places)
        if not valeur.is_finite() or abs(valeur) >= limite:
            return None
        return valeur.quantize(Decimal(1).scaleb(-champ.decimal_places))
    if champ.get_internal_type() == 'BooleanField':
        return brute if isinstance(brute, bool) else None
    texte = str(brute).strip()
    if champ.choices and texte not in dict(champ.choices):
        return None
    try:
        champ.run_validators(texte[:champ.max_length or None])
    except ValidationError:
        return None
    return texte[:champ.max_length] if champ.max_length else texte


def appliquer_mesures_point_eau(lead, mesures, user):
    """AGR413 — recopie sur le lead les mesures d'un relevé du point d'eau
    VALIDÉ (``visites.selectors.mesures_point_eau_pour_lead``).

    La mesure REMPLACE la déclaration ; une mesure absente ou vide n'efface
    JAMAIS rien ; le journal ancien→nouveau est automatique
    (``activity.log_changes``), avec pour auteur l'utilisateur qui valide.
    Idempotent : re-valider avec les mêmes mesures ne change rien et
    n'écrit aucune ligne. Renvoie la liste des colonnes écrites."""
    if lead is None or not isinstance(mesures, dict) or not mesures:
        return []
    avant = Lead.objects.get(pk=lead.pk)
    ecrites = []
    for categorie, code, colonne, provenance in RETOUR_LEAD_POINT_EAU:
        bloc = mesures.get(categorie)
        brute = bloc.get(code) if isinstance(bloc, dict) else None
        if brute is None or (isinstance(brute, str) and not brute.strip()):
            continue
        valeur = _valeur_colonne_lead(colonne, brute)
        if valeur is None:
            continue
        if getattr(lead, colonne) != valeur:
            setattr(lead, colonne, valeur)
            ecrites.append(colonne)
        if provenance:
            source, origine = provenance
            if getattr(lead, source) != origine:
                setattr(lead, source, origine)
                ecrites.append(source)
    if ecrites:
        lead.save(update_fields=ecrites + ['date_modification'])
        activity.log_changes(avant, lead, user)
    return ecrites


# ── CIQ607 — LE RELEVÉ C&I REMPLACE LA DÉCLARATION ──────────────────────────
#
# Contrat CIQ5 (``visites/contract_samples/visite_terrain.json`` →
# ``retour_lead_ci``) : à la VALIDATION d'une visite ``ci``, le constaté du
# bloc ``releve_ci`` (``visites.selectors.releve_ci_de_visite``) est recopié
# sur les colonnes du contrat CIQ1, avec la provenance ``mesure_visite`` sur
# la colonne ``*_source`` quand elle existe. Le type de toiture arrive déjà
# converti par la table CIQ603 (plusieurs couvertures ⇒ ``None``, non
# recopié). Le type du lead n'est JAMAIS changé (convention 20).
#: ``(cle du releve_ci, colonne Lead, colonne de provenance | None)``.
RETOUR_LEAD_CI = (
    ('niveau_tension', 'tension_raccordement', 'tension_source'),
    ('puissance_souscrite_kva', 'compteur_puissance_kva',
     'puissance_souscrite_source'),
    ('type_toiture', 'type_toiture', None),
    ('surface_utile', 'surface_toiture_m2', 'surface_source'),
)
#: CIQ5 (lignes ``factures_mt.cos_phi_constate`` et ``reactif_secours.
#: groupe_kva`` de ``retour_lead_ci``) — relevés HORS comparaison
#: déclaré/constaté : le sélecteur les sert en ``{constate}`` (le cos φ
#: seulement si sa source est connue). Même forme que ``RETOUR_LEAD_CI``.
RETOUR_LEAD_CI_SUPPLEMENT = (
    ('cos_phi', 'cos_phi', 'cos_phi_source'),
    ('groupe_kva', 'groupe_kva', None),
)
#: La provenance posée par une mesure de visite (forme AGR2/CIQ1).
ORIGINE_MESURE_VISITE = 'mesure_visite'


def _valeur_valide(colonne, valeur):
    """Les validateurs de la colonne Lead (ex. cos φ dans ]0 ; 1]) : une
    mesure hors bornes n'est jamais recopiée."""
    from django.core.exceptions import ValidationError

    try:
        Lead._meta.get_field(colonne).run_validators(valeur)
    except ValidationError:
        return False
    return True


def appliquer_releve_ci(lead, releve, user):
    """CIQ607 — recopie sur le lead le relevé C&I d'une visite VALIDÉE.

    La mesure REMPLACE la déclaration ; une mesure vide ou « non relevée »
    n'efface JAMAIS rien ; le journal ancien→nouveau est automatique
    (``activity.log_changes``), auteur = le valideur. Idempotent : re-valider
    n'écrit rien. Rend ``{colonne: {valeur, provenance: {origine, detail,
    date}}}`` des colonnes écrites (``{}`` = rien)."""
    if lead is None or not isinstance(releve, dict) or not releve:
        return {}
    avant = Lead.objects.get(pk=lead.pk)
    provenance = {
        'origine': ORIGINE_MESURE_VISITE,
        'detail': f"visite {releve.get('visite_id')}",
        'date': releve.get('validee_le'),
    }
    ecrites, rendu = [], {}
    for cle, colonne, source in RETOUR_LEAD_CI + RETOUR_LEAD_CI_SUPPLEMENT:
        bloc = releve.get(cle)
        if not isinstance(bloc, dict) or bloc.get('non_releve'):
            continue
        brute = bloc.get('constate')
        if brute is None or (isinstance(brute, str) and not brute.strip()):
            continue
        valeur = _valeur_colonne_lead(colonne, brute)
        if valeur is None or not _valeur_valide(colonne, valeur):
            continue
        if getattr(lead, colonne) != valeur:
            setattr(lead, colonne, valeur)
            ecrites.append(colonne)
            rendu[colonne] = {'valeur': valeur, 'provenance': provenance}
        if source and getattr(lead, source) != ORIGINE_MESURE_VISITE:
            setattr(lead, source, ORIGINE_MESURE_VISITE)
            ecrites.append(source)
    if ecrites:
        lead.save(update_fields=ecrites + ['date_modification'])
        activity.log_changes(avant, lead, user)
    if releve.get('besoin_continuite_service') is True:
        _noter_besoin_secours(lead, user)
    return rendu


#: CIQ652 — la note de chatter posée quand une visite déclare un besoin de
#: continuité de service. Aucune taille, aucune autonomie, aucun prix.
NOTE_BESOIN_SECOURS = (
    "À faire par le bureau d'études : orienter vers une étude de secours "
    '(batterie / groupe) — besoin déclaré à la visite')


def _noter_besoin_secours(lead, user):
    """CIQ652 — UNE note interne « orienter vers une étude de secours », jamais
    un message client ; re-valider ne la double pas. Auteur = le valideur."""
    if LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body=NOTE_BESOIN_SECOURS).exists():
        return None
    return activity.log_note(lead, user, NOTE_BESOIN_SECOURS)
