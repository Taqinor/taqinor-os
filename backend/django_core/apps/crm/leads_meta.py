"""Arrivée des leads Meta Lead Ads et Click-to-WhatsApp (SPL23, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import logging
import re as _re

from django.utils import timezone

from apps.records.provenance import ecrire_si_libre

from . import activity
from .cadence_plan import demarrer_cadence_contact
from .leads_attribution import default_responsable_for
from .leads_consentement import (
    BASE_LEGALE_NON_COLLECTEE,
    BASE_LEGALE_SOLLICITATION,
    CONSENT_SOURCE_META_LEAD_ADS,
    CONSENT_SOURCE_WHATSAPP_ENTRANT,
    enregistrer_base_legale_lead,
)
from .leads_doublons import find_duplicates_by_contact
from .leads_notifications import notify_new_lead
from .leads_score import recompute_lead_score
from .models import Lead, LeadActivity

logger = logging.getLogger(__name__)


_META_LEAD_ADS_SYSTEM = 'meta_lead_ads'

# Marqueur d'idempotence de la note « réponses du formulaire » (une seule note
# par lead, quel que soit le nombre de retries webhook / passes du pull).
_META_FORM_NOTE_MARKER = '[Formulaire Meta]'


def _norm_form_text(value):
    """Minuscule, sans accents, underscores → espaces — les clés/valeurs des
    Instant Forms Meta arrivent en snake_case accentué (ex.
    ``quelle_est_votre_facture_moyenne_d'électricité_par_mois_?`` /
    ``entre_1000_dh_à_2000_dh``) ; ce normalisateur rend le matching tolérant
    aux variantes de wording entre formulaires."""
    import unicodedata

    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.replace('_', ' ').lower().strip()


# ── CAD-K ── CAD134 — le délai déclaré côté Meta, dans le champ DÉJÀ scoré ──
#
# Mots-clés → ``Lead.ProjectTimeline``, sur du texte libre normalisé par
# ``_norm_form_text``. TOLÉRANT (les libellés varient d'un Instant Form à
# l'autre) et SANS invention : un libellé non reconnu ne pose RIEN — mieux
# vaut un champ vide qu'un délai deviné, qui vaudrait des points au score.
# L'ORDRE compte : « le plus tôt possible » gagne avant « 3 mois ».
_META_TIMELINE_MOTS = (
    (('plus tot possible', 'ce mois', 'immediat', 'des que possible',
      'urgent'), Lead.ProjectTimeline.IMMEDIAT),
    (('renseigne', 'plus tard', 'pas presse', 'aucune idee', 'compare'),
     Lead.ProjectTimeline.PLUS_TARD),
    (('3 mois', 'trois mois'), Lead.ProjectTimeline.MOINS_3_MOIS),
    (('6 mois', 'six mois'), Lead.ProjectTimeline.MOINS_6_MOIS),
)


def _meta_project_timeline(valeur_normalisee):
    """CAD134 — le délai déclaré côté Meta en clé ``ProjectTimeline``, ou ''.

    ``valeur_normalisee`` est déjà passée par ``_norm_form_text``. Renvoie
    une chaîne VIDE quand rien n'est reconnu : on ne devine pas un délai."""
    texte = str(valeur_normalisee or '')
    for mots, cle in _META_TIMELINE_MOTS:
        if any(mot in texte for mot in mots):
            return cle
    return ''


# ── CIQ407 — formulaire Meta « pour mon entreprise » (D-CIQ-19) ─────────────
#
# Mots ENTIERS sur du texte normalisé (``_norm_form_text``). L'ORDRE compte :
# un mot d'industrie l'emporte sur « entreprise »/« société » (« Entreprise
# industrielle » est une usine) ; un cas qui touche deux segments que rien
# ne départage ne pose AUCUN type (il reste dans la note).
_META_MOTS_RESIDENTIEL = (r'villa', r'maison', r'appartement', r'domicile',
                          r'residen\w*')
_META_MOTS_INDUSTRIEL = (r'usine', r'industri\w*', r'atelier', r'hangar')
_META_MOTS_AGRICOLE = (r'ferme', r'agricole', r'pompage', r'puits')
#: Activité → ``Lead.categorie_commerciale`` (liste fermée du contrat CIQ1).
_META_CATEGORIES = (
    ((r'hotel', r'riad'), 'hotel'),
    ((r'restaurant', r'cafe', r'snack'), 'restaurant'),
    ((r'entrepot frigorifique', r'chambre froide', r'froid'), 'froid'),
    ((r'supermarche', r'magasin', r'commerce', r'boutique'), 'commerce'),
    ((r'bureau', r'bureaux'), 'bureau'),
    ((r'clinique', r'cabinet', r'sante', r'centre medical'), 'sante'),
    ((r'ecole', r'creche', r'lycee'), 'ecole'),
    ((r'hammam', r'spa', r'gym', r'salle de sport'), 'hammam'),
    ((r'boulangerie', r'patisserie'), 'boulangerie'),
)
_META_MOTS_COMMERCIAL = (r'entreprise', r'societe', r'local')
_META_MOTS_TRANCHE_OUVERTE = ('plus de', 'au dela', 'superieur', '>',
                              'more than', 'over')
#: TQ-F6 (10/2026) — « moins de X » : le plancher d'une facture est 0, la
#: réponse vaut donc la tranche FERMÉE 0–X (même convention de milieu que les
#: autres tranches fermées) — jamais X comme montant.
_META_MOTS_TRANCHE_OUVERTE_BASSE = ('moins de', 'inferieur', '<',
                                    'less than', 'under')


def _meta_mot_entier(texte, motifs):
    return any(_re.search(rf'\b{motif}\b', texte) for motif in motifs)


def _meta_categorie(valeur_normalisee):
    """CIQ407 — la catégorie commerciale d'une réponse, ou '' (mots entiers ;
    la première catégorie de la table qui répond gagne)."""
    for motifs, cle in _META_CATEGORIES:
        if _meta_mot_entier(valeur_normalisee, motifs):
            return cle
    return ''


