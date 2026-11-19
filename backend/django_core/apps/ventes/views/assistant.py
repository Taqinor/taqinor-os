"""COP2-V2 — lecture COMPACTE du catalogue vendable pour l'assistant.

``GET /api/django/ventes/assistant/catalogue/`` — contrat
``contract_samples/assistant_catalogue.json``. Le classement est celui du
résolveur unique (``domain/resolution_catalogue``), donc celui de la
composition imposée du devis automatique : ce que la recherche rend est ce que
``POST ventes/devis/auto/`` accepte.

Garde : lecture du module Ventes (``LectureVentes`` — code ``ventes_voir``,
celui que déclare l'action ``ventes.catalogue.chercher``). Société TOUJOURS
celle de l'utilisateur. Jamais de prix d'achat, de marge ni de quantité en
stock — même pour un administrateur. Chaque paramètre est borné et publié ; un
paramètre inconnu, répété ou hors borne répond 400 en le nommant (aussi quand
le contrôle de plateforme ``API_QUERY_PARAMS_STRICT`` est éteint).
"""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.roles.permissions import DroitDeLaGrille
from authentication.permissions import IsResponsableOrAdmin
from core.champs_stricts import MOTIF_SANS_NUL
from core.parseurs import PARSEURS_JSON

from .. import selectors_assistant as SA
from ..domain import resolution_catalogue as rc
from ..gardes_lecture import LectureFactures, LectureVentes
from . import openapi_assistant as DA
from . import openapi_docs as D

#: Bornes PUBLIÉES (schéma) et APPLIQUÉES (ci-dessous) de chaque paramètre.
BORNES = {
    'kw': (0.5, 100.0),
    'kwh': (0.5, 100.0),
    'wc': (100.0, 1000.0),
}
LIMITE_DEFAUT = 10
LIMITE_MAX = 25
Q_MAX = 100
ID_MAX = 2 ** 31 - 1  # borne d'une clé primaire entière PostgreSQL
FAMILLES_RECHERCHE = rc.FAMILLES_DEMANDABLES + (rc.FAMILLE_OFFGRID,)

PARAMETRES = [
    OpenApiParameter('q', {'type': 'string', 'maxLength': Q_MAX,
                           'pattern': MOTIF_SANS_NUL},
                     OpenApiParameter.QUERY, required=False,
                     description='Texte cherché dans le nom ou la marque.'),
    OpenApiParameter('genre', {'type': 'string', 'enum': list(rc.GENRES)},
                     OpenApiParameter.QUERY, required=False),
    OpenApiParameter('kw', {'type': 'number', 'minimum': BORNES['kw'][0],
                            'maximum': BORNES['kw'][1]},
                     OpenApiParameter.QUERY, required=False,
                     description='Puissance d\'onduleur (avec genre=onduleur).'),
    OpenApiParameter('kwh', {'type': 'number', 'minimum': BORNES['kwh'][0],
                             'maximum': BORNES['kwh'][1]},
                     OpenApiParameter.QUERY, required=False,
                     description='Capacité de batterie (avec genre=batterie).'),
    OpenApiParameter('wc', {'type': 'number', 'minimum': BORNES['wc'][0],
                            'maximum': BORNES['wc'][1]},
                     OpenApiParameter.QUERY, required=False,
                     description='Puissance de panneau (avec genre=panneau).'),
    OpenApiParameter('phase', {'type': 'string', 'enum': list(rc.PHASES)},
                     OpenApiParameter.QUERY, required=False),
    OpenApiParameter('famille', {'type': 'string',
                                 'enum': list(FAMILLES_RECHERCHE)},
                     OpenApiParameter.QUERY, required=False),
    OpenApiParameter('limite', {'type': 'integer', 'minimum': 1,
                                'maximum': LIMITE_MAX},
                     OpenApiParameter.QUERY, required=False),
]
NOMS = frozenset(p.name for p in PARAMETRES) | {'format'}

