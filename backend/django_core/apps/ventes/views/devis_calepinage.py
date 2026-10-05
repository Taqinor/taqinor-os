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
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import Devis
from authentication.permissions import IsResponsableOrAdmin
from ..utils.client_links import chemin_proposition
from .devis_gardes import _refus_modifiabilite, _reponse_non_modifiable
from .devis_gardes import _pourcentage_saisi  # ACAL278


def _emettre_layout_finalise(devis, user):
    """PV79 — annonce que la conception 3D d'un devis est finalisée.

    Passe par le bus ``core.events`` (M6) plutôt que par un appel direct à
    ``crm`` : les deux apps restent découplées, et un futur abonné (chantier,
    notifications…) se branche sans toucher ce fichier. Ne change AUCUN statut
    et n'écrit rien lui-même (règle #4).

    Jamais bloquant : un abonné en échec ne doit pas faire échouer la
    finalisation d'un calepinage déjà enregistré. L'erreur est journalisée.
    """
    from core.events import layout_finalise
    try:
        layout_finalise.send(sender='ventes.views.devis', devis=devis,
                             user=user)
    except Exception:  # noqa: BLE001 — un abonné cassé ne casse pas le devis
        import logging as _logging
        _logging.getLogger(__name__).exception(
            'PV79 : abonné en échec sur layout_finalise (devis %s)', devis.pk)


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
            validate_composition_for_layout)
        from ..models import ShareLink

        company = request.user.company
        if company is None:
            return Response(
                {'detail': 'Utilisateur sans société.'},
                status=status.HTTP_400_BAD_REQUEST)

        layout = request.data.get('layout')
        # CAL185 — DEUXIÈME ENTRÉE, MÊME CHEMIN. Le commercial compare ses
        # options DANS le calepinage, en retient une… et rien ne partait de
        # cette variante retenue. `{"calepinage": <id>}` (sans `layout`) fait
        # lire sa conception par `apps.calepinage.selectors` — jamais ses
        # modèles — et la fait chiffrer par CE service, qui délègue lui-même à
        # `build_devis_from_layout` : aucun second chemin de création de
        # lignes. Un corps qui porte un `layout` explicite est inchangé.
        calepinage_id = request.data.get('calepinage')
        nomenclature = None
        if (not isinstance(layout, dict) or not layout) and calepinage_id:
            from apps.calepinage.selectors import nomenclature_variante_retenue
            nomenclature = nomenclature_variante_retenue(
                calepinage_id, company)
            if nomenclature is None:
                return Response(
                    {'detail': "Aucune variante retenue à chiffrer sur ce "
                               "calepinage : comparez vos options, retenez-en "
                               "une, puis relancez.",
                     'champ': 'calepinage'},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            layout = nomenclature['layout']
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
        taux_tva, erreur = _pourcentage_saisi(
            request.data, 'taux_tva', Decimal('20'))
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
        lhash = layout_hash(layout)
        existing = None
        if lead_obj is not None and lhash:
            existing = (
                Devis.objects.filter(
                    company=company,
                    lead=lead_obj,
                    statut=Devis.Statut.BROUILLON,
                    layout_hash=lhash,
                )
                .order_by('-date_creation')
                .first()
            )
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
        # CAL185 — le rapport « à renseigner » n'existe que sur l'entrée
        # calepinage ; l'entrée historique est byte-identique.
        rapport = None
        try:
            if nomenclature is not None:
                from ..services import build_devis_depuis_calepinage_retenu
                devis, rapport = build_devis_depuis_calepinage_retenu(
                    calepinage_id=calepinage_id, user=request.user,
                    company=company, lead=lead_obj, client=client_obj,
                    **_composition)
            else:
                devis = build_devis_from_layout(
                    layout=layout, user=request.user, company=company,
                    lead=lead_obj, client=client_obj, **_composition)
        except AutoDevisError as refus:
            # ACAL32 — un refus de composition (site isolé non servable…) est
            # un 422 NOMMÉ, jamais un 500 ; rien n'a été écrit.
            return Response({refus.field or 'detail': refus.message},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # QJ17 — persist the layout hash on the newly-created devis so future
        # duplicate requests are caught in O(1).
        if lhash:
            Devis.objects.filter(pk=devis.pk).update(layout_hash=lhash)
            devis.layout_hash = lhash

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
        }
        # CAL185 — clés AJOUTÉES seulement sur l'entrée calepinage : la
        # réponse de l'entrée historique ne bouge pas d'un octet.
        if rapport is not None:
            corps['calepinage'] = rapport['calepinage']
            corps['variante'] = rapport['variante']
            corps['a_renseigner'] = rapport['a_renseigner']
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
        from ..services import sync_devis_from_layout, SyncLayoutError

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
        try:
            resultat = sync_devis_from_layout(devis, payload, request.user)
        except SyncLayoutError as exc:
            return Response(
                {'detail': exc.detail,
                 'revision_possible': exc.revision_possible},
                status=status.HTTP_409_CONFLICT)
        # PV79 — même annonce qu'à la création : la toiture vient d'être
        # redessinée et les lignes suivent. Un renvoi du MÊME layout
        # (``inchange``) n'annonce rien : il ne s'est rien passé.
        if not (isinstance(resultat, dict) and resultat.get('inchange')):
            _emettre_layout_finalise(devis, request.user)
            # CJ2b / L-1V — les lignes viennent d'être resynchronisées
            # (quantités de panneaux, batterie, onduleur) : les QUATRE études
            # doivent repartir de cette composition COURANTE — pas seulement le
            # bloc horaire, sans quoi le schéma unifilaire de la page client
            # décrirait la composition d'avant (best-effort, jamais bloquant —
            # voir ``services.rafraichir_etudes_du_devis``).
            # QJR20 — « composition COURANTE » est désormais GARANTI et non
            # espéré : ``sync_devis_from_layout`` recale l'instance qu'on lui a
            # passée sur la ligne qu'il a verrouillée et écrite
            # (``_resynchroniser_instance_appelante``). Sans ce recalage,
            # ``devis`` gardait les lignes PRÉCHARGÉES en début de requête
            # (``prefetch_related('lignes')`` du queryset) et les quatre études
            # se recalculaient — puis se PERSISTAIENT — sur la composition
            # d'AVANT la resynchro.
            from ..services import rafraichir_etudes_du_devis
            rafraichir_etudes_du_devis(devis)
        return Response(resultat)

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
        if request.method == 'GET':
            stockee = conception_electrique_stockee(devis)
            if stockee is not None:
                return Response(stockee)
            return Response(build_electrical_design(devis))
        surcharges = request.data if isinstance(request.data, dict) else {}
        return Response(build_electrical_design(devis, overrides=surcharges))

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
        404). Seuls ``roof_layout`` et ``layout_hash`` sont touchés ; aucun
        statut ne bouge (préservation des statuts, règle #4).

        CAL39 — CE CHEMIN ÉTAIT MUET. Il n'émettait AUCUN événement et ne
        posait même pas ``layout_hash``, alors que ``from-layout`` et
        ``sync-layout`` font les deux. Conséquences : la dédup au clic suivant
        ne pouvait pas le reconnaître, et tout abonné au bus (le miroir de
        calepinage, la note au chatter du lead) ignorait cet enregistrement —
        un calepinage créé depuis la fiche lead restait gelé pendant que le
        devis, lui, était redessiné ici. Il émet désormais le MÊME événement
        que les deux autres, et pose la MÊME empreinte. AUCUNE ligne d'écran
        ne change : le geste, la route et la réponse sont identiques."""
        from ..services import layout_hash, poser_layout_hash

        devis = self.get_object()
        if request.method == 'GET':
            return Response({'roof_layout': devis.roof_layout})
        # QJR516 — POST gardé (geste ETUDE : le layout brut, pas la
        # resynchronisation des lignes, qui reste CALEPINAGE).
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        # POST — le corps entier est le layout (on accepte aussi un wrapper
        # {"roof_layout": …} pour rester souple côté front).
        payload = request.data
        if isinstance(payload, dict) and set(payload.keys()) == {'roof_layout'}:
            payload = payload['roof_layout']
        # ACAL41 (C-ACAL-090) — sur un ENVOYÉ, ce geste est une correction
        # de la CONCEPTION imprimée : encadré comme sync-layout (début de geste
        # AVANT la première écriture, fin de geste après) ; renvoyer le même
        # document ne laisse aucune trace. Hors envoyé : no-op.
        from ..domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis)
        avant_geste = debut_de_geste_devis(devis, request.user)
        devis.roof_layout = payload
        devis.save(update_fields=['roof_layout'])
        # La MÊME empreinte que les deux autres chemins (écriture ciblée, aucun
        # statut touché) — puis la MÊME annonce.
        poser_layout_hash(devis, layout_hash(payload))
        fin_de_geste_devis(devis, request.user, avant=avant_geste,
                           objet='calepinage')
        _emettre_layout_finalise(devis, request.user)
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
        Renvoie l'URL pré-signée de relecture (lecture seule, 1 h)."""
        from ..utils.pdf import upload_roof_image, roof_image_signed_url
        from ..quote_engine.builder import _ensure_pdf_bucket

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
            {'roof_image': key, 'url': roof_image_signed_url(key)},
            status=status.HTTP_201_CREATED,
        )