def _meta_type_installation(valeur_normalisee):
    """CIQ407 — le segment d'une réponse « où installer », ou ''.

    Industrie AVANT entreprise/société ; « local » en mot entier seulement ;
    une activité commerciale reconnue (clinique, école…) vaut commercial. Un
    cas ambigu (résidentiel ou agricole ET autre chose) ne pose rien."""
    v = valeur_normalisee
    residentiel = _meta_mot_entier(v, _META_MOTS_RESIDENTIEL)
    industriel = _meta_mot_entier(v, _META_MOTS_INDUSTRIEL)
    agricole = _meta_mot_entier(v, _META_MOTS_AGRICOLE)
    commercial = (_meta_mot_entier(v, _META_MOTS_COMMERCIAL)
                  or bool(_meta_categorie(v)))
    pro = industriel or commercial
    if sum((residentiel, agricole, pro)) != 1:
        return ''
    if residentiel:
        return Lead.TypeInstallation.RESIDENTIEL
    if agricole:
        return Lead.TypeInstallation.AGRICOLE
    if industriel:
        return Lead.TypeInstallation.INDUSTRIEL
    return Lead.TypeInstallation.COMMERCIAL


def _meta_tranche_facture(valeur_normalisee, libelle):
    """CIQ407 (D-CIQ-19) — ``(montant, tranche)`` d'une réponse de facture.

    Tranche FERMÉE (deux nombres) : montant = milieu (inchangé) + tranche
    {min, max}. Tranche OUVERTE (« plus de X ») : AUCUN montant, tranche
    {X, None}. Nombre unique sans « plus de » : un montant, pas de tranche."""
    texte = _re.sub(r'(?<=\d)[\s.](?=\d{3}\b)', '', valeur_normalisee)
    nums = [int(n) for n in _re.findall(r'\d{3,6}', texte)]
    if len(nums) >= 2:
        bas, haut = sorted(nums[:2])
        return (bas + haut) // 2, {'min_mad': bas, 'max_mad': haut,
                                   'libelle': libelle, 'source': 'meta'}
    if nums:
        if any(mot in texte for mot in _META_MOTS_TRANCHE_OUVERTE):
            return None, {'min_mad': nums[0], 'max_mad': None,
                          'libelle': libelle, 'source': 'meta'}
        if any(mot in texte for mot in _META_MOTS_TRANCHE_OUVERTE_BASSE):
            return nums[0] // 2, {'min_mad': 0, 'max_mad': nums[0],
                                  'libelle': libelle, 'source': 'meta'}
        return nums[0], None
    return None, None


def _parse_meta_form_extras(field_data):
    """Réponses NON-contact du formulaire Meta → champs CRM structurés.

    Renvoie un dict : ``qa`` (paires question/réponse verbatim, pour la note
    chatter — rien n'est perdu), et selon les questions reconnues :
    ``facture_estimee`` (MAD/mois — milieu de tranche, ou borne pour une
    tranche ouverte « plus de X »), ``facture_declaree`` (réponse verbatim),
    ``type_installation`` (choix canonique du modèle), ``priorite`` (dérivée
    du délai déclaré : « le plus tôt possible » → haute, « je me renseigne » →
    basse, sinon normale)."""
    contact_keys = {'full_name', 'nom', 'name', 'first_name', 'email',
                    'phone_number', 'telephone', 'city', 'ville'}
    extras = {'qa': []}
    for entry in (field_data or []):
        raw_name = str(entry.get('name', '')).strip()
        if raw_name.lower() in contact_keys:
            continue
        values = entry.get('values') or []
        raw_value = str((values[0] if values else '') or '')
        if not raw_value:
            continue
        extras['qa'].append((raw_name, raw_value))
        # CIQ407 — raison sociale et fonction : champs Meta standard,
        # recopiés en remplissage seulement (et cités dans la note).
        if raw_name.lower() == 'company_name':
            extras['societe'] = raw_value.strip()[:255]
            continue
        if raw_name.lower() == 'job_title':
            extras['fonction_contact'] = raw_value.strip()[:120]
            continue
        q = _norm_form_text(raw_name)
        v = _norm_form_text(raw_value)
        if 'facture' in q:
            # CIQ407 (D-CIQ-19) — une tranche OUVERTE (« plus de 4000 dh »)
            # n'est JAMAIS un montant : elle va dans la tranche déclarée,
            # la facture reste vide.
            montant, tranche = _meta_tranche_facture(
                v, raw_value.replace('_', ' '))
            if montant is not None:
                extras['facture_estimee'] = montant
            if tranche is not None:
                extras['facture_tranche'] = tranche
            extras['facture_declaree'] = raw_value
        elif 'quand' in q or 'commencer' in q or 'delai' in q:
            if 'plus tot possible' in v or 'ce mois' in v or 'immediat' in v:
                extras['priorite'] = Lead.Priorite.HAUTE
            elif 'renseigne' in v or 'compare' in v:
                extras['priorite'] = Lead.Priorite.BASSE
            else:
                extras['priorite'] = Lead.Priorite.NORMALE
            # CAD134 (audit L3 du 21/09/2026) — LA MÊME PHRASE VAUT LE MÊME
            # SCORE DES DEUX CÔTÉS. Depuis le site, « je veux démarrer
            # immédiatement » devenait `project_timeline='immediat'` et valait
            # +8 au score ; depuis Meta, « le plus tôt possible » ne devenait
            # qu'une `priorite=haute` — absente de `compute_score`, donc ZÉRO
            # point, aucune remontée dans la file, aucun changement d'heure ni
            # de canal. Le webhook Meta écrit donc AUSSI `project_timeline`,
            # qui est déjà scoré ; la priorité reste le drapeau MANUEL du
            # commercial.
            #
            # Conversion TOLÉRANTE (ce sont des mots-clés sur du texte libre,
            # de qualité inégale) et TRACÉE : le libellé BRUT part dans
            # `extras['qa']`, que la note de formulaire recopie telle quelle —
            # un humain peut donc toujours relire ce que le client a coché.
            # Un délai non reconnu ne pose RIEN plutôt qu'une valeur inventée.
            extras['delai_declare'] = raw_value
            delai = _meta_project_timeline(v)
            if delai:
                extras['project_timeline'] = delai
        elif 'install' in q or 'logement' in q or 'type de bien' in q:
            # CIQ407 — industrie AVANT entreprise/société, mots entiers ; un
            # cas ambigu ne pose aucun type (il reste dans la note).
            segment = _meta_type_installation(v)
            if segment:
                extras['type_installation'] = segment
            categorie = _meta_categorie(v)
            if categorie and segment == Lead.TypeInstallation.COMMERCIAL:
                extras['categorie_commerciale'] = categorie
        elif 'contact' in q and ('prefer' in q or 'joindre' in q
                                 or 'comment' in q):
            # TQ-F6 (10/2026) — « Comment préférez-vous être contacté ? » →
            # la préférence EXPLICITE du lead (QW3), remplissage seulement.
            if 'whatsapp' in v:
                extras['contact_preference'] = (
                    Lead.ContactPreference.WHATSAPP_ONLY)
            elif 'appel' in v or 'telephone' in v or 'phone' in v:
                extras['contact_preference'] = Lead.ContactPreference.PHONE_OK
        elif _meta_mot_entier(v, (r'proprietaire', r'locataire')):
            # TQ-F6 — « Vous êtes : propriétaire / locataire » → ownership
            # (champ site CAD150, éditable avec provenance).
            extras['ownership'] = (
                Lead.Ownership.PROPRIETAIRE if 'proprietaire' in v
                else Lead.Ownership.LOCATAIRE)
        elif 'activite' in q or 'secteur' in q or 'etablissement' in q:
            # CIQ407 — question d'activité du formulaire modifié par Reda.
            categorie = _meta_categorie(v)
            if categorie:
                extras['categorie_commerciale'] = categorie
        else:
            # AGR410 — FORM-AGRI-1 : questions de pompage reconnues par
            # mots-clés (``_meta_reponse_agricole``).
            _meta_reponse_agricole(q, v, extras)
    # AGR410 — une question AGRICOLE pose le type agricole, seulement si le
    # formulaire n'a pas dit autre chose (et ``_apply_meta_form_extras`` ne
    # l'écrit que sur un type VIDE).
    if extras.pop('_agricole', False):
        extras.setdefault('type_installation',
                          Lead.TypeInstallation.AGRICOLE)
    return extras


