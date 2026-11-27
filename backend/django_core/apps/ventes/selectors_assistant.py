"""Copilote vague 2 (lane VAD) — lectures COMPACTES de la vente pour l'assistant.

Lectures pures (aucune écriture) servies par les vues minces de
``views/assistant.py`` et, pour le point du matin, par :func:`brief_ventes`
(sélecteur PUBLIC lu par ``apps/crm``). Chaque lecture compose les calculs
EXISTANTS (``vente_facturation.etat_vente``, le recouvrement de
``apps.facturation.recouvrement``) : aucun montant n'est recalculé ici.

Délibérément ABSENTS de toute sortie : prix d'achat, marge, coût, téléphone et
e-mail du client (décision D-W2-Q6 ; contrats ``assistant_*.json``).
"""
from decimal import Decimal, ROUND_HALF_UP

#: Au plus cinq factures dans l'état compact d'une vente (les plus récentes).
FACTURES_MAX = 5
#: Statuts d'une facture émise (reste dû réclamable).
STATUTS_EMIS = ('emise', 'en_retard')


def texte_montant(valeur):
    """Un montant en texte décimal à deux décimales (``"15000.00"``)."""
    return str(Decimal(str(valeur or 0)).quantize(Decimal('0.01'),
                                                  rounding=ROUND_HALF_UP))


def nom_du_client(client):
    """« Nom Prénom » du client (même forme que la liste des relances)."""
    if client is None:
        return ''
    return f"{client.nom or ''} {client.prenom or ''}".strip()


def lien_devis(devis_id):
    """L'écran du devis (table ``agent/contract_samples/assistant_ecrans.json``)."""
    return f'/ventes/devis?devis={devis_id}'


def lien_facture(facture_id):
    """L'écran de la facture (même table)."""
    return f'/ventes/factures?facture={facture_id}'


# ── VAD1 — l'état compact d'une vente ───────────────────────────────────────

def _factures_compactes(etat, devis):
    """Les ``FACTURES_MAX`` dernières factures de l'état, avec leur reste dû
    (``Facture.montant_du`` d'une facture émise ; 0 sinon)."""
    from apps.facturation.selectors import factures_avec_montant_du
    from .models import Facture

    dernieres = list(etat.get('factures') or [])[-FACTURES_MAX:]
    objets = {f.pk: f for f in factures_avec_montant_du(Facture.objects.filter(
        pk__in=[f['id'] for f in dernieres], company_id=devis.company_id))}
    compactes = []
    for f in dernieres:
        objet = objets.get(f['id'])
        du = (objet.montant_du if objet is not None
              and f['statut'] in STATUTS_EMIS else 0)
        compactes.append({
            'facture_id': f['id'], 'reference': f['reference'],
            'nature': f['nature'], 'statut': f['statut'],
            'total_ttc': f['total_ttc'], 'montant_paye': f['montant_paye'],
            'montant_du': texte_montant(du),
            'date_emission': f['date_emission'],
        })
    return compactes


def _a_faire_vente(etat, factures):
    """Le geste suivant, ensemble FERMÉ : facturer | emettre_brouillon |
    encaisser | reviser | rien (``reviser`` : pas la tête de chaîne)."""
    if not etat['est_tete']:
        return 'reviser'
    if any(f['statut'] == 'brouillon' for f in etat.get('factures') or []):
        return 'emettre_brouillon'
    if etat['prochaine_action'] != 'aucune' and not etat['raison_bloquee']:
        return 'facturer'
    if any(f['statut'] in STATUTS_EMIS and Decimal(f['montant_du']) > 0
           for f in factures):
        return 'encaisser'
    return 'rien'


def vente_etat_compacte(devis, user):
    """L'état COMPACT de la vente de ``devis`` (contrat
    ``assistant_vente_etat.json``) : ``etat_vente`` réduit, montants en texte,
    cinq factures au plus, ``a_faire`` et ``lien``."""
    from .vente_facturation import etat_vente

    etat = etat_vente(devis, user)
    factures = _factures_compactes(etat, devis)
    validite = getattr(devis, 'date_validite', None)
    return {
        'etat': etat,
        'client': nom_du_client(getattr(devis, 'client', None)),
        'date_validite': validite.isoformat() if validite else None,
        'factures': factures,
        'a_faire': _a_faire_vente(etat, factures),
        'lien': lien_devis(devis.pk),
    }


# ── VAD3 — retrouver une facture ─────────────────────────────────────────────

#: VAD3 — statuts de facture acceptés par ``statut`` (ceux du modèle).
STATUTS_FACTURE = ('brouillon', 'emise', 'en_retard', 'payee', 'annulee')
#: Un ``q`` d'au moins ce nombre de chiffres est AUSSI cherché comme téléphone.
CHIFFRES_TELEPHONE = 8


