"""SPL136 — le cycle de vie du devis (variantes, révision, acceptation,
refus, lots, dérive lead, modèle, notes), déplacement pur depuis
``views/devis.py`` : corps octet-identiques, routes inchangées.

``variante_config`` RESTE dans ``DevisViewSet`` : seule action sans
``permission_classes=`` en ligne, elle est gardée par le ``get_permissions``
du viewset (``core/action_permission_scan``). Les imports function-locaux
des corps restent dans les corps (les ``mock.patch`` ``apps.ventes.services.*``
n'interceptent qu'ainsi).
"""
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import Devis
from ..serializers import DevisSerializer, DevisActivitySerializer
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
    HasPermissionOrLegacy,
)
from .devis_gardes import _refus_modifiabilite, _reponse_non_modifiable


class _LotCreationSerializer(serializers.Serializer):
    """QJR648 — le corps de ``POST /devis/<id>/lots/`` : ``nom_lot`` requis,
    ``adresse_site`` facultative, ``ordre`` entier ≥ 0 facultatif, ``lignes``
    liste d'entiers facultative. Une entrée invalide répond 400, jamais 500."""

    nom_lot = serializers.CharField(
        max_length=150, required=False, allow_blank=True, allow_null=True,
        error_messages={'max_length': 'Nom de lot trop long (150 max).'})
    adresse_site = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True)
    ordre = serializers.IntegerField(
        min_value=0, required=False, allow_null=True,
        error_messages={'invalid': 'Ordre : entier positif attendu.',
                        'min_value': 'Ordre : entier positif attendu.'})
    lignes = serializers.ListField(
        child=serializers.IntegerField(
            error_messages={'invalid': 'Lignes : identifiants entiers '
                                       'attendus.'}),
        required=False, allow_null=True)

    def validate_nom_lot(self, valeur):
        nom = (valeur or '').strip()
        if not nom:
            raise serializers.ValidationError('Nom de lot requis.')
        return nom

    def validate(self, attrs):
        if not (attrs.get('nom_lot') or '').strip():
            raise serializers.ValidationError(
                {'nom_lot': 'Nom de lot requis.'})
        return attrs


