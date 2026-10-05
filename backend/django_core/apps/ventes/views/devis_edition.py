"""SPL135 — l'édition du devis (``atomic``, ``replace-lines``,
``perform_update`` et leurs gardes), déplacement pur depuis
``views/devis.py`` : corps octet-identiques, routes inchangées.

``DevisEditionActionsMixin`` se place AVANT ``CompanyScopedModelViewSet``
dans les bases de ``DevisViewSet`` : le ``super().perform_update(serializer)``
sans argument garde la même chaîne MRO. Les imports function-locaux des corps
restent dans les corps (les ``mock.patch`` ``apps.ventes.services.*``
n'interceptent qu'ainsi).
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from ..models import Devis
from ..serializers import DevisSerializer, DevisWriteSerializer
from authentication.permissions import IsResponsableOrAdmin
from ..utils.company_settings import create_numbered
from .devis_gardes import (
    _refus_modifiabilite,
    _reponse_non_modifiable,
    _refus_verrou,
)
# QJR73 — L'ÉCRIVAIN UNIQUE DES LIGNES N'EST PLUS UNE MÉTHODE DE CE VIEWSET.
# `_replace_lines_atomic` vivait ici, donc hors d'atteinte de tout autre
# appelant, alors que les tests le décrivent comme « le SEUL chemin d'écriture »
# des lignes. Son corps est parti TEL QUEL dans `domain/lignes.remplacer_lignes`
# (dédenté, `self` retiré, pas une ligne de logique touchée).
# QJR93 (M5, bascule 1/5) — CE FICHIER N'APPELLE PLUS `remplacer_lignes`.
# `atomic` et `replace-lines` recopiaient la MÊME paire de gestes (écrire les
# lignes sous transaction, puis rafraîchir les quatre études hors transaction),
# chacun avec son propre commentaire de dix lignes expliquant l'autre. Les deux
# passent désormais par `domain/pipeline.appliquer` — le mode `ecrire` pour la
# première moitié, le mode `rafraichir` pour la seconde — donc par LE MÊME
# écrivain et LE MÊME ordonnancement que les quatre autres origines de devis.
# Les frontières de transaction n'ont pas bougé d'une ligne : les réponses des
# endpoints sont inchangées à l'octet.
from ..domain.pipeline import (
    MODE_ECRIRE, MODE_RAFRAICHIR, ORIGINE_ECRAN, IntentionDevis, appliquer,
)


def _garde_kwh_declare(devis):
    """ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES (décision fondateur 30/09/2026)
    — un kWh mensuel déclaré que les factures du MÊME dossier contredisent
    (facture au barème ÷ facture déclarée hors [0,5 ; 2]) REFUSE
    l'enregistrement : 400 ``{detail, code}``, jamais un chiffrage
    silencieux. Partagée par ``/atomic`` (sous sa transaction, rien n'est
    créé) et ``replace-lines`` (avant toute écriture)."""
    from rest_framework.exceptions import ValidationError
    from ..etude_horaire import (
        CODE_KWH_INCOHERENT, MESSAGE_KWH_INCOHERENT,
        controle_kwh_declare_du_devis)
    controle = controle_kwh_declare_du_devis(devis)
    if controle is not None and not controle['coherent']:
        raise ValidationError({'detail': MESSAGE_KWH_INCOHERENT,
                               'code': CODE_KWH_INCOHERENT})


def _valider_etude_ecran(etude_in):
    """QJR544 — pré-validation des CHOIX d'écran (``etude_params`` clés
    ECRAN) avant toute écriture, partagée par ``/atomic`` et
    ``replace-lines`` : un refus pointe ``etude_params`` et n'écrit rien."""
    from rest_framework.exceptions import ValidationError
    from ..domain.etude_schema import ECRAN, fusionner
    if etude_in is None:
        return
    if not isinstance(etude_in, dict):
        raise ValidationError({'etude_params': "Objet {clé: valeur} attendu."})
    try:
        fusionner({}, proprietaire=ECRAN, **etude_in)
    except (ValueError, TypeError) as exc:
        raise ValidationError({'etude_params': str(exc)})


