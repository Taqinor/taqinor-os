"""SPL140 — les actions de conception 3D / électrique / simulation / layout
du devis, déplacement pur depuis ``views/devis.py`` (propriétaire
calepinage) : corps octet-identiques, routes inchangées.

Le littéral ``sender='ventes.views.devis'`` de ``_emettre_layout_finalise``
reste IDENTIQUE (aucun récepteur ne filtre sur le sender). Les
``getLogger(__name__)`` des corps journalisent désormais sous
``apps.ventes.views.devis_calepinage``. Les imports function-locaux restent
dans les corps (patchs ``apps.ventes.utils.pdf.*``,
``apps.ventes.quote_engine.*``, ``apps.ventes.services.*``,
``core.events.layout_finalise.send``).
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from . import openapi_docs as D
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from ..utils.client_links import chemin_proposition
from .devis_gardes import _refus_modifiabilite, _reponse_non_modifiable
from .devis_gardes import _pourcentage_saisi  # ACAL278


def _emettre_layout_finalise(devis, user):
    """PV79 — annonce que la conception 3D d'un devis est finalisée.

    ACAL34 — le corps vit dans ``domain/resynchronisation`` (l'enveloppe
    ``resynchroniser_conception`` l'émet elle-même) ; ce nom reste le point
    d'appel des vues (même ``sender``, même try/except, jamais bloquant).
    """
    from ..domain.resynchronisation import emettre_layout_finalise
    emettre_layout_finalise(devis, user)


def _jeton_if_match(request):
    """ACAL96 — l'empreinte « document » de l'en-tête ``If-Match`` (ETag
    tolérée), ``None`` si absent : le jeton n'est comparé que s'il est
    FOURNI (C-ACAL-044)."""
    brut = request.headers.get('If-Match')
    if brut is None or not brut.strip():
        return None
    brut = brut.strip()
    if brut.startswith('W/'):
        brut = brut[2:]
    return brut.strip().strip('"').strip()


def _ecrire_conception(devis, payload, request):
    """ACAL96 — calepinage lié écrit puis devis resynchronisé ; les refus
    deviennent les réponses existantes (409 ``{detail, revision_possible}``,
    refus du calepinage tels quels)."""
    from ..domain.resynchronisation import (
        ConceptionRefusee, ecrire_conception_du_devis)
    from ..services import SyncLayoutError

    try:
        resultat = ecrire_conception_du_devis(
            devis, payload, request.user,
            base_empreinte=_jeton_if_match(request))
    except SyncLayoutError as exc:
        return Response(
            {'detail': exc.detail,
             'revision_possible': exc.revision_possible},
            status=status.HTTP_409_CONFLICT)
    except ConceptionRefusee as refus:
        return Response(refus.corps, status=refus.statut)
    return Response(resultat)


class DevisCalepinageActionsMixin:
    """SPL140 — actions calepinage / conception de ``DevisViewSet`` (mixin, aucune base)."""

    @action(detail=False, methods=['post'], url_path='from-layout',
            permission_classes=[IsResponsableOrAdmin])
    def from_layout(self, request):
        """Q3/B1 — transforme un layout toiture 3D FINALISÉ en Devis brouillon,
        puis frappe un lien public de proposition.

        Corps : ``{layout, lead, client, taux_tva?, remise_globale?}``. Le
        ``layout`` est le JSON sérialisé tel que stocké par l'action ``layout``
        (AreaRecord[] + result + renderPlan). La société est TOUJOURS celle du
        user (jamais lue du corps) ; lead et client sont résolus bornés à cette
        société (404/400 si une autre société). Au moins un lead OU un client est
        requis. Aucun statut n'est touché : le service renvoie un brouillon
        (préservation des statuts, règle #4) et la numérotation anti-collision
        est gérée par le service.

        QJ17 — idempotency: if a brouillon devis with the same lead + layout hash
        already exists for this company, it is returned (HTTP 200) instead of
        creating a duplicate.  A pre-flight composition check validates the
        catalogue before building and returns HTTP 422 with inline French guidance
        on failure (instead of a PDF error at render time).
        """
        from decimal import Decimal
        from ..services import (
            AutoDevisError, build_devis_from_layout, layout_hash,
            poser_layout_hash, validate_composition_for_layout)
        from ..selectors import devis_brouillon_pour_layout
        from ..models import ShareLink

        company = request.user.company
        if company is None:
            return Response(
                {'detail': 'Utilisateur sans société.'},
                status=status.HTTP_400_BAD_REQUEST)

        layout = request.data.get('layout')
        # ACAL108 (D-ACAL-2) — la porte jumelle CAL185 `{calepinage}` est
        # RETIRÉE : un calepinage se chiffre par SON « Générer le devis »
        # (retenir une variante l'écrit comme conception courante). Refus
        # nommé, rien n'est écrit ; un `layout` explicite est inchangé.
        if ((not isinstance(layout, dict) or not layout)
                and request.data.get('calepinage')):
            return Response(
                {'detail': "Un calepinage se chiffre par « Générer le devis » "
                           "du calepinage : la variante retenue en est la "
                           "conception courante",
                 'champ': 'calepinage'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        if not isinstance(layout, dict) or not layout:
            return Response(
                {'detail': 'Layout manquant ou invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        # Résolution bornée société du lead et du client. On passe par les
        # sélecteurs/services crm (jamais d'import direct des models crm depuis
        # ventes) ; un id d'une autre société → 404 (introuvable dans la portée).
        lead_obj = None
        client_obj = None
        lead_id = request.data.get('lead')
        client_id = request.data.get('client')
        if lead_id:
            from apps.crm.selectors import get_company_lead
            lead_obj = get_company_lead(company, lead_id)
            if lead_obj is None:
                return Response({'detail': 'Lead inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
        if client_id:
            from apps.crm.selectors import get_company_client
            client_obj = get_company_client(company, client_id)
            if client_obj is None:
                return Response({'detail': 'Client inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
        if lead_obj is None and client_obj is None:
            return Response(
                {'detail': 'Un client ou un lead est requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        # ACAL278 — UNE règle de module (fini, 0..100, 2 décimales) au lieu
        # d'un ``_dec`` imbriqué sans borne : 400 NOMMÉ, jamais l'IntegrityError
        # de ck_devis_remise_globale_0_100 (500).
        # APAR49 — défaut = taux STANDARD de la société (``tva_standard``).
        from ..utils.company_settings import tva_standard
        taux_tva, erreur = _pourcentage_saisi(
            request.data, 'taux_tva', tva_standard(company))
        remise, erreur_remise = _pourcentage_saisi(
            request.data, 'remise_globale', Decimal('0'))
        erreur = erreur or erreur_remise
        if erreur:
            return Response(
                dict(erreur, detail=next(iter(erreur.values()))),
                status=status.HTTP_400_BAD_REQUEST)

        # STKCAT8 — le chemin 3D était MUET sur la structure : il ne
        # transmettait NI l'id du produit choisi NI le type, donc tout devis né
        # du calepinage était composé en ACIER par défaut, quoi qu'ait choisi le
        # commercial. Valeur non numérique ⇒ ignorée (repli sur le type), jamais
        # un 500 ; l'id est résolu dans le catalogue DÉJÀ scopé société, côté
        # composition (un id d'une autre société n'y désigne rien).
        _brut_structure_id = request.data.get('structure_produit_id')
        try:
            structure_produit_id = (
                int(_brut_structure_id)
                if _brut_structure_id not in (None, '') else None)
        except (TypeError, ValueError):
            structure_produit_id = None
        # STKCAT9 bis — absent = None : la création 3D retombe alors sur la
        # structure du LEAD (produit épinglé, puis préférence), comme /auto/.
        structure_type = request.data.get('structure_type') or None

        # QJ17 — pre-flight composition check: validate catalogue before building.
        # ACAL32 — le pré-vol compose avec la phase et le site isolé du LEAD
        # (déduits par le pré-vol lui-même) ; un site isolé que le catalogue
        # ne sert pas est un 422 NOMMÉ {hors_reseau: …}.
        try:
            composition_errors = validate_composition_for_layout(
                layout, company, lead=lead_obj)
        except AutoDevisError as refus:
            return Response({refus.field or 'detail': refus.message},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        if composition_errors:
            return Response(
                {'detail': composition_errors[0], 'errors': composition_errors},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # QJ17 — idempotency: dedupe by lead + layout hash.
        # Re-clicking « Générer » returns the existing brouillon, not a duplicate.
        # ACAL88 — la dédup est CELLE du sélecteur (brouillons ACTIFS
        # seulement, la même que le module calepinage) : la copie inline est
        # SUPPRIMÉE, un brouillon archivé n'est plus jamais rendu.
        lhash = layout_hash(layout)
        existing = None
        if lead_obj is not None and lhash:
            existing = devis_brouillon_pour_layout(company, lead_obj.pk, lhash)
        if existing is not None:
            link = ShareLink.for_devis(existing)
            import logging as _logging
            _logging.getLogger(__name__).info(
                'QJ17: dedup hit — returning existing brouillon %s (hash %s…)',
                existing.reference, lhash[:8])
            return Response(
                {
                    'id': existing.id,
                    'reference': existing.reference,
                    'statut': existing.statut,
                    'proposal_token': link.token,
                    'proposal_path': chemin_proposition(existing, link.token),
                    'avertissements': [],
                    'marques_manquantes': [],
                    'deduplicated': True,
                },
                status=status.HTTP_200_OK)

        # L-TRI / ACAL32 — la phase ET le site isolé du lead sont déduits UNE
        # fois par ``build_devis_from_layout`` (même point pour le module
        # calepinage) : la déduction inline d'ici est SUPPRIMÉE.
        _composition = dict(
            taux_tva=taux_tva, remise_globale=remise,
            structure_produit_id=structure_produit_id,
            structure_type=(str(structure_type) if structure_type else None))
        # ACAL88 — le canal de la construction (U3) : ce que la composition a
        # refusé de faire remonte dans la réponse (contrat devis_from_layout).
        journal = {}
        try:
            devis = build_devis_from_layout(
                layout=layout, user=request.user, company=company,
                lead=lead_obj, client=client_obj, journal=journal,
                **_composition)
        except AutoDevisError as refus:
            # ACAL32 — un refus de composition (site isolé non servable…) est
            # un 422 NOMMÉ, jamais un 500 ; rien n'a été écrit.
            return Response({refus.field or 'detail': refus.message},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # QJ17 — persist the layout hash on the newly-created devis so future
        # duplicate requests are caught in O(1).
        # ACAL88 — l'écriture inline est SUPPRIMÉE : le poseur unique.
        poser_layout_hash(devis, lhash)

        # PV79 — la conception 3D est FINALISÉE. Aucun statut ne bouge : on
        # ANNONCE seulement le fait, et les abonnés (crm : note au chatter du
        # lead) réagissent — ventes n'importe donc jamais crm.
        _emettre_layout_finalise(devis, request.user)

        link = ShareLink.for_devis(devis)
        corps = {
            'id': devis.id,
            'reference': devis.reference,
            'statut': devis.statut,
            'proposal_token': link.token,
            'proposal_path': chemin_proposition(devis, link.token),
            # ACAL88 / ACAL4 — la branche ToitureDesign.jsx qui les lit
            # devient vivante.
            'avertissements': list(journal.get('avertissements') or ()),
            'marques_manquantes': list(
                journal.get('marques_manquantes') or ()),
        }
        return Response(corps, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='design-context',
            permission_classes=[IsResponsableOrAdmin])
    def design_context(self, request, pk=None):
        """PV17 — TOUT ce que l'écran de conception 3D doit savoir d'un devis,
        en UN SEUL appel et sous UNE SEULE forme.

        Renvoie ``{devis, geometrie, cible, carte, modifiable,
        raison_lecture_seule, avertissements}`` — toutes les clés TOUJOURS
        présentes (contrat ``contract_samples/devis_design_context.json``) : un
        panier vide vaut ``[]``, une valeur inconnue ``None``/``''``, jamais
        une clé absente. L'écran n'a donc rien à deviner et ne peut pas
        ``.map()`` sur ``undefined``.

        LECTURE PURE, scopée société par ``get_queryset`` (un devis d'une autre
        société → 404) : aucun statut, aucune ligne, aucun layout n'est écrit
        (règle #4)."""
        from ..selectors import contexte_conception_devis

        devis = self.get_object()  # borné société par get_queryset
        contexte = contexte_conception_devis(devis, request.user.company)
        if contexte is None:
            return Response({'detail': 'Devis inconnu.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(contexte)

    @action(detail=True, methods=['post'], url_path='sync-layout',
            permission_classes=[IsResponsableOrAdmin])
    def sync_layout(self, request, pk=None):
        """PV18 — resynchronise les LIGNES du devis sur un nouveau calepinage.

        Corps : le layout sérialisé (on accepte aussi les enveloppes
        ``{"layout": …}`` / ``{"roof_layout": …}``, comme l'action ``layout``).

        Mise à jour CHIRURGICALE d'un brouillon : quantités de panneaux,
        présence de la batterie et onduleur accordé au scénario — prix
        négociés, remises, sections, notes, ordre et groupes multi-villa
        restent intacts. PVHEAL — le KIT MANQUANT (structures, socles,
        accessoires, tableau AC/DC, installation, transport…) est en plus
        AJOUTÉ quand il manque, jamais re-tarifé quand il est là ; un
        composant introuvable ou non tarifé est sauté et DIT dans
        ``avertissements``, et ``lignes_ajoutees`` compte les ajouts. Le
        STATUT n'est jamais écrit (règle #4) : un devis « envoyé » est CORRIGÉ
        SUR PLACE (200, QJR557 — chatter « corrigé après envoi : calepinage »,
        marqueur ``resync_apres_envoi``, statut inchangé) ; un devis accepté
        répond 409 avec ``revision_possible: true`` (le bon geste est
        « Réviser ») ; refusé/expiré, 409 avec ``revision_possible: false``.
        Renvoyer le MÊME layout ne fait aucune écriture
        (``inchange: true``). Devis d'une autre société → 404 (get_queryset)."""
        devis = self.get_object()  # borné société par get_queryset
        payload = request.data
        if isinstance(payload, dict):
            for enveloppe in ('layout', 'roof_layout'):
                if set(payload.keys()) == {enveloppe}:
                    payload = payload[enveloppe]
                    break
        if not isinstance(payload, dict) or not payload:
            return Response({'detail': 'Layout manquant ou invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # ACAL96 (D-ACAL-1) — le layout est écrit dans le CALEPINAGE lié
        # (adopté/créé au besoin), puis l'enveloppe ACAL34 resynchronise le
        # devis depuis CE calepinage : plus d'écriture de Devis.roof_layout
        # depuis le corps.
        return _ecrire_conception(devis, payload, request)

    @extend_schema(request=D.ConceptionElectriqueRequest, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=['get', 'post'],
            url_path='conception-electrique',
            permission_classes=[IsResponsableOrAdmin])
    def conception_electrique(self, request, pk=None):
        """PV41 — l'ÉTUDE ÉLECTRIQUE du devis, en UN SEUL appel.

        ``GET`` renvoie l'étude rangée sur le devis, et la calcule si elle
        n'existe pas encore. ``POST`` la RECALCULE en appliquant les
        surcharges du corps (``dc_m``, ``ac_m``, ``phases``, ``regime``,
        ``batterie``, ``zone_keraunique``, ``temp_froid_c``, ``temp_chaud_c``,
        ``longueur_chaine_forcee``, ``plafond_kwc_par_onduleur``,
        ``inclure_prise_terre`` — toute autre clé est ignorée). Les DEUX
        rendent EXACTEMENT la même forme, celle du
        contrat partagé ``contract_samples/conception_electrique.json``
        (``chaines``, ``conformite``, ``ratio_dc_ac``, ``ratio_ac_dc``,
        ``protections``, ``cables``, ``bom``, ``note``, ``parametres``) —
        toutes les clés TOUJOURS présentes, une liste vide valant ``[]``.

        Recalculer aux mêmes entrées n'écrit RIEN (empreinte identique,
        idempotence QJ17). Aucun statut, aucune ligne, aucun prix n'est touché
        — l'étude est une pièce technique et le moteur ne connaît aucun montant
        (règle #4 : ``/proposal`` reste le seul chemin du PDF client). Scopé
        société par ``get_queryset`` : un devis d'une autre société → 404.
        """
        from ..electrical_service import (
            build_electrical_design, conception_electrique_stockee)

        devis = self.get_object()  # borné société par get_queryset
        # ADEV58 (C-ADEV-040) — prédicat de modifiabilité (geste ETUDE) : un
        # devis accepté/refusé/expiré ou remplacé ne voit plus son étude
        # RÉÉCRITE (le schéma servi au client d'un accepté est figé).
        non_modifiable = _refus_modifiabilite(devis, 'ETUDE')
        if request.method == 'GET':
            stockee = conception_electrique_stockee(devis)
            if stockee is not None:
                return Response(stockee)
            # GET non modifiable sans étude rangée : calculée pour l'affichage,
            # JAMAIS persistée.
            return Response(build_electrical_design(
                devis, persister=not non_modifiable))
        if non_modifiable:
            return _reponse_non_modifiable(devis, 'ETUDE')
        from ..domain.modifiabilite import (
            consigner_correction_apres_envoi, _est_envoye)
        from ..domain.verrou_devis import toucher

        surcharges = request.data if isinstance(request.data, dict) else {}
        hash_avant = devis.electrical_design_hash
        design = build_electrical_design(devis, overrides=surcharges)
        # Un ENVOYÉ se corrige sur place (D-QJR5-1) : une étude réellement
        # réécrite est tracée « corrigé après envoi — étude » et avance le
        # jeton d'édition. Aux mêmes entrées (idempotence) : rien.
        if devis.electrical_design_hash != hash_avant and _est_envoye(devis):
            consigner_correction_apres_envoi(
                devis, user=request.user, objet='etude',
                resume='étude (conception électrique)')
            toucher(devis)
        return Response(design)

    @action(detail=True, methods=['post'], url_path='simuler',
            permission_classes=[IsResponsableOrAdmin])
    def simuler(self, request, pk=None):
        """PV74 — lance l'ÉTUDE BANKABLE du devis en tâche de fond → 202.

        L'étude interroge PVGIS par pan de toiture : la faire dans la requête
        bloquerait un slot serveur pendant des secondes et casserait au premier
        hoquet réseau. On répond donc immédiatement ``202`` avec un jeton et
        l'URL à interroger, exactement comme l'export asynchrone de cette app
        (SCA41) :

            {detail, job_id, status: 'pending', zones, status_url}

        Corps : ``{"force_refresh": true}`` pour ignorer le cache PVGIS (PV73)
        et refaire les appels réseau ; absent/false → un second calcul du même
        toit ne recoûte aucun aller-retour.

        Un devis SANS calepinage exploitable répond ``400`` plutôt que de
        lancer une étude vide. Le STATUT du devis n'est jamais écrit (règle #4 :
        la tâche ne pose que ``etude_params['simulation']``). Scopé société par
        ``get_queryset`` : un devis d'une autre société → 404.
        """
        import uuid

        from django.core.cache import cache

        from ..tasks import (
            SIMULATION_JOB_CACHE_TTL, simulation_job_cache_key,
            task_simulate_bankable_study, zones_etude_du_devis,
        )

        devis = self.get_object()  # borné société par get_queryset
        # ADEV58 — même garde que la conception : l'étude bancable d'un devis
        # accepté ou remplacé n'est plus relancée (409).
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        zones = zones_etude_du_devis(devis)
        if not zones:
            return Response(
                {'detail': ('Ce devis ne porte aucun pan de toiture '
                            'exploitable : dessinez le calepinage 3D avant de '
                            'lancer la simulation.')},
                status=status.HTTP_400_BAD_REQUEST)

        corps = request.data if isinstance(request.data, dict) else {}
        force_refresh = bool(corps.get('force_refresh'))

        token = uuid.uuid4().hex
        company = request.user.company
        # État initial en cache AVANT dispatch, scopé société — le endpoint de
        # statut vérifie cette société avant tout accès (jamais inter-tenant).
        cache.set(simulation_job_cache_key(token), {
            'company_id': company.id,
            'devis_id': devis.pk,
            'status': 'pending',
        }, SIMULATION_JOB_CACHE_TTL)
        task_simulate_bankable_study.apply_async(
            args=[devis.pk, company.id, token],
            kwargs={'force_refresh': force_refresh},
            queue='interactive')

        return Response({
            'detail': 'Simulation lancée en arrière-plan.',
            'job_id': token,
            'status': 'pending',
            'zones': len(zones),
            'status_url': ('/api/django/ventes/devis/%s/simulation-status/%s/'
                           % (devis.pk, token)),
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'],
            url_path=r'simulation-status/(?P<token>[0-9a-f]{32})',
            permission_classes=[IsResponsableOrAdmin])
    def simulation_status(self, request, pk=None, token=None):
        """PV74 — état d'une simulation lancée par ``simuler``.

        ``202 {status: 'pending'}`` tant qu'elle tourne, ``200 {status:
        'ready', simulation: {...}}`` quand elle est rangée, ``500 {status:
        'error'}`` si le calcul a échoué. Un jeton inconnu — ou appartenant à
        une AUTRE société — répond ``404`` indistinct : on ne révèle pas
        l'existence d'un job qui n'est pas le sien (même discipline que
        ``export_status``, SCA41).

        La charge ``simulation`` est relue sur le DEVIS
        (``etude_params['simulation']``), jamais recopiée depuis le cache : le
        document reste l'unique source de vérité. LECTURE PURE."""
        from django.core.cache import cache

        from ..tasks import simulation_job_cache_key

        devis = self.get_object()  # borné société par get_queryset
        job = cache.get(simulation_job_cache_key(token))
        if (not job or job.get('company_id') != request.user.company_id
                or job.get('devis_id') != devis.pk):
            return Response({'detail': 'Simulation introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        etat = job.get('status')
        if etat == 'ready':
            simulation = (devis.etude_params or {}).get('simulation')
            return Response({'status': 'ready', 'simulation': simulation})
        if etat == 'error':
            return Response(
                {'status': 'error', 'detail': 'La simulation a échoué.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'status': 'pending'},
                        status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'],
            url_path='ajouter-boq-electrique',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_boq_electrique(self, request, pk=None):
        """PV47 — reporte le BORDEREAU électrique (PV41) en lignes de devis.

        Geste EXPLICITE et jamais silencieux : la conception électrique se
        recalcule à chaque changement de disposition, et si elle réécrivait les
        lignes toute seule, le prix d'un devis bougerait sous les yeux du
        client. Ces lignes n'apparaissent donc QUE sur cet appel.

        Deux issues par ligne de bordereau : un produit du catalogue
        correspond (ligne produit à SON prix — 0 et « à chiffrer » tant que le
        fondateur ne l'a pas renseigné), ou aucun ne correspond (ligne de NOTE
        « à chiffrer », sans prix, et la ligne remonte dans ``manques``).
        Aucun prix n'est JAMAIS inventé.

        GARDE DE STATUT (patron PV15) : seuls « brouillon » et « envoyé »
        acceptent l'ajout ; au-delà, 409 avec le statut NOMMÉ (le bon geste est
        « Réviser »). Cette garde LIT le statut, elle ne l'écrit jamais
        (règle #4). Devis d'une autre société → 404 (get_queryset).
        """
        from ..services import ajouter_lignes_boq_electrique

        devis = self.get_object()  # borné société par get_queryset
        # QJR516 — le prédicat UNIQUE (domain/modifiabilite, geste BOQ) ;
        # texte et code 409 {'detail'} CONSERVÉS.
        if _refus_modifiabilite(devis, 'BOQ'):
            return _reponse_non_modifiable(
                devis, 'BOQ',
                'Devis « %s » : on ne peut plus y ajouter de lignes. '
                'Utilisez « Réviser » pour en créer une nouvelle version.')
        design = getattr(devis, 'electrical_design', None)
        if not isinstance(design, dict) or not design.get('bom'):
            return Response(
                {'detail': "Ce devis n'a pas encore de conception électrique : "
                           'lancez d\'abord « Conception électrique ».'},
                status=status.HTTP_400_BAD_REQUEST)
        resultat = ajouter_lignes_boq_electrique(devis, request.user)
        return Response(resultat)

    # ACAL97 a retiré le re-POST de ToitureDesign : from-layout range déjà la
    # conception ENRICHIE, ce second envoi l'écrasait. Porte gardée (GET/POST).
    # api-only: plus d'appelant écran depuis ACAL97 (intégrations/scripts)
    @action(
        detail=True,
        methods=['get', 'post'],
        url_path='layout',
        permission_classes=[IsResponsableOrAdmin],
    )
    def layout(self, request, pk=None):
        """Q1 — lit (GET) ou enregistre (POST) le layout 3D FINALISÉ du devis.

        Le corps POST EST le layout sérialisé (AreaRecord[] + result +
        renderPlan) tel que le produit l'outil roofPro11. La société n'est
        jamais lue du corps : le devis est déjà borné à la société de
        l'utilisateur par ``get_queryset`` (un devis d'une autre société →
        404). Aucun statut ne bouge (préservation des statuts, règle #4).

        ACAL96 (D-ACAL-1) — le POST écrit le CALEPINAGE lié (adopté/créé au
        besoin) puis resynchronise le devis par l'enveloppe unique, exactement
        comme ``sync-layout`` : ``Devis.roof_layout`` est l'instantané RANGÉ
        (``_pans_geometry``) de la conception, plus jamais le corps brut.
        La réponse reste ``{roof_layout}``."""
        devis = self.get_object()
        if request.method == 'GET':
            return Response({'roof_layout': devis.roof_layout})
        # QJR516 — POST gardé (geste ETUDE).
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        # POST — le corps entier est le layout (on accepte aussi un wrapper
        # {"roof_layout": …} pour rester souple côté front).
        payload = request.data
        if isinstance(payload, dict) and set(payload.keys()) == {'roof_layout'}:
            payload = payload['roof_layout']
        if not isinstance(payload, dict):
            return Response({'detail': 'Layout manquant ou invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # ACAL96 (D-ACAL-1) — l'écriture brute ``devis.roof_layout = payload``
        # est SUPPRIMÉE : même chemin que sync-layout (calepinage lié écrit,
        # puis resynchro — empreinte, trace « corrigé après envoi » et annonce
        # PV79 posées par l'enveloppe). Réponse inchangée.
        reponse = _ecrire_conception(devis, payload, request)
        if reponse.status_code != status.HTTP_200_OK:
            return reponse
        devis.refresh_from_db(fields=['roof_layout'])
        return Response({'roof_layout': devis.roof_layout})

    @action(
        detail=True,
        methods=['post'],
        url_path='roof-image',
        permission_classes=[IsResponsableOrAdmin],
    )
    def roof_image(self, request, pk=None):
        """Q4 — réceptionne le snapshot PNG 3D et le stocke dans MinIO.

        L'image part dans le bucket PDF existant sous une clé scopée société
        (``roofs/<company>/<reference>.png``) et la clé est mémorisée sur
        ``devis.roof_image``. La société est forcée côté serveur (clé dérivée
        du devis, lui-même borné à la société par ``get_queryset``) ; rien
        n'est lu du corps hors le fichier. Aucun statut ne bouge (règle #4).
        ACAL314 — renvoie le chemin RELATIF de relecture servi par Django
        (``roof-image/fichier/``), jamais une URL pré-signée vers l'hôte
        interne du magasin."""
        from ..utils.pdf import upload_roof_image
        from ..quote_engine.builder import _ensure_pdf_bucket
        from ..services import url_fichier_toiture_devis

        # QJR516 — garde (geste ETUDE) AVANT l'upload MinIO : un devis
        # accepté ne reçoit plus de rendu, et aucun objet n'est écrit.
        devis_garde = self.get_object()
        if _refus_modifiabilite(devis_garde, 'ETUDE'):
            return _reponse_non_modifiable(devis_garde, 'ETUDE')
        upload = request.FILES.get('image') or request.FILES.get('file')
        if upload is None:
            return Response(
                {'detail': "Fichier image manquant (champ « image »)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = upload.read()
        # Validation magic-bytes : PNG (\x89PNG) ou JPEG (\xff\xd8\xff).
        is_png = data[:8] == b'\x89PNG\r\n\x1a\n'
        is_jpeg = data[:3] == b'\xff\xd8\xff'
        if not (is_png or is_jpeg):
            return Response(
                {'detail': 'Image invalide (PNG ou JPEG attendu).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        devis = self.get_object()
        ext = 'png' if is_png else 'jpg'
        ctype = 'image/png' if is_png else 'image/jpeg'
        company_id = getattr(devis, 'company_id', None) or '0'
        key = f'roofs/{company_id}/{devis.reference}.{ext}'
        _ensure_pdf_bucket()
        upload_roof_image(data, key, content_type=ctype)
        devis.roof_image = key
        devis.save(update_fields=['roof_image'])
        return Response(
            {'roof_image': key, 'url': url_fichier_toiture_devis(devis.pk)},
            status=status.HTTP_201_CREATED,
        )

    # api-only: chemin fabriqué côté serveur (url_fichier_toiture_devis),
    # rendu par roof-image et lu tel quel par un <img src> (ACAL314)
    @extend_schema(responses={(200, 'image/*'): OpenApiTypes.BINARY, 404: None})
    @action(detail=True, methods=['get'], url_path='roof-image/fichier',
            permission_classes=[IsAnyRole])
    def roof_image_fichier(self, request, pk=None):
        """ACAL314 (C-ACAL-019) — les OCTETS de l'affiche du devis, par Django.

        Même origine (cookie httpOnly), jamais l'hôte interne ``minio:9000``
        d'une URL pré-signée. La clé est celle que porte le devis
        (``Devis.roof_image``), lue par ``services.lire_image_toiture`` ;
        le MIME vient des octets. Un devis d'une AUTRE société, un devis sans
        affiche ou un objet absent rendent le MÊME 404 : aucun oracle
        d'existence. Lecture seule, aucun statut touché (règle #4)."""
        from django.http import Http404, HttpResponse

        from ..services import lire_image_toiture

        introuvable = Response({'detail': 'Fichier introuvable.'},
                               status=status.HTTP_404_NOT_FOUND)
        try:
            devis = self.get_object()  # borné société par get_queryset
        except Http404:
            return introuvable
        octets, mime = lire_image_toiture(
            (getattr(devis, 'roof_image', None) or '').strip())
        if octets is None:
            return introuvable
        reponse = HttpResponse(octets, content_type=mime)
        reponse['Cache-Control'] = 'private, max-age=300'
        reponse['X-Content-Type-Options'] = 'nosniff'
        return reponse
