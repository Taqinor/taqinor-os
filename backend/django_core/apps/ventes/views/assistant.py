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
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from ..domain import resolution_catalogue as rc
from ..gardes_lecture import LectureVentes
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
FAMILLES_RECHERCHE = rc.FAMILLES_DEMANDABLES + (rc.FAMILLE_OFFGRID,)

PARAMETRES = [
    OpenApiParameter('q', {'type': 'string', 'maxLength': Q_MAX},
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


def _lire(request):
    """Les paramètres validés ; 400 nommant chaque paramètre fautif."""
    params = request.query_params
    erreurs = {}
    for nom in sorted(set(params.keys()) - NOMS):
        erreurs[nom] = ['Paramètre de requête non déclaré pour cette opération.']
    for nom in NOMS & set(params.keys()):
        if len(params.getlist(nom)) > 1:
            erreurs[nom] = [f"Le paramètre « {nom} » ne doit figurer qu'une fois."]
    lus = {}
    q = (params.get('q') or '').strip()
    if len(q) > Q_MAX or '\x00' in q:
        erreurs['q'] = [f'Texte de {Q_MAX} caractères au plus, sans caractère nul.']
    lus['q'] = q
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
    brut = params.get('limite')
    lus['limite'] = LIMITE_DEFAUT
    if brut is not None:
        if not brut.isdigit() or not (1 <= int(brut) <= LIMITE_MAX):
            erreurs['limite'] = ['Entier attendu entre 1 et %d.' % LIMITE_MAX]
        else:
            lus['limite'] = int(brut)
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