# ── AGR410 — Formulaire Meta agricole (FORM-AGRI-1) ─────────────────────────
#
# Mots-clés sur du texte NORMALISÉ (``_norm_form_text``). Une TRANCHE ne
# devient JAMAIS un nombre (pas de milieu de tranche) : seule une réponse à
# nombre UNIQUE, sans « plus/moins/entre », remplit une colonne ; sinon la
# réponse reste dans la note, mot pour mot. Rien n'est jamais écrasé
# (``_apply_meta_form_extras``). Aucune création de campagne ici (règle #3).
_META_SOURCE_EAU_MOTS = (
    (('forage',), 'forage'),
    (('puits',), 'puits'),
    (('bassin',), 'bassin'),
    (('riviere', 'oued'), 'riviere'),
)
_META_ENERGIE_POMPE_MOTS = (
    (('pas de pompe', 'aucune', 'pas encore'), 'aucune'),
    # « gazoil » AVANT « gaz » : l'ordre de la table compte.
    (('gasoil', 'diesel', 'gazoil'), 'diesel'),
    (('butane', 'gaz'), 'butane'),
    (('electri', 'reseau', 'onee'), 'electrique'),
)
_META_MOTS_TRANCHE = ('plus', 'moins', 'entre', '>', '<', 'jusqu')


def _meta_nombre_unique(valeur_normalisee):
    """Le nombre d'une réponse à nombre UNIQUE, ou None (tranche / texte)."""
    from decimal import Decimal, InvalidOperation

    texte = str(valeur_normalisee or '')
    if any(mot in texte for mot in _META_MOTS_TRANCHE):
        return None
    nombres = _re.findall(r'\d+(?:[.,]\d+)?', texte.replace(' ', ''))
    if len(nombres) != 1:
        return None
    try:
        return Decimal(nombres[0].replace(',', '.'))
    except InvalidOperation:
        return None


def _meta_mot_cle(valeur_normalisee, table):
    for mots, cle in table:
        if any(mot in valeur_normalisee for mot in mots):
            return cle
    return ''


def _meta_reponse_agricole(q, v, extras):
    """AGR410 — une question de pompage du formulaire Meta → ``extras``.

    ``q``/``v`` déjà normalisés. Pose ``extras['_agricole']`` dès qu'une
    question agricole est reconnue, même si sa réponse ne remplit rien."""
    from decimal import Decimal

    if (('eau' in q and ('source' in q or 'vient' in q or 'provient' in q))
            or 'puits' in q or 'forage' in q):
        extras['_agricole'] = True
        source = _meta_mot_cle(v, _META_SOURCE_EAU_MOTS)
        if source:
            extras['source_eau'] = source
    elif 'pompe' in q and any(k in q for k in (
            'energie', 'fonctionne', 'marche', 'alimente', 'alimentation')):
        extras['_agricole'] = True
        energie = _meta_mot_cle(v, _META_ENERGIE_POMPE_MOTS)
        if energie:
            extras['pompe_alim_actuelle'] = energie
    elif 'hectare' in q or ('surface' in q and (
            'irrig' in q or 'cultiv' in q or 'terrain' in q
            or 'exploitation' in q)):
        extras['_agricole'] = True
        surface = _meta_nombre_unique(v)
        if surface is not None and surface < Decimal('10000000'):
            extras['surface_irriguee_ha'] = surface
    elif ('depense' in q or 'depensez' in q) and any(k in q for k in (
            'carburant', 'gasoil', 'butane', 'gaz', 'pompe', 'diesel')):
        extras['_agricole'] = True
        depense = _meta_nombre_unique(v)
        if depense is not None and depense < Decimal('100000000'):
            extras['depense_carburant_mad_mois'] = depense