#: La taille qui donne un verdict, par genre.
TAILLE_DU_GENRE = {rc.GENRE_PANNEAU: 'wc', rc.GENRE_ONDULEUR: 'kw',
                   rc.GENRE_BATTERIE: 'kwh'}
_ORDRE_GENRE = {g: i for i, g in enumerate(rc.GENRES)}


def _non_declares(params, noms, erreurs):
    """Un paramètre inconnu ou répété : 400 qui le nomme."""
    for nom in sorted(set(params.keys()) - noms):
        erreurs[nom] = ['Paramètre de requête non déclaré pour cette opération.']
    for nom in noms & set(params.keys()):
        if len(params.getlist(nom)) > 1:
            erreurs[nom] = [f"Le paramètre « {nom} » ne doit figurer qu'une fois."]


def _texte_q(params, erreurs):
    q = (params.get('q') or '').strip()
    if len(q) > Q_MAX or '\x00' in q:
        erreurs['q'] = [f'Texte de {Q_MAX} caractères au plus, sans caractère nul.']
    return q


def _limite(params, erreurs):
    brut = params.get('limite')
    if brut is None:
        return LIMITE_DEFAUT
    if not brut.isdigit() or not (1 <= int(brut) <= LIMITE_MAX):
        erreurs['limite'] = ['Entier attendu entre 1 et %d.' % LIMITE_MAX]
        return LIMITE_DEFAUT
    return int(brut)


def _lire(request):
    """Les paramètres validés ; 400 nommant chaque paramètre fautif."""
    params = request.query_params
    erreurs = {}
    _non_declares(params, NOMS, erreurs)
    lus = {'q': _texte_q(params, erreurs)}
    for nom, choix in (('genre', rc.GENRES), ('phase', rc.PHASES),
                       ('famille', FAMILLES_RECHERCHE)):
        valeur = params.get(nom)
        if valeur is not None and valeur not in choix:
            erreurs[nom] = ['Valeur « %s » invalide : attendu %s.'
                            % (valeur, ', '.join(choix))]
        lus[nom] = valeur or ''
    for nom, (mini, maxi) in BORNES.items():
        brut = params.get(nom)
        lus[nom] = None
        if brut is None:
            continue
        try:
            valeur = float(brut)
        except ValueError:
            valeur = None
        if valeur is None or valeur != valeur or brut.strip() != brut \
                or not (mini <= valeur <= maxi):
            erreurs[nom] = ['Nombre attendu entre %s et %s.' % (
                rc._fmt(mini), rc._fmt(maxi))]
            continue
        lus[nom] = valeur
    lus['limite'] = _limite(params, erreurs)
    if erreurs:
        raise ValidationError(erreurs)
    return lus


class CatalogueAssistantView(APIView):
    """Catalogue vendable de la société, lu pour l'assistant (COP2-V2)."""

    permission_classes = [LectureVentes]
    http_method_names = ['get', 'head', 'options']

    @extend_schema(parameters=PARAMETRES,
                   responses={200: D.CatalogueAssistantResponse,
                              400: D.ErreurDetail})
    def get(self, request):
        company = getattr(request.user, 'company', None)
        if company is None:
            raise ValidationError({'detail': 'Utilisateur sans société.'})
        lus = _lire(request)
        entrees = rc.vivier(company)
        if lus['q']:
            cherche = rc._sans_accents(lus['q'])
            entrees = [e for e in entrees if cherche in rc._sans_accents(
                '%s %s' % (getattr(e.produit, 'nom', '') or '',
                           getattr(e.produit, 'marque', '') or ''))]
        genre = lus['genre']
        if genre:
            entrees = [e for e in entrees if e.genre == genre]
        if lus['phase'] or lus['famille']:
            entrees = [e for e in entrees if e.genre == rc.GENRE_ONDULEUR
                       and (not lus['phase'] or e.phase == lus['phase'])
                       and (not lus['famille'] or e.famille == lus['famille'])]
        statut, raison = '', ''
        taille = lus.get(TAILLE_DU_GENRE.get(genre, ''), None) if genre else None
        if taille:
            resolution = self._resoudre(company, genre, entrees, taille, lus)
            statut, raison = resolution.statut, resolution.raison
            entrees = resolution.candidats
        else:
            entrees = sorted(entrees, key=lambda e: (
                _ORDRE_GENRE.get(e.genre, 9),
                rc._sans_accents(getattr(e.produit, 'nom', ''))))
        total = len(entrees)
        lignes = [rc.ligne_catalogue(e, company)
                  for e in entrees[:lus['limite']]]
        return Response({
            'q': lus['q'],
            'genre': genre,
            'total': total,
            'limite': lus['limite'],
            'statut': statut,
            'raison': raison,
            'lignes': lignes,
        })

    @staticmethod
    def _resoudre(company, genre, entrees, taille, lus):
        if genre == rc.GENRE_PANNEAU:
            return rc.resoudre_panneau(company, entrees, wc=taille)
        if genre == rc.GENRE_ONDULEUR:
            hors_reseau = lus['famille'] == rc.FAMILLE_OFFGRID
            return rc.resoudre_onduleur(
                company, entrees, kw=taille, phase=lus['phase'] or None,
                famille=None if hors_reseau else (lus['famille'] or None),
                hors_reseau=hors_reseau)
        return rc.resoudre_batterie(company, entrees, kwh=taille,
                                    haute_tension='haute tension' in
                                    rc._sans_accents(lus['q']))


