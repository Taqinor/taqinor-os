"""XPLT6 — alertes de seuil sur KPI AGRÉGÉS configurables.

CRUD company-scopé (`KpiAlerteViewSet`) + évaluation (job Beat quotidien,
`evaluate_all_kpi_alertes`) qui calcule chaque KPI du catalogue FERMÉ à
travers les selectors reporting EXISTANTS, compare au seuil configuré
et notifie une seule fois par franchissement (dédup via `deja_notifie`).

Catalogue fermé (``KpiAlerte.Kpi``) :
  * ``encours_echu_total``   — Σ des tranches d'âge >30 j de la balance âgée
                                (``apps.reporting.balance_export.balance_agee_rows``,
                                même app).
  * ``valeur_stock_totale``  — valorisation vente du stock
                                (même agrégat que ``apps.reporting.reports.
                                stock_report``).
  * ``uptime_moyen_12_mois`` / ``jours_depuis_dernier_drill_reussi`` /
    ``quota_le_plus_charge_pct`` (NTOBS31) — les trois KPI « Fiabilité »
                                cross-module, dérivés de ``core.sla.
                                SlaSnapshot``, ``core.models.BackupRun`` et
                                ``core.usage_limits.usage_summary`` (rien de
                                neuf : ce module se contente de les brancher
                                au catalogue fermé, comme les autres).
"""
from decimal import Decimal

from rest_framework import serializers, viewsets

from authentication.permissions import IsResponsableOrAdmin
from core.mixins import TenantMixin

from .models import KpiAlerte


