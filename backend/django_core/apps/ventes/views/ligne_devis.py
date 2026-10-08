from rest_framework import viewsets
from ..models import LigneDevis
from ..serializers import LigneDevisSerializer
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
from core.viewsets import CompanyScopedModelViewSet  # ARC5

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


def _retarifer_forfaits(devis):
    """QJR220 — les FORFAITS AU PANNEAU suivent le compte réellement écrit.

    ``retarifer_forfaits_par_panneau`` (QJR83) n'avait qu'UN appelant :
    ``lignes.remplacer_lignes``. Ce viewset change pourtant lui aussi le
    compte de panneaux d'un devis existant (ajouter, modifier ou retirer une
    ligne panneau), et la pose / les accessoires / le tableau restaient au
    barème de l'ANCIEN compte — de l'argent faux sur un document client.

    Best-effort et sans avertissement remonté, exactement comme le
    rafraîchissement des études juste à côté : une re-tarification ratée ne
    doit jamais annuler l'écriture de ligne que l'utilisateur vient de faire.
    Les abstentions D12 (``prix_manuel``, forfait commun divergent) sont
    celles de la fonction elle-même — ce chemin n'en ajoute aucune.
    """
    from ..domain.lignes import retarifer_forfaits_par_panneau

    try:
        retarifer_forfaits_par_panneau(devis)
    except Exception:  # noqa: BLE001 — best-effort, comme les études
        pass


def _rafraichir(devis):
    """QJR554 — le mode RAFRAICHIR du pipeline après une écriture de ligne :
    les quatre études (best-effort) PUIS les caches du devis (kWc depuis les
    lignes, marge interne) — sans lui, ``puissance_kwc`` et ``marge_snapshot``
    restaient ceux d'avant la ligne ajoutée / modifiée / retirée."""
    from ..domain.pipeline import (
        MODE_RAFRAICHIR, ORIGINE_ECRAN, IntentionDevis, appliquer)
    appliquer(devis, IntentionDevis(
        origine=ORIGINE_ECRAN, mode=MODE_RAFRAICHIR, company=devis.company))


def _instantane(devis, user):
    """QJR550 — UN instantané de configuration par geste de ligne, avec son
    auteur (``request.user``) ; remplace le signal ``post_save`` par ligne."""
    from ..domain.historique_config import instantane_de_geste
    instantane_de_geste(devis, user=user)


# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class LigneDevisViewSet(CompanyScopedModelViewSet):
    # ARC5 — sweep TenantMixin : base transverse unique. LigneDevis N'A PAS de
    # champ `company` (elle est scopée via son parent `devis__company`), donc la
    # base TenantMixin ne convient PAS telle quelle : son get_queryset
    # (`qs.filter(company=…)`) lèverait un FieldError, et son perform_create
    # (`save(company=…)`) écrirait un champ inexistant. On SURCHARGE donc
    # INTÉGRALEMENT get_queryset (scoping via devis__company, en partant du
    # queryset ModelViewSet non filtré — PAS de super() TenantMixin) ainsi que
    # perform_create/perform_update. Comportement et matrice 401/403/404 (404
    # cross-tenant) STRICTEMENT inchangés ; l'héritage sert la classification au
    # socle (règle #4 : aucun statut/sérialisation touché).
    queryset = LigneDevis.objects.select_related('devis', 'produit').all()
    serializer_class = LigneDevisSerializer

    def get_queryset(self):
        # NE PAS passer par super() (TenantMixin filtrerait sur un champ
        # `company` absent de LigneDevis) : on part du queryset ModelViewSet brut.
        qs = viewsets.ModelViewSet.get_queryset(self)
        user = self.request.user
        if user.company_id:
            # ADEV21 (C-ADEV-025) — même portée équipe que ``DevisViewSet``
            # (``owner_fields=['created_by']`` du devis parent) : une ligne
            # d'un devis hors portée est introuvable (404), jamais modifiable.
            from core.scoping import scope_queryset
            return scope_queryset(qs.filter(devis__company=user.company),
                                  user, ['devis__created_by'])
        if user.is_superuser:
            return qs
        return qs.none()

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['destroy']:
            # Retirer une LIGNE fait partie de l'édition normale d'un
            # brouillon (le générateur remplace les lignes) — même niveau
            # que les autres écritures. Supprimer le DEVIS entier reste admin.
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def _check_tenant(self, serializer):
        """ERR7 — le devis ciblé par la ligne doit appartenir à la société de
        l'utilisateur (refuse l'injection IDOR d'une ligne sur le document d'un
        autre tenant). Superuser sans société : non borné."""
        from rest_framework.exceptions import ValidationError
        user = self.request.user
        devis = serializer.validated_data.get('devis')
        if devis is not None and user.company_id \
                and devis.company_id != user.company_id:
            raise ValidationError({'devis': 'Devis inconnu.'})

    def _check_devis_not_frozen(self, devis):
        """YDOCF2 — les lignes d'un devis figé (accepté/refusé/expiré) ne sont
        plus librement éditables : le BC/Facture/BoM chantier aval sont déjà
        générés depuis le contenu figé. `reviser` (clone en V+1) reste la
        voie de modification."""
        from rest_framework.exceptions import ValidationError
        # QJR516 — le prédicat UNIQUE (domain/modifiabilite, geste LIGNES) ;
        # 400 {'devis'} et son texte CONSERVÉS pour un devis clos ; un devis
        # remplacé/archivé reçoit la raison du prédicat.
        from ..domain.modifiabilite import LIGNES, verdict
        if devis is None:
            return
        v = verdict(devis, LIGNES)
        if not v['modifiable']:
            raise ValidationError({'devis': (
                'Devis figé — révisez-le (reviser) pour le modifier.'
                if devis.is_active else v['raison_non_modifiable'])})

    def _check_devis_inchange(self, serializer):
        """QJR516 — une ligne ne CHANGE jamais de devis : ``PATCH {devis}``
        déplaçait une ligne d'un devis vers un autre (serializer
        ``__all__``), hors de toute garde du devis d'arrivée."""
        from rest_framework.exceptions import ValidationError
        cible = serializer.validated_data.get('devis')
        if cible is not None and cible.pk != serializer.instance.devis_id:
            raise ValidationError({
                'devis': "Une ligne ne change pas de devis : supprimez-la et "
                         "ajoutez-la sur l'autre devis."})

    def perform_create(self, serializer):
        from ..domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis)
        self._check_tenant(serializer)
        self._check_devis_not_frozen(serializer.validated_data.get('devis'))
        # QJR518 — état vu par le client capturé AVANT (envoyé seulement).
        avant_geste = debut_de_geste_devis(
            serializer.validated_data.get('devis'), self.request.user)
        serializer.save()
        # ACAL90 — une ligne de kit AJOUTÉE à la main sort du marqueur.
        from ..domain.lignes import noter_ligne_ajoutee
        noter_ligne_ajoutee(serializer.instance)
        # CJ2b / L-1V — une ligne AJOUTÉE peut changer la puissance kWc
        # résidentielle : les QUATRE études du devis (bloc horaire,
        # dimensionnement, profils comparatifs, CONCEPTION ÉLECTRIQUE) doivent
        # repartir de la composition COURANTE. Ce chemin n'en rafraîchissait
        # qu'UNE — le bloc horaire — si bien qu'ajouter une ligne faisait bouger
        # le graphe de la page client sans toucher au schéma unifilaire, qui
        # continuait de décrire la composition d'avant. Best-effort, ne lève
        # jamais (voir ``services.rafraichir_etudes_du_devis``).
        _retarifer_forfaits(serializer.instance.devis)
        _rafraichir(serializer.instance.devis)
        _instantane(serializer.instance.devis, self.request.user)
        fin_de_geste_devis(serializer.instance.devis, self.request.user,
                           avant=avant_geste, objet='ligne')
        # ADEV23 — la réponse égale la ligne RELUE (après re-tarification).
        serializer.instance.refresh_from_db()

    def perform_update(self, serializer):
        from ..domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis)
        self._check_tenant(serializer)
        self._check_devis_inchange(serializer)
        self._check_devis_not_frozen(serializer.instance.devis)
        avant_geste = debut_de_geste_devis(
            serializer.instance.devis, self.request.user)
        serializer.save()
        # CJ2b / L-1V — voir perform_create ci-dessus (même raison : la ligne
        # MODIFIÉE peut changer la puissance kWc).
        _retarifer_forfaits(serializer.instance.devis)
        _rafraichir(serializer.instance.devis)
        _instantane(serializer.instance.devis, self.request.user)
        fin_de_geste_devis(serializer.instance.devis, self.request.user,
                           avant=avant_geste, objet='ligne')
        # ADEV23 — la réponse égale la ligne RELUE (après re-tarification).
        serializer.instance.refresh_from_db()

    def perform_destroy(self, instance):
        from ..domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis)
        self._check_devis_not_frozen(instance.devis)
        devis = instance.devis
        avant_geste = debut_de_geste_devis(devis, self.request.user)
        # ACAL90 — LE point de suppression à la main : une ligne de kit
        # retirée est mémorisée (``kit_retire``), jamais recréée par la
        # resynchro (D-ACAL-22).
        from ..domain.lignes import supprimer_ligne
        supprimer_ligne(instance)
        # CJ2b / L-1V — voir perform_create ci-dessus (même raison : une ligne
        # RETIRÉE peut changer, voire annuler, la puissance kWc).
        _retarifer_forfaits(devis)
        _rafraichir(devis)
        _instantane(devis, self.request.user)
        fin_de_geste_devis(devis, self.request.user, avant=avant_geste,
                           objet='ligne')