# ── Les listes de facturation de l'assistant (VAD2, VAD3) ───────────────────

def _q_param():
    schema = {'type': 'string', 'maxLength': Q_MAX, 'pattern': MOTIF_SANS_NUL}
    return OpenApiParameter('q', schema, OpenApiParameter.QUERY, required=False)


def _parametres_liste(*extra):
    return [_q_param(),
            OpenApiParameter('client', {'type': 'integer', 'minimum': 1,
                                        'maximum': ID_MAX},
                             OpenApiParameter.QUERY, required=False,
                             description='Identifiant du client.'),
            *extra,
            OpenApiParameter('limite', {'type': 'integer', 'minimum': 1,
                                        'maximum': LIMITE_MAX},
                             OpenApiParameter.QUERY, required=False)]


PARAMETRES_IMPAYES = _parametres_liste(OpenApiParameter(
    'mes_relances', {'type': 'boolean'}, OpenApiParameter.QUERY,
    required=False, description='Seulement les clients dont je suis le '
                                'responsable de relance.'))
BOOLEENS = {'true': True, '1': True, 'false': False, '0': False}


def _lire_liste(request, parametres, statuts=()):
    """Paramètres d'une liste de l'assistant (``q``, ``client``, ``limite``,
    ``mes_relances``, ``statut``) ; 400 nommant chaque paramètre fautif."""
    params = request.query_params
    erreurs = {}
    _non_declares(params, frozenset(p.name for p in parametres) | {'format'},
                  erreurs)
    lus = {'q': _texte_q(params, erreurs), 'limite': _limite(params, erreurs),
           'client': None, 'mes_relances': False, 'statut': ''}
    brut = params.get('client')
    if brut is not None:
        if not brut.isdigit() or not 1 <= int(brut) <= ID_MAX:
            erreurs['client'] = ['Identifiant de client entier positif attendu.']
        else:
            lus['client'] = int(brut)
    brut = params.get('mes_relances')
    if brut is not None:
        if brut not in BOOLEENS:
            erreurs['mes_relances'] = ['Booléen attendu (true ou false).']
        else:
            lus['mes_relances'] = BOOLEENS[brut]
    brut = params.get('statut')
    if brut is not None:
        if brut not in statuts:
            erreurs['statut'] = ['Valeur « %s » invalide : attendu %s.'
                                 % (brut, ', '.join(statuts))]
        else:
            lus['statut'] = brut
    if erreurs:
        raise ValidationError(erreurs)
    return lus