def _apply_meta_form_extras(lead, extras):
    """Pose les champs structurés du formulaire SANS jamais écraser une valeur
    déjà présente (une saisie humaine gagne toujours sur l'auto-remplissage).
    ``priorite`` : posée seulement en « upgrade » (NORMALE par défaut → HAUTE
    déclarée) — jamais de downgrade automatique. Renvoie la liste des champs
    modifiés (vide si rien à faire)."""
    from decimal import Decimal

    changed = []
    # AGR410 — le type d'abord : sur un lead AGRICOLE, la tranche de facture
    # ne remplit PAS facture_hiver (elle gonflerait son score) — elle reste
    # dans la note seulement.
    if extras.get('type_installation') and not lead.type_installation:
        lead.type_installation = extras['type_installation']
        changed.append('type_installation')
    if (extras.get('facture_estimee') is not None and lead.facture_hiver is None
            and lead.type_installation != Lead.TypeInstallation.AGRICOLE):
        lead.facture_hiver = Decimal(int(extras['facture_estimee']))
        changed.append('facture_hiver')
    # CIQ407 (D-CIQ-19) — la tranche déclarée : toujours pour une tranche
    # OUVERTE (jamais un montant), en plus du milieu pour un PRO.
    tranche = extras.get('facture_tranche')
    if (tranche and lead.facture_tranche_declaree is None
            and lead.type_installation != Lead.TypeInstallation.AGRICOLE
            and (tranche['max_mad'] is None or lead.type_installation in (
                Lead.TypeInstallation.COMMERCIAL,
                Lead.TypeInstallation.INDUSTRIEL))):
        lead.facture_tranche_declaree = dict(tranche)
        changed.append('facture_tranche_declaree')
    # CIQ407 — activité, raison sociale, fonction : remplissage seulement.
    for champ in ('categorie_commerciale', 'societe', 'fonction_contact'):
        if extras.get(champ) and not getattr(lead, champ, None):
            setattr(lead, champ, extras[champ])
            changed.append(champ)
    # AGR410 — réponses de pompage : remplissage seulement, jamais
    # d'écrasement.
    for champ in ('source_eau', 'pompe_alim_actuelle', 'surface_irriguee_ha',
                  'depense_carburant_mad_mois'):
        if extras.get(champ) is not None and getattr(lead, champ) in (
                None, ''):
            setattr(lead, champ, extras[champ])
            changed.append(champ)
    if (extras.get('priorite') == Lead.Priorite.HAUTE
            and lead.priorite == Lead.Priorite.NORMALE
            and ecrire_si_libre(lead, 'priorite', Lead.Priorite.HAUTE)):
        changed.append('priorite')
    # CAD134 — le délai déclaré remplit le champ DÉJÀ scoré, et seulement
    # s'il est vide : un délai saisi à la main par la commerciale (ou venu du
    # site) n'est JAMAIS écrasé par un mot-clé lu sur du texte libre.
    if extras.get('project_timeline') and not getattr(
            lead, 'project_timeline', None):
        lead.project_timeline = extras['project_timeline']
        changed.append('project_timeline')
    # TQ-F6 (10/2026) — statut d'occupation et préférence de contact lus sur
    # le formulaire : remplissage seulement, jamais d'écrasement ; la
    # préférence est horodatée (QX15 : le SLA rappel court depuis sa pose).
    if extras.get('ownership') and not getattr(lead, 'ownership', None):
        lead.ownership = extras['ownership']
        changed.append('ownership')
    if (extras.get('contact_preference')
            and not getattr(lead, 'contact_preference', None)):
        lead.contact_preference = extras['contact_preference']
        lead.contact_preference_set_at = timezone.now()
        changed.extend(['contact_preference', 'contact_preference_set_at'])
    # Un lead Meta arrive par mobile : le même numéro sert de lien wa.me pour
    # la première prise de contact — AMET19 : jamais sur un WhatsApp saisi.
    if (lead.telephone and not lead.whatsapp
            and ecrire_si_libre(lead, 'whatsapp', lead.telephone)):
        changed.append('whatsapp')
    return changed


def _enrichir_meta_trace(lead, extras):
    """ACRM14 (C-ACRM-009) — applique ``_apply_meta_form_extras`` et
    JOURNALISE chaque champ écrit (une ligne MODIFICATION par champ :
    champ, ancienne → nouvelle valeur, acteur système) : un enrichissement
    automatique est visible au chatter comme toute autre écriture. Enregistre
    les champs modifiés et les rend."""
    from . import activity as _activity

    avant = {}
    for champ in ('type_installation', 'facture_hiver',
                  'facture_tranche_declaree', 'categorie_commerciale',
                  'societe', 'fonction_contact', 'source_eau',
                  'pompe_alim_actuelle', 'surface_irriguee_ha',
                  'depense_carburant_mad_mois', 'priorite', 'project_timeline',
                  'whatsapp', 'ownership', 'contact_preference'):
        avant[champ] = getattr(lead, champ, None)
    changed = _apply_meta_form_extras(lead, extras)
    if changed:
        lead.save(update_fields=changed)
        for champ in changed:
            if champ == 'contact_preference_set_at':
                continue   # horodatage technique, pas une donnée du client
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.MODIFICATION, field=champ,
                field_label=_activity.TRACKED_FIELDS.get(champ, champ),
                old_value=_activity._display(lead, champ, avant.get(champ)),
                new_value=_activity._display(
                    lead, champ, getattr(lead, champ, None)))
    return changed


def _meta_deja_enrichi(lead):
    """ACRM14 — la note « [Formulaire Meta] » (marqueur EXISTANT de
    ``_ensure_meta_form_note``) dit qu'une première passe a déjà enrichi ce
    lead : une passe suivante (rejeu webhook, pull) ne réécrit plus rien —
    une correction humaine faite entre-temps SURVIT."""
    return LeadActivity.objects.filter(
        lead=lead, body__startswith=_META_FORM_NOTE_MARKER).exists()


def _ensure_meta_form_note(lead, extras, form_id=''):
    """Une note chatter avec TOUTES les réponses verbatim du formulaire —
    rien n'est perdu, même les questions non reconnues. Idempotente par
    marqueur (retries webhook / re-passes du pull ne dupliquent jamais)."""
    if not extras.get('qa'):
        return
    if LeadActivity.objects.filter(
            lead=lead, body__startswith=_META_FORM_NOTE_MARKER).exists():
        return
    suffix = f' (formulaire {form_id})' if form_id else ''
    lines = [f'{_META_FORM_NOTE_MARKER} Réponses du prospect{suffix} :']
    for question, answer in extras['qa']:
        lines.append('• %s → %s' % (question.replace('_', ' '),
                                    answer.replace('_', ' ')))
    # AGR410 — sur un lead agricole, la facture n'est PAS pré-remplie : la
    # note ne le prétend pas (la réponse reste citée mot pour mot plus haut).
    if (extras.get('facture_estimee') is not None
            and lead.type_installation != Lead.TypeInstallation.AGRICOLE):
        lines.append(
            '(facture hiver pré-remplie à %s MAD depuis la tranche déclarée '
            '« %s » — à préciser au premier appel)'
            % (int(extras['facture_estimee']),
               extras.get('facture_declaree', '').replace('_', ' ')))
    elif (extras.get('facture_tranche') or {}).get('max_mad', 0) is None:
        # CIQ407 (D-CIQ-19) — tranche ouverte : AUCUN montant pré-rempli.
        lines.append(
            '(tranche ouverte « %s » : aucune facture pré-remplie — le '
            'montant réel est à demander au premier appel)'
            % extras.get('facture_declaree', '').replace('_', ' '))
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body='\n'.join(lines))