def _gardes_mise_a_jour(instance, validated_data, user, *, t17=True):
    """QJR544 — les gardes d'une mise à jour d'en-tête, en UN point (PATCH
    ``perform_update`` et ``replace-lines`` avec ``entete``) :

    * QJR521 — un devis remplacé / archivé ne se réactive jamais ;
    * QJR516 — prédicat de modifiabilité (geste ENTETE), 400 {'statut'} et
      l'exception « désactivation seule » conservés ;
    * ERR8 — lead / client d'une autre société refusés ;
    * QJR539 (``t17``) — correction d'un ENVOYÉ : une remise globale ENTRANTE
      plus profonde au-dessus du seuil n'est plus couverte par l'approbation
      d'avant (400 {'statut'}). ``replace-lines`` passe ``t17=False`` et juge
      APRÈS l'écriture des lignes, dans sa transaction.

    Lit le statut, ne l'écrit jamais (règle #4)."""
    from rest_framework.exceptions import ValidationError
    if (instance.is_active is False
            and validated_data.get('is_active') is True):
        raise ValidationError({
            'is_active': 'Un devis remplacé ou archivé ne se réactive pas.'})
    from ..domain.modifiabilite import ENTETE, verdict
    if not verdict(instance, ENTETE)['modifiable']:
        nouveau_is_active = validated_data.get(
            'is_active', instance.is_active)
        only_deactivation = (
            nouveau_is_active is False and instance.is_active is True
            and set(validated_data.keys()) <= {'is_active'}
        )
        if not only_deactivation:
            raise ValidationError({
                'statut': 'Devis figé — révisez-le (reviser) pour le '
                          'modifier.'})
    company = getattr(user, 'company', None)
    if company is not None:
        lead = validated_data.get('lead')
        client = validated_data.get('client')
        if lead is not None and lead.company_id != company.id:
            raise ValidationError({'lead': 'Lead inconnu.'})
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})
    if t17 and instance.statut == 'envoye':
        from ..services import (
            RemiseNonApprouvee, reverifier_remise_apres_correction)
        from ..domain.tarification import profondeur_remise_effective
        try:
            reverifier_remise_apres_correction(
                instance, user, avant=profondeur_remise_effective(instance),
                remise_globale=validated_data.get(
                    'remise_globale', instance.remise_globale))
        except RemiseNonApprouvee as erreur:
            raise ValidationError({'statut': erreur.message})


class _DevisModifie(APIException):
    """QJR545 — 409 ``{code: 'devis_modifie', detail, updated_at,
    updated_by_nom}`` : le devis a bougé depuis l'ouverture (verrou
    optimiste, contrat ``devis_verrou_edition.json``)."""
    status_code = status.HTTP_409_CONFLICT
    default_code = 'devis_modifie'