class ImpayesAssistantView(APIView):
    """VAD2 — « qui me doit de l'argent ? » (contrat ``assistant_impayes.json``,
    action ``ventes.impayes.lister``) : calcul de
    ``apps.facturation.recouvrement.impayes_assistant`` (mêmes exigibles,
    niveaux et promesses que la liste des relances), portée de l'utilisateur.
    Jamais le téléphone ni l'e-mail du client."""

    permission_classes = [LectureFactures]
    http_method_names = ['get', 'head', 'options']

    @extend_schema(parameters=PARAMETRES_IMPAYES,
                   responses={200: DA.ImpayesAssistantResponse,
                              400: D.ErreurDetail})
    def get(self, request):
        from apps.facturation.recouvrement import impayes_assistant
        lus = _lire_liste(request, PARAMETRES_IMPAYES)
        lu = impayes_assistant(
            request.user, q=lus['q'], client_id=lus['client'],
            mes_relances=lus['mes_relances'], limite=lus['limite'])
        return Response({
            'total_du': lu['total_du'],
            'nb_factures': lu['nb_factures'],
            'tranches': lu['tranches'],
            'limite': lu['limite'],
            'lignes': lu['lignes'],
            'lien': '/ventes/relances',
        })


PARAMETRES_FACTURES = _parametres_liste(OpenApiParameter(
    'statut', {'type': 'string', 'enum': list(SA.STATUTS_FACTURE)},
    OpenApiParameter.QUERY, required=False))


class FacturesAssistantView(APIView):
    """VAD3 — retrouver une facture par sa référence, le nom ou le téléphone
    du client (contrat ``assistant_factures.json``, action
    ``ventes.facture.chercher``). Portée de la liste des factures. Le
    téléphone sert à chercher, il n'est jamais rendu."""

    permission_classes = [LectureFactures]
    http_method_names = ['get', 'head', 'options']

    @extend_schema(parameters=PARAMETRES_FACTURES,
                   responses={200: DA.FacturesAssistantResponse,
                              400: D.ErreurDetail})
    def get(self, request):
        lus = _lire_liste(request, PARAMETRES_FACTURES, SA.STATUTS_FACTURE)
        lu = SA.factures_cherchees(
            request.user, q=lus['q'], client_id=lus['client'],
            statut=lus['statut'], limite=lus['limite'])
        return Response({
            'q': lus['q'],
            'statut': lus['statut'],
            'total': lu['total'],
            'limite': lus['limite'],
            'lignes': lu['lignes'],
        })


class RelanceWhatsappAssistantView(APIView):
    """VAD8 — le WhatsApp de RELANCE d'une facture, préparé pour l'assistant
    (action ``ventes.facture.whatsapp_relance``, carte ``wa_message``) : texte
    du modèle « relance » VALIDÉ de la société, lien wa.me que la personne
    envoie elle-même ; opposition, contestation, facture non relançable et
    numéro inexploitable refusés (409 nommé) — voir
    ``domain/relance_assistant.py``. Portée de la liste des factures ; trace au
    chatter de la facture. Sans le droit de voir les coordonnées du client,
    ``wa_url`` vaut null."""

    permission_classes = [IsResponsableOrAdmin, DroitDeLaGrille('ventes_modifier')]
    parser_classes = PARSEURS_JSON  # corps JSON : pas de multipart publié
    http_method_names = ['post', 'options']

    @extend_schema(request=DA.RelanceWhatsappRequest,
                   responses={200: DA.RelanceWhatsappResponse,
                              400: D.ErreurDetail, 404: D.ErreurDetail,
                              409: DA.ErreurRelanceWhatsapp})
    def post(self, request, pk):
        from rest_framework import status
        from rest_framework.exceptions import NotFound
        from ..domain.relance_assistant import RelanceRefusee, preparer_relance
        from ..utils.corps import valider_corps
        facture = SA.facture_de_la_portee(request.user, pk)
        if facture is None:
            raise NotFound('Facture introuvable.')
        langue = valider_corps(request, DA.RelanceWhatsappRequest).get('langue') or 'fr'
        try:
            texte, wa_url = preparer_relance(request, facture, langue)
        except RelanceRefusee as refus:
            return Response(refus.corps, status=status.HTTP_409_CONFLICT)
        if not getattr(request.user, 'can_view_client_pii', True):
            wa_url = None
        return Response({
            'facture_id': facture.pk,
            'reference': facture.reference,
            'texte': texte,
            'wa_url': wa_url,
            'langue_servie': langue,
            'lien': SA.lien_facture(facture.pk),
        })