def _clients_par_telephone(company_id, q):
    """Les clients de la société dont le téléphone normalisé est celui de
    ``q`` (``crm.selectors.normalize_phone_key``). Le téléphone sert à
    CHERCHER, il n'est jamais rendu."""
    from apps.crm.selectors import client_base_qs, normalize_phone_key

    if sum(c.isdigit() for c in q) < CHIFFRES_TELEPHONE:
        return []
    cle = normalize_phone_key(q)
    if not cle:
        return []
    return [pk for pk, tel in client_base_qs().filter(company_id=company_id)
            .exclude(telephone='').values_list('id', 'telephone')
            if tel and normalize_phone_key(tel) == cle]


def _factures_du_texte(qs, company_id, q):
    from django.db.models import Q

    filtre = (Q(reference__icontains=q) | Q(client__nom__icontains=q)
              | Q(client__prenom__icontains=q))
    par_tel = _clients_par_telephone(company_id, q)
    if par_tel:
        filtre |= Q(client_id__in=par_tel)
    return qs.filter(filtre)


def _a_faire_facture(facture, du, jours_retard):
    """Ensemble FERMÉ : emettre | encaisser | relancer | rien."""
    if facture.statut == 'brouillon':
        return 'emettre'
    if facture.statut not in STATUTS_EMIS or du <= 0:
        return 'rien'
    if jours_retard > 0 and not getattr(facture, 'contestee_le', None):
        return 'relancer'
    return 'encaisser'


def _ligne_facture(facture):
    du = facture.montant_du if facture.statut in STATUTS_EMIS else Decimal('0')
    jours = int(getattr(facture, 'jours_retard', 0) or 0)
    emission, echeance = facture.date_emission, facture.date_echeance
    return {
        'facture_id': facture.pk,
        'reference': facture.reference,
        'client_nom': nom_du_client(facture.client if facture.client_id else None),
        'nature': facture.type_facture,
        'statut': facture.statut,
        'total_ttc': texte_montant(facture.total_ttc),
        'montant_du': texte_montant(du),
        'date_emission': emission.isoformat() if emission else None,
        'date_echeance': echeance.isoformat() if echeance else None,
        'jours_retard': jours,
        'a_faire': _a_faire_facture(facture, du, jours),
        'lien': lien_facture(facture.pk),
    }


def _factures_de_la_portee(user):
    from authentication.scoping import scope_queryset
    from .models import Facture

    return scope_queryset(Facture.objects.filter(company_id=user.company_id),
                          user, ['created_by'])


def facture_de_la_portee(user, facture_id):
    """VAD8 — la facture ``facture_id`` si elle est dans la portée de la liste
    des factures de ``user`` (société + ``created_by``), sinon ``None``."""
    if not getattr(user, 'company_id', None):
        return None
    return (_factures_de_la_portee(user)
            .select_related('client', 'company', 'lead', 'devis__lead',
                            'bon_commande__devis__lead')
            .filter(pk=facture_id).first())


def factures_cherchees(user, *, q='', client_id=None, statut='', limite=10):
    """VAD3 — les factures de la portée de ``user`` (celle de la liste des
    factures : société + ``scope_queryset(['created_by'])``) qui répondent à
    ``q`` (référence, nom ou téléphone du client), ``client``, ``statut`` ;
    les plus récentes d'abord. ``{total, lignes}`` (contrat
    ``assistant_factures.json``)."""
    from apps.facturation.selectors import factures_avec_montant_du

    if not getattr(user, 'company_id', None):
        return {'total': 0, 'lignes': []}
    qs = _factures_de_la_portee(user)
    if q:
        qs = _factures_du_texte(qs, user.company_id, q)
    if client_id is not None:
        qs = qs.filter(client_id=client_id)
    if statut:
        qs = qs.filter(statut=statut)
    total = qs.count()
    page = factures_avec_montant_du(
        qs.select_related('client').order_by('-id'))[:limite]
    return {'total': total, 'lignes': [_ligne_facture(f) for f in page]}


# ── 21/11/2026 — retrouver des devis (lecture de la portée du rôle) ─────────

#: ``limite`` de ``devis_cherches`` : défaut et plafond.
DEVIS_LIMITE_DEFAUT = 20
DEVIS_LIMITE_MAX = 50


def _devis_du_texte(qs, company_id, q):
    """Référence, nom/prénom du client, nom/prénom/téléphone du lead (le
    téléphone sert à CHERCHER, il n'est jamais rendu)."""
    from django.db.models import Q

    filtre = (Q(reference__icontains=q) | Q(client__nom__icontains=q)
              | Q(client__prenom__icontains=q) | Q(lead__nom__icontains=q)
              | Q(lead__prenom__icontains=q))
    if sum(c.isdigit() for c in q) >= CHIFFRES_TELEPHONE:
        filtre |= Q(lead__telephone__icontains=q.strip())
        par_tel = _clients_par_telephone(company_id, q)
        if par_tel:
            filtre |= Q(client_id__in=par_tel)
    return qs.filter(filtre)


