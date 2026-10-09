"""SPL137 — les études, surcharges et offres de taille du devis,
déplacement pur depuis ``views/devis.py`` : corps octet-identiques, routes
inchangées.

Les imports function-locaux des corps (``from ..services import
rafraichir_etudes_du_devis``, ``from ..serializers import OverridesSerializer``
…) restent dans les corps : les ``mock.patch`` ``apps.ventes.services.*``
n'interceptent qu'ainsi.
"""
from drf_spectacular.utils import extend_schema
from ..openapi_params import qstr
import logging
from django.db import transaction
from rest_framework import status
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.permissions import IsResponsableOrAdmin
from .devis_gardes import (
    _refus_modifiabilite,
    _reponse_non_modifiable,
    _refus_verrou,
)


def _jeton(devis):
    """QJR545 — le jeton d'édition à renvoyer dans une réponse 2xx."""
    valeur = getattr(devis, 'updated_at', None)
    # Même représentation que le GET (DateTimeField de DRF) : le jeton
    # renvoyé est comparable, à l'octet, à celui que sert la fiche.
    return serializers.DateTimeField().to_representation(valeur) if valeur else None


class DevisEtudesActionsMixin:
    """SPL137 — actions études / surcharges / tailles de ``DevisViewSet`` (mixin, aucune base)."""

    # ── TAILLES (ordre fondateur, 26/08/2026) — les trois tailles côté vendeur ─
    #
    # TROIS actions, et le découpage n'est pas cosmétique : ``get_permissions``
    # raisonne sur ``self.action``, donc une action qui porterait à la fois le
    # GET et le PATCH sous un seul nom forcerait la LECTURE au niveau de garde
    # de l'ÉCRITURE. Une action par verbe = une garde juste par verbe.
    #
    # PIÈGE VX199 : les trois sont inscrites dans la liste de ``get_permissions``
    # ci-dessus, ET déclarent la MÊME classe dans leur décorateur. Sans
    # l'inscription, elles tomberaient sur le repli ``IsAdminRole`` — le
    # décorateur ne serait jamais consulté et fermerait l'écran aux
    # responsables tout en AYANT L'AIR ouvert.

    def _offres_tailles_reponse(self, devis):
        """L'état COMPLET des trois tailles, tel que l'écran vendeur le lit.

        MÊME dérivation que la page client (``offres_tailles.deriver``) : le
        vendeur et le client ne peuvent pas voir deux jeux de chiffres. Seule
        différence, assumée : ici aucune taille n'est cachée sous le seuil de
        deux (c'est un écran d'édition, pas une comparaison), et un devis non
        dérivable répond ``editable: false`` avec sa raison EN CLAIR plutôt
        qu'une section muette.
        """
        from ..offres_tailles import deriver
        from ..quote_engine.builder import build_quote_data

        try:
            data = build_quote_data(devis, {'pdf_mode': 'full'})
            bloc = deriver(devis, data)
        except Exception:  # noqa: BLE001 — un écran d'édition ne tombe jamais
            logging.getLogger(__name__).warning(
                'offres_tailles indisponibles sur %s',
                getattr(devis, 'reference', '?'), exc_info=True)
            bloc = None
        if bloc is None:
            return {
                'offres_tailles': None,
                'editable': False,
                'raison_non_editable': (
                    'Ce devis ne permet pas encore de dériver des tailles : '
                    'il doit être résidentiel, porter un profil de '
                    'consommation réel et un tableau de dimensionnement.'
                ),
            }
        return {'offres_tailles': bloc, 'editable': True}

    # ── QJR58 — LE REGISTRE DE SURCHARGES (décision fondateur D12) ───────────

    @staticmethod
    def _overrides_reponse(devis, chemins_regeneres=()):
        """La forme du contrat PACT10 ``contract_samples/devis_overrides.json``.

        ``effectif`` est DÉRIVÉ À CHAQUE LECTURE, jamais stocké : la carte des
        valeurs ``auto`` est celle que le moteur rend AUJOURD'HUI.

        QJR216 — LA CARTE ``autos`` EST ENFIN ALIMENTÉE. Elle valait ``{}`` en
        dur depuis QJR58, si bien que **toute** réponse annonçait ``auto:
        null``, y compris sur les chemins dont le moteur a une valeur lisible :
        le bloc promettait « valeur posée vs valeur moteur, côte à côte » et ne
        portait que la première. Elle vient désormais de
        ``domain.overrides.autos_du_devis`` — les chemins que le moteur ne sait
        pas dériver restent OMIS, jamais remplis d'un défaut (règle Z2).

        ``chemins_regeneres`` — les chemins qui viennent de repasser en
        automatique (DELETE). Ils sont FORCÉS dans la vue pour que la réponse
        les porte avec leur valeur moteur : sortis du registre, ils
        disparaissaient purement et simplement de la réponse, alors que
        l'endpoint promet « retour à l'automatique ».

        QJR305 — ILS SONT FORCÉS DANS LA VUE, PAS DANS LA CARTE ``autos``. Les
        y insérer avec ``None`` (l'ancien ``setdefault``) faisait passer pour
        « valeur automatique nulle » un chemin dont le moteur n'a simplement
        AUCUNE valeur : ``vue_effective`` ne pouvait plus le marquer
        ``non_derivable`` et l'écran retombait sur le champ vide ambigu.

        ``lignes`` est une carte ``{id: {...}}`` — JAMAIS une liste indexée par
        position (une ligne supprimée déplacerait la surcharge sur une autre).
        """
        from ..domain import overrides as registre_overrides

        lignes = {}
        for ligne in devis.lignes.all():
            marques = {
                champ: bool(getattr(ligne, champ))
                for champ in ('quantite_manuelle', 'prix_manuel')
                if hasattr(ligne, champ)
            }
            if any(marques.values()):
                lignes[str(ligne.pk)] = marques
        autos = registre_overrides.autos_du_devis(devis)
        return {
            'overrides': registre_overrides.registre_du_devis(devis),
            'effectif': registre_overrides.vue_effective(
                devis, autos,
                chemins_supplementaires=tuple(chemins_regeneres)),
            'lignes': lignes,
        }

    @extend_schema(parameters=[qstr('chemin', desc='DELETE : chemin à régénérer.')])
    @action(detail=True, methods=['get', 'patch', 'delete'],
            url_path='overrides',
            permission_classes=[IsResponsableOrAdmin])
    def overrides(self, request, pk=None):
        """GET / PATCH / DELETE du REGISTRE de surcharges de CE devis.

        * **GET** — le registre + le bloc ``effectif`` dérivé à la lecture.
        * **PATCH** — FUSIONNE le sous-ensemble de chemins reçu : envoyer
          ``{"taille.nb_panneaux": {"valeur": 14}}`` ne touche AUCUN autre
          chemin déjà posé. Un champ DÉRIVÉ, un chemin hors liste blanche D12
          ou une clé indexée par POSITION sont refusés en 400 avec un message
          FR qui NOMME le chemin — jamais un silence.
        * **DELETE ?chemin=<chemin>** — ``regenerer`` : SUPPRIME l'override de
          ce chemin (retour à l'automatique). Il ne le REMPLACE jamais dans le
          REGISTRE par une valeur calculée : reposer une valeur exige un
          nouveau PATCH explicite. QJR216 — la RÉPONSE, elle, porte le chemin
          régénéré avec la valeur que le moteur calcule : sans quoi « retour à
          l'automatique » rendait un trou au lieu de la valeur promise.

        L'ÉCRITURE PASSE PAR UN ``UPDATE`` D'UNE SEULE COLONNE
        (``domain.overrides.ecrire_colonne``) : ni ``updated_at`` ni le gel
        ``prix_par_kwc`` ne bougent — les deux effets de bord de ``Devis.save``
        sont faux pour une pose d'override. Aucune ligne, aucun total, aucun
        statut n'est touché (règle #4).

        QJR223 — LE CYCLE LIRE-FUSIONNER-ÉCRIRE EST VERROUILLÉ (``select_for_
        update``), PAS SEULEMENT L'ÉCRITURE. ``ecrire_colonne`` fait un
        ``UPDATE`` inconditionnel de la colonne entière : sans verrou, deux
        PATCH concurrents sur deux chemins DIFFÉRENTS relisent tous deux le
        MÊME registre de départ, fusionnent chacun sur cette même base, puis
        s'écrasent l'un l'autre au ``UPDATE`` — le perdant répond quand même
        200 comme si sa surcharge était stockée (``ecrire_colonne`` réécrit
        aussi ``devis.overrides`` EN MÉMOIRE avant que la course ne tranche).
        Le verrou de ligne (``domain.overrides.relire_verrouille``, jamais
        ``Devis.save()`` — ce serait réintroduire les deux effets de bord
        ci-dessus) SÉRIALISE les deux requêtes : la seconde relit alors le
        registre DÉJÀ enrichi par la première et fusionne par-dessus — les
        deux surcharges survivent.
        """
        from ..domain import overrides as registre_overrides
        from ..domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis)
        from ..serializers import OverridesSerializer

        devis = self.get_object()
        if request.method == 'GET':
            return Response(self._overrides_reponse(devis))
        # QJR516 — PATCH et DELETE gardés (geste ETUDE).
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        # QJR545 — verrou optimiste (jeton optionnel).
        refus = _refus_verrou(devis, request)
        if refus is not None:
            return refus
        from ..domain.verrou_devis import toucher

        if request.method == 'DELETE':
            chemin = request.query_params.get('chemin') or ''
            if not chemin:
                return Response(
                    {'chemin': 'Paramètre requis : quel chemin régénérer ?'},
                    status=status.HTTP_400_BAD_REQUEST)
            if not registre_overrides.chemin_autorise(chemin):
                return Response(
                    {'chemin': registre_overrides.MSG_CHEMIN_INCONNU},
                    status=status.HTTP_400_BAD_REQUEST)
            avant_geste = debut_de_geste_devis(devis, request.user)
            with transaction.atomic():
                devis = registre_overrides.relire_verrouille(devis)
                registre_overrides.ecrire_colonne(
                    devis, registre_overrides.regenerer(devis, chemin))
            self._rafraichir_etudes_apres_surcharge(devis)
            fin_de_geste_devis(devis, request.user, avant=avant_geste,
                               objet='surcharges')
            toucher(devis)
            # QJR216 — le chemin régénéré REVIENT dans la réponse avec la
            # valeur du moteur (avant, il en disparaissait : « retour à
            # l'automatique » se soldait par un trou).
            reponse = self._overrides_reponse(
                devis, chemins_regeneres=(chemin,))
            reponse['updated_at'] = _jeton(devis)
            return Response(reponse)

        serializer = OverridesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        avant_geste = debut_de_geste_devis(devis, request.user)
        try:
            with transaction.atomic():
                devis = registre_overrides.relire_verrouille(devis)
                registre = registre_overrides.fusionner(
                    devis, serializer.validated_data, utilisateur=request.user)
                registre_overrides.ecrire_colonne(devis, registre)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        self._rafraichir_etudes_apres_surcharge(devis)
        fin_de_geste_devis(devis, request.user, avant=avant_geste,
                           objet='surcharges')
        toucher(devis)
        reponse = self._overrides_reponse(devis)
        reponse['updated_at'] = _jeton(devis)
        return Response(reponse)

    @staticmethod
    def _rafraichir_etudes_apres_surcharge(devis):
        """QJR564 — une surcharge posée ou régénérée (``etude.jour_reference``,
        ``taille.nb_panneaux``, ``taille.panel_watt``…) nourrit le moteur ; les
        études STOCKÉES (lues telles quelles par ``/proposal``) sont donc
        relancées APRÈS la transaction. Inconditionnel : les empreintes
        QJR43/QJR44 court-circuitent une étude dont les entrées n'ont pas
        bougé — aucune liste de chemins tenue à la main ici. Best-effort : une
        étude en échec n'annule jamais une surcharge enregistrée."""
        from ..services import rafraichir_etudes_du_devis
        try:
            rafraichir_etudes_du_devis(devis)
        except Exception:  # noqa: BLE001
            pass

    @action(detail=True, methods=['get', 'patch'], url_path='etude-params',
            permission_classes=[IsResponsableOrAdmin])
    def etude_params(self, request, pk=None):
        """QJR62 — GET / PATCH **FUSIONNANT** d'``etude_params``.

        LE TROU QUE CECI FERME. L'écran sauvegardait le devis en RECONSTRUISANT
        ``etude_params`` de zéro et en le PATCHant sur un sérialiseur
        permissif : chaque clé qu'il ne reconstruit pas lui-même —
        ``factures_mensuelles_reelles``, ``gamme``, et tout ce que les quatre
        rafraîchisseurs du serveur avaient écrit — DISPARAISSAIT à la
        sauvegarde suivante du vendeur.

        Ici, seules les clés REÇUES bougent ; les autres restent intouchées,
        bit à bit. Une clé inconnue du schéma ou d'un type impossible est
        refusée en 400 avec un message FR, jamais ignorée en silence ; une clé
        DÉRIVÉE dont l'écran n'est pas propriétaire (le bloc horaire, le
        tableau de dimensionnement, les profils comparatifs, la simulation)
        l'est aussi — c'est le moteur qui les calcule.

        Une valeur ``null`` RETIRE la clé (règle Z2 : une étude qui n'est plus
        calculable est retirée, jamais laissée périmée).

        Ce correctif est SERVEUR et ne dépend d'aucun changement d'écran.
        L'écriture est chirurgicale (``update_fields=['etude_params']``) :
        aucune ligne, aucun total, aucun statut ne bouge (règle #4).

        QJR66 / passe Fable pré-merge — LES ÉTUDES SUIVENT LEURS ENTRÉES.
        Depuis que l'écran écrit par ICI (et non plus dans le corps atomique du
        devis), ses factures réelles arrivent APRÈS le rafraîchissement des
        quatre études déclenché par l'écriture des lignes : le PDF servait
        alors des économies dérivées d'entrées PÉRIMÉES — une régression franche
        par rapport au chemin d'hier. On relance donc les études quand, et
        seulement quand, une clé qui NOURRIT le moteur vient de bouger. La
        liste vit dans le SCHÉMA (``entrees_du_moteur``), pas ici. L'appel est
        quasi gratuit quand rien n'a réellement changé : les empreintes
        QJR43/QJR44 court-circuitent chaque étude dont les entrées sont
        identiques — c'est exactement leur rôle.
        """
        from ..domain.etude_schema import ECRAN, ecrire, entrees_du_moteur

        devis = self.get_object()
        if request.method == 'GET':
            return Response({'etude_params': devis.etude_params or {}})
        # QJR516 — PATCH gardé (geste ETUDE).
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        # QJR545 — verrou optimiste (jeton optionnel, retiré du corps : ce
        # n'est pas une clé d'étude). Réponse littérale : la forme du 409
        # reste lisible par check_api_shapes.
        from ..domain.verrou_devis import verifier_jeton
        charge = verifier_jeton(devis, request.data)
        if charge is not None:
            return Response(
                {'code': charge['code'], 'detail': charge['detail'],
                 'updated_at': charge['updated_at'],
                 'updated_by_nom': charge['updated_by_nom']},
                status=status.HTTP_409_CONFLICT)

        corps = request.data
        if isinstance(corps, dict) and 'expected_updated_at' in corps:
            corps = {k: v for k, v in corps.items()
                     if k != 'expected_updated_at'}
        if not isinstance(corps, dict) or not corps:
            return Response(
                {'detail': 'Corps invalide : un objet {clé: valeur} non vide '
                           'est attendu.'},
                status=status.HTTP_400_BAD_REQUEST)
        # QJR518 — l'option recommandée est IMPRIMÉE : sur un envoyé, sa
        # correction est tracée (instantané avant, trace après).
        from ..domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis)
        avant_geste = debut_de_geste_devis(devis, request.user)
        try:
            bloc = ecrire(devis, proprietaire=ECRAN, **corps)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        except TypeError:
            return Response(
                {'detail': "Clé d'étude invalide : les noms de clés doivent "
                           'être des identifiants simples.'},
                status=status.HTTP_400_BAD_REQUEST)
        if entrees_du_moteur(corps.keys()):
            # Best-effort, comme sur les trois autres chemins d'écriture : une
            # étude qui échoue ne doit JAMAIS annuler une entrée correctement
            # enregistrée.
            from ..services import rafraichir_etudes_du_devis
            try:
                rafraichir_etudes_du_devis(devis)
            except Exception:  # noqa: BLE001
                pass
        fin_de_geste_devis(devis, request.user, avant=avant_geste,
                           objet='étude')
        # La réponse reste LE BLOC FUSIONNÉ — ce que l'appelant vient de poser,
        # plus ce qui était déjà là. Délibéré : c'est le contrat de cet endpoint
        # (`contract_samples`), et y injecter les blocs dérivés fraîchement
        # recalculés en changerait la forme sans que personne les lise. Ils sont
        # en base, à leur place, pour le moteur PDF.
        # QJR545 — le jeton d'édition (avancé par ``ecrire``) accompagne le
        # bloc : clé ADDITIVE, la forme ``{etude_params}`` est inchangée.
        return Response({'etude_params': bloc, 'updated_at': _jeton(devis)})

    @action(detail=True, methods=['get'], url_path='offres-tailles',
            permission_classes=[IsResponsableOrAdmin])
    def offres_tailles(self, request, pk=None):
        """LECTURE des trois tailles Éco / Recommandé / Max de ce devis."""
        return Response(self._offres_tailles_reponse(self.get_object()))

    @action(detail=True, methods=['patch'], url_path='offres-tailles/config',
            permission_classes=[IsResponsableOrAdmin])
    def offres_tailles_config(self, request, pk=None):
        """ÉCRITURE de la CONFIGURATION d'UNE taille — elle seule.

        Le sérialiseur refuse en 400 tout nombre dérivé : il n'existe aucun
        chemin par lequel un prix tapé à la main entre dans le stockage. Les
        deux autres tailles ne sont pas touchées, marqueur ``ajuste`` compris.
        Aucune ligne, aucun total, aucun statut du devis ne bouge (règle #4).
        """
        from ..offres_tailles import enregistrer_config
        from ..serializers import OffreTailleEcritureSerializer

        devis = self.get_object()
        # QJR516 — geste ETUDE (configuration d'exploration).
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        serializer = OffreTailleEcritureSerializer(
            data=request.data, context={'company': devis.company})
        serializer.is_valid(raise_exception=True)
        enregistrer_config(devis, serializer.validated_data['cle'],
                           serializer.validated_data['config'],
                           utilisateur=request.user)
        return Response(self._offres_tailles_reponse(devis))

    @action(detail=True, methods=['post'],
            url_path='offres-tailles/regenerer',
            permission_classes=[IsResponsableOrAdmin])
    def offres_tailles_regenerer(self, request, pk=None):
        """RÉGÉNÈRE UNE taille depuis le moteur — elle seule.

        Retire la configuration du vendeur pour CETTE taille (et donc son
        marqueur « ajustée ») : la dérivation moteur reprend la main. Les deux
        autres tailles restent intouchées, y compris leur propre marqueur.
        """
        from ..offres_tailles import regenerer_taille
        from ..serializers import OffreTailleRegenerationSerializer

        devis = self.get_object()
        # QJR516 — geste ETUDE.
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        # QJR545 — verrou optimiste (jeton optionnel).
        refus = _refus_verrou(devis, request)
        if refus is not None:
            return refus
        serializer = OffreTailleRegenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        regenerer_taille(devis, serializer.validated_data['cle'])
        from ..domain.verrou_devis import toucher
        toucher(devis)
        reponse = self._offres_tailles_reponse(devis)
        reponse['updated_at'] = _jeton(devis)
        return Response(reponse)

    @action(detail=True, methods=['post'],
            url_path='offres-tailles/appliquer',
            permission_classes=[IsResponsableOrAdmin])
    def offres_tailles_appliquer(self, request, pk=None):
        """APPLIQUE la taille « Recommandé » AU DEVIS (lignes, totaux, études).

        LA DIFFÉRENCE AVEC ``offres-tailles/config``, ET C'EST TOUT LE SUJET.
        Le PATCH écrit une CONFIGURATION d'exploration : la carte change, le
        devis officiel ne bouge pas. Ce POST-ci fait l'inverse — il RECOMPOSE
        le devis lui-même sur la configuration ajustée de « Recommandé », par
        ``sync_devis_from_layout`` (l'unique machinerie de recomposition), si
        bien que le PDF, les totaux et la page client changent réellement.

        Le STATUT n'est jamais écrit (règle #4) : c'est la garde de
        ``sync_devis_from_layout`` qui décide, et un refus revient en 400 avec
        son motif EN FRANÇAIS (``revision_possible`` dit si « Réviser » est la
        bonne suite). Éco et Max sont refusées : ce sont des explorations.
        """
        from ..offres_tailles import ApplicationImpossible, appliquer_au_devis
        from ..serializers import OffreTailleRegenerationSerializer

        devis = self.get_object()
        # QJR545 — verrou optimiste (jeton optionnel).
        refus = _refus_verrou(devis, request)
        if refus is not None:
            return refus
        serializer = OffreTailleRegenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resume = appliquer_au_devis(devis, serializer.validated_data['cle'],
                                        utilisateur=request.user)
        except ApplicationImpossible as erreur:
            # PAS de ``ValidationError`` ICI, ET C'EST DÉLIBÉRÉ. DRF passe le
            # detail d'une ``ValidationError`` par ``_get_error_details``, qui
            # transforme TOUTE feuille en ``ErrorDetail`` (une chaîne) et
            # enveloppe les scalaires dans une liste : ``revision_possible``
            # partait donc en ``["True"]`` sur le fil. L'écran teste un BOOLÉEN
            # pour choisir entre « Réviser » et un refus sec — une chaîne
            # « True » et une chaîne « False » sont toutes deux vraies en JS,
            # et le bouton « Réviser » se serait affiché sur un devis clos.
            return Response(
                {'detail': erreur.detail,
                 'revision_possible': bool(erreur.revision_possible)},
                status=status.HTTP_400_BAD_REQUEST)
        from ..domain.verrou_devis import toucher
        toucher(devis)
        devis.refresh_from_db()
        reponse = self._offres_tailles_reponse(devis)
        reponse['applique'] = resume
        reponse['updated_at'] = _jeton(devis)
        return Response(reponse)