class DevisCycleActionsMixin:
    """SPL136 — actions de cycle de vie de ``DevisViewSet`` (mixin, aucune base)."""

    @action(detail=True, methods=['post'], url_path='save-preset',
            permission_classes=[IsResponsableOrAdmin])
    def save_preset(self, request, pk=None):
        """QJ16-wiring — Enregistre le devis courant comme preset (modèle de devis).

        Body (tous optionnels sauf ``nom``) :
          - ``nom``         : nom du modèle (obligatoire, max 150 caractères)
          - ``description`` : note libre (optionnel)

        La company est TOUJOURS forcée depuis ``devis.company`` — jamais du corps.
        Retourne le preset créé (id, nom, mode_installation, lignes_snapshot…).
        """
        from ..services import save_devis_as_preset
        from ..serializers import DevisPresetSerializer
        devis = self.get_object()
        nom = (request.data.get('nom') or '').strip()
        if not nom:
            return Response(
                {'detail': 'Le nom du modèle est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        description = (request.data.get('description') or '').strip()
        try:
            preset = save_devis_as_preset(
                devis, nom, description, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DevisPresetSerializer(preset).data,
            status=status.HTTP_201_CREATED)

    def _reponse_derive(self, request, devis, resultat):
        """QJR588 — la réponse 200 du contrat QJR505."""
        from ..domain.verrou_devis import toucher
        devis.refresh_from_db()
        toucher(devis)
        return Response({
            'devis': DevisSerializer(devis, context={'request': request}).data,
            'champs_repris': resultat.get('champs_repris', []),
            'corrige_apres_envoi': bool(resultat.get('corrige_apres_envoi')),
            'avertissements': resultat.get('avertissements', []),
        })

    @staticmethod
    def _refus_derive_fige(devis):
        """QJR588 — accepté / refusé / expiré / remplacé : 400
        ``{detail, code: 'devis_fige'}`` (garde QJR516, statut LU)."""
        from ..domain.modifiabilite import (
            LIGNES, DevisNonModifiable, exiger_modifiable)
        try:
            exiger_modifiable(devis, LIGNES)
        except DevisNonModifiable:
            return Response(
                {'detail': 'Devis figé — révisez-le (reviser) pour le '
                           'modifier.', 'code': 'devis_fige'},
                status=status.HTTP_400_BAD_REQUEST)
        return None

    @action(detail=True, methods=['post'], url_path='reappliquer-lead',
            permission_classes=[IsResponsableOrAdmin])
    def reappliquer_lead(self, request, pk=None):
        """QJR588 (contrat ``devis_reappliquer_lead.json``) — « Reprendre
        les valeurs du lead » : études recalculées depuis le lead courant,
        compte de panneaux réconcilié (prix négociés, lignes manuelles,
        sections et notes intacts), estampille reposée. Brouillon et envoyé
        sur place (envoyé : correction tracée) ; figé → 400 ``devis_fige``."""
        from ..domain.pipeline import reappliquer_lead
        devis = self.get_object()  # borné société
        refus = self._refus_derive_fige(devis)
        if refus is not None:
            return refus
        resultat = reappliquer_lead(devis, user=request.user,
                                    company=request.user.company)
        return self._reponse_derive(request, devis, resultat)

    @action(detail=True, methods=['post'], url_path='acquitter-derive',
            permission_classes=[IsResponsableOrAdmin])
    def acquitter_derive(self, request, pk=None):
        """QJR588 — « Garder les valeurs du devis » : l'estampille est
        reposée sur les valeurs COURANTES du lead, rien d'autre (lignes et
        études octet-identiques). Figé → 400 ``devis_fige``."""
        from ..domain.pipeline import restamper_provenance
        devis = self.get_object()
        refus = self._refus_derive_fige(devis)
        if refus is not None:
            return refus
        restamper_provenance(devis)
        return self._reponse_derive(request, devis, {
            'champs_repris': [], 'corrige_apres_envoi': False,
            'avertissements': []})

    @action(detail=True, methods=['post'], url_path='dupliquer-variante',
            permission_classes=[IsResponsableOrAdmin])
    def dupliquer_variante(self, request, pk=None):
        """QJ15 — Crée 2–3 variantes de taille du devis pour comparaison
        côte-à-côte.

        Chaque variante est un devis brouillon indépendant partageable :
          - même client / lead / mode / TVA / remise que l'original ;
          - lignes clonées avec quantités ajustées selon le facteur de
            dimensionnement (``scale``) passé dans le corps — ou déduit
            automatiquement : ×0.8 (−20 %) / ×1.0 (identique) / ×1.25 (+25 %) ;
          - ``version_parent`` positionné sur l'original (ou son propre parent)
            pour grouper les variantes sans créer une revision :
            ``is_active=True`` sur toutes → ce sont des alternatives, pas des
            remplacements ;
          - aucun changement de statut (règle #4) ;
          - numéros de référence séquentiels via ``create_numbered``.

        Corps optionnel :
          ``scales`` : liste de flottants explicites, ex. [0.8, 1.0, 1.25]
                       (override par requête, max 3 éléments) ;
          ``variante_pct`` : pourcentage p → échelles symétriques
                       [1−p, 1.0, 1+p] (override par requête).

        QG9 — Sans override, le pourcentage vient de
        ``CompanyProfile.variante_pct`` (défaut 20 → échelles 0.8 / 1.0 / 1.2),
        scopé société. Retourne la liste des devis créés.
        """
        source = self.get_object()
        company = source.company
        root = source.version_parent or source

        # QG9 — échelles depuis un pourcentage : override requête ``scales``
        # (rétro-compat) > override requête ``variante_pct`` > config société
        # ``CompanyProfile.variante_pct`` (défaut 20). Symétrique : [1−p, 1, 1+p].
        def _scales_from_pct(pct):
            try:
                p = float(pct) / 100.0
            except (TypeError, ValueError):
                return None
            if not (0 < p < 1):
                return None
            return [round(1 - p, 4), 1.0, round(1 + p, 4)]

        scales = None
        raw_scales = request.data.get('scales')
        if raw_scales:
            try:
                scales = [float(s) for s in raw_scales][:3]
            except (TypeError, ValueError):
                scales = None
        if scales is None:
            pct = request.data.get('variante_pct')
            if pct is None:
                from apps.parametres.models import CompanyProfile
                pct = getattr(CompanyProfile.get(company=company),
                              'variante_pct', 20)
            scales = _scales_from_pct(pct) or [0.8, 1.0, 1.25]
        if not scales:
            scales = [0.8, 1.0, 1.25]

        # Labels FR dérivés de l'échelle : « −X % » / « Standard » / « +X % ».
        def _label_for(scale):
            if abs(scale - 1.0) < 1e-9:
                return 'Standard'
            pct = round((scale - 1.0) * 100)
            sign = '+' if pct > 0 else '−'
            return f'{sign}{abs(pct)} %'

        created = []
        from decimal import Decimal, ROUND_HALF_UP
        # ── QJR407 (S5-1 / S5-2 / S5-4) — LE CLONEUR DU DOMAINE ─────────────
        # Cette boucle réimplémentait ``Devis.objects.create(...)`` et OMETTAIT
        # les sept champs que le cloneur porte depuis QJR146(a) : ``devise``,
        # ``taux_change``, ``echeancier``, ``acompte_pct``, ``acompte_montant``,
        # ``entite``, ``custom_data`` — une variante perdait l'échéancier
        # NÉGOCIÉ et l'acompte de l'original. Elle créait en outre le devis
        # HORS transaction avant de cloner ses lignes (S5-4). La
        # réimplémentation est SUPPRIMÉE (règle permanente 2).
        #
        # L'ÉCHELLE reste propre à cette vue — c'est la seule chose que ce
        # chemin a de particulier, et elle passe par ``remplacements``.
        # QJR84 conservé mot pour mot : ``quantite_manuelle`` NE se recopie
        # PAS — la quantité vient d'être mise à l'échelle, elle n'est plus
        # celle que le commercial avait tapée. QJR202 (purge des clés dérivées
        # + rafraîchissement FORCÉ des études sur la taille RÉELLE de la copie)
        # est porté par le cloneur, pour les quatre chemins à la fois.
        from ..domain.creation_clone import cloner_devis

        for scale in scales:
            variant_note = _label_for(scale)

            def _echelle(ligne, _scale=scale):
                brute = ligne.quantite * Decimal(str(_scale))
                qty = brute.quantize(Decimal('0.01'),
                                     rounding=ROUND_HALF_UP)
                return {'quantite': max(qty, Decimal('0.01')),
                        'quantite_manuelle': False}

            nd = cloner_devis(
                source, user=request.user,
                note=(f'[Variante {variant_note}] '
                      + (source.note or '')).strip(),
                # Groupe : version_parent = racine, version incrémentée,
                # is_active=True (alternative, pas remplacement).
                version=source.version + len(created) + 1,
                version_parent=root,
                remplacements=_echelle)
            created.append(nd)

        return Response(
            [DevisSerializer(v, context={'request': request}).data
             for v in created],
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='dupliquer-variante-gamme',
            permission_classes=[IsResponsableOrAdmin])
    def dupliquer_variante_gamme(self, request, pk=None):
        """GAMME (fondateur 2026-08-18) — crée la SŒUR « gamme » de ce devis.

        Une gamme = une VARIANTE de devis (même mécanique QJ15 : devis frère
        complet groupé par ``version_parent``, composition et prix PROPRES).
        Le libellé est une DONNÉE libre — aucune marque codée en dur : il est
        stocké dans ``etude_params['gamme']`` (aucun changement de modèle).

        Corps :
          ``nom``            : libellé de la gamme créée (défaut « Premium ») ;
          ``nom_source``     : libellé de la gamme du devis courant
                               (défaut « Essentielle », ou celui déjà posé) ;
          ``recommandee``    : ``true`` pour que la NOUVELLE gamme porte le
                               badge « Recommandé » (défaut : la source le
                               garde — le devis porteur est la recommandée).

        Aucun statut n'est touché (règle #4). Renvoie les DEUX devis."""
        from ..services import (
            GAMME_NOMS_DEFAUT, creer_variante_gamme, gamme_info,
        )
        source = self.get_object()
        nom = (str(request.data.get('nom') or '').strip()
               or GAMME_NOMS_DEFAUT[1])
        nom_source = (str(request.data.get('nom_source') or '').strip()
                      or None)
        recommandee = request.data.get('recommandee') in (
            True, 'true', 'True', '1', 1, 'on')
        try:
            soeur = creer_variante_gamme(
                source, nom, user=request.user,
                nom_gamme_source=nom_source, recommandee=recommandee)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        source.refresh_from_db(fields=['etude_params'])
        ctx = {'request': request}
        return Response(
            {
                'source': DevisSerializer(source, context=ctx).data,
                'gamme': DevisSerializer(soeur, context=ctx).data,
                'gammes': [gamme_info(source), gamme_info(soeur)],
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='variantes',
            permission_classes=[IsResponsableOrAdmin])
    def variantes(self, request, pk=None):
        """QJ15 — Liste les variantes liées à ce devis (même version_parent,
        toutes actives). Utilisé par la proposal côte-à-côte."""
        devis = self.get_object()
        root = devis.version_parent or devis
        siblings = (
            Devis.objects
            .filter(company=devis.company, version_parent=root, is_active=True)
            .select_related('client')
            .order_by('version', 'id')
        )
        # An isolated devis (no version_parent and no child variants) is not
        # part of any variant group → return an empty comparison set.
        if devis.version_parent_id is None and not siblings.exists():
            return Response([])
        # Include root itself in the comparison set.
        root_devis = Devis.objects.filter(
            pk=root.pk, company=devis.company, is_active=True).first()
        results = []
        if root_devis:
            results.append(root_devis)
        for s in siblings:
            if s.pk not in {r.pk for r in results}:
                results.append(s)
        return Response(
            [DevisSerializer(v, context={'request': request}).data
             for v in results],
        )

    # api-only: TEMPORAIRE (QJR667) — aucun bouton « Dupliquer » du devis n'appelle
    # encore cette action ; retirer ce marqueur dès que l'écran la câble.
    @action(detail=True, methods=['post'], url_path='dupliquer',
            permission_classes=[IsResponsableOrAdmin])
    def dupliquer(self, request, pk=None):
        """NTUX13 — Duplication INDÉPENDANTE (à ne pas confondre avec
        ``dupliquer-variante``, QJ15, qui groupe ses copies via
        ``version_parent`` pour une comparaison côte-à-côte). Le duplicata
        repart TOUJOURS en ``brouillon`` avec un nouveau numéro, quel que
        soit le statut de la source (jamais une copie de statut ``accepte``/
        ``envoye``), et ne porte aucun lien vers le chantier/BonCommande/
        Facture de l'original (ces objets naissent en aval d'une acceptation
        et ne sont référencés nulle part sur ``Devis`` — rien à copier)."""
        source = self.get_object()
        from ..services import dupliquer_devis
        copie = dupliquer_devis(source, user=request.user)
        return Response(
            DevisSerializer(copie, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='approuver-remise',
            permission_classes=[IsAdminRole])
    def approuver_remise(self, request, pk=None):
        """Approbation admin de la remise (T17) — débloque l'envoi du devis."""
        devis = self.get_object()
        # ADEV33 — la profondeur approuvée est mémorisée avec le booléen.
        from ..domain.tarification import approuver_remise_devis
        approuver_remise_devis(devis, request.user)
        return Response(
            DevisSerializer(devis, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='reviser',
            permission_classes=[IsResponsableOrAdmin])
    def reviser(self, request, pk=None):
        """Révise un devis en une NOUVELLE version (v2, v3…). La nouvelle version
        clone les lignes et repart en brouillon ; l'ancienne devient inactive et
        pointe vers sa remplaçante (lecture seule côté UI). Les liens lead/client
        et le schéma de numérotation sont préservés. Additif, sans perte."""
        # QJR521 — le corps inline (cloner_devis puis save HORS transaction :
        # fourche au double clic, v1 active à côté d'un brouillon orphelin)
        # est remplacé par LE service de domaine verrouillé. QJR407 (cloneur
        # unique, sept champs, lignes QJR224/QJR84) vit dans ``cloner_devis``,
        # appelé par ``reviser_devis``.
        from ..domain.revision import RevisionError, reviser_devis
        old = self.get_object()
        try:
            nd = reviser_devis(old, user=request.user)
        except RevisionError as exc:
            return Response({'detail': exc.message},
                            status=status.HTTP_409_CONFLICT)
        return Response(
            DevisSerializer(nd, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'],
            url_path='historique-configuration',
            permission_classes=[IsResponsableOrAdmin])
    def historique_configuration(self, request, pk=None):
        """NTCPQ20 — Historique FIN des configurations d'un devis brouillon
        ou ENVOYÉ (QJR552 : l'état vu par le client avant une correction après
        envoi, puis l'état corrigé — D-QJR5-1 / D-QJR5-7). Un instantané par
        geste d'enregistrement (QJR550), apparié par identité stable (QJR551).

        GET : la liste des instantanés (id, horodatage, auteur, nombre de
        lignes, contenu). ``?a=<id>&b=<id>`` renvoie EN PLUS le diff des lignes
        entre deux instantanés (ajoutées / retirées / modifiées). Lecture
        seule : ne crée ni ne modifie aucun instantané."""
        from ..services import diff_configurations_devis
        from ..domain.historique_config import contenu_servi
        devis = self.get_object()
        snapshots = list(devis.config_snapshots.select_related('auteur').all())
        payload = {
            'snapshots': [{
                'id': s.id,
                'date': s.date_creation.isoformat(),
                'auteur': (getattr(s.auteur, 'username', None)
                           if s.auteur_id else None),
                'nb_lignes': len((s.contenu or {}).get('lignes') or []),
                # AGNR9 — clés ÉCRAN absentes = null, même pour un
                # instantané stocké avant (normalisation à la lecture).
                'contenu': contenu_servi(s.contenu),
            } for s in snapshots],
        }
        a_id = request.query_params.get('a')
        b_id = request.query_params.get('b')
        if a_id and b_id:
            index = {str(s.id): s for s in snapshots}
            a = index.get(str(a_id))
            b = index.get(str(b_id))
            if a is None or b is None:
                return Response({'detail': 'Instantané introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
            payload['diff'] = diff_configurations_devis(a, b)
        return Response(payload)

    @action(detail=True, methods=['get', 'post'], url_path='lots',
            permission_classes=[IsResponsableOrAdmin])
    def lots(self, request, pk=None):
        """NTCPQ18 — Lots (sites/bâtiments) d'un devis multi-sites.

        GET : sous-total HT par lot + total consolidé (chaîne canonique, donc
        cohérent au centime avec le total du devis). Devis sans lot →
        ``{'lots': [], 'total_consolide': None}`` (comportement mono-site
        inchangé).
        POST : crée un lot — corps ``{nom_lot, adresse_site?, ordre?,
        lignes?: [ligne_id, ...]}`` ; les lignes citées lui sont rattachées."""
        from rest_framework.exceptions import ValidationError
        from ..models import LotDevis
        from ..selectors import lots_totaux
        devis = self.get_object()
        if request.method == 'POST':
            # QJR516 — rattacher des lignes à un lot est une édition de LIGNES.
            if _refus_modifiabilite(devis, 'LIGNES'):
                return _reponse_non_modifiable(devis, 'LIGNES')
            # QJR648 — l'entrée est VALIDÉE avant toute écriture (un « ordre »
            # ou des « lignes » non numériques répondaient 500) et la création
            # + le rattachement tiennent dans UNE transaction : jamais de lot
            # orphelin qu'un nouvel essai refuserait comme « déjà existant ».
            entree = _LotCreationSerializer(data=request.data)
            entree.is_valid(raise_exception=True)
            donnees = entree.validated_data
            nom = donnees['nom_lot']
            if devis.lots.filter(nom_lot=nom).exists():
                raise ValidationError(
                    {'nom_lot': 'Ce lot existe déjà sur ce devis.'})
            with transaction.atomic():
                lot = LotDevis.objects.create(
                    company=devis.company, devis=devis, nom_lot=nom,
                    adresse_site=(donnees.get('adresse_site') or '').strip(),
                    ordre=donnees.get('ordre') or 0)
                ids = donnees.get('lignes') or []
                if ids:
                    # Jamais une ligne d'un autre devis (donc d'une autre
                    # société).
                    devis.lignes.filter(id__in=ids).update(lot=lot)
        resultat = lots_totaux(devis)
        if resultat is None:
            resultat = {'lots': [], 'hors_lot': None,
                        'total_consolide': None}
        return Response(
            resultat,
            status=(status.HTTP_201_CREATED if request.method == 'POST'
                    else status.HTTP_200_OK))

    # api-only: TEMPORAIRE (QJR667) — aucun bouton « Renouveler » du devis n'appelle
    # encore cette action ; retirer ce marqueur dès que l'écran la câble.
    @action(detail=True, methods=['post'], url_path='renouveler',
            permission_classes=[IsResponsableOrAdmin])
    def renouveler(self, request, pk=None):
        """NTCPQ13 — Renouvelle un devis ACCEPTÉ (ou expiré) : nouveau brouillon
        reprenant les lignes actuelles aux PRIX CATALOGUE COURANTS, lié à son
        devis d'origine (``devis_origine``) et numéroté
        (``numero_renouvellement``). Le devis source reste intact — distinct de
        ``reviser`` (qui crée la V+1 d'un devis envoyé, accepté, refusé ou
        expiré — D-QJR5-2 ; un accepté révisé garde son chantier, QJR559)."""
        from ..services import renouveler_devis
        nouveau = renouveler_devis(self.get_object(), user=request.user)
        return Response(
            DevisSerializer(nouveau, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='accepter',
            permission_classes=[HasPermissionOrLegacy('ventes_valider')])
    def accepter(self, request, pk=None):
        """N25 — marque le devis « accepté » à une date choisie, en capturant le
        nom de la personne qui accepte ; l'acceptation est consignée dans le
        chatter du devis et avance le funnel CRM (→ SIGNED). C'est le
        déclencheur explicite de la création d'un chantier."""
        from datetime import date as _date
        from ..services import accept_devis, AcceptError
        devis = self.get_object()
        nom = (request.data.get('nom') or '').strip()
        date_str = (request.data.get('date') or '').strip()
        try:
            date_acc = _date.fromisoformat(date_str) if date_str \
                else timezone.now().date()
        except ValueError:
            return Response({'detail': 'Date invalide (attendu AAAA-MM-JJ).'},
                            status=status.HTTP_400_BAD_REQUEST)
        # CIQ323 — devis papier signé d'un C&I : raison sociale, qualité et
        # ICE FACULTATIFS ici (D-CIQ-11 ne les exige qu'en ligne) ; un ICE
        # saisi est validé par ``validate_ice_ma`` (400 qui nomme le champ).
        from ..domain.cycle_vie import (
            AcceptationBloquee, EntrepriseInvalide,
            lire_entreprise_acceptation,
        )
        try:
            entreprise = lire_entreprise_acceptation(
                devis, request.data.get('entreprise'), obligatoire=False)
        except EntrepriseInvalide as exc:
            return Response({'detail': exc.detail, 'champ': exc.champ},
                            status=status.HTTP_400_BAD_REQUEST)
        # A1 — option retenue (« Sans batterie » / « Avec batterie »). La
        # résolution (deux options → choix explicite obligatoire ; mono-option
        # → déduit du scénario) et le tampon d'acceptation passent désormais
        # par le service unique accept_devis (réutilisé par la proposition web
        # tokenisée Q7), préservant 1:1 la chaîne bon-commande/facture (règle #4).
        option = (request.data.get('option') or '').strip()
        try:
            # QJR135 / ES4 — ON SÉRIALISE L'INSTANCE QUE LE SERVICE A ÉCRITE.
            # ``accept_devis`` REBIND son nom local sur la relecture VERROUILLÉE
            # (``select_for_update().get(...)``) : l'objet de l'appelant reste
            # celui d'AVANT, donc ``statut`` y valait encore « envoyé »,
            # ``option_acceptee`` '' et ``accepte_par_nom`` '' juste après une
            # acceptation réussie. On reprend donc sa VALEUR DE RETOUR — jamais
            # un second ``refresh_from_db`` qui redemanderait ce que le service
            # a déjà en main.
            # ADEV13 — blocage crédit (XFAC28) et avertissement de vente
            # bloquant (ZSAL9) : la garde vit DANS ``accept_devis`` (une seule
            # règle pour les trois portes) ; cette vue ne fait que transmettre
            # les drapeaux d'override et traduire le refus en 403 détaillé.
            devis = accept_devis(
                devis=devis, user=request.user, nom=nom,
                date_acceptation=date_acc, option=option,
                idempotent_reaccept=False, entreprise=entreprise,
                override_credit=bool(request.data.get('override_credit')),
                override_avertissement=bool(
                    request.data.get('override_avertissement')))
        except AcceptationBloquee as exc:
            if exc.nature == 'credit_hold':
                return Response(
                    {'detail': (
                        'Client en blocage crédit : '
                        f'{exc.motif}. Un responsable ou un administrateur '
                        'peut passer outre avec `override_credit: true`.'),
                     'credit_hold': True},
                    status=status.HTTP_403_FORBIDDEN)
            return Response(
                {'detail': (
                    f'Avertissement de vente bloquant : {exc.motif}. '
                    'Un responsable ou un administrateur peut passer outre '
                    'avec `override_avertissement: true`.'),
                 'sale_warning': True},
                status=status.HTTP_403_FORBIDDEN)
        except AcceptError as exc:
            return Response(
                {'detail': exc.message},
                status=(status.HTTP_409_CONFLICT if exc.conflict
                        else status.HTTP_400_BAD_REQUEST))
        return Response(
            DevisSerializer(devis, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='refuser',
            permission_classes=[HasPermissionOrLegacy('ventes_valider')])
    def refuser(self, request, pk=None):
        """FG44 — marque le devis « refusé » avec date + motif + chatter.

        Symétrique à « accepter » : consigne le refus dans l'historique du devis.
        Body optionnel :
          - ``motif``  : raison du refus (libre, max 255 caractères)
          - ``date``   : date ISO AAAA-MM-JJ (défaut = aujourd'hui)
          - ``marquer_lead_perdu`` : true → émet devis_refused → CRM marque
                                     le lead associé perdu (si lead_id présent)
        """
        from datetime import date as _date
        from .. import activity
        from core.events import devis_refused

        devis = self.get_object()
        # ADEV7 — une version remplacée par une révision ne se refuse plus :
        # 409 ``version_remplacee`` (contrat devis_refuser.json), aucun
        # ``devis_refused`` (le lead et la cadence de la V2 restent intacts).
        from ..domain.modifiabilite import (
            REFUSER, corps_version_remplacee, geste_cycle_permis)
        if not geste_cycle_permis(devis, REFUSER)[0]:
            return Response(corps_version_remplacee(devis),
                            status=status.HTTP_409_CONFLICT)
        if devis.statut not in (
            Devis.Statut.BROUILLON, Devis.Statut.ENVOYE,
        ):
            return Response(
                {'detail': (
                    'Seul un devis en cours (brouillon ou envoyé) peut être '
                    f'refusé ; statut actuel : '
                    f'« {devis.get_statut_display()} ».'
                ), 'code': 'statut'},
                status=status.HTTP_409_CONFLICT,
            )
        # ADEV44 (contrat devis_refuser.json) — ``motif`` = le NOM d'un
        # MotifPerte ACTIF de la société, validé par le CRM (sans casse) et
        # rangé sous son libellé exact ; un nom inconnu/archivé ⇒ 400 et le
        # devis reste en l'état. Un refus SANS motif reste accepté tant que la
        # question fondateur AGRM37 (motif obligatoire ?) est ouverte.
        motif_saisi = (request.data.get('motif') or '').strip()
        motif = ''
        if motif_saisi:
            from apps.crm.services import motif_refus_valide
            motif = motif_refus_valide(devis.company, motif_saisi) or ''
            if not motif:
                return Response(
                    {'motif': ['Choisissez un motif de refus de la liste.']},
                    status=status.HTTP_400_BAD_REQUEST)
        motif = motif[:255]
        note = (request.data.get('note') or '').strip()[:255]
        date_str = (request.data.get('date') or '').strip()
        try:
            date_ref = _date.fromisoformat(date_str) if date_str \
                else timezone.now().date()
        except ValueError:
            return Response({'detail': 'Date invalide (attendu AAAA-MM-JJ).'},
                            status=status.HTTP_400_BAD_REQUEST)
        marquer_lead_perdu = bool(
            request.data.get('marquer_lead_perdu', False))

        devis.statut = Devis.Statut.REFUSE
        devis.date_refus = date_ref
        devis.motif_refus = motif
        devis.save(update_fields=['statut', 'date_refus', 'motif_refus'])
        activity.log_devis_refusal(devis, request.user, motif, date_ref,
                                   note=note)

        # M6 — événement découplé : ventes émet, crm réagit
        # (marque le lead perdu si demandé et lead_id présent).
        devis_refused.send(
            sender=Devis, devis=devis, user=request.user,
            motif_refus=motif,
            marquer_lead_perdu=marquer_lead_perdu,
        )
        return Response(
            DevisSerializer(devis, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Chatter du devis (notes + acceptation)."""
        devis = self.get_object()
        return Response(
            DevisActivitySerializer(devis.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin])
    def noter(self, request, pk=None):
        """Ajoute une note manuelle au chatter du devis."""
        from .. import activity
        devis = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'detail': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = activity.log_devis_note(devis, request.user, body)
        return Response(DevisActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)