#: MRY0 (lot B) — bornes d'acceptation d'une ``created_time`` Meta : on ne
#: repose JAMAIS une date de création hors de cette fenêtre (une valeur
#: aberrante fausserait SLA et KPI aussi sûrement que l'heure du pull).
_META_CREATED_TIME_MAX_ANCIENNETE_JOURS = 90
_META_CREATED_TIME_MARGE_FUTUR_MINUTES = 5


def _parse_meta_created_time(brut):
    """``created_time`` Meta → datetime aware, ou ``None``.

    Deux formes réelles : ISO ``2026-09-03T11:04:04+0000`` (pull) et epoch
    secondes (webhook). Hors de la fenêtre ``[now - 90 j, now + 5 min]`` →
    ``None`` (refusée, jamais posée)."""
    import datetime as _dt

    from django.utils.dateparse import parse_datetime as _parse_dt

    if brut in (None, ''):
        return None
    moment = None
    if isinstance(brut, bool):
        return None
    if isinstance(brut, _dt.datetime):
        moment = brut
    elif isinstance(brut, (int, float)):
        try:
            moment = _dt.datetime.fromtimestamp(
                int(brut), tz=_dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        texte = str(brut).strip()
        if texte.isdigit():
            try:
                moment = _dt.datetime.fromtimestamp(
                    int(texte), tz=_dt.timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
        else:
            try:
                moment = _parse_dt(texte)
            except ValueError:
                return None
    if moment is None:
        return None
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment, _dt.timezone.utc)
    maintenant = timezone.now()
    if moment > maintenant + _dt.timedelta(
            minutes=_META_CREATED_TIME_MARGE_FUTUR_MINUTES):
        return None
    if moment < maintenant - _dt.timedelta(
            days=_META_CREATED_TIME_MAX_ANCIENNETE_JOURS):
        return None
    return moment


def create_lead_from_meta_lead_ads(
        *, company, leadgen_id, field_data,
        ad_id='', adgroup_id='', form_id='', access_token='',
        created_time=None, origine='') -> Lead:
    """XMKT32 — Crée (ou dédupe sur) un lead depuis un formulaire Meta Lead Ads.

    Point d'entrée cross-app sanctionné (services.py), appelé par
    ``webhooks.meta_lead_ads_webhook`` une fois le lead récupéré via l'API
    officielle (jamais de scraping). ``field_data`` est la liste
    ``[{'name': ..., 'values': [...]}, ...]`` renvoyée par le Graph API pour
    ce ``leadgen_id`` — seuls des champs connus (nom/email/téléphone/ville)
    sont lus.

    Dédup — D-CRX1 (décision fondateur du 02/09/2026) : UNE SEULE couche.
      1. même ``leadgen_id`` déjà traité (idempotence webhook — retries Meta)
         → renvoie le lead existant, enrichi (backfill) depuis le formulaire.

    L'ancienne « Couche 2 (QJ8) » — téléphone/e-mail connu dans la société ⇒
    ABSORPTION de la touche dans le lead existant — est SUPPRIMÉE. Chaque
    touche Meta est une nouvelle demande et crée un NOUVEAU lead, exactement
    comme une soumission du site (règle fondateur du 18/08/2026, étendue à Meta
    le 02/09/2026). Aucun lead existant n'est plus écrit par ce chemin : le
    rapprochement se fait EN VISIBILITÉ, avec les deux mêmes primitives que le
    webhook site (aucune seconde implémentation) —
      • ``webhooks._flag_possible_duplicates`` pose UNE note chatter de doublon
        sur le NOUVEAU lead (les archivés y sont mentionnés, cf. QW11) ;
      • ``webhooks._pick_owner_from_duplicates`` fait HÉRITER le commercial du
        doublon le plus pertinent (parité QW11), pour qu'un même client ne soit
        jamais rappelé par deux commerciaux différents.
    Conséquence VOULUE : un contact connu mais ARCHIVÉ donne lui aussi un
    NOUVEAU lead — il est signalé dans la note sans transmettre son owner
    (l'absorption, elle, ressuscitait silencieusement la fiche au rebut).
    L'attribution (canal/utm/meta_ids) et ``external_system``/``external_id``
    se posent donc TOUJOURS sur le lead nouvellement créé.

    Attribution (ADSENG1) : ``canal=META_ADS``, ``utm_source='facebook'``.
    Meta ne pousse JAMAIS campaign_name/adset_name dans le webhook leadgen ; il
    pousse ``ad_id``/``adgroup_id``/``form_id`` — capturés ici en clés de
    jointure stables (``meta_ad_id``/``meta_adset_id``/``meta_campaign_id``/
    ``meta_form_id``). Les NOMS lisibles sont résolus via les miroirs adsengine
    (``adsengine.selectors.resolve_meta_ad_names`` — jamais un import des modèles
    adsengine), avec repli paresseux via l'API si ``access_token`` est fourni.
    ``utm_campaign`` porte le nom de campagne résolu ; ``utm_content`` suit la
    convention ``ad-<ad_id>`` (formalisée en ADSENG23) — jamais l'adset_name,
    toujours vide en prod.

    Best-effort côté séquence de bienvenue : XMKT1 (moteur d'exécution des
    séquences) n'est pas encore construit — aucune inscription automatique
    tant qu'il n'existe pas ; ce service reste le point d'accroche futur.

    MRY0 (lot B) — ``created_time`` : l'heure Meta RÉELLE de la soumission.
    Appliquée UNIQUEMENT à la création (jamais sur un lead déjà capturé) et
    seulement si elle tombe dans ``[now - 90 j, now + 5 min]``. ``date_creation``
    étant ``auto_now_add``, elle n'est pas posable au ``create()`` : on la
    repose par un ``update()`` ciblé. Sans elle, un lead rattrapé par le pull
    portait l'heure du beat (07:25) et faussait SLA, KPI premier contact et
    notifications. ``origine`` (texte libre, ex. « Meta Lead Ads (webhook) »)
    nomme le chemin d'entrée dans la ligne « création » du chatter.
    """
    fields = {}
    for entry in (field_data or []):
        name = str(entry.get('name', '')).strip().lower()
        values = entry.get('values') or []
        value = (values[0] if values else '') or ''
        if name in ('full_name', 'nom', 'name'):
            fields['nom'] = str(value)[:255]
        elif name == 'first_name':
            fields.setdefault('nom', str(value)[:255])
        elif name in ('email',):
            fields['email'] = str(value)[:254]
        elif name in ('phone_number', 'telephone'):
            fields['telephone'] = str(value)[:20]
        elif name in ('city', 'ville'):
            fields['ville'] = str(value)[:120]
    # Réponses métier du formulaire (facture, type d'installation, délai…) —
    # structurées vers les VRAIS champs CRM, verbatim conservé en note.
    extras = _parse_meta_form_extras(field_data)

    # ── Couche 1 : idempotence sur le leadgen_id (retries webhook Meta) ──────
    # Un lead déjà capturé n'est PAS renvoyé tel quel : il est ENRICHI
    # (backfill) depuis les réponses du formulaire — champs vides uniquement,
    # jamais un écrasement de saisie humaine. C'est ce chemin qui remplit les
    # leads importés avant que le mapping complet n'existe.
    existing = Lead.objects.filter(
        company=company, external_system=_META_LEAD_ADS_SYSTEM,
        external_id=str(leadgen_id)).first()
    if existing is not None:
        # ACRM14 — UNE seule passe d'enrichissement : déjà enrichi (note
        # « [Formulaire Meta] » présente) → aucune écriture, la saisie
        # humaine faite depuis la première passe gagne.
        if _meta_deja_enrichi(existing):
            return existing
        _enrichir_meta_trace(existing, extras)
        if fields.get('ville') and not existing.ville:
            existing.ville = fields['ville']
            existing.save(update_fields=['ville'])
        _ensure_meta_form_note(existing, extras, form_id=str(form_id or ''))
        return existing

    nom = (fields.get('nom') or '').strip() or 'Lead Meta Ads'
    telephone = fields.get('telephone') or ''
    # ACRM38 — l'e-mail du formulaire Meta est nettoyé et validé comme
    # celui du site (``_clean_email``) : un « ' ' » n'est jamais une identité.
    from .webhooks import _clean_email
    email = _clean_email(fields.get('email')) or ''

    # ── D-CRX1 : plus AUCUNE absorption ─────────────────────────────────────
    # Les doublons sont cherchés ICI, AVANT la création, pour DEUX usages
    # strictement en lecture : (a) l'héritage du commercial (QW11) qui doit
    # être décidé avant le round-robin, (b) la note de signalement posée après
    # la création. Aucun lead existant n'est modifié sur ce chemin. Une seule
    # requête, réutilisée par les deux (jamais deux fois la même).
    dupes = []
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)

    # ADSENG1 — identifiants Meta natifs (clés de jointure stables) + noms
    # résolus via les miroirs adsengine (jamais un import des modèles adsengine).
    ad_id = str(ad_id or '')
    adgroup_id = str(adgroup_id or '')
    form_id = str(form_id or '')
    from apps.adsengine.selectors import resolve_meta_ad_names
    names = resolve_meta_ad_names(
        company, ad_id=ad_id, adgroup_id=adgroup_id, access_token=access_token)

    utm_source = 'facebook'
    utm_campaign = (names.get('campaign_name') or '')[:300] or None
    # Convention ADSENG23 : utm_content = ad-<ad_id> (jamais l'adset_name).
    utm_content = f'ad-{ad_id}'[:300] if ad_id else None
    meta_ad_id = ad_id[:64] or None
    meta_adset_id = adgroup_id[:64] or None
    meta_campaign_id = (names.get('campaign_id') or '')[:64] or None
    meta_form_id = form_id[:64] or None

    # QW11 (parité site) — l'héritage du commercial se décide AVANT le
    # round-robin : un lead qui EST un doublon n'entre pas dans l'attribution
    # normale, il revient au commercial qui suit déjà ce contact. Les deux
    # filtres d'éligibilité (doublon non archivé, owner actif+habilité) sont
    # DANS ``_pick_owner_from_duplicates`` — jamais redécidés ici.
    from .webhooks import _flag_possible_duplicates, _pick_owner_from_duplicates

    extra = {}
    inherited_owner, inherited_from = _pick_owner_from_duplicates(
        dupes, telephone=telephone, email=email, company=company)
    if inherited_owner is not None:
        extra['owner'] = inherited_owner
    else:
        # CIQ416 — le type lu sur le formulaire route un lead pro vers son
        # responsable désigné (sinon : comportement inchangé).
        default = default_responsable_for(
            company,
            lead_attrs={'type_installation': extras.get('type_installation')})
        if default is not None:
            extra['owner'] = default
    # À la CRÉATION, le délai déclaré pose la priorité pleinement (haute,
    # normale ou basse) ; en enrichissement (leads existants), seule la
    # montée NORMALE→HAUTE est automatique (_apply_meta_form_extras).
    if extras.get('priorite'):
        extra['priorite'] = extras['priorite']
    # CAD134 — et le MÊME délai déclaré pose `project_timeline`, le champ que
    # `compute_score` lit déjà : depuis Meta la phrase « le plus tôt possible »
    # valait zéro point, contre +8 pour la même phrase venue du site.
    if extras.get('project_timeline'):
        extra['project_timeline'] = extras['project_timeline']
    lead = Lead.objects.create(
        company=company,
        nom=nom,
        email=email or None,
        telephone=telephone or None,
        ville=fields.get('ville') or None,
        source=Lead.Source.META_LEAD_ADS,
        canal=Lead.Canal.META_ADS,
        utm_source=utm_source,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
        meta_ad_id=meta_ad_id,
        meta_adset_id=meta_adset_id,
        meta_campaign_id=meta_campaign_id,
        meta_form_id=meta_form_id,
        external_system=_META_LEAD_ADS_SYSTEM,
        external_id=str(leadgen_id),
        **extra,
    )
    # Réponses métier du formulaire → champs structurés (facture hiver,
    # type d'installation, priorité selon le délai déclaré, wa.me).
    # ACRM14 — chaque champ écrit est journalisé (ancien → nouveau).
    _enrichir_meta_trace(lead, extras)
    # MRY0 (lot B) — vraie date d'arrivée : ``date_creation`` est
    # ``auto_now_add`` (models.py), donc jamais posable au ``create()``.
    moment_meta = _parse_meta_created_time(created_time)
    if moment_meta is not None:
        Lead.objects.filter(pk=lead.pk).update(date_creation=moment_meta)
        lead.refresh_from_db(fields=['date_creation'])
    activity.log_creation(lead, None, origine=origine)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body='Lead créé depuis Meta Lead Ads (formulaire Facebook/Instagram).')
    _ensure_meta_form_note(lead, extras, form_id=str(form_id or ''))
    # CAD90 — la cohorte Meta n'avait aucune entrée au registre : ses données
    # ne sont pas collectées auprès de la personne par nous (art. 5 §3), et
    # l'horodatage tracé est celui de l'arrivée RÉELLE, jamais celui du beat.
    enregistrer_base_legale_lead(
        lead, source=CONSENT_SOURCE_META_LEAD_ADS,
        base_legale=BASE_LEGALE_NON_COLLECTEE,
        occurred_at=moment_meta or lead.date_creation)
    # D-CRX1 — signalement du doublon EN VISIBILITÉ (jamais une fusion), avec
    # la mention de l'héritage quand il a eu lieu. Réutilise ``dupes`` déjà
    # calculés (jamais une 2e requête). Best-effort, comme côté site : un
    # rapprochement en échec ne remet jamais la capture du lead en cause.
    try:
        _flag_possible_duplicates(
            lead, telephone=telephone, email=email, dupes=dupes,
            inherited_owner=inherited_owner, inherited_from=inherited_from)
    except Exception as _exc:  # noqa: BLE001 — best-effort
        logger.warning(
            'create_lead_from_meta_lead_ads: note de doublon échouée '
            '(lead #%s) : %s', lead.pk, _exc)
    try:
        notify_new_lead(lead)
    except Exception:  # noqa: BLE001 — best-effort
        pass

    # MRY6 — démarrage EXPLICITE de la cadence de contact. Best-effort :
    # une cadence en échec ne fait JAMAIS échouer la création du lead.
    demarrer_cadence_contact(lead, origine='meta_lead_ads')
    recompute_lead_score(lead)
    return lead