class KpiAlerteSerializer(serializers.ModelSerializer):
    kpi_label = serializers.CharField(source='get_kpi_display', read_only=True)
    operateur_label = serializers.CharField(
        source='get_operateur_display', read_only=True)
    # NTDATA13 — clé lisible de la métrique ciblée (vide pour une alerte
    # « catalogue »), pour que l'écran n'ait pas à re-interroger semantic.
    metric_cle = serializers.CharField(
        source='metric_definition.cle', read_only=True, default='')
    # NTDATA41 — libellé FR du mode de détection (seuil / variation / anomalie).
    mode_detection_label = serializers.CharField(
        source='get_mode_detection_display', read_only=True)

    class Meta:
        model = KpiAlerte
        # company posée côté serveur — jamais lue du corps.
        fields = [
            'id', 'nom', 'source', 'kpi', 'kpi_label', 'metric_definition',
            'metric_cle', 'mode_detection', 'mode_detection_label',
            'operateur', 'operateur_label',
            'seuil', 'destinataire_role', 'destinataires_utilisateurs',
            'actif', 'deja_notifie', 'derniere_valeur',
            'derniere_evaluation_le', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'kpi_label', 'metric_cle', 'mode_detection_label',
            'operateur_label',
            'deja_notifie', 'derniere_valeur', 'derniere_evaluation_le',
            'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        """NTDATA13 — la même règle que ``KpiAlerte.clean()``, rendue au
        CHAMP fautif (le front sait alors lequel surligner).

        La métrique est cherchée DANS LA SOCIÉTÉ de l'appelant : le corps de
        requête ne peut pas faire pointer une alerte vers le tenant voisin.
        """
        instance = getattr(self, 'instance', None)
        source = attrs.get('source', getattr(instance, 'source', None)
                           or KpiAlerte.Source.CATALOGUE)
        metrique = attrs.get(
            'metric_definition', getattr(instance, 'metric_definition', None))
        kpi = attrs.get('kpi', getattr(instance, 'kpi', ''))
        if source == KpiAlerte.Source.METRIQUE:
            if metrique is None:
                raise serializers.ValidationError({
                    'metric_definition':
                        'Choisissez la métrique nommée à surveiller.'})
            requete = self.context.get('request')
            company = getattr(getattr(requete, 'user', None), 'company', None)
            if company is not None and metrique.company_id != company.id:
                raise serializers.ValidationError({
                    'metric_definition':
                        "Cette métrique appartient à une autre société."})
        elif not kpi:
            raise serializers.ValidationError({
                'kpi': 'Choisissez le KPI à surveiller.'})
        # NTDATA41 — même règle que `KpiAlerte.clean()`, portée au CHAMP.
        mode = attrs.get('mode_detection',
                         getattr(instance, 'mode_detection', None)
                         or KpiAlerte.ModeDetection.SEUIL)
        if (mode != KpiAlerte.ModeDetection.SEUIL
                and source != KpiAlerte.Source.METRIQUE):
            raise serializers.ValidationError({
                'mode_detection':
                    'La détection « %s » compare une trajectoire : elle exige '
                    'une métrique nommée (les KPI du catalogue ne rendent que '
                    'leur valeur du jour).'
                    % dict(KpiAlerte.ModeDetection.choices)[mode]})
        return attrs


class KpiAlerteViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des alertes KPI, bornées à la société (réservé admin/responsable
    par cohérence avec les autres réglages de Paramètres)."""
    serializer_class = KpiAlerteSerializer
    permission_classes = [IsResponsableOrAdmin]
    queryset = KpiAlerte.objects.all()


# ── Évaluation des KPI (lecture via selectors EXISTANTS uniquement) ─────────

def _compute_encours_echu_total(company, user):
    """Σ des tranches >30 j de la balance âgée (même app — pas de selector
    cross-app requis)."""
    from .balance_export import balance_agee_rows
    rows = balance_agee_rows(user)
    if not rows:
        return Decimal('0')
    # La dernière ligne est le pied de page « Total » (b31_60+b61_90+b90_plus).
    total_row = rows[-1]
    if total_row[0] != 'Total':
        return Decimal('0')
    return Decimal(str(total_row[2])) + Decimal(str(total_row[3])) \
        + Decimal(str(total_row[4]))


def _compute_valeur_stock_totale(company):
    """Valorisation vente du stock — même agrégat que
    ``apps.reporting.reports.stock_report`` (même app, pas de selector requis)."""
    from django.db.models import Sum, F, DecimalField
    from django.db.models.functions import Coalesce
    from apps.stock.models import Produit

    qs = Produit.objects.filter(company=company, is_archived=False)
    dec = DecimalField()
    sum_vente = Coalesce(
        Sum(F('prix_vente') * F('quantite_stock'), output_field=dec),
        Decimal('0'))
    return qs.aggregate(t=sum_vente)['t'] or Decimal('0')


def _compute_i18n(company, cle):
    """NTI18N52 — une des deux valeurs du sélecteur dédié
    ``apps.reporting.i18n_kpi`` (import paresseux, même patron que les autres).

    ``None`` = non mesurable (KPI ignoré, tuile masquée), jamais un 0 trompeur :
    ``couverture_i18n_pct`` vaut ``None`` tant qu'aucun instantané NTI18N39
    n'existe, et ``documents_non_fr_pct`` vaut ``None`` tant que la langue d'un
    PDF généré n'est journalisée nulle part (voir ``i18n_kpi.py``).
    """
    from .i18n_kpi import kpis_i18n
    valeur = kpis_i18n(company).get(cle)
    if valeur is None:
        return None
    return Decimal(str(valeur))


# ── NTOBS31 — 3 KPI « Fiabilité » cross-module ──────────────────────────────
#
# Chacun délègue à une source DÉJÀ BÂTIE par le groupe NTOBS (aucun nouveau
# moteur) : ``core.sla.SlaSnapshot`` (NTOBS3, rapport SLA mensuel),
# ``core.models.BackupRun`` (YOPSB1/2, dump + drill de restauration réels),
# ``core.usage_limits.usage_summary`` (NTOBS8, quotas par ressource). ``core``
# reste importable depuis ``reporting`` (couche de fondation, cf. CLAUDE.md) —
# import FONCTION-LOCAL, même patron que les autres calculateurs de ce fichier.

def _compute_uptime_moyen_12_mois(company):
    """Moyenne (%) des ``SlaSnapshot.uptime_pct`` de la société sur les 12
    derniers mois. ``None`` (jamais un chiffre inventé) tant qu'aucun
    snapshot n'existe pour la période."""
    from django.db.models import Avg

    from core.sla import SlaSnapshot, premier_du_mois

    # Arithmétique directe plutôt que 12 appels chaînés à `mois_precedent` :
    # celui-ci relit son résultat via `premier_du_mois`, qui appelle `.date()`
    # en supposant TOUJOURS un `datetime` — or `premier_du_mois()` renvoie déjà
    # un `datetime.date` (sans `.date()`), donc le chaînage lève
    # ``AttributeError: 'datetime.date' object has no attribute 'date'`` dès
    # le premier tour. Un seul appel non chaîné à `premier_du_mois()` évite le
    # problème.
    borne = premier_du_mois()
    annee, mois = borne.year, borne.month - 12
    while mois <= 0:
        mois += 12
        annee -= 1
    borne = borne.replace(year=annee, month=mois)
    moyenne = SlaSnapshot.objects.filter(
        company=company, periode__gte=borne,
    ).aggregate(m=Avg('uptime_pct'))['m']
    return Decimal(str(moyenne)) if moyenne is not None else None


def _compute_jours_depuis_dernier_drill_reussi(company):
    """Jours écoulés depuis le dernier ``BackupRun`` de type
    ``restore_drill`` TERMINÉ. Le drill (YOPSB2) est un contrôle SYSTÈME
    (``company`` nul — toute l'instance, pas une société), donc la valeur est
    la même pour toutes les sociétés — cohérent avec le reste du catalogue où
    un KPI transverse n'a pas besoin d'être différencié par société pour être
    surveillable par société. ``None`` tant qu'aucun drill réussi n'a jamais
    été enregistré (jamais un 0 trompeur)."""
    from django.utils import timezone

    from core.models import BackupRun

    dernier = (
        BackupRun.objects.filter(
            kind=BackupRun.KIND_RESTORE_DRILL,
            statut=BackupRun.STATUT_TERMINE,
            purge_is_deleted=False,
        )
        .exclude(termine_le__isnull=True)
        .order_by('-termine_le')
        .first()
    )
    if dernier is None:
        return None
    return Decimal((timezone.now() - dernier.termine_le).days)


def _compute_quota_le_plus_charge_pct(company):
    """Le ratio (%) le plus élevé parmi les ressources à limite CONNUE de
    ``usage_summary`` (NTOBS8) — une ressource illimitée (``limite`` vide ou
    nulle) n'entre jamais dans le calcul. ``None`` s'il n'existe aucune
    ressource limitée pour cette société (jamais un 0 trompeur)."""
    from core.usage_limits import usage_summary

    ratios = [
        Decimal(str(ressource['utilise'])) * 100 / Decimal(str(ressource['limite']))
        for ressource in usage_summary(company).get('ressources', [])
        if ressource.get('limite')
    ]
    return max(ratios) if ratios else None


# SOL14 — module PROPRIÉTAIRE d'un KPI, quand il en a un. Un KPI dont le
# module est éteint pour la société DÉGRADE PROPREMENT : valeur `None`, donc
# aucun franchissement, aucune notification, et la tuile disparaît de l'écran
# (l'UI n'affiche pas un KPI sans valeur) — au lieu d'appeler un sélecteur
# d'app coupée et de rendre un 0 trompeur. Les KPI transverses (encours,
# valeur de stock) n'ont pas d'entrée : ils ne sont jamais masqués.
KPI_MODULE = {}


def kpi_disponible(company, kpi):
    """Vrai si ce KPI est calculable pour cette société (module actif)."""
    module = KPI_MODULE.get(kpi)
    if not module:
        return True
    from core.feature_flags import module_actif
    try:
        return module_actif(company, module)
    except Exception:  # pragma: no cover - jamais masquer sur une erreur
        return True


def kpis_disponibles(company):
    """Clés de KPI proposables à cette société (pour l'UI et les tests)."""
    return [
        valeur for valeur, _libelle in KpiAlerte.Kpi.choices
        if kpi_disponible(company, valeur)
    ]


_KPI_COMPUTERS = {
    KpiAlerte.Kpi.ENCOURS_ECHU_TOTAL: lambda company, user:
        _compute_encours_echu_total(company, user),
    KpiAlerte.Kpi.VALEUR_STOCK_TOTALE: lambda company, user:
        _compute_valeur_stock_totale(company),
    # NTI18N52 — KPI i18n : mesures du PRODUIT (couverture de l'interface) et
    # des documents produits, indépendantes du `user` et d'un module métier
    # (aucune entrée dans KPI_MODULE : ils ne sont jamais masqués par une
    # édition, ils dégradent d'eux-mêmes en `None` quand la mesure manque).
    KpiAlerte.Kpi.COUVERTURE_I18N_PCT: lambda company, user:
        _compute_i18n(company, 'couverture_i18n_pct'),
    KpiAlerte.Kpi.DOCUMENTS_NON_FR_PCT: lambda company, user:
        _compute_i18n(company, 'documents_non_fr_pct'),
    # NTOBS31 — 3 KPI « Fiabilité » (aucun des trois ne dépend du `user` : ce
    # sont des agrégats système/société, jamais des données à confidentialité
    # variable comme le juridique). Aucune entrée dans `KPI_MODULE` : ces KPI
    # ne sont jamais masqués par un module métier éteint.
    KpiAlerte.Kpi.UPTIME_MOYEN_12_MOIS: lambda company, user:
        _compute_uptime_moyen_12_mois(company),
    KpiAlerte.Kpi.JOURS_DEPUIS_DERNIER_DRILL_REUSSI: lambda company, user:
        _compute_jours_depuis_dernier_drill_reussi(company),
    KpiAlerte.Kpi.QUOTA_LE_PLUS_CHARGE_PCT: lambda company, user:
        _compute_quota_le_plus_charge_pct(company),
}


def _compute_metrique(alerte, user):
    """NTDATA13 — la valeur d'une alerte de source « métrique ».

    Passe par le résolveur de la couche sémantique (NTDATA8, import
    FONCTION-LOCAL : `reporting` n'importe `semantic` qu'à l'appel). La
    métrique est résolue SANS regroupement — un seuil compare un nombre, pas
    une série — et le lecteur transmis est l'utilisateur représentatif de la
    société, donc un champ sous permission reste masqué (AUD801) et la
    métrique rend alors VIDE plutôt que de divulguer.

    Rend `None` (aucun franchissement) quand la métrique est introuvable,
    inactive ou inexécutable : une alerte ne doit jamais se déclencher sur un
    chiffre qui n'existe pas.
    """
    from apps.semantic import services as semantic_services

    try:
        valeur = semantic_services.resolve_metric_valeur(
            alerte.company, user, alerte.metric_definition.cle)
    except (semantic_services.MetriqueInconnue,
            semantic_services.MetriqueNonResolvable):
        return None
    if valeur is None:
        return None
    return Decimal(str(valeur))


# ── NTDATA41 — détection sur la TRAJECTOIRE (variation / anomalie) ─────────
#
# Le mode `seuil` (défaut, et toutes les alertes existantes) compare la VALEUR
# du jour. Les deux modes ajoutés comparent une DÉRIVÉE de la métrique :
#
#   * `variation` — le Δ % entre les DEUX DERNIÈRES PÉRIODES COMPLÈTES. La
#     période EN COURS est exclue : le 3 du mois elle contient trois jours et
#     afficherait mécaniquement une chute de ~90 %, donc une alerte tous les
#     débuts de mois ;
#   * `anomalie` — le z-score du DERNIER point face à sa propre série, via
#     `core.anomaly.scan_for_outliers` (le scorer EXISTANT, jamais une seconde
#     statistique). Le `seuil` est alors le nombre d'écarts-types.
#
# UNE DÉRIVÉE NON CALCULABLE NE DÉCLENCHE RIEN. Moins de deux périodes, une
# période précédente à zéro (« +∞ % » n'est pas un nombre), une série trop
# courte pour un z-score : la valeur rendue est `None`, donc aucun
# franchissement — jamais un 0 qui ferait passer une absence de mesure pour une
# stabilité.


def _compute_variation(alerte, user):
    """Δ % de la métrique entre les deux dernières périodes complètes."""
    from apps.semantic import selectors as semantic_selectors

    pourcentage, _courante, _precedente = semantic_selectors.variation_pct(
        alerte.company, user, alerte.metric_definition.cle)
    if pourcentage is None:
        return None
    return Decimal(str(round(pourcentage, 2)))


def _compute_anomalie(alerte, user):
    """|z-score| du DERNIER point de la série de la métrique.

    Rend `None` — donc aucun franchissement — quand la série est trop courte
    ou plate pour que `core.anomaly` se prononce : c'est exactement le
    garde-fou anti-faux-positif du scorer, on ne le contourne pas.
    """
    from apps.semantic import selectors as semantic_selectors
    from core.anomaly import scan_for_outliers

    points = semantic_selectors.periodes_completes(
        semantic_selectors.serie_temporelle(
            alerte.company, user, alerte.metric_definition.cle))
    if len(points) < 2:
        return None
    series = [{'id': index, 'value': point['valeur']}
              for index, point in enumerate(points)]
    dernier = len(points) - 1
    # `z_threshold=0` : on veut le SCORE du dernier point, pas le verdict du
    # scorer — c'est le `seuil` de l'alerte qui tranche, pas un seuil codé ici.
    candidats = scan_for_outliers(series, z_threshold=0.0, min_points=2)
    for candidat in candidats:
        if candidat.subject_id == str(dernier):
            return Decimal(str(round(abs(candidat.score), 4)))
    return None


def _resolve_representative_user(company):
    """Un utilisateur actif de la société pour porter le scope des selectors
    qui exigent un ``user`` (ex. ``balance_agee_rows``). Préfère un
    admin/responsable actif ; dégrade proprement à None (KPI ignoré) si
    aucun utilisateur exploitable."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return (User.objects
            .filter(company=company, is_active=True)
            .order_by('id')
            .first())


def evaluate_kpi_alerte(alerte, *, now=None):
    """XPLT6 — évalue UNE alerte : calcule le KPI, compare au seuil, notifie
    au FRANCHISSEMENT (jamais en répétition tant que ``deja_notifie`` est
    vrai), et RÉ-ARME la dédup dès que la valeur repasse du bon côté.

    Renvoie ``(valeur, franchi, notifie)``. Ne lève jamais : une source
    manquante dégrade à ``valeur=None`` (jamais de franchissement)."""
    from django.utils import timezone

    # NTDATA13 — deux SOURCES possibles. `catalogue` (le défaut, et toutes
    # les alertes existantes) passe par le catalogue fermé ci-dessus ;
    # `metrique` résout N'IMPORTE QUELLE MetricDefinition de la société via la
    # couche sémantique (NTDATA8). Les deux chemins partagent ensuite
    # EXACTEMENT la même comparaison, la même dédup et la même notification.
    est_metrique = alerte.source == KpiAlerte.Source.METRIQUE
    computer = None
    if not est_metrique:
        computer = _KPI_COMPUTERS.get(alerte.kpi)
        if computer is None:
            return None, False, False
        # SOL14 — module du KPI éteint pour cette société : dégradation propre
        # (aucune valeur, donc aucun franchissement ni notification, et la
        # tuile disparaît). On n'appelle SURTOUT pas le sélecteur d'une app
        # coupée.
        if not kpi_disponible(alerte.company, alerte.kpi):
            return None, False, False
    elif alerte.metric_definition_id is None:
        # Définition supprimée : l'alerte survit (SET_NULL) mais n'a plus rien
        # à mesurer — aucune valeur, donc aucun franchissement.
        return None, False, False

    user = _resolve_representative_user(alerte.company)
    if user is None:
        return None, False, False

    try:
        # NTDATA41 — le MODE décide de ce qui est comparé au seuil : la valeur
        # du jour (défaut historique), sa variation, ou son écart à l'habitude.
        mode = getattr(alerte, 'mode_detection', KpiAlerte.ModeDetection.SEUIL)
        if mode == KpiAlerte.ModeDetection.VARIATION and est_metrique:
            valeur = _compute_variation(alerte, user)
        elif mode == KpiAlerte.ModeDetection.ANOMALIE and est_metrique:
            valeur = _compute_anomalie(alerte, user)
        elif mode != KpiAlerte.ModeDetection.SEUIL:
            # Mode de trajectoire sur une source SANS historique : le modèle
            # l'interdit à la création ; une alerte ancienne mal formée ne doit
            # pas pour autant se déclencher sur un chiffre inventé.
            valeur = None
        elif est_metrique:
            valeur = _compute_metrique(alerte, user)
        else:
            valeur = computer(alerte.company, user)
    except Exception:  # pragma: no cover - dégradation défensive
        valeur = None

    franchi = alerte.est_franchi(valeur)
    notifie = False

    if franchi and not alerte.deja_notifie:
        _notify_kpi_alerte(alerte, valeur)
        alerte.deja_notifie = True
        notifie = True
    elif not franchi and alerte.deja_notifie:
        # Repassé sous (ou au-dessus) le seuil → ré-arme pour la prochaine
        # notification au prochain re-franchissement.
        alerte.deja_notifie = False

    alerte.derniere_valeur = valeur
    alerte.derniere_evaluation_le = timezone.now() if now is None else now
    alerte.save(update_fields=[
        'deja_notifie', 'derniere_valeur', 'derniere_evaluation_le'])
    return valeur, franchi, notifie


def _libelle_surveille(alerte):
    """Ce que l'alerte surveille, en clair — jamais une chaîne vide.

    Source « catalogue » : le libellé du KPI. Source « métrique » : le libellé
    de la définition (ou sa clé). Repli : le nom donné à l'alerte.
    """
    if alerte.source == KpiAlerte.Source.METRIQUE:
        definition = alerte.metric_definition
        if definition is not None:
            return definition.libelle or definition.cle
        return alerte.nom or 'métrique supprimée'
    return alerte.get_kpi_display() or alerte.nom or 'KPI'


def _notify_kpi_alerte(alerte, valeur):
    """Notifie les destinataires configurés (rôle legacy + utilisateurs
    précis). Réutilise ``apps.notifications.services.notify`` — best-effort,
    ne lève jamais."""
    from apps.notifications.services import notify
    from apps.notifications.models import EventType

    # NTDATA41 — le message NOMME ce qui est surveillé et ce qui a été comparé.
    # Une alerte de source « métrique » n'a pas de `kpi` : `get_kpi_display()`
    # y rendait une chaîne VIDE (« Alerte KPI :  »), et les deux modes de
    # trajectoire sont métrique-seulement — toutes leurs notifications auraient
    # été anonymes.
    sujet = _libelle_surveille(alerte)
    mode = getattr(alerte, 'mode_detection', KpiAlerte.ModeDetection.SEUIL)
    if mode == KpiAlerte.ModeDetection.VARIATION:
        mesure = (f'sa variation vs la période précédente est de {valeur} % '
                  f'(seuil : {alerte.get_operateur_display()} '
                  f'{alerte.seuil} %)')
    elif mode == KpiAlerte.ModeDetection.ANOMALIE:
        mesure = (f"son écart à l'habitude est de {valeur} écart(s)-type(s) "
                  f'(seuil : {alerte.get_operateur_display()} '
                  f'{alerte.seuil})')
    else:
        mesure = (f'valeur actuelle {valeur} (seuil : '
                  f'{alerte.get_operateur_display()} {alerte.seuil})')
    title = f'Alerte KPI : {sujet}'
    body = f'{sujet} — {mesure}.'

    recipients = list(alerte.destinataires_utilisateurs.all())
    if alerte.destinataire_role:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recipients += list(User.objects.filter(
            company=alerte.company, is_active=True,
            role_legacy=alerte.destinataire_role))

    seen_ids = set()
    for user in recipients:
        if user.id in seen_ids:
            continue
        seen_ids.add(user.id)
        try:
            notify(user, EventType.DIGEST, title, body=body,
                   company=alerte.company)
        except Exception:  # pragma: no cover - défensif, best-effort
            continue


def evaluate_all_kpi_alertes(now=None):
    """XPLT6 — évalue toutes les alertes ACTIVES de toutes les sociétés.

    Appelée par le job Beat quotidien. Chaque alerte est isolée (une erreur
    n'interrompt jamais les suivantes)."""
    results = []
    for alerte in KpiAlerte.objects.filter(actif=True).select_related(
            'company', 'metric_definition'):
        try:
            valeur, franchi, notifie = evaluate_kpi_alerte(alerte, now=now)
            results.append({
                'alerte_id': alerte.id, 'valeur': valeur,
                'franchi': franchi, 'notifie': notifie,
            })
        except Exception:  # pragma: no cover - défensif
            continue
    return results


try:
    from celery import shared_task

    @shared_task(name='reporting.evaluate_kpi_alertes')
    def evaluate_kpi_alertes_task():
        """XPLT6 — tâche Beat quotidienne d'évaluation des alertes KPI."""
        evaluate_all_kpi_alertes()
except ImportError:  # pragma: no cover - celery absent en environnement de test
    pass