# ── VAD7 — la taille d'un devis (aperçu puis écriture confirmée) ────────────

PARAMETRES_TAILLE = [
    OpenApiParameter('nb_panneaux', {'type': 'integer', 'minimum': 1,
                                     'maximum': 200},
                     OpenApiParameter.QUERY, required=True),
    OpenApiParameter('batterie_nb_modules', {'type': 'integer', 'minimum': 1},
                     OpenApiParameter.QUERY, required=False,
                     description='Modules de batterie ; absent : inchangés.'),
]


def _entier_borne(params, nom, erreurs, mini, maxi=None, requis=False):
    brut = params.get(nom)
    if brut is None:
        if requis:
            erreurs[nom] = ['Paramètre obligatoire.']
        return None
    if not brut.isdigit() or int(brut) < mini or (maxi and int(brut) > maxi):
        erreurs[nom] = ['Entier attendu entre %d et %s.' % (mini, maxi or '∞')]
        return None
    return int(brut)


def _lire_taille(request):
    """``(nb_panneaux, batterie_nb_modules)`` de l'aperçu ; 400 nommé."""
    params, erreurs = request.query_params, {}
    _non_declares(params, frozenset(p.name for p in PARAMETRES_TAILLE)
                  | {'format'}, erreurs)
    nb = _entier_borne(params, 'nb_panneaux', erreurs, 1, 200, requis=True)
    modules = _entier_borne(params, 'batterie_nb_modules', erreurs, 1)
    if erreurs:
        raise ValidationError(erreurs)
    return nb, modules


def _refus_taille(refus):
    from rest_framework import status
    return Response(refus.corps, status=status.HTTP_409_CONFLICT)