def import_external_notes_for_contact(company, *, phone=None, email=None,
                                      notes):
    """Importe des notes EXTERNES (ex. chatter Odoo) dans le chatter du lead
    correspondant — point d'entrée cross-app sanctionné (services.py), appelé
    par la commande ``adsengine.odoo_import_notes``.

    ``notes`` : liste de paires ``(marker, body)`` — ``marker`` est le préfixe
    d'idempotence du corps (ex. ``[Odoo note 123]``) : une note déjà importée
    (même marqueur sur ce lead) n'est JAMAIS dupliquée, la commande est
    re-exécutable à volonté.

    Matching : téléphone puis email, via les mêmes colonnes normalisées que le
    reste du CRM (``find_duplicates_by_contact``) ; prend le lead le plus
    récent. Renvoie ``(matched: bool, created: int)`` — aucun lead n'est créé
    ici (les leads sans correspondance attendent la migration complète)."""
    dupes = find_duplicates_by_contact(
        company, phone=phone or None, email=email or None)
    if not dupes:
        return False, 0
    lead = sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]
    created = 0
    for marker, body in notes:
        if not (body or '').strip():
            continue
        if LeadActivity.objects.filter(
                lead=lead, body__startswith=marker).exists():
            continue
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=body)
        created += 1
    return True, created