def _devis_de_la_periode(qs, statut, depuis, jusqu_a):
    """``depuis`` / ``jusqu_a`` (dates incluses) sur la date de création ; pour
    un devis ACCEPTÉ, sur la date d'acceptation (à défaut, la création)."""
    from django.db.models import Q

    for borne, op in ((depuis, 'gte'), (jusqu_a, 'lte')):
        if borne is None:
            continue
        creation = Q(**{f'date_creation__date__{op}': borne})
        if statut == 'accepte':
            qs = qs.filter(Q(**{f'date_acceptation__{op}': borne})
                           | (Q(date_acceptation__isnull=True) & creation))
        else:
            qs = qs.filter(creation)
    return qs


def _ligne_devis(devis):
    envoi = devis.date_envoi
    accepte = devis.date_acceptation
    total = devis.total_ttc
    return {
        'devis_id': devis.pk,
        'reference': devis.reference,
        'statut': devis.statut,
        'client': nom_du_client(devis.client if devis.client_id else None),
        'lead_id': devis.lead_id,
        'total_ttc': texte_montant(total) if total is not None else None,
        'cree_le': devis.date_creation.date().isoformat(),
        'envoye_le': envoi.date().isoformat() if envoi else None,
        'accepte_le': accepte.isoformat() if accepte else None,
        'lien': lien_devis(devis.pk),
    }


def devis_cherches(qs, company_id, *, statut='', depuis=None, jusqu_a=None,
                   q='', limite=DEVIS_LIMITE_DEFAUT):
    """Les devis de ``qs`` — le queryset DÉJÀ borné par ``DevisViewSet.
    get_queryset()`` (société + visibilité du rôle + règle du responsable de
    lead : exactement les lignes de l'écran) — qui répondent aux filtres ; les
    plus récents d'abord. ``{total, limite, lignes}`` (contrat
    ``assistant_devis_liste.json``). Jamais de prix d'achat ni de marge."""
    limite = max(1, min(int(limite or DEVIS_LIMITE_DEFAUT), DEVIS_LIMITE_MAX))
    qs = qs.prefetch_related(None)
    if statut:
        qs = qs.filter(statut=statut)
    qs = _devis_de_la_periode(qs, statut, depuis, jusqu_a)
    if q:
        qs = _devis_du_texte(qs, company_id, q)
    total = qs.count()
    page = (qs.select_related('client')
            .prefetch_related('lignes', 'lignes__produit')
            .order_by('-date_creation', '-id')[:limite])
    return {'total': total, 'limite': limite,
            'lignes': [_ligne_devis(d) for d in page]}


# ── VAD10 — le bloc « impayés » du point du matin ───────────────────────────

#: Au plus cinq lignes par liste du point du matin (contrat du digest).
BRIEF_LIGNES = 5


def lit_les_factures(user):
    """La règle de lecture des factures (``LectureFactures``) sans requête :
    compte interne authentifié portant un code du module Ventes (ou palier
    administrateur / compte hérité)."""
    from apps.roles.permissions import is_portal_user
    from authentication.permissions import peut_lire_module

    return bool(user is not None and getattr(user, 'is_authenticated', False)
                and not is_portal_user(user) and peut_lire_module(user, 'ventes'))


def lit_les_devis(user):
    """Lot 8 (D-ACAL-106) — LA garde de LECTURE d'un devis, évaluée telle quelle : celle de
    ``views/devis.py::DevisViewSet.get_permissions`` pour ``list`` / ``retrieve``, soit
    ``gardes_lecture.py::LectureVentes`` (``LectureDuModule``, module figé ``ventes``, octrois
    ``OCTROIS_LECTURE`` de la vue ``DevisViewSet`` compris). Sans requête ; ``False`` hors
    session. Lu par le calepinage pour ne jamais NOMMER un devis à qui ne peut pas le lire."""
    from types import SimpleNamespace

    from .gardes_lecture import LectureVentes

    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    vue = type('DevisViewSet', (), {'__module__': 'apps.ventes.views.devis'})()
    return bool(LectureVentes().has_permission(SimpleNamespace(method='GET', user=user), vue))