class DevisAssistantActionsMixin:
    """Copilote vague 2 (lane VAD) — routes de ``DevisViewSet`` réservées à
    l'assistant (mixin, aucune base). Portée = ``get_object`` (société +
    visibilité du rôle, celle de la liste des devis) : hors portée → 404."""

    # api-only: lue par l'assistant (action `ventes.vente.etat`), aucun écran ne l'appelle.
    @extend_schema(request=None,
                   responses={200: DA.VenteEtatAssistantResponse,
                              404: D.ErreurDetail})
    @action(detail=True, methods=['get'], url_path='vente-assistant',
            permission_classes=[LectureVentes])
    def vente_assistant(self, request, pk=None):
        """VAD1 — l'état COMPACT de la vente (contrat
        ``assistant_vente_etat.json``) : la lecture obligatoire avant
        ``ventes.vente.facturer`` (``prochaines_echeances[0].cle``)."""
        devis = self.get_object()
        lu = SA.vente_etat_compacte(devis, request.user)
        etat = lu['etat']
        return Response({
            'devis_id': devis.pk,
            'reference': devis.reference,
            'statut': devis.statut,
            'client': lu['client'],
            'est_tete': etat['est_tete'],
            'tete_id': etat['tete_id'],
            'revision_en_cours': etat['revision_en_cours'],
            'date_validite': lu['date_validite'],
            'prix_convenu_ttc': etat['prix_convenu_ttc'],
            'emis_ttc': etat['emis_ttc'],
            'brouillons_ttc': etat['brouillons_ttc'],
            'paye_ttc': etat['paye_ttc'],
            'reste_a_facturer_ttc': etat['reste_a_facturer_ttc'],
            'reste_a_payer_ttc': etat['reste_a_payer_ttc'],
            'prochaine_action': etat['prochaine_action'],
            'raison_bloquee': etat['raison_bloquee'],
            'prochaines_echeances': etat['prochaines_echeances'],
            'factures': lu['factures'],
            'a_faire': lu['a_faire'],
            'lien': lu['lien'],
        })

    # api-only: lue par l'assistant avant `ventes.devis.taille` (ancien → nouveau total), aucun écran.
    @extend_schema(request=None, parameters=PARAMETRES_TAILLE,
                   responses={200: DA.TailleAssistantApercuResponse,
                              400: D.ErreurDetail, 404: D.ErreurDetail,
                              409: DA.ErreurTailleAssistant})
    @action(detail=True, methods=['get'], url_path='assistant-taille/apercu',
            permission_classes=[IsResponsableOrAdmin,
                                DroitDeLaGrille('ventes_modifier')])
    def assistant_taille_apercu(self, request, pk=None):
        """VAD7 — l'APERÇU de « mets-lui N panneaux » (contrat
        ``assistant_devis_taille_apercu.json``) : le chemin de l'écriture joué
        dans une transaction annulée — rien n'est écrit."""
        from ..domain.taille_assistant import TailleRefusee, mesurer
        devis = self.get_object()
        nb, modules = _lire_taille(request)
        try:
            m = mesurer(devis, nb, modules, utilisateur=request.user)
        except TailleRefusee as refus:
            return _refus_taille(refus)
        inchange = (m['nouveau_total_ttc'] == m['ancien_total_ttc']
                    and m['nb_panneaux'] == m['nb_panneaux_avant'])
        return Response({
            'devis_id': devis.pk,
            'reference': devis.reference,
            'statut': m['statut'],
            'corrige_apres_envoi': m['corrige_apres_envoi'],
            'nb_panneaux_avant': m['nb_panneaux_avant'],
            'nb_panneaux': m['nb_panneaux'],
            'kwc_avant': m['kwc_avant'],
            'kwc': m['kwc'],
            'ancien_total_ttc': m['ancien_total_ttc'],
            'nouveau_total_ttc': m['nouveau_total_ttc'],
            'alertes': m['alertes'],
            'a_faire': 'rien' if inchange else 'proposer',
            'lien': SA.lien_devis(devis.pk),
        })

    # api-only: écrite par l'assistant (action `ventes.devis.taille`, confirmée), aucun écran.
    @extend_schema(request=DA.TailleAssistantRequest,
                   responses={200: DA.TailleAssistantResponse,
                              400: D.ErreurDetail, 404: D.ErreurDetail,
                              409: DA.ErreurTailleAssistant})
    @action(detail=True, methods=['post'], url_path='assistant-taille',
            permission_classes=[IsResponsableOrAdmin,
                                DroitDeLaGrille('ventes_modifier')])
    def assistant_taille(self, request, pk=None):
        """VAD7 — change la taille d'un devis BROUILLON ou ENVOYÉ en place
        (contrat ``assistant_devis_taille.json``) ; l'ancien et le nouveau
        total confirmés doivent être ceux que le serveur recalcule (409
        ``apercu_perime`` sinon, rien n'est écrit). Statut jamais écrit ;
        aucun PDF produit (règle #4)."""
        from ..domain.composition_imposee import lignes_ttc
        from ..domain.taille_assistant import TailleRefusee, mesurer
        from ..domain.verrou_devis import toucher
        from ..utils.corps import valider_corps
        devis = self.get_object()
        corps = valider_corps(request, DA.TailleAssistantRequest)
        try:
            m = mesurer(devis, corps['nb_panneaux'],
                        corps.get('batterie_nb_modules'),
                        utilisateur=request.user, ecrire=True, attendus=corps)
        except TailleRefusee as refus:
            return _refus_taille(refus)
        toucher(devis)
        return Response({
            'devis_id': devis.pk,
            'reference': devis.reference,
            'statut': m['statut'],
            'corrige_apres_envoi': m['corrige_apres_envoi'],
            'nb_panneaux': m['nb_panneaux'],
            'kwc': m['kwc'],
            'ancien_total_ttc': m['ancien_total_ttc'],
            'nouveau_total_ttc': m['nouveau_total_ttc'],
            'composition': lignes_ttc(devis),
            'alertes': m['alertes'],
            'lien': SA.lien_devis(devis.pk),
        })