class DevisEditionActionsMixin:
    """SPL135 — actions d'édition de ``DevisViewSet`` (mixin, aucune base)."""

    @action(detail=False, methods=['post'], url_path='atomic',
            permission_classes=[IsResponsableOrAdmin])
    def atomic(self, request):
        """QX21be — création TRANSACTIONNELLE d'un devis + ses lignes en UN
        SEUL commit. Remplace les 1+N allers-retours non gardés du générateur
        (qui laissaient des brouillons orphelins/partiels qu'un vendeur pouvait
        ensuite envoyer). Couper la connexion en cours de route laisse soit
        RIEN, soit un devis complet.

        Corps : les champs de devis (statut/taux_tva/remise_globale/lead/
        client/mode_installation/etude_params…) + ``lignes`` : liste de
        ``{produit, designation, quantite, prix_unitaire, remise?, taux_tva?}``.
        La société est TOUJOURS forcée côté serveur. Aucun ``prix_achat``.
        """
        from django.db import transaction
        from rest_framework.exceptions import ValidationError
        from apps.crm.services import resolve_client_for_lead

        company = request.user.company
        if company is None:
            return Response({'detail': 'Utilisateur sans société.'},
                            status=status.HTTP_400_BAD_REQUEST)

        lignes_in = request.data.get('lignes')
        if not isinstance(lignes_in, list) or not lignes_in:
            return Response({'detail': 'Au moins une ligne est requise.'},
                            status=status.HTTP_400_BAD_REQUEST)

        head = {k: v for k, v in request.data.items() if k != 'lignes'}
        head.pop('company', None)  # jamais accepté du corps
        # ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — les CHOIX de l'écran
        # (``scenario``, ``recommended_option``, ``nombre_proprietes``)
        # décident de l'option que suit l'argent (``utils/options.py``
        # ``deux_options_declarees``). Ils arrivaient APRÈS la création (PATCH
        # ``etude-params``) : la réponse de création totalisait alors TOUTES
        # les lignes (les deux onduleurs compris) et l'écran « Devis
        # enregistré » annonçait un prix qu'aucun document ne porte. Ils sont
        # désormais écrits par l'unique écrivain (``etude_schema.ecrire``)
        # sous la MÊME transaction. Validés AVANT : un refus pointe le champ
        # ``etude_params`` et ne crée rien. Absents ⇒ comportement d'hier.
        from ..domain.etude_schema import ECRAN, ecrire
        etude_in = head.pop('etude_params', None)
        _valider_etude_ecran(etude_in)
        serializer = DevisWriteSerializer(data=head)
        serializer.is_valid(raise_exception=True)

        lead = serializer.validated_data.get('lead')
        client = serializer.validated_data.get('client')
        if lead is not None and lead.company_id != company.id:
            raise ValidationError({'lead': 'Lead inconnu.'})
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})
        if client is None:
            if lead is None:
                raise ValidationError(
                    {'client': 'Un client ou un lead est requis.'})
            client = resolve_client_for_lead(lead)

        # QJR563 — même devise par défaut de la société que POST /devis/ ;
        # une devise fournie dans le corps est respectée.
        devise_kwargs = {}
        if 'devise' not in serializer.validated_data:
            from ..domain.creation import devise_par_defaut
            devise_kwargs['devise'] = devise_par_defaut(company)
        try:
            with transaction.atomic():
                def _save(ref):
                    devis = serializer.save(
                        reference=ref, client=client,
                        created_by=request.user, company=company,
                        **devise_kwargs)
                    if etude_in:
                        ecrire(devis, proprietaire=ECRAN, **etude_in)
                    # ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — refus sous la
                    # transaction : un kWh déclaré contredit ne crée RIEN.
                    _garde_kwh_declare(devis)
                    # QJR93 — l'ÉTAPE 5 du pipeline, sous la MÊME transaction :
                    # la composition est celle que l'écran a arrêtée, le
                    # pipeline ne la recompose pas (recomposer détruirait les
                    # prix et quantités tapés par le commercial).
                    # QJR550 — ``user`` : l'auteur de l'instantané du
                    # geste, jamais lu du corps.
                    appliquer(devis, IntentionDevis(
                        origine=ORIGINE_ECRAN, mode=MODE_ECRIRE,
                        company=company, user=request.user,
                        composition=lignes_in))
                    return devis
                create_numbered(Devis, company, 'devis', _save)
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Enregistrement échoué : {exc}'},
                            status=status.HTTP_400_BAD_REQUEST)

        devis = serializer.instance
        # QJR554 — la marge interne (QX23be) et le kWc sont posés par le mode
        # RAFRAICHIR du pipeline ci-dessous (``finaliser_caches``) : plus de
        # rattrapage manuel ici.
        # L-QA1 (24/08/2026) — MÊME rafraîchissement que ``replace_lines``
        # ci-dessous : ``atomic`` EST le chemin de création du générateur
        # (devis + lignes en un seul commit) et, avant ce correctif, ne posait
        # ni le bloc horaire ni le tableau de dimensionnement — un devis créé
        # ici gardait ``etude_params`` sans ``etude_horaire``/``dimensionnement``
        # tant qu'aucune édition ultérieure (``replace-lines``) ne les
        # déclenchait. HORS de la transaction ci-dessus, best-effort (voir la
        # docstring des deux fonctions) : un devis correctement créé ne doit
        # jamais être annulé par une étude.
        # L-1V (24/08/2026) — LES QUATRE ÉTUDES EN UN SEUL GESTE : la liste
        # recopiée ici (et une deuxième fois dans ``replace_lines``, et une
        # TROISIÈME, incomplète, dans ``LigneDevisViewSet``) vit maintenant
        # dans ``services.rafraichir_etudes_du_devis``. Une étude ajoutée
        # demain part sur les trois chemins d'écriture, ou sur aucun.
        # QJR47 — ``force=True`` RETIRÉ : il protégeait contre un cache posé
        # sur la simple PRÉSENCE de la clé. Depuis QJR43/QJR44 c'est
        # l'EMPREINTE des entrées (et, pour le bloc horaire, la composition)
        # qui décide — un devis qui vient d'être créé n'a aucun bloc, donc les
        # quatre études se calculent de toute façon.
        # QJR93 — l'ÉTAPE 7 du pipeline. Elle RELIT l'instance avant les
        # études (QJR20) : sur un devis qui vient d'être créé la relecture ne
        # change rien, mais le contrat cesse d'être « espéré » selon le chemin.
        appliquer(devis, IntentionDevis(
            origine=ORIGINE_ECRAN, mode=MODE_RAFRAICHIR, company=company))
        return Response(DevisSerializer(
            devis, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='replace-lines',
            permission_classes=[IsResponsableOrAdmin])
    def replace_lines(self, request, pk=None):
        """QX21be — remplace ATOMIQUEMENT toutes les lignes d'un devis en un
        seul commit (édition). Remplace le delete-all-puis-recréer à erreurs
        avalées du générateur, qui pouvait laisser un devis avec moins/aucune
        ligne. Un échec préserve les lignes d'origine (rollback complet).

        PV15 — GARDE DE STATUT. Cet endpoint SUPPRIME puis recrée toutes les
        lignes : sans garde, un appel sur un devis ACCEPTÉ (ou refusé/expiré)
        effaçait le contenu d'un document déjà engagé, dont la chaîne
        BonCommande/Facture dépend. Seuls « brouillon » et « envoyé » restent
        modifiables ; au-delà, 409 avec le statut NOMMÉ (le bon geste est
        « Réviser », qui crée une nouvelle version). Cette garde ne CHANGE
        jamais le statut — elle le LIT (règle #4)."""
        from django.db import transaction
        devis = self.get_object()  # borné société par get_queryset
        # QJR516 — le prédicat UNIQUE (geste LIGNES) ; texte et code 409
        # {'detail'} CONSERVÉS.
        if _refus_modifiabilite(devis, 'LIGNES'):
            return _reponse_non_modifiable(
                devis, 'LIGNES',
                'Devis « %s » : ses lignes ne peuvent plus être '
                'remplacées. Utilisez « Réviser » pour en créer une '
                'nouvelle version.')
        # QJR545 — verrou optimiste (jeton optionnel).
        refus = _refus_verrou(devis, request)
        if refus is not None:
            return refus
        lignes_in = request.data.get('lignes')
        if not isinstance(lignes_in, list):
            return Response({'detail': 'Champ « lignes » requis (liste).'},
                            status=status.HTTP_400_BAD_REQUEST)
        # QJR204 — ALIGNÉ SUR ``/atomic``, QUI REFUSE DÉJÀ L'ENSEMBLE VIDE.
        # Cet endpoint SUPPRIME puis recrée : une liste VIDE effaçait toutes
        # les lignes d'un devis brouillon/envoyé et répondait 200. Vérifié
        # avant d'en faire un refus : aucun flux légitime de « tout vider »
        # n'existe (``ventesApi.replaceLignesDevis`` est l'unique appelant de
        # production et l'écran n'offre aucun geste de ce genre). L'écrivain
        # unique du domaine porte la même garde, pour les chemins non-HTTP.
        if not lignes_in:
            from ..domain.lignes import MSG_REMPLACEMENT_VIDE
            return Response({'detail': MSG_REMPLACEMENT_VIDE},
                            status=status.HTTP_400_BAD_REQUEST)
        # QJR544 (contrat QJR504, devis_replace_lines_entete.json) — UNE
        # transaction pour l'édition entière : en-tête + lignes + choix
        # d'écran. ``entete`` et ``etude_params`` sont OPTIONNELS : sans eux,
        # comportement identique à l'octet. ``statut`` dans l'en-tête est
        # IGNORÉ (QJR541). Tout est VALIDÉ avant la première écriture.
        from rest_framework.exceptions import ValidationError
        entete_in = request.data.get('entete')
        etude_in = request.data.get('etude_params')
        entete_ser = None
        if entete_in is not None:
            if not isinstance(entete_in, dict):
                return Response({'detail': 'Champ « entete » : objet attendu.'},
                                status=status.HTTP_400_BAD_REQUEST)
            entete = {k: v for k, v in entete_in.items()
                      if k not in ('statut', 'company')}
            entete_ser = DevisWriteSerializer(devis, data=entete, partial=True)
            entete_ser.is_valid(raise_exception=True)
            _gardes_mise_a_jour(devis, entete_ser.validated_data,
                                request.user, t17=False)
        _valider_etude_ecran(etude_in)
        # ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — avant toute écriture.
        _garde_kwh_declare(devis)
        from ..services import (
            RemiseNonApprouvee, reverifier_remise_apres_correction)
        from ..domain.tarification import profondeur_remise_effective
        # QJR539 — correction d'un ENVOYÉ : profondeur de remise AVANT le geste.
        envoye = devis.statut == 'envoye'
        remise_avant = profondeur_remise_effective(devis) if envoye else None
        geste_complet = entete_ser is not None or bool(etude_in)
        try:
            with transaction.atomic():
                # QJR544 — avec un en-tête, la trace QJR518 encadre le geste
                # ENTIER : UNE ligne de chatter et UN instantané par clic.
                avant_geste = None
                if geste_complet:
                    from ..domain.modifiabilite import debut_de_geste_devis
                    avant_geste = debut_de_geste_devis(devis, request.user)
                if entete_ser is not None:
                    entete_ser.save(updated_by=request.user)
                if etude_in:
                    from ..domain.etude_schema import ECRAN, ecrire
                    ecrire(devis, proprietaire=ECRAN, **etude_in)
                # QJR93 — l'ÉTAPE 5 du pipeline, sous la MÊME transaction
                # qu'hier : un échec préserve les lignes d'origine.
                # QJR518 — ``user`` : l'auteur d'une correction après envoi
                # (chatter + instantané), jamais lu du corps.
                appliquer(devis, IntentionDevis(
                    origine=ORIGINE_ECRAN, mode=MODE_ECRIRE,
                    company=devis.company, user=request.user,
                    composition=lignes_in,
                    tracer_correction=not geste_complet))
                # QJR539 — remise plus profonde au-dessus du seuil sur un
                # envoyé : la garde T17 s'applique, un refus annule le geste.
                if envoye:
                    reverifier_remise_apres_correction(
                        devis, request.user, avant=remise_avant)
                if avant_geste is not None:
                    from ..domain.modifiabilite import fin_de_geste_devis
                    fin_de_geste_devis(devis, request.user, avant=avant_geste,
                                       objet='lignes')
        except RemiseNonApprouvee as erreur:
            return Response({'detail': erreur.message},
                            status=status.HTTP_400_BAD_REQUEST)
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 — rollback : lignes d'origine
            return Response({'detail': f'Remplacement échoué : {exc}'},
                            status=status.HTTP_400_BAD_REQUEST)
        # CJ2b — C'EST LE CHEMIN D'ENREGISTREMENT DU GÉNÉRATEUR. L'écran de
        # devis sauvegarde une édition en deux appels : ``PATCH /devis/<id>/``
        # puis CE remplacement atomique de TOUTES les lignes. Sans ce
        # rafraîchissement, la composition qui vient d'être posée (panneaux,
        # onduleur, batterie) ne serait jamais celle que le bloc horaire décrit,
        # et le devis retomberait sur le modèle forfaitaire alors qu'un calcul
        # heure par heure exact est possible.
        # HORS de la transaction ci-dessus, et best-effort : un devis
        # correctement remplacé ne doit jamais être annulé par une étude.
        # L-1V (24/08/2026) — LES QUATRE ÉTUDES EN UN SEUL GESTE (bloc horaire,
        # dimensionnement, profils comparatifs, conception électrique) : voir
        # ``services.rafraichir_etudes_du_devis``. La composition vient de
        # changer, les quatre études doivent décrire les lignes COURANTES.
        # QJR47 — ``force=True`` RETIRÉ. Il couvrait le cas « les lignes ET
        # ``etude_params`` ont changé dans le même enregistrement » : les DEUX
        # entrent désormais dans l'empreinte (la composition pour le bloc
        # horaire et les profils, le profil client pour l'empreinte des
        # entrées), donc un vrai changement recalcule et un faux ne coûte plus
        # trois balayages complets.
        # QJR93 — l'ÉTAPE 7 du pipeline, HORS de la transaction ci-dessus,
        # comme hier. La relecture (QJR20) est ce que ce chemin faisait déjà
        # implicitement : ``remplacer_lignes`` supprime la relation préchargée
        # par le queryset, ce qui vide son cache de résultats — le contrat est
        # désormais EXPLICITE plutôt que dépendant de ce détail de Django.
        # QJR544 — un en-tête / une étude changés dans ce geste sont des
        # grandeurs invisibles depuis les lignes : ``force_etudes`` (comme le
        # PATCH d'en-tête). Sans eux, comportement d'hier.
        appliquer(devis, IntentionDevis(
            origine=ORIGINE_ECRAN, mode=MODE_RAFRAICHIR,
            company=devis.company, force_etudes=geste_complet))
        # QJR545 — le jeton d'édition avance (lignes sauvées hors Devis.save)
        # et la réponse porte celui réellement en base.
        from ..domain.verrou_devis import toucher
        toucher(devis)
        return Response(DevisSerializer(
            devis, context={'request': request}).data)

    def perform_update(self, serializer):
        # YDOCF2 / QJR516 / QJR521 / ERR8 / QJR539 — les gardes d'une mise à
        # jour d'en-tête vivent en UN point (``_gardes_mise_a_jour``), partagé
        # avec ``replace-lines`` (QJR544). QJR541 — ``statut`` est en lecture
        # seule : un PATCH ne fait plus passer un devis en « envoyé » ni
        # n'avance le funnel.
        # QJR545 — verrou optimiste (jeton optionnel, autres clients).
        from ..domain.verrou_devis import verifier_jeton
        charge = verifier_jeton(serializer.instance, self.request.data)
        if charge is not None:
            raise _DevisModifie(charge)
        _gardes_mise_a_jour(serializer.instance, serializer.validated_data,
                            self.request.user)
        company = self.request.user.company
        # QJR518 — état vu par le client capturé AVANT l'écriture (ENVOYÉ
        # seulement) ; trace posée en fin de geste si l'en-tête ou la note
        # visibles ont changé.
        from ..domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis)
        avant_geste = debut_de_geste_devis(
            serializer.instance, self.request.user)
        super().perform_update(serializer)
        # QJR552 — l'instantané APRÈS le geste (brouillon ou envoyé : l'en-tête
        # corrigé, remise / échéancier, entre dans l'historique) ; dédoublonné.
        from ..domain.cycle_vie import instantane_de_geste
        instantane_de_geste(serializer.instance, user=self.request.user)
        # VX98 — dernier auteur de modification (server-side, jamais du corps) :
        # alimente la puce de fraîcheur. Pattern archived_by.
        serializer.instance.updated_by = self.request.user
        serializer.instance.save(update_fields=['updated_by'])
        # CJ2b — le bloc horaire canonique doit refléter le devis TEL QU'IL EST
        # APRÈS cette écriture (puissance, factures, profil ont pu changer) :
        # sans ce rafraîchissement, un devis résidentiel édité hors auto-devis
        # gardait un bloc PÉRIMÉ ou ABSENT et retombait sur le modèle
        # « facture »/forfait alors qu'un calcul heure par heure exact restait
        # possible. Best-effort, ne lève jamais (voir la docstring de la
        # fonction) : un rafraîchissement raté n'empêche jamais la sauvegarde.
        # ``force`` : une mise à jour de devis peut avoir changé les FACTURES
        # ou le profil dans ``etude_params`` — grandeurs invisibles depuis les
        # lignes, donc le court-circuit « composition inchangée » ne s'applique
        # pas ici.
        #
        # QJR94 (M5, bascule 2/5) — LES QUATRE ÉTUDES, PLUS DEUX.
        # Ce chemin n'appelait QUE deux des quatre rafraîchisseurs (le bloc
        # horaire et le dimensionnement), ce qui DÉFAISAIT la façade « les
        # quatre études en un seul geste » (L-1V) que les trois autres chemins
        # d'écriture respectent : après tout PATCH touchant ``etude_params``,
        # les PROFILS COMPARATIFS et la CONCEPTION ÉLECTRIQUE restaient ceux
        # d'avant. La conception électrique, seule des quatre à n'être jamais
        # recalculée à la lecture, PERSISTAIT alors un schéma unifilaire
        # décrivant une composition que le devis ne vend plus — et c'est ce
        # schéma-là que le client voit sur sa page proposition.
        # CHANGEMENT DE COMPORTEMENT ASSUMÉ (R4-C.5), porté au DONE LOG.
        # ``force=True`` est CONSERVÉ, et vaut désormais pour les quatre : la
        # raison qui l'imposait aux deux premiers (un PATCH change des
        # grandeurs qu'aucune lecture de lignes ne voit) vaut à l'identique
        # pour les deux autres.
        appliquer(serializer.instance, IntentionDevis(
            origine=ORIGINE_ECRAN, mode=MODE_RAFRAICHIR,
            company=company, force_etudes=True))
        fin_de_geste_devis(serializer.instance, self.request.user,
                           avant=avant_geste, objet='en-tête')
        # QJR545 — les écritures de fin de geste passent en ``update_fields`` :
        # le jeton servi par la réponse est réaligné sur la base.
        from ..domain.verrou_devis import toucher
        toucher(serializer.instance)