def brief_ventes(user, aujourdhui=None):
    """Sélecteur PUBLIC du point du matin (lu par ``apps/crm``, BRF1) : le bloc
    ``impayes`` de ``crm/contract_samples/assistant_digest_matin.json``
    (``vague2.exemple_copilote.impayes``) — ``{total_du, nb_factures, lignes,
    lien}``, ``lignes`` = au plus cinq lignes de
    ``ventes/contract_samples/assistant_impayes.json``, les plus en retard
    d'abord ; total et nombre portent sur TOUTES les factures exigibles de la
    portée. ``None`` (bloc absent) pour un compte qui ne lit pas les factures.
    Le copilote allumé (``copilote_allume_pour``) reste vérifié par l'appelant.
    Lecture pure ; aucun chiffre d'affaires, aucun téléphone."""
    from apps.facturation.recouvrement import impayes_assistant

    if not lit_les_factures(user):
        return None
    lu = impayes_assistant(user, limite=BRIEF_LIGNES, aujourdhui=aujourdhui)
    return {
        'total_du': lu['total_du'],
        'nb_factures': lu['nb_factures'],
        'lignes': lu['lignes'],
        'lien': '/ventes/relances',
    }


def panneau_par_defaut_id(company):
    """Identifiant du panneau que le devis automatique retient quand rien n'est
    précisé (LE résolveur du compositeur) ; ``None`` s'il n'en désigne pas UN.

    D-ACAL-169 — réconcilié avec le stock : ``resoudre_panneau`` rend le panneau
    PAR DÉFAUT désigné quand il est utilisable et au vivier, sinon le choix
    d'aujourd'hui (710 Wc, « Canadien » au départage). Appelant hors tests :
    ``calepinage/services/contenance.py::_panneau``."""
    from .domain.resolution_catalogue import STATUT_UNIQUE, resoudre_panneau, vivier

    resolution = resoudre_panneau(company, vivier(company))
    if resolution.statut != STATUT_UNIQUE or resolution.produit is None:
        return None
    return resolution.produit.pk


# ── Les OPTIONS d'un devis (incident DEV-202611-0090 du 20/11/2026) ─────────
#
# L'assistant disait « le total TTC est de 44 900 DH, je ne peux pas dire à
# quelle option il correspond » : les réponses ne portaient qu'UN total. Le
# bloc ``options`` dit chaque option avec SES chiffres, lus par les fonctions
# canoniques : total = ``utils.options.option_totaux`` (la chaîne HT → remise
# → TVA → TTC du PDF, filtrage d'option compris) ; panneaux et kWc d'une
# option = ``domain.lignes.cible_depuis_lignes`` (QJR33, même variante) ; kWc
# d'un devis à une option = ``domain.scenario.puissance_kwc_du_devis``.

LIBELLES_OPTIONS = {'sans': 'Sans batterie', 'avec': 'Avec batterie',
                    '': 'Option unique'}


def _kwc_arrondi(valeur):
    """T4-X6-001 — au centième, sur la valeur EXACTE : la règle du PDF
    (``quote_engine.premium_base.kwc_str``). Au millième, 35,035 kWc
    (49 × 715 W) s'écrivait 35,04 sur le bandeau « Devis créé » et 35,03 sur
    la fiche et le PDF."""
    try:
        return round(float(valeur), 2) if valeur is not None else None
    except (TypeError, ValueError):
        return None


def options_du_devis(devis):
    """``[{variante, libelle, kwc, nb_panneaux, total_ttc}]`` — une entrée
    par option d'un devis à deux options (« sans » puis « avec »), une seule
    (``variante=''``) sinon. Lecture pure, relue en base ; jamais d'achat."""
    from .domain.lignes import cible_depuis_lignes
    from .domain.scenario import puissance_kwc_du_devis
    from .utils.options import (
        AVEC_BATTERIE, SANS_BATTERIE, deux_options_declarees, option_totaux)

    frais = type(devis).objects.get(pk=devis.pk)
    if not deux_options_declarees(frais):
        cible = cible_depuis_lignes(frais, 'sans')
        return [{'variante': '', 'libelle': LIBELLES_OPTIONS[''],
                 'kwc': _kwc_arrondi(puissance_kwc_du_devis(frais)),
                 'nb_panneaux': int(cible.get('panneaux') or 0),
                 'total_ttc': texte_montant(option_totaux(frais)['ttc'])}]
    options = []
    # Ligne ``variante`` 'sans'/'avec' ; option du noyau 'sans_batterie'/…
    for variante, option in (('sans', SANS_BATTERIE), ('avec', AVEC_BATTERIE)):
        cible = cible_depuis_lignes(frais, variante)
        options.append({
            'variante': variante, 'libelle': LIBELLES_OPTIONS[variante],
            'kwc': _kwc_arrondi(cible.get('kwc')),
            'nb_panneaux': int(cible.get('panneaux') or 0),
            'total_ttc': texte_montant(
                option_totaux(frais, option=option)['ttc'])})
    return options