def create_minimal_lead_from_ctwa(*, company, phone, ad_id='') -> Lead:
    """PUB27 — Crée (ou dédupe sur) un Lead minimal pour une conversation
    WhatsApp/CTWA entrante SANS lead préalable.

    Point d'entrée cross-app WRITE sanctionné (services.py — jamais un import
    des modèles crm côté adsengine) : appelé par
    ``apps.adsengine.whatsapp_webhook`` quand ``_lead_id_for_phone`` ne trouve
    AUCUN lead pour le téléphone d'un message entrant portant un ``referral``
    CTWA (Click-to-WhatsApp) — jusqu'ici, ce cas laissait le ``CtwaReferral``
    orphelin (``crm_lead_id=None``) et l'attribution par ad était perdue.

    Dédupliqué par TÉLÉPHONE (``find_duplicates_by_contact`` — mêmes colonnes
    normalisées QW10 que le reste du CRM, indexées) : un second message de la
    même conversation (ou un prospect déjà connu par un autre canal) ne crée
    JAMAIS de doublon — renvoie le lead existant le plus récent tel quel, sans
    l'altérer (« referral avec lead → comportement inchangé »).

    Env-gated COMME le webhook : cette fonction n'est jamais appelée hors de
    ``WhatsAppCloudWebhookView.post`` (gardé par
    ``WHATSAPP_CLOUD_VERIFY_TOKEN``/``WHATSAPP_CLOUD_APP_SECRET`` — sans les
    deux, le webhook répond 404 et n'atteint jamais ce chemin), donc aucun
    flag séparé n'est nécessaire ici.

    Attribution : ``canal=WHATSAPP_CTWA``, ``meta_ad_id`` posé quand
    ``ad_id`` est fourni (même colonne de jointure que ADSENG1/XMKT32 — la
    variante Meta reste résolvable par ``apps.adsengine.attribution``).
    ``source=OS_NATIVE`` (créé nativement dans l'ERP — CTWA n'est pas un
    import, contrairement à ``META_LEAD_ADS``)."""
    phone = (phone or '').strip()
    if not phone or company is None:
        return None

    dupes = find_duplicates_by_contact(company, phone=phone)
    if dupes:
        return sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]

    extra = {}
    default = default_responsable_for(company)
    if default is not None:
        extra['owner'] = default
    ad_id = str(ad_id or '')[:64] or None
    lead = Lead.objects.create(
        company=company,
        nom='Lead WhatsApp/CTWA',
        telephone=phone,
        source=Lead.Source.OS_NATIVE,
        canal=Lead.Canal.WHATSAPP_CTWA,
        meta_ad_id=ad_id,
        **extra,
    )
    activity.log_creation(lead, None)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body='Lead créé depuis une conversation WhatsApp/CTWA entrante '
             '(aucun lead préalable trouvé pour ce numéro).',
    )
    # CAD90 — la personne a ÉCRIT la première : relation précontractuelle à
    # sa demande. Le registre le dit, plutôt que de rester muet sur un lead
    # dont la touche n°1 partira justement sur WhatsApp.
    enregistrer_base_legale_lead(
        lead, source=CONSENT_SOURCE_WHATSAPP_ENTRANT,
        base_legale=BASE_LEGALE_SOLLICITATION)
    try:
        notify_new_lead(lead)
    except Exception:  # noqa: BLE001 — best-effort
        pass
    # MRY6 — démarrage EXPLICITE de la cadence de contact. Best-effort :
    # une cadence en échec ne fait JAMAIS échouer la création du lead.
    demarrer_cadence_contact(lead, origine='ctwa')
    recompute_lead_score(lead)
    return lead


def fetch_meta_lead_node(leadgen_id, access_token):  # pragma: no cover - réseau
    """ADSENG1 — Récupère les identifiants natifs (ad_id/adgroup_id/form_id) du
    nœud lead Meta via le Graph API officiel, pour le backfill.

    Isolé en fonction module (jamais dans ``webhooks.py`` — inchangé hors
    mapping) pour rester simulable en test (monkeypatch). Renvoie le dict brut
    ou lève sur échec (capté par l'appelant, best-effort par lead).

    CRX5 — la version de l'API vient de la SOURCE UNIQUE partagée
    (``apps.adsengine.api_version.GRAPH_BASE_URL``), jamais d'un littéral :
    la « v25.0 » codée en dur ici était la dernière copie divergente du
    dépôt, et c'est exactement de cette façon que la v19.0 du webhook est
    restée morte en production pendant des mois (ADSENG2). Constante plain —
    aucun modèle adsengine n'est importé.
    """
    import json
    import urllib.parse
    import urllib.request

    from apps.adsengine.api_version import GRAPH_BASE_URL

    qs = urllib.parse.urlencode({
        'fields': 'ad_id,adgroup_id,form_id',
        'access_token': access_token,
    })
    url = f'{GRAPH_BASE_URL}/{leadgen_id}?{qs}'
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


def backfill_meta_lead_attribution(
        *, company=None, access_token='', fetch_fn=None, limit=None):
    """ADSENG1 — Rétro-remplit l'attribution par variante des leads Lead Ads
    EXISTANTS (créés avant qu'on capture ad_id/adgroup_id/form_id).

    Pour chaque ``Lead`` de source ``meta_lead_ads`` dont ``meta_ad_id`` est
    encore vide, récupère ses identifiants natifs (ad_id/adgroup_id/form_id)
    depuis le nœud lead Meta via ``fetch_fn(leadgen_id, access_token)`` (défaut :
    ``services.fetch_meta_lead_node``, juste au-dessus — CRX5 : la docstring
    nommait ``webhooks.fetch_meta_lead_node``, qui n'a jamais existé et
    envoyait le lecteur chercher dans le mauvais module ; injectable/simulable
    en test), les
    stocke, résout les noms via les miroirs adsengine, et remplit ``utm_content``
    = ``ad-<ad_id>`` + ``utm_campaign`` = nom de campagne résolu.

    IDEMPOTENT : un lead déjà backfillé (``meta_ad_id`` non vide) est sauté ; une
    seconde exécution ne change rien. Best-effort par lead : un échec réseau sur
    un lead n'interrompt jamais le lot (loggé, sauté). Scopé société si
    ``company`` fourni. Renvoie ``{'scanned', 'updated', 'skipped', 'failed'}``.
    """
    import logging
    from django.db.models import Q
    from apps.adsengine.selectors import resolve_meta_ad_names

    if fetch_fn is None:
        fetch_fn = fetch_meta_lead_node
    _log = logging.getLogger(__name__)

    qs = Lead.objects.filter(
        external_system=_META_LEAD_ADS_SYSTEM,
        external_id__isnull=False,
    ).filter(
        Q(meta_ad_id__isnull=True) | Q(meta_ad_id=''),
    )
    if company is not None:
        qs = qs.filter(company=company)
    qs = qs.order_by('id')
    if limit:
        qs = qs[:limit]

    stats = {'scanned': 0, 'updated': 0, 'skipped': 0, 'failed': 0}
    for lead in qs:
        stats['scanned'] += 1
        try:
            node = fetch_fn(lead.external_id, access_token) or {}
        except Exception as exc:  # noqa: BLE001 — un lead ne bloque pas le lot
            stats['failed'] += 1
            _log.warning(
                'backfill_meta_lead_attribution: fetch échoué (lead #%s) : %s',
                lead.pk, exc)
            continue
        ad_id = str(node.get('ad_id') or '')
        adgroup_id = str(node.get('adgroup_id') or node.get('adset_id') or '')
        form_id = str(node.get('form_id') or '')
        if not ad_id:
            stats['skipped'] += 1
            continue
        names = resolve_meta_ad_names(
            lead.company, ad_id=ad_id, adgroup_id=adgroup_id,
            access_token=access_token)
        lead.meta_ad_id = ad_id[:64]
        lead.meta_adset_id = adgroup_id[:64] or lead.meta_adset_id
        lead.meta_form_id = form_id[:64] or lead.meta_form_id
        campaign_id = (names.get('campaign_id') or '')[:64]
        if campaign_id and not lead.meta_campaign_id:
            lead.meta_campaign_id = campaign_id
        # utm_content = ad-<ad_id> (convention ADSENG23) ; remplit sans écraser
        # une valeur déjà posée par un autre canal (first-touch préservée).
        if not lead.utm_content:
            lead.utm_content = f'ad-{ad_id}'[:300]
        campaign_name = (names.get('campaign_name') or '')[:300]
        if campaign_name and not lead.utm_campaign:
            lead.utm_campaign = campaign_name
        lead.save()
        stats['updated'] += 1
    return stats
