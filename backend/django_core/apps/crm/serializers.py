from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import DecimalField as ModelDecimalField
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from core.mixins import SameCompanyFKSerializerMixin
from core.serializers import (
    model_is_company_scoped,
    request_company_id,
    scope_related_field,
)
from .models import (
    AppareilEquipe, Apporteur, Appointment, Client, ConcurrentPerte,
    DealEnregistre, Defi,
    EquipeCommerciale,
    EtapePlanActivite, ForecastEntry, ForecastSnapshot, Lead, LeadActivity,
    LeadPlaybookProgress, MessageTemplate, ObjectifCommercial, Parrainage,
    Partenaire, PlanActivite, PlanCompte, Playbook, PlaybookEtape,
    PlaybookTache, PointContact, RelanceEtape, RevueCompte, SalleVente,
    SalleVenteItem, SavedView, SiteProfile, VisiteExterne, WebsiteLeadPayload,
)
from .devis_auto import (
    champs_manquants_detail, champs_requis, message_manquants,
    source_conso, visite_avant_devis, visite_point_eau_avant_devis)
from . import cadence_temps
from .scoring import compute_score, score_label, score_reasons


# ── LW29/CRX19 — PII du lead : une SEULE liste, un SEUL masquage ────────────
#
# ``LeadSerializer`` masque déjà ces six champs pour un rôle sans
# ``client_pii_voir``… mais le CHATTER les recopiait en clair dans
# ``old_value``/``new_value`` : « telephone : 0612345678 → 0698765432 » restait
# lisible par tout le monde. Le masquage vit donc AU NIVEAU DU SÉRIALISEUR
# d'activité, donc PAR CONSTRUCTION sur les trois surfaces qui servent le
# chatter (action ``historique``, ``chatter_recent`` embarqué au retrieve, et
# l'enveloppe uniforme ARC9).
#: CAD144 — + le téléphone du contact SECONDAIRE (co-associé, technicien) :
#: un numéro reste une PII, qu'il soit le premier ou le second de la fiche.
LEAD_PII_FIELDS = ('telephone', 'email', 'adresse', 'whatsapp',
                   'gps_lat', 'gps_lng', 'lien_maps',
                   'contact_secondaire_telephone')

#: Remplacement affiché à la place d'une valeur PII masquée.
PII_MASQUE = '•••'


def pii_masquee_pour(user) -> bool:
    """Condition UNIQUE du masquage PII (LW29) : ``user`` connu et privé de
    ``client_pii_voir``. Sans utilisateur (rendu serveur/interne, tâche de
    fond), rien n'est masqué — comportement historique."""
    return user is not None and not getattr(user, 'can_view_client_pii', True)


def masquer_valeurs_chatter(field, old_value, new_value, user):
    """Renvoie ``(old_value, new_value)`` masqués si ``field`` est une PII du
    lead et que ``user`` n'a pas le droit de la voir.

    Fonction PARTAGÉE par ``LeadActivitySerializer`` et par l'enveloppe
    uniforme (``selectors.lead_chatter_envelope``) : une seule règle, jamais
    deux implémentations qui divergent.
    """
    if not pii_masquee_pour(user):
        return old_value, new_value
    if (field or '') not in LEAD_PII_FIELDS:
        return old_value, new_value
    return (PII_MASQUE if old_value else old_value,
            PII_MASQUE if new_value else new_value)


class LeadActivitySerializer(serializers.ModelSerializer):
    user_nom = serializers.SerializerMethodField()
    # VX111 — pièce jointe optionnelle sur une note (photo prise depuis
    # mobile). Même forme d'URL que AttachmentSerializer.get_url (proxy
    # Django même origine, jamais MinIO direct) — pas de sérialiseur imbriqué
    # pour rester compatible avec la structure plate consommée par
    # ChatterTimeline côté frontend.
    attachment_url = serializers.SerializerMethodField()
    attachment_filename = serializers.SerializerMethodField()
    attachment_mime = serializers.SerializerMethodField()

    class Meta:
        model = LeadActivity
        fields = [
            'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'outcome', 'bulk', 'pinned', 'user_nom', 'created_at',
            'attachment_url', 'attachment_filename', 'attachment_mime',
        ]

    def get_user_nom(self, obj):
        return getattr(obj.user, 'username', None)

    def get_attachment_url(self, obj):
        if not obj.attachment_id:
            return None
        return f'/api/django/records/attachments/{obj.attachment_id}/download/'

    def get_attachment_filename(self, obj):
        return getattr(obj.attachment, 'filename', None)

    def get_attachment_mime(self, obj):
        return getattr(obj.attachment, 'mime', None)

    def to_representation(self, instance):
        """CRX19 — masque ``old_value``/``new_value`` quand l'entrée porte sur
        une PII du lead et que l'utilisateur n'a pas ``client_pii_voir``.

        Ici et NULLE PART AILLEURS : les trois surfaces qui servent le chatter
        (``historique``, ``chatter_recent``, enveloppe ARC9) héritent donc du
        masquage par construction. Sans ``context['request']`` (rendu interne),
        rien n'est masqué — comportement historique."""
        data = super().to_representation(instance)
        request = self.context.get('request') if hasattr(self, 'context') \
            else None
        user = getattr(request, 'user', None) if request is not None else None
        data['old_value'], data['new_value'] = masquer_valeurs_chatter(
            data.get('field'), data.get('old_value'), data.get('new_value'),
            user)
        return data


def nom_affichable_lead(lead) -> str:
    """Le nom affiché d'un lead dans la file (« Nom Prénom ») — ``lead_nom``
    de ``RelanceEtapeSerializer``, partagé avec le bloc « Contrôle du suivi »
    (``controle_suivi.py``) : une seule règle, jamais deux qui divergent."""
    if lead is None:
        return ''
    return f'{lead.nom} {lead.prenom or ""}'.strip()


def nom_affichable_responsable(user) -> str | None:
    """Le nom affiché du RESPONSABLE d'un lead — ``lead_owner_nom`` de
    ``RelanceEtapeSerializer`` (l'identifiant de connexion), ``None`` sans
    responsable. Partagé avec ``controle_suivi.py`` : aucun prénom en dur."""
    return getattr(user, 'username', None)


class RelanceEtapeSerializer(serializers.ModelSerializer):
    """RELANCE FOUNDATION — étape du plan de relance structuré d'un lead, pour
    le panneau « Relances du jour ». Plate (jamais de sérialiseur Lead
    imbriqué) — même convention que ``LeadActivitySerializer`` ci-dessus."""

    lead_nom = serializers.SerializerMethodField()
    lead_owner_nom = serializers.SerializerMethodField()
    lead_telephone = serializers.SerializerMethodField()
    lead_whatsapp = serializers.SerializerMethodField()
    # CAD176 — MÊME masquage PII que `lead_telephone`/`lead_whatsapp` : sans
    # cette adresse, le seul barreau e-mail de la cadence (CAD86) ne pouvait
    # jamais dire à QUI le texte rendu s'adresse.
    lead_email = serializers.SerializerMethodField()
    lead_langue = serializers.SerializerMethodField()
    lead_score = serializers.SerializerMethodField()
    lead_priorite = serializers.SerializerMethodField()
    # AGR531 (contrat `relance_etape_v2.json`, AGR500) — le segment du lead
    # (`type_installation`, '' si non renseigné). Lecture seule : il ne sert
    # qu'aux CONSIGNES d'écran, jamais au rythme de la cadence.
    lead_segment = serializers.SerializerMethodField()
    devis_reference = serializers.SerializerMethodField()
    overdue = serializers.SerializerMethodField()
    # MRY30 — QUI a traité la touche, et QUAND. Le modèle les portait déjà
    # (`traite_par`/`traite_le`, écrits par `marquer_etape_relance`) mais rien
    # ne les servait : l'écran « Suivi des relances » montrait une touche
    # « faite » sans pouvoir dire par qui ni à quelle heure — une traçabilité
    # écrite en base et invisible ne trace rien.
    traite_le = serializers.DateTimeField(read_only=True)
    traite_par_nom = serializers.SerializerMethodField()
    # CKP1 — le LIBELLÉ du statut, servi par le serveur : le badge « Sautée »
    # nu ne distinguait pas la décision HUMAINE de l'annulation MOTEUR, et
    # l'écran n'avait aucun moyen de le faire sans réinventer la table des
    # libellés. « Annulée (moteur) » vient donc du modèle, pas du front.
    statut_libelle = serializers.SerializerMethodField()
    # RLC3 — le message de CETTE touche a-t-il été OUVERT ? Horodatage de
    # l'activité « WhatsApp ouvert » (posée par le clic humain,
    # ``services.journaliser_whatsapp_ouvert`` — jamais un envoi), ou ``null``.
    # Le panneau « Fait » d'une touche MESSAGE le rappelle et, à défaut,
    # demande une confirmation explicite : Meryem peut avoir écrit depuis son
    # téléphone, donc jamais un blocage — seulement une question.
    message_ouvert_le = serializers.SerializerMethodField()
    # CAD32 — sur un lead « WhatsApp uniquement », les barreaux d'appel du
    # protocole naissent en WhatsApp. Sans cette phrase, la commerciale verrait
    # « Appel 3 » sur une touche WhatsApp sans savoir POURQUOI : un
    # comportement caché, et elle rappellerait par téléphone un client qui a
    # demandé le contraire. Chaîne VIDE — jamais null — quand rien n'est
    # adapté, comme les autres champs de confort de ce sérialiseur.
    canal_adapte = serializers.SerializerMethodField()
    # CAD11 — le lead de cette touche est-il JUNK (perdu avec un motif marqué
    # `MotifPerte.est_junk` : numéro invalide, spam, hors zone…) ? Le drapeau
    # vivait au niveau du lead, à trois écrans de la touche : l'exposer ici
    # rend mesurable la qualité des numéros qui arrivent des publicités.
    lead_est_junk = serializers.SerializerMethodField()
    # CAD17 — la SUITE de chaque réponse du panneau « Fait », DÉRIVÉE du
    # moteur (``suite_touche.promesses_touche``) : ``{cle: [codes d'effet]}``.
    # L'écran ne fait plus que traduire chaque code en UNE phrase ; il
    # n'écrit plus de promesse par cadence, qui mentait dès que le libellé ou
    # le rang de la touche changeait la suite réelle (CAD1/CAD3/CAD16/CAD97).
    suites = serializers.SerializerMethodField()
    # CAD82 — la PRÉFÉRENCE de contact du client atteint enfin la touche :
    # deux boutons (Appeler / WhatsApp) étaient proposés à égalité sans dire
    # que ce client a demandé à n'être joint que par écrit. Chaîne VIDE —
    # jamais null — quand rien n'est posé (valeurs de `Lead.ContactPreference`).
    lead_contact_preference = serializers.SerializerMethodField()
    # CAD82 — POURQUOI le numéro est vide : `lead_telephone` vaut '' aussi bien
    # pour un lead SANS numéro que pour un rôle privé de `client_pii_voir`.
    # Sans ce drapeau, le bouton « Appeler » désactivé ne pouvait pas dire sa
    # cause (règle fondateur : le champ fautif, le message exact).
    lead_pii_masquee = serializers.SerializerMethodField()
    # PARAM-CADENCE (25/09/2026) — la visite du lead, servie sur TOUTE touche
    # pour que la file du jour la montre à côté de « Confirmer la visite » /
    # « Débrief visite » (contrat `relance_etape_v2`, additif).
    visite_prevue_le = serializers.SerializerMethodField()
    visite_id = serializers.SerializerMethodField()
    visite_retour_disponible = serializers.SerializerMethodField()
    # COCKPIT-CONTRÔLE (30/09/2026, contrat `relance_etape_v2`, note
    # `cockpit_controle`) — la touche TYPÉE et ses deux traces : le type de la
    # table du parcours (`suite_touche.type_etape`), la TÂCHE (traitable dès
    # maintenant, jamais « sautée »), les reports humains, l'échéance
    # d'origine et l'instant où l'étape a été posée. Additifs, sans requête.
    type_etape = serializers.SerializerMethodField()
    est_tache = serializers.SerializerMethodField()
    posee_le = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = RelanceEtape
        # MRY5 — forme `relance_etape_v2` (contrat MRY25).
        # MRY30 — `traite_le`/`traite_par_nom` s'ajoutent (contrat
        # `relance_etapes_suivi`) : ADDITIF, la file du jour les sert aussi
        # (null / '' tant que la touche est à faire) plutôt que d'entretenir
        # deux sérialiseurs qui divergeraient.
        fields = [
            'id', 'lead', 'lead_nom', 'lead_owner_nom', 'lead_telephone',
            'lead_whatsapp', 'lead_langue', 'lead_score', 'lead_priorite',
            'cadence', 'ordre', 'due_date', 'due_at', 'canal', 'libelle',
            'template_cle', 'statut', 'note', 'overdue', 'devis',
            'devis_reference', 'traite_le', 'traite_par_nom',
            'statut_libelle', 'message_ouvert_le', 'canal_adapte',
            'lead_est_junk', 'suites',
            # CAD82 — additifs.
            'lead_contact_preference', 'lead_pii_masquee',
            # PARAM-CADENCE — additifs : la clé du barreau paramétré (l'écran
            # la lit AVANT le libellé, qu'une société peut renommer) et la
            # visite technique du lead.
            'cle', 'visite_prevue_le', 'visite_id',
            'visite_retour_disponible',
            # CAD176 — additif : l'adresse e-mail du lead, pour le seul
            # barreau e-mail de la cadence.
            'lead_email',
            # COCKPIT-CONTRÔLE — additifs (voir plus haut).
            'type_etape', 'est_tache', 'nb_reports', 'due_initial_at',
            'posee_le',
            # AGR531 — additif (contrat `relance_etape_v2.json`).
            'lead_segment',
        ]
        read_only_fields = [
            'id', 'lead', 'cadence', 'ordre', 'due_date', 'due_at', 'canal',
            'libelle', 'template_cle', 'devis', 'traite_le', 'cle',
            'nb_reports', 'due_initial_at',
        ]

    def get_lead_nom(self, obj) -> str:
        return nom_affichable_lead(obj.lead)

    def get_lead_owner_nom(self, obj) -> str | None:
        return nom_affichable_responsable(obj.lead.owner)

    def get_type_etape(self, obj) -> str:
        """COCKPIT-CONTRÔLE — l'identifiant du type dans la table du parcours
        (``suite_touche.type_etape`` : la clé moteur, puis le libellé, puis
        cadence + canal), ``''`` si la table ne le connaît pas. Pur."""
        from .suite_touche import type_etape_connu
        return type_etape_connu(obj)

    def get_est_tache(self, obj) -> bool:
        """COCKPIT-CONTRÔLE — une TÂCHE de la table (préparer le devis,
        planifier la visite, décider la suite, devis modifié, question de
        prix) : traitable dès maintenant, jamais « sautée ». Pur."""
        from .suite_touche import est_tache
        return est_tache(obj)

    def _pii_masquee(self) -> bool:
        """MRY5 — MÊME règle que ``LeadSerializer.PII_FIELDS`` : un rôle sans
        ``client_pii_voir`` ne doit pas récupérer par la file de relances le
        numéro que la fiche lui masque."""
        request = self.context.get('request')
        return pii_masquee_pour(getattr(request, 'user', None))

    def get_lead_telephone(self, obj) -> str:
        return '' if self._pii_masquee() else (obj.lead.telephone or '')

    def get_lead_whatsapp(self, obj) -> str:
        return '' if self._pii_masquee() else (obj.lead.whatsapp or '')

    def get_lead_email(self, obj) -> str:
        """CAD176 — MÊME règle que ``get_lead_telephone`` : chaîne vide pour
        un rôle sans ``client_pii_voir``, comme pour une fiche sans adresse."""
        return '' if self._pii_masquee() else (obj.lead.email or '')

    def get_lead_langue(self, obj) -> str:
        return obj.lead.langue_preferee or 'fr'

    def get_lead_segment(self, obj) -> str:
        """AGR531 — ``Lead.type_installation`` ou ``''`` (lead déjà chargé :
        aucune requête de plus)."""
        return getattr(obj.lead, 'type_installation', None) or ''

    def get_lead_contact_preference(self, obj) -> str:
        """CAD82 — ``whatsapp_only`` | ``phone_ok`` | '' (rien de posé)."""
        return getattr(obj.lead, 'contact_preference', '') or ''

    def get_lead_pii_masquee(self, obj) -> bool:
        """CAD82 — ``True`` quand les coordonnées sont MASQUÉES pour ce
        demandeur (même règle que ``get_lead_telephone``) : un numéro vide
        n'est alors pas un numéro absent. Aucune requête (drapeau utilisateur)."""
        return self._pii_masquee()

    def get_canal_adapte(self, obj) -> str:
        """CAD32 — la phrase qui explique un canal qui n'est pas celui du
        libellé. Jamais un comportement caché."""
        if (getattr(obj.lead, 'contact_preference', '')
                == Lead.ContactPreference.WHATSAPP_ONLY):
            return ('Canal adapté à la préférence du client : '
                    'WhatsApp uniquement.')
        # CIQ505 — la conversion d'un fixe (e-mail, sinon appel) : la MÊME
        # fonction pure que le moteur (`cadence_temps.conversion_numero`),
        # appliquée aux seules touches nées WhatsApp au protocole.
        if (obj.canal in (cadence_temps.CANAL_EMAIL, cadence_temps.CANAL_APPEL)
                and obj.template_cle
                and self._canal_protocole(obj) == cadence_temps.CANAL_WHATSAPP):
            conversion = cadence_temps.conversion_numero(
                obj.lead, obj.template_cle)
            if conversion is not None and conversion[0] == obj.canal:
                return conversion[1]
        return ''

    def _canal_protocole(self, obj) -> str:
        """CIQ505 — le canal que le PROTOCOLE de la société donne à cette
        touche (par cadence et rang), mis en cache pour la réponse : sert à
        reconnaître une touche née WhatsApp puis convertie. Lecture seule —
        jamais ``cadence_pour``, qui sème à la volée."""
        cache = self.context.setdefault('_ciq505_canaux_protocole', {})
        cle = (obj.company_id, obj.cadence)
        if cle not in cache:
            from apps.parametres.models_relance import CadenceRelanceEtape
            cache[cle] = dict(CadenceRelanceEtape.objects.filter(
                company_id=obj.company_id, cadence=obj.cadence, actif=True,
            ).values_list('ordre', 'canal'))
        return cache[cle].get(obj.ordre, '')

    def get_lead_est_junk(self, obj) -> bool:
        """CAD11 — ``True`` si le lead est PERDU avec un motif « junk » de sa
        société (même rapprochement insensible à la casse que le signal
        qualité PUB28 : ``Lead.motif_perte`` reste un texte libre).

        COÛT BORNÉ : aucune requête pour un lead non perdu (le cas de toute
        touche encore dans la file), et une seule lecture des motifs junk par
        société et par réponse (cache dans le contexte partagé du
        sérialiseur, liste comprise)."""
        lead = obj.lead
        if not getattr(lead, 'perdu', False):
            return False
        motif = (getattr(lead, 'motif_perte', '') or '').strip().lower()
        if not motif:
            return False
        cache = self.context.setdefault('_cad11_motifs_junk', {})
        if lead.company_id not in cache:
            from .models import MotifPerte
            cache[lead.company_id] = {
                (nom or '').strip().lower()
                for nom in MotifPerte.objects.filter(
                    company_id=lead.company_id, est_junk=True,
                ).values_list('nom', flat=True)}
        return motif in cache[lead.company_id]

    @extend_schema_field(serializers.IntegerField())
    def get_lead_score(self, obj):
        return getattr(obj.lead, 'score', None)

    def get_lead_priorite(self, obj) -> str:
        return getattr(obj.lead, 'priorite', '') or ''

    def get_devis_reference(self, obj) -> str:
        # `select_related('devis')` côté sélecteur : jamais une requête par
        # ligne dans la file de Meryem.
        return getattr(obj.devis, 'reference', '') or ''

    def get_overdue(self, obj) -> bool:
        from core.dates import aujourd_hui_local
        return obj.due_date < aujourd_hui_local()

    def get_traite_par_nom(self, obj) -> str:
        # `select_related('traite_par')` côté sélecteur de période : jamais
        # une requête par ligne. '' — jamais null — pour une touche à faire
        # ou marquée par le système (contrat `relance_etapes_suivi`).
        return getattr(obj.traite_par, 'username', '') or ''

    def get_statut_libelle(self, obj) -> str:
        return obj.get_statut_display()

    @extend_schema_field(serializers.DictField(
        child=serializers.ListField(child=serializers.CharField())))
    def get_suites(self, obj):
        """CAD17 — ``{cle_de_reponse: [codes d'effet]}`` pour une touche À
        FAIRE ; ``{}`` pour une touche déjà traitée (plus rien à annoncer).

        COÛT BORNÉ : aucune requête pour une touche traitée ; sinon UNE lecture
        des barreaux actifs par (société, cadence) et par réponse, mise en
        cache dans le contexte partagé du sérialiseur (liste comprise) — même
        patron que ``get_lead_est_junk``."""
        if obj.statut != RelanceEtape.Statut.A_FAIRE:
            return {}
        from .suite_touche import (
            lecteur_paliers_actifs, ordres_de_la_cadence, promesses_touche)
        cache = self.context.setdefault('_cad17_ordres', {})
        cle = (obj.company_id, obj.cadence)
        if cle not in cache:
            cache[cle] = ordres_de_la_cadence(obj.company_id, obj.cadence)
        # PARAM-CADENCE — les paliers gardés par la société : UN lecteur
        # paresseux par société et par réponse (au plus une requête).
        paliers = self.context.setdefault('_param_cad_paliers', {})
        if obj.company_id not in paliers:
            paliers[obj.company_id] = lecteur_paliers_actifs(obj.company_id)
        return promesses_touche(obj, ordres=cache[cle],
                                est_actif=paliers[obj.company_id])

    @extend_schema_field(serializers.DateField(allow_null=True))
    def get_visite_prevue_le(self, obj):
        """PARAM-CADENCE — ``Lead.visite_prevue_le`` (ISO), ``None`` sans
        visite. Aucune requête (le lead est déjà chargé)."""
        jour = getattr(obj.lead, 'visite_prevue_le', None)
        return jour.isoformat() if jour else None

    def _visite_du_lead(self, obj):
        """``(id, retour_disponible)`` de la visite terrain la PLUS RÉCENTE
        du lead, lue par le sélecteur de l'app visites (frontière M3 : jamais
        ``apps.visites.models``), ou ``(None, False)``.

        D2 — COÛT BORNÉ, quel que soit le nombre de leads : aucune requête
        pour un lead sans visite prévue ni effectuée (le cas de presque toute
        la file) ; sinon UNE lecture EN LOT (``visites_recentes_par_lead``),
        jamais une par lead. Sur une réponse de LISTE, ``self.parent`` est le
        ``ListSerializer`` et son ``.instance`` porte TOUTES les touches de
        cette page (``select_related('lead')`` côté sélecteur : lire
        ``t.lead`` ici ne coûte rien de plus) — la première touche qui a
        besoin d'une visite déclenche UNE lecture qui couvre tous les leads
        candidats de la page, mise en cache dans le contexte partagé du
        sérialiseur (même patron que ``get_lead_est_junk``). Sur un DÉTAIL
        (``self.parent`` absent), un seul lead. Avant ce correctif : UNE
        lecture par lead ET par réponse (mesuré 11 requêtes pour 1 lead, 21
        pour 6). Best-effort : une lecture en échec rend ``(None, False)``,
        jamais une erreur de file."""
        lead = obj.lead
        if not (getattr(lead, 'visite_prevue_le', None)
                or getattr(lead, 'visite_effectuee', False)):
            return None, False
        cache = self.context.setdefault('_param_cad_visites', {})
        if lead.pk not in cache:
            instances = getattr(self.parent, 'instance', None)
            if instances is not None:
                candidats = {
                    t.lead_id for t in instances
                    if (getattr(t.lead, 'visite_prevue_le', None)
                        or getattr(t.lead, 'visite_effectuee', False))}
            else:
                candidats = {lead.pk}
            try:
                from apps.visites.selectors import visites_recentes_par_lead
                lignes = visites_recentes_par_lead(lead.company, candidats)
            except Exception:  # noqa: BLE001 — jamais bloquant
                lignes = {}
            for lid in candidats:
                ligne = lignes.get(lid)
                cache[lid] = ((ligne['id'], bool(ligne['retour_disponible']))
                              if ligne else (None, False))
        return cache[lead.pk]

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_visite_id(self, obj):
        return self._visite_du_lead(obj)[0]

    def get_visite_retour_disponible(self, obj) -> bool:
        return self._visite_du_lead(obj)[1]

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_message_ouvert_le(self, obj):
        """RLC3 — quand le message de cette touche a été OUVERT (dernière
        activité « WhatsApp ouvert » portant son libellé), sinon ``None``.

        COÛT BORNÉ, délibérément : une requête, et seulement pour une touche
        MESSAGE encore À FAIRE — le seul cas où le panneau « Fait » peut
        s'ouvrir et donc le seul où la réponse sert. Une touche d'appel, ou
        déjà traitée, ne paie rien : la file du jour et l'écran de suivi (qui
        servent surtout de l'historique) ne gagnent pas une requête par ligne.

        Le préfixe de reconnaissance vient de ``services`` — la même fonction
        que l'écriture, jamais un second littéral."""
        if obj.statut != RelanceEtape.Statut.A_FAIRE:
            return None
        if obj.canal not in (RelanceEtape.Canal.WHATSAPP,
                             RelanceEtape.Canal.EMAIL):
            return None
        from .services import prefixe_activite_message_ouvert
        return (LeadActivity.objects
                .filter(lead_id=obj.lead_id,
                        kind=LeadActivity.Kind.WHATSAPP,
                        body__startswith=prefixe_activite_message_ouvert(obj))
                .order_by('-created_at')
                .values_list('created_at', flat=True).first())


class _CurrentCompanyDefault:
    """Société du user courant, injectée CÔTÉ SERVEUR (jamais lue du corps
    de la requête). Satisfait le validateur d'unicité (company, email) qui,
    sinon, exigeait `company` dans le payload — cassait « Nouveau client »."""
    requires_context = True

    def __call__(self, serializer_field):
        return serializer_field.context['request'].user.company


# ── CRX13 — relations NUES re-scopées société (primitive CRX12) ──────────────
#
# Treize relations d'``apps/crm`` étaient déclarées (ou auto-construites) avec
# un queryset NON scopé : un POST/PATCH pouvait donc rattacher l'objet à une
# ligne d'une AUTRE société, et l'erreur renvoyée servait d'ORACLE d'existence.
# Le re-scope se fait par PROMOTION du champ déjà construit
# (``core.serializers.scope_related_field``) plutôt que par re-déclaration :
# les arguments d'origine (``required``, ``allow_null``, ``source``, messages)
# sont conservés à l'identique — seule la résolution de l'id change. Un champ
# déjà en lecture seule, ou dont la cible n'a pas de ``company``, est ignoré.


class _CompanyScopedRelationsMixin:
    """Re-scope société les relations nommées dans ``scoped_relations``.

    Posé en PREMIÈRE base du sérialiseur : un ``get_fields`` propre au
    sérialiseur (ClientSerializer, LeadSerializer) reste prioritaire et appelle
    ``super()``, donc la promotion s'applique dans tous les cas.
    """

    #: Noms de champs de relation à re-scoper sur ``request.user.company``.
    scoped_relations: tuple = ()

    def get_fields(self):
        fields = super().get_fields()
        for name in self.scoped_relations:
            field = fields.get(name)
            if field is not None:
                scope_related_field(field)
        return fields


class _CompanyScopedUniqueValidator(UniqueValidator):
    """``UniqueValidator`` dont le queryset est re-scopé société.

    Le validateur d'unicité auto-généré par DRF pour un champ ``unique``
    interroge TOUTES les sociétés : répondre « déjà utilisé » sur un id qui
    n'appartient pas au demandeur révèle l'existence d'une ligne voisine. On
    restreint donc la recherche à la société de la requête. Sans requête (rendu
    interne) ou pour un acteur sans société, le comportement d'origine est
    conservé à l'identique.
    """

    def __call__(self, value, serializer_field):
        company_id = request_company_id(serializer_field.context)
        if company_id is not None and model_is_company_scoped(
                self.queryset.model):
            scoped = UniqueValidator(
                queryset=self.queryset.filter(company_id=company_id),
                message=self.message, lookup=self.lookup)
            return scoped(value, serializer_field)
        return super().__call__(value, serializer_field)


def _scope_unique_validators(field):
    """Remplace les ``UniqueValidator`` d'un champ par leur version scopée."""
    if field is None:
        return
    validators = getattr(field, 'validators', None)
    if not validators:
        return
    field.validators = [
        _CompanyScopedUniqueValidator(
            queryset=v.queryset, message=v.message, lookup=v.lookup)
        if type(v) is UniqueValidator else v
        for v in validators
    ]


class ClientSerializer(_CompanyScopedRelationsMixin,
                       serializers.ModelSerializer):
    # CRX13 — la liste de prix négociée et la fiche du répertoire unifié sont
    # deux relations SORTANTES (ventes/tiers) : sans re-scope, un PATCH pouvait
    # rattacher le client au tarif d'une autre société.
    scoped_relations = ('liste_prix', 'tiers')

    devis_count = serializers.SerializerMethodField()
    total_facture_ttc = serializers.SerializerMethodField()
    total_paye = serializers.SerializerMethodField()
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    # Traçabilité (L16) : qui a créé le client + dernière modification.
    # created_by est forcé côté serveur (perform_create) — jamais lu du corps.
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by_nom = serializers.SerializerMethodField()
    # CIQ402 (contrat CIQ8 ``client_entreprise.json``, D-CIQ-11) — ce qui
    # manque à l'identité légale d'un client entreprise et ce que chaque
    # étape exige (rien ne bloque un devis). Pur, sans requête.
    identite_entreprise = serializers.SerializerMethodField()

    # FG20 — coordonnées personnelles masquées quand le rôle n'a pas
    # ``client_pii_voir``. Source unique des champs PII partagée avec le Lead.
    PII_FIELDS = ('telephone', 'email', 'adresse')

    def validate(self, attrs):
        # Champs personnalisés (T11, L808) : valider/nettoyer le custom_data du
        # client contre les définitions du module « client », même chemin que
        # Lead. À la création on valide toujours (champs obligatoires) ; en
        # mise à jour, uniquement si custom_data est fourni.
        is_create = self.instance is None
        if is_create or 'custom_data' in attrs:
            from apps.customfields.serializers import validate_custom_data
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            if company is not None:
                attrs['custom_data'] = validate_custom_data(
                    'client', company, attrs.get('custom_data'))
        return attrs

    def validate_ice(self, value):
        # NTI18N19 — validateur MA formalisé (framework extensible par
        # pack_pays, NTI18N16 — pas encore construit, GATED-founder : en
        # attendant, 'MA' est passé en dur, comportement historique puisque
        # toute société actuelle EST marocaine). Jamais bloquant pour un
        # champ vide (optionnel côté modèle).
        from apps.parametres.tax_id_validators import validate_tax_id
        resultat = validate_tax_id('MA', 'ice', value)
        if not resultat['valide']:
            raise serializers.ValidationError(resultat['message'])
        return value

    def validate_parent(self, value):
        # XSAL9 — anti-cycle + même société, appliqué ici car DRF n'invoque
        # PAS Model.clean() automatiquement à l'écriture API (seul
        # full_clean() le ferait — jamais appelé sur ce chemin).
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'La société mère doit appartenir à la même société.')
        if self.instance is not None:
            if value.pk == self.instance.pk:
                raise serializers.ValidationError(
                    "Un client ne peut pas être sa propre société mère.")
            seen = {self.instance.pk}
            current = value
            depth = 0
            while current is not None:
                if current.pk in seen or depth > 100:
                    raise serializers.ValidationError(
                        'Cette hiérarchie créerait un cycle.')
                seen.add(current.pk)
                current = current.parent
                depth += 1
        return value

    def get_fields(self):
        fields = super().get_fields()
        # FG20 — masque la PII en LECTURE pour les rôles non autorisés. On rend
        # les champs lecture-seule (plutôt que de les retirer) afin de ne jamais
        # casser une écriture légitime, et on les vide à la sérialisation.
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'can_view_client_pii', True):
            for name in self.PII_FIELDS:
                if name in fields:
                    fields[name].read_only = True
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'can_view_client_pii', True):
            for name in self.PII_FIELDS:
                if name in data:
                    data[name] = None
        return data

    class Meta:
        model = Client
        fields = '__all__'
        read_only_fields = ['date_modification']

    def get_created_by_nom(self, obj):
        return getattr(obj.created_by, 'username', None)

    @extend_schema_field(serializers.DictField())
    def get_identite_entreprise(self, obj):
        from .models import identite_entreprise
        return identite_entreprise(
            entreprise=obj.type_client == Client.TypeClient.ENTREPRISE,
            raison_sociale=obj.nom,
            raison_a_confirmer=obj.raison_sociale_a_confirmer,
            ice=obj.ice, rc=obj.rc, if_fiscal=obj.if_fiscal,
            adresse_siege=obj.adresse_siege, adresse=obj.adresse)

    def get_devis_count(self, obj):
        return obj.devis.count()

    def get_total_facture_ttc(self, obj):
        """Valeur cumulée FACTURÉE (TTC) du client : somme des factures non
        annulées. total_ttc est une propriété calculée → agrégation en Python.
        Aucun prix d'achat ni marge n'intervient (totaux client-facing)."""
        from decimal import Decimal
        total = Decimal('0')
        for f in obj.factures.all():
            if f.statut != 'annulee':
                total += f.total_ttc
        return str(total)

    def get_total_paye(self, obj):
        """Total ENCAISSÉ du client (somme des montant_paye des factures)."""
        from decimal import Decimal
        total = Decimal('0')
        for f in obj.factures.all():
            if f.statut != 'annulee':
                total += f.montant_paye
        return str(total)


class LeadDecimalField(serializers.DecimalField):
    """ALEA17 — un nombre décimal du LEAD, NORMALISÉ au lieu d'être refusé.

    Règle fondateur « normaliser plutôt que refuser » (08/09/2026) : un GPS
    collé à 7 décimales (33.5731104, constaté en direct le 07/10/2026 : 15
    PATCH 400 en ~20 s, toast « pas plus de 6 chiffres » en boucle) ou une
    facture « 450,555 » sont des intentions limpides. La valeur est arrondie
    au nombre de décimales DU MODÈLE (demi-supérieur, ``ROUND_HALF_UP``) et la
    virgule décimale est acceptée. Ce qui n'est pas un nombre reste refusé en
    nommant le champ ; ``max_digits`` et les bornes (validateurs du modèle,
    ex. GPS [-90, 90] / [-180, 180]) restent appliqués par DRF.

    Appliquée à TOUS les ``DecimalField`` de ``Lead`` par le mapping de
    ``LeadSerializer`` (aucune liste écrite à la main)."""

    def to_internal_value(self, data):
        brut = data.strip().replace(',', '.') if isinstance(data, str) else data
        if self.decimal_places is not None and not isinstance(brut, bool):
            try:
                valeur = Decimal(str(brut))
                if valeur.is_finite():
                    pas = Decimal(1).scaleb(-self.decimal_places)
                    brut = str(valeur.quantize(pas, rounding=ROUND_HALF_UP))
            except (InvalidOperation, TypeError, ValueError):
                pass  # DRF refusera en nommant le champ
        return super().to_internal_value(brut)


class _PuissanceKwField(LeadDecimalField):
    """Puissance d'ÉQUIPEMENT saisie en kW (questionnaire d'appel).

    Relevé fondateur 08/09/2026 (lead Ali Mahraz) : une valeur tapée en WATTS
    (« 2800 » pour une clim de 2,8 kW) dépassait les 3 chiffres entiers du
    champ et faisait échouer TOUTE l'autosauvegarde du lead, avec pour seul
    message « pas plus de 3 chiffres avant la virgule » — sans nommer le
    champ. Aucun équipement domestique de ce questionnaire n'atteint 200 kW :
    une valeur ≥ 200 est lue comme des WATTS et ramenée en kW (2800 → 2,80).
    C'est une conversion d'unité tracée par le chatter (ancien → nouveau),
    jamais un chiffre inventé ; une saisie en kW reste intacte."""

    SEUIL_WATTS = Decimal('200')

    def to_internal_value(self, data):
        brut = data.strip().replace(',', '.') if isinstance(data, str) else data
        try:
            valeur = Decimal(str(brut))
        except (InvalidOperation, TypeError, ValueError):
            return super().to_internal_value(data)
        if valeur >= self.SEUIL_WATTS:
            brut = str((valeur / Decimal('1000')).quantize(Decimal('0.01')))
        return super().to_internal_value(brut)


#: AGR405 — libellés des segments dans le message d'incohérence (contrat
#: ``lead_pompage.json`` : « typé « résidentiel » … devis agricole »).
_LIBELLES_SEGMENT = {
    'residentiel': 'résidentiel', 'commercial': 'commercial',
    'industriel': 'industriel', 'agricole': 'agricole',
}


#: CIQ409 — segments pro (l'industriel d'abord : il l'emporte).
_SEGMENTS_PRO = ('industriel', 'commercial')


def _message_incoherence(segment_lead, mode_devis):
    cible = _LIBELLES_SEGMENT.get(mode_devis, mode_devis)
    if segment_lead:
        debut = ('Ce lead est typé « %s »'
                 % _LIBELLES_SEGMENT.get(segment_lead, segment_lead))
    else:
        debut = "Ce lead n'a pas de type"
    return ('%s mais porte un devis %s. Changer le type du lead en « %s » ?'
            % (debut, cible, cible))


def incoherence_segment(type_lead, devis):
    """AGR405 (D-AGR-9) — ``None`` ou ``{segment_lead, mode_devis, devis:
    [{id, reference}], message}`` : le lead porte au moins un devis agricole
    alors que son type n'est pas « agricole » (vide compris) ; ou, à
    l'inverse, le lead est agricole et TOUS ses devis sont résidentiels.
    CIQ409 (contrat ``lead_pro.json``) étend la règle au C&I : un devis
    commercial/industriel sur un lead qui n'est ni l'un ni l'autre, ou un
    lead pro dont tous les devis sont résidentiels. Fonction PURE sur la lecture mince ``devis`` de ventes ; elle n'écrit
    rien — le commercial change le type à la main."""
    type_lead = type_lead or ''
    par_mode = {}
    for d in devis or ():
        par_mode.setdefault(d.get('mode_installation') or '', []).append(d)
    modes_pro = [m for m in _SEGMENTS_PRO if par_mode.get(m)]
    mode = None
    if type_lead != 'agricole' and par_mode.get('agricole'):
        mode = 'agricole'
    elif type_lead not in _SEGMENTS_PRO and modes_pro:
        # CIQ409 — un devis commercial/industriel sur un lead qui n'est ni
        # l'un ni l'autre ; l'industriel l'emporte s'il y a les deux.
        mode = modes_pro[0]
    elif (type_lead in ('agricole',) + _SEGMENTS_PRO
          and set(par_mode) == {'residentiel'}):
        # AGR405 / CIQ409 — l'inverse : un lead agricole ou pro dont TOUS
        # les devis sont résidentiels.
        mode = 'residentiel'
    if mode is None:
        return None
    return {
        'segment_lead': type_lead or None,
        'mode_devis': mode,
        'devis': [{'id': d['id'], 'reference': d['reference']}
                  for d in par_mode[mode]],
        'message': _message_incoherence(type_lead, mode),
    }


class LeadSerializer(SameCompanyFKSerializerMixin,
                     _CompanyScopedRelationsMixin,
                     serializers.ModelSerializer):
    # CRX13 — ``deleted_by`` (auto-construit depuis ``__all__``) désignait
    # n'importe quel utilisateur, toutes sociétés confondues. CRX15 l'a depuis
    # verrouillé en LECTURE SEULE (cf. ``Meta.read_only_fields``) : la
    # promotion est alors un no-op, conservée comme filet si le champ
    # redevenait un jour inscriptible.
    # STKCAT9 — ``structure_produit`` est une relation SORTANTE INSCRIPTIBLE
    # vers ``stock.Produit`` : sans re-scope, un PATCH pouvait épingler sur un
    # lead le produit d'une AUTRE société. Promue ici, elle refuse cet id avec
    # le message « objet inexistant » standard de DRF — indiscernable d'un id
    # qui n'existe pas, donc aucun oracle d'existence inter-tenant.
    # PÉRIMÈTRE ASSUMÉ ET ÉCRIT : le re-scope filtre sur
    # ``company_id=<société de la requête>``, donc les fiches GLOBALES du
    # catalogue (``company`` NULL, semées par ``seed_catalogue``) ne sont pas
    # sélectionnables PAR CE CHAMP. La composition, elle, continue de les
    # accepter (son catalogue est ``company`` OU global) : une société qui veut
    # épingler une structure globale sur ses leads la duplique dans son propre
    # catalogue. C'est le prix de la garde d'isolation, et il est connu.
    # ALEA16 — ``entite`` (FK sortante INSCRIPTIBLE vers ``entites.Entite``)
    # acceptait l'id d'une entité d'une AUTRE société (sonde V3 LFICHE-2 /
    # V4 LCOUT-5 : 200, stocké). Bornée ici comme ``structure_produit`` : un
    # id étranger reçoit la même réponse qu'un id absent.
    scoped_relations = ('deleted_by', 'structure_produit', 'entite')

    # STKCAT9 — LA MÊME GARDE, DÉCLARÉE : ``same_company_fields`` est le patron
    # que la garde CI ``scripts/check_fk_scoping.py`` sait reconnaître sur une
    # FK cross-app écrivable (AUD601). Ceinture ET bretelles avec le re-scope
    # ci-dessus : le champ refuse déjà l'id d'une autre société à la
    # résolution, et si ce re-scope venait à sauter, ``to_internal_value``
    # refuserait encore — avec un message français explicite.
    same_company_fields = ('structure_produit', 'entite')

    # ALEA17 — TOUS les ``DecimalField`` du modèle Lead naissent
    # ``LeadDecimalField`` (arrondi au nombre de décimales du modèle, virgule
    # acceptée) : la garde ``tests_alea_lead_decimal_normalise`` le vérifie
    # par introspection de ``Lead._meta``.
    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        ModelDecimalField: LeadDecimalField,
    }

    # Relevé fondateur 08/09/2026 — les puissances d'équipement acceptent une
    # saisie en watts (ramenée en kW) au lieu de bloquer l'autosauvegarde.
    equip_piscine_pompe_kw = _PuissanceKwField(
        max_digits=5, decimal_places=2, required=False, allow_null=True)
    equip_chauffe_eau_kw = _PuissanceKwField(
        max_digits=5, decimal_places=2, required=False, allow_null=True)
    equip_ve_chargeur_kw = _PuissanceKwField(
        max_digits=5, decimal_places=2, required=False, allow_null=True)
    equip_clim_kw = _PuissanceKwField(
        max_digits=5, decimal_places=2, required=False, allow_null=True)

    stage_label = serializers.CharField(source='get_stage_display', read_only=True)
    source_label = serializers.CharField(source='get_source_display', read_only=True)
    client_nom = serializers.SerializerMethodField()
    # QJR590 (contrat ``lead_client_ecart.json``) — champs d'identité où la
    # fiche Client liée diffère du lead ; lecture seule.
    client_ecart = serializers.SerializerMethodField()
    # QJR586 (contrat ``lead_ville_effective.json``) — la ville de CALCUL,
    # lecture seule, '' jamais null.
    ville_effective = serializers.SerializerMethodField()
    devis = serializers.SerializerMethodField()
    owner_nom = serializers.SerializerMethodField()
    owner_poste = serializers.SerializerMethodField()
    owner_avatar = serializers.SerializerMethodField()
    devis_auto = serializers.SerializerMethodField()
    next_activity = serializers.SerializerMethodField()
    # FG27 — Score de qualité du lead (lecture seule, calculé à la volée).
    score = serializers.SerializerMethodField()
    score_label = serializers.SerializerMethodField()
    # VX221 — décomposition « pourquoi ce score » (facteurs + points), pour le
    # tooltip du badge. Pure exposition des composantes déjà calculées.
    score_reasons = serializers.SerializerMethodField()
    # FG29 — Âge dans l'étape courante (jours depuis le dernier changement d'étape).
    stage_since_days = serializers.SerializerMethodField()
    # VX98 — auteur de la dernière modification (puce de fraîcheur). Lecture seule.
    updated_by_nom = serializers.CharField(
        source='updated_by.username', read_only=True, default=None)
    # STKCAT9 — le NOM de la structure épinglée, en lecture seule : l'écran CRM
    # affiche « Pergola acier 4x3 » sans avoir à re-demander le produit au
    # catalogue. ``default=None`` : un lead sans structure rend ``null``, jamais
    # une erreur d'attribut (même patron qu'``updated_by_nom`` ci-dessus).
    structure_produit_nom = serializers.CharField(
        source='structure_produit.nom', read_only=True, default=None)
    # VX243(a) — confiance au niveau du DOSSIER : « archivé par X le … ». Les
    # champs archived_by/archived_at sont posés côté serveur (jamais rendus
    # avant) — on expose ici le NOM de l'archiviste en lecture seule pour que
    # la ligne archivée le montre. Silencieux si le lead n'est pas archivé.
    archived_by_nom = serializers.CharField(
        source='archived_by.username', read_only=True, default=None)
    # LW29 — masquage PII rendu VISIBLE (au lieu de silencieux) : le front
    # peut afficher les champs PII_FIELDS verrouillés-cadenas plutôt que de
    # laisser croire à une édition qui sera jetée (drop silencieux au PATCH).
    # Même condition EXACTE que get_fields()/to_representation() ci-dessous
    # — source unique, jamais une seconde règle qui pourrait diverger.
    pii_masked = serializers.SerializerMethodField()
    # LW30 — 50 dernières LeadActivity embarquées sur le RETRIEVE seulement
    # (jamais list() — payload) : voir get_fields() plus bas.
    chatter_recent = serializers.SerializerMethodField()
    # PV78 — conception 3D du lead {kwc, image_url}. RETRIEVE SEULEMENT, même
    # porte que chatter_recent : ce bloc coûte une requête devis + une URL
    # pré-signée PAR LEAD, ce qui serait un N+1 franc sur une liste de 50
    # cartes. Voir get_fields() plus bas.
    conception = serializers.SerializerMethodField()
    # CAD150/CAD159 — la PROVENANCE des champs captés par le site
    # (`selectors.provenance_site`) : RETRIEVE SEULEMENT, même porte que
    # `conception` (une requête par lead — jamais sur une liste).
    provenance_site = serializers.SerializerMethodField()
    # AGR404 (contrat AGR1 ``lead_pompage.json``) — les entrées du
    # dimensionnement agricole lues sur le lead, avec leur provenance :
    # RETRIEVE SEULEMENT (une requête d'historique), même porte.
    entrees_pompage = serializers.SerializerMethodField()
    # CIQ402 (contrat CIQ8 ``client_entreprise.json``) — l'identité légale
    # attendue d'un lead pro (manquants, requis_pour). Pur, sans requête ;
    # RETRIEVE SEULEMENT, même porte que les autres blocs de détail.
    identite_entreprise = serializers.SerializerMethodField()
    # CIQ405 (contrat CIQ1 ``lead_pro.json``) — les entrées du moteur C&I
    # lues sur le lead, avec leur provenance : RETRIEVE SEULEMENT (une
    # requête d'historique), même porte ; ``null`` hors commercial/industriel.
    entrees_ci = serializers.SerializerMethodField()
    # CIQ428 — indicateurs INTERNES du vendeur (« audit énergétique
    # obligatoire probable », loi 47-09) : DÉTAIL SEULEMENT, jamais la liste,
    # jamais une sortie client.
    indicateurs_internes = serializers.SerializerMethodField()
    # AGR405 (D-AGR-9, contrat ``lead_pompage.json``) — drapeau
    # d'incohérence entre le type du lead et le mode de ses devis : DÉTAIL
    # SEULEMENT (une requête ventes par lead — jamais sur la liste). Calculé
    # à la lecture ; le type du lead n'est JAMAIS écrit automatiquement.
    incoherence_segment = serializers.SerializerMethodField()
    # AGR406 (contrat ``lead_pompage.json``) — segment SUGGÉRÉ depuis la
    # première page et des mots-clés (``crm/segment_suggere.py``, pur, sans
    # requête) : DÉTAIL SEULEMENT, jamais écrit.
    segment_suggere = serializers.SerializerMethodField()
    # MRY5 — prochaine touche de cadence, ANNOTÉE dans le queryset
    # (``LeadViewSet.get_queryset``), jamais un SerializerMethodField : la
    # liste et le kanban affichent le badge « touche due » pour 50 cartes,
    # une requête par carte serait un N+1 franc. Les trois champs valent
    # ``None``/``False`` quand l'annotation est absente (ex. un `retrieve`
    # servi par un autre queryset) — jamais une exception.
    prochaine_touche_at = serializers.DateTimeField(
        read_only=True, required=False, allow_null=True, default=None)
    prochaine_touche_canal = serializers.CharField(
        read_only=True, required=False, allow_null=True, default=None)
    touche_en_retard = serializers.SerializerMethodField()
    # MRY20 — nombre de TENTATIVES humaines (appel/WhatsApp/e-mail avec un
    # auteur), annoté par `LeadViewSet.get_queryset`. C'est ce chiffre qui dit
    # si un dossier a été assez travaillé pour être classé — et il vaut 0,
    # jamais `None`, quand l'annotation est absente (un `retrieve` servi par
    # un autre queryset ne doit pas afficher un trou).
    nb_tentatives = serializers.SerializerMethodField()
    # LB39 — marqueur d'ANNULATION du dernier changement d'étape. Champ HORS
    # MODÈLE, write-only, jamais persisté (retiré dans validate()) : à lui
    # seul il n'autorise RIEN — il déclenche seulement la vérification
    # serveur `_undo_of_last_stage_change` (le chatter doit porter le
    # mouvement inverse exact, daté de moins de UNDO_WINDOW_SECONDS). La
    # garde funnel reste intégralement en place pour tout autre recul.
    undo = serializers.BooleanField(write_only=True, required=False)
    # Fenêtre d'annulation, alignée sur la durée d'affichage du toast
    # « Annuler » côté client (VX95) avec une marge confortable.
    UNDO_WINDOW_SECONDS = 300
    # ORDRE FONDATEUR 2026-08-01 — « les leads doivent pouvoir REVENIR EN
    # ARRIÈRE d'étape, avec une confirmation avant ». Même patron que ``undo``
    # (champ HORS MODÈLE, write-only, retiré dans validate(), jamais persisté),
    # mais une sémantique différente et volontairement plus large :
    #   • ``undo`` = annulation MACHINE du dernier mouvement, revérifiée contre
    #     le chatter et bornée dans le temps — l'utilisatrice n'affirme rien ;
    #   • ``confirme_recul`` = décision HUMAINE explicite. Le client a montré
    #     une boîte de confirmation nommant le lead et les deux étapes, et
    #     l'utilisatrice a dit oui. Il n'y a donc rien à revérifier contre
    #     l'historique : un recul volontaire est un fait métier légitime (un
    #     devis retombe en relance, un « signé » se dénoue), pas un accident.
    # Ce qu'il n'ouvre PAS : le verrou du lead perdu (vérifié AVANT, comme pour
    # ``undo``) et les actions en MASSE (voir la garde funnel plus bas).
    confirme_recul = serializers.BooleanField(write_only=True, required=False)
    # CAD158 (décision fondateur du 21/09/2026, Q24) — combien de mois couvre
    # la facture DÉCLARÉE dans ce même corps (`mensuelle` | `bimestrielle`).
    # Jamais stocké (aucun champ « périodicité ») : le montant est ramené au
    # mois dans `validate`, et c'est lui qu'on enregistre et qu'on relit.
    facture_periodicite = serializers.CharField(
        write_only=True, required=False, allow_blank=True)

    @staticmethod
    def _canonical_phone(value):
        """Forme canonique '212XXXXXXXXX' d'un numéro marocain saisi librement
        (06 12-34 56 78, +212612…, 00212…). Source unique : le normaliseur des
        ventes (apps.ventes.utils.phone) — pas de logique dupliquée ici. Vide
        ou non normalisable → on conserve la valeur saisie telle quelle (jamais
        de rejet : le formulaire est volontairement permissif).

        25/08/2026 — LANE NUMÉROS INTERNATIONAUX : cette garde ne réécrit la
        saisie QUE quand `normalize_ma_phone` reconnaît un numéro marocain ;
        avant cette date, `normalize_ma_phone` forçait quand même un préfixe
        '212' sur presque tout le reste (le `or value` ci-dessous ne se
        déclenchait donc presque jamais), ce qui CORROMPAIT silencieusement un
        numéro étranger saisi (ex. +33612345678 → '21233612345678') plutôt que
        de le conserver tel quel. `normalize_ma_phone` renvoie désormais None
        pour tout ce qui n'est pas reconnaissable comme marocain, donc un +33
        posté ici relit exactement +33 (voir test_lead_foreign_phone_survives_
        api_write, apps/crm/tests)."""
        if value in (None, ''):
            return value
        from apps.ventes.utils.phone import normalize_ma_phone
        return normalize_ma_phone(value) or value

    def validate_telephone(self, value):
        return self._canonical_phone(value)

    def validate_whatsapp(self, value):
        return self._canonical_phone(value)

    def validate_ville(self, value):
        """VREF — auto-correction de la ville à l'écriture (même règle que
        le webhook site et la sync Odoo) : une graphie connue, une forme
        raccourcie unique (« belksiri » → Mechraa Bel Ksiri) ou une faute de
        frappe sûre est remplacée par le nom canonique du gazetier — le log
        de champ automatique du chatter trace le remplacement. Ambigu ou
        inconnu : le texte reste TEL QUEL (jamais deviné), l'écran
        « Vérifier la ville » prend le relais."""
        if not value:
            return value
        from apps.parametres.villes_resolution import corriger_ville
        return corriger_ville(value)

    def get_devis_auto(self, obj):
        """Prêt pour le devis automatique ? Même règle que l'endpoint
        POST /leads/<id>/devis-auto/ (source unique : devis_auto.py)."""
        # QJR600 (contrat ``devis_auto_pret.json``) — la règle SERVIE
        # structurée : ``manquants_detail`` [{champ, label}] (champ = nom du
        # champ Lead, cible de la puce) et ``requis`` (groupes « l'un des »).
        # ``manquants`` et ``message`` inchangés.
        detail = champs_manquants_detail(obj)
        manquants = [entree['label'] for entree in detail]
        return {
            'pret': not manquants,
            'manquants': manquants,
            'message': message_manquants(manquants) if manquants else None,
            'manquants_detail': detail,
            'requis': champs_requis(obj),
            # AGR403 (D-AGR-4) — {requise, motifs} pour un agricole, null
            # ailleurs : une information, jamais un blocage de `pret`.
            'visite_point_eau_avant_devis': visite_point_eau_avant_devis(obj),
            # CIQ404 (contrat CIQ1, D-CIQ-5) — la colonne qui remplit le
            # groupe pro et la visite AVANT le devis final : commercial et
            # industriel seulement, null ailleurs ; jamais un blocage.
            'source_conso': source_conso(obj),
            'visite_avant_devis': visite_avant_devis(obj),
        }

    def get_next_activity(self, obj):
        """Activité ouverte la plus proche (pour la pastille horloge de la
        carte kanban) : {state: overdue/today/upcoming, due_date, summary}.

        YOPSB13 — sur une LISTE, ``LeadViewSet.list()`` précharge une carte
        {lead_id: Activity} en UNE requête pour toute la page et la pose dans
        le contexte (``next_activity_map``) : on la préfère quand elle existe
        pour éviter une requête PAR LIGNE (N+1). Sans contexte (ex. detail
        unique, ou appel serializer hors vue), on retombe sur la requête
        individuelle — comportement inchangé."""
        try:
            next_activity_map = self.context.get('next_activity_map')
            if next_activity_map is not None:
                act = next_activity_map.get(obj.id)
            else:
                from django.contrib.contenttypes.models import ContentType
                from apps.records.models import Activity
                ct = ContentType.objects.get_for_model(obj.__class__)
                act = (Activity.objects
                       .filter(content_type=ct, object_id=obj.id, done=False,
                               due_date__isnull=False)
                       .order_by('due_date').first())
            if act is None:
                return None
            from apps.records.serializers import activity_state
            return {
                'state': activity_state(act.due_date, False),
                'due_date': act.due_date.isoformat(),
                'summary': act.summary or act.activity_type.nom,
            }
        except Exception:
            return None

    def get_owner_nom(self, obj):
        return getattr(obj.owner, 'username', None)

    def get_owner_poste(self, obj):
        return getattr(obj.owner, 'poste', None) or None

    def get_owner_avatar(self, obj):
        """URL présignée de la photo du responsable (avatar Odoo)."""
        if not obj.owner_id:
            return None
        from authentication.avatars import presign_avatar
        return presign_avatar(getattr(obj.owner, 'avatar_key', ''))

    # FG27 — Score de qualité (lecture seule)
    def get_score(self, obj):
        """CRX22 — sert la colonne PERSISTÉE ``Lead.score``.

        Avant, le badge recalculait le score À LA VOLÉE pour chaque ligne
        alors que le TRI (``ordering_fields``) et « Ma file »
        (``selectors.leads_chauds_non_contactes``, ``score__gte``) filtrent sur
        la COLONNE : deux valeurs différentes pour le même lead, donc une
        liste triée « par score » dont les badges n'étaient pas dans l'ordre.
        Une seule valeur fait foi maintenant — celle que
        ``services.recompute_lead_score`` écrit à chaque édition et que le job
        beat quotidien rafraîchit sur les leads non touchés.

        Repli sur le calcul UNIQUEMENT quand la colonne est encore NULL (leads
        importés avant la migration QJ6, jamais réenregistrés) : le badge ne
        doit pas afficher un trou.
        """
        if obj.score is not None:
            return obj.score
        return compute_score(obj)

    def get_score_label(self, obj):
        return score_label(self.get_score(obj))

    def get_score_reasons(self, obj):
        # VX221 — liste [{facteur, label, points}] triée par points décroissants.
        return score_reasons(obj)

    # FG29 — Âge dans l'étape courante
    def get_stage_since_days(self, obj):
        """Nombre de jours depuis le dernier changement d'étape de ce lead.

        Source : dernière entrée LeadActivity de type MODIFICATION sur le champ
        'stage'. Si aucune → âge depuis la création du lead (première entrée).
        Renvoie None si indétectable.
        """
        try:
            from django.utils import timezone
            # YOPSB13/perf_n1 — sur une LISTE, LeadViewSet.list() précharge une
            # carte {lead_id: dernière date de changement d'étape} en UNE requête
            # (stage_since_map) : sinon c'était 1 requête LeadActivity PAR LIGNE
            # (N+1). Hors contexte (détail) → requête individuelle inchangée.
            stage_since_map = self.context.get('stage_since_map')
            if stage_since_map is not None:
                ref = stage_since_map.get(obj.id) or obj.date_creation
            else:
                from .models import LeadActivity
                last_change = (
                    LeadActivity.objects
                    .filter(lead=obj, kind=LeadActivity.Kind.MODIFICATION,
                            field='stage')
                    .order_by('-created_at')
                    .first()
                )
                ref = last_change.created_at if last_change else obj.date_creation
            if ref is None:
                return None
            now = timezone.now()
            if hasattr(ref, 'tzinfo') and ref.tzinfo is None:
                from django.utils.timezone import make_aware
                ref = make_aware(ref)
            return (now - ref).days
        except Exception:
            return None

    def validate_owner(self, value):
        # Le responsable assigné doit appartenir à la même société.
        request = self.context.get('request')
        if value and request and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value

    def validate_canal(self, value):
        """Le canal doit appartenir aux canaux GÉRÉS de la société (Paramètres →
        CRM) en plus des choices figés du modèle. Vide accepté. Source unique :
        le référentiel Canal — un PATCH avec une clé inconnue est rejeté 400."""
        if value in (None, ''):
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return value
        from .models import Canal as CanalModel
        existe = CanalModel.objects.filter(
            company=company, cle=value, archived=False).exists()
        # Le référentiel peut ne pas être amorcé (lazy seed) : on tolère alors
        # les clés du modèle pour ne pas casser un import/création légitime.
        if not existe and CanalModel.objects.filter(company=company).exists():
            raise serializers.ValidationError('Canal inconnu.')
        return value

    def _undo_of_last_stage_change(self, current, target):
        """LB39 — le PATCH demandé est-il l'ANNULATION du dernier changement
        d'étape de CE lead, dans la fenêtre courte ?

        Vérification côté SERVEUR uniquement : le marqueur ``undo`` du client
        n'est jamais cru sur parole. La dernière entrée de chatter
        ``LeadActivity`` field='stage' doit avoir enregistré EXACTEMENT le
        mouvement inverse (``old_value`` = l'étape demandée, ``new_value`` =
        l'étape actuelle) et dater de moins de ``UNDO_WINDOW_SECONDS``. Toute
        autre marche arrière reste refusée par la garde funnel — on n'ouvre
        donc jamais un recul manuel, seulement le retour en arrière de sa
        PROPRE action, tant que le toast « Annuler » est à l'écran.
        """
        from django.utils import timezone
        from . import stages as stage_mod

        last = (LeadActivity.objects
                .filter(lead=self.instance,
                        kind=LeadActivity.Kind.MODIFICATION,
                        field='stage')
                .order_by('-created_at', '-id')
                .first())
        if last is None or last.created_at is None:
            return False
        age = (timezone.now() - last.created_at).total_seconds()
        if age < 0 or age > self.UNDO_WINDOW_SECONDS:
            return False
        # Le chatter stocke le LIBELLÉ FR (activity._display) ; d'anciennes
        # écritures peuvent porter la clé brute — les deux sont acceptées, la
        # comparaison reste exacte dans les deux cas.
        labels = stage_mod.STAGE_LABELS

        def _is(stored, key):
            return stored is not None and stored in (labels.get(key), key)

        return _is(last.old_value, target) and _is(last.new_value, current)

    def validate(self, attrs):
        # LB39 — marqueur d'annulation : jamais persisté (champ hors modèle),
        # retiré ici pour ne jamais atteindre ``.save()``.
        undo = bool(attrs.pop('undo', False))
        # Ordre fondateur 2026-08-01 : confirmation humaine d'un recul. Jamais
        # persisté non plus (champ hors modèle) — retiré ici comme ``undo``.
        confirme_recul = bool(attrs.pop('confirme_recul', False))
        # CAD158 — une facture déclarée sur DEUX mois est ramenée au mois
        # AVANT d'être enregistrée (le moteur lit un montant mensuel). Refus
        # qui NOMME le champ : période inconnue, ou période sans montant.
        periodicite = (attrs.pop('facture_periodicite', '') or '').strip()
        if periodicite:
            from .services import facture_au_mois, refus_periodicite_facture
            refus = refus_periodicite_facture(periodicite)
            if refus:
                raise serializers.ValidationError(
                    {'facture_periodicite': [refus]})
            montants = [champ for champ in ('facture_hiver', 'facture_ete')
                        if attrs.get(champ) is not None]
            if not montants:
                raise serializers.ValidationError({'facture_periodicite': [
                    '« Période de la facture » : indiquez le montant de la '
                    'facture dans la même saisie.']})
            for champ in montants:
                attrs[champ] = facture_au_mois(attrs[champ], periodicite)
        # MRY22 — MOTIF DE PERTE OBLIGATOIRE. « Perdu sans raison » est la
        # ligne qui ne sert à personne : elle sort le lead du pipeline sans
        # rien apprendre, et le KPI « perdus avec motif » (MRY21) ne peut plus
        # rien dire. Un motif déjà posé sur l'instance suffit (on ne redemande
        # pas un motif à qui ne fait que re-cocher la case).
        if attrs.get('perdu') is True:
            motif = (attrs.get('motif_perte')
                     or getattr(self.instance, 'motif_perte', None) or '')
            if not str(motif).strip():
                raise serializers.ValidationError(
                    {'motif_perte': 'Motif de perte obligatoire.'})
        # Garde funnel côté serveur (aligné sur la règle bulk _bulk_stage_allowed):
        # en MISE À JOUR, un lead perdu ne change pas d'étape, et un recul dans
        # l'entonnoir doit être EXPLICITEMENT assumé (Froid = parking, jamais
        # une régression : _bulk_stage_allowed l'autorise déjà des deux côtés).
        if self.instance is not None and 'stage' in attrs:
            from .services import _bulk_stage_allowed
            current = self.instance.stage
            target = attrs['stage']
            if target != current:
                # Verrou du lead perdu : il PRÉCÈDE toute échappatoire — ni
                # ``undo`` ni ``confirme_recul`` ne le déverrouillent.
                if self.instance.perdu:
                    raise serializers.ValidationError(
                        {'stage': 'Lead perdu — étape non modifiable.'})
                if not _bulk_stage_allowed(current, target):
                    # DEUX échappatoires, et deux seulement :
                    # LB39 — l'annulation, validée serveur, du dernier
                    # changement d'étape de ce lead (le toast « Annuler » de
                    # VX95 PATCHait en arrière et se prenait un 400
                    # systématique — l'undo était mort en production) ;
                    # ordre fondateur 2026-08-01 — la confirmation humaine
                    # explicite d'un recul volontaire (le client a montré une
                    # boîte nommant le lead et les deux étapes). Sans l'un des
                    # deux, un recul nu reste un 400 : le refus par défaut est
                    # inchangé, c'est la seule manière d'empêcher un
                    # glisser-déposer maladroit de défaire un pipeline.
                    if not (confirme_recul
                            or (undo and self._undo_of_last_stage_change(current, target))):
                        raise serializers.ValidationError(
                            {'stage': "On ne recule pas une étape."})
        # ORDRE FONDATEUR (24/08/2026) — le GPS ne doit JAMAIS être écrasé ni
        # supplanté par l'adresse. Le Lead Workspace (LW9, draftCore.js) ne
        # PATCH déjà que les clés réellement modifiées (dirty keys) — éditer
        # l'adresse seule n'envoie donc jamais gps_lat/gps_lng. Ce garde est
        # une DÉFENSE EN PROFONDEUR pour tout AUTRE appelant (import, script,
        # futur écran) : une mise à jour qui n'apporte pas de nouvelles
        # coordonnées EXPLICITES (vide/nulle) ne doit jamais effacer un GPS
        # déjà posé sur ce lead.
        # 08/09/2026 (relevé fondateur) — la garde bloquait AUSSI l'humain :
        # impossible d'EFFACER un GPS depuis le formulaire alors qu'on peut
        # le MODIFIER. L'écran envoie ``effacer_gps: true`` quand
        # l'utilisateur vide explicitement les champs : ce geste-là passe ;
        # tout autre appelant (import, script, webhook) reste protégé.
        effacer_gps = bool((self.initial_data or {}).get('effacer_gps'))
        if self.instance is not None and not effacer_gps:
            for gps_field in ('gps_lat', 'gps_lng'):
                if (gps_field in attrs and attrs[gps_field] in (None, '')
                        and getattr(self.instance, gps_field) is not None):
                    attrs.pop(gps_field)
        # Champs personnalisés (T11) : valider/nettoyer contre les définitions
        # du module « lead ». À la création on valide toujours (champs
        # obligatoires) ; en mise à jour, uniquement si custom_data est fourni
        # (pour ne pas bloquer un PATCH d'un autre champ / édition en place).
        is_create = self.instance is None
        if is_create or 'custom_data' in attrs:
            from apps.customfields.serializers import validate_custom_data
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            if company is not None:
                attrs['custom_data'] = validate_custom_data(
                    'lead', company, attrs.get('custom_data'))
        self._poser_provenances_pompage(attrs)
        self._valider_dossier_subvention(attrs)
        self._valider_colonnes_pro(attrs)
        self._poser_provenances_pro(attrs)
        return attrs

    # CIQ401 (contrat CIQ1 ``lead_pro.json``) — DRF n'appelle pas
    # ``Model.clean`` : les règles croisées des colonnes pro vivent ici (les
    # règles par champ sont les ``validators`` du modèle).
    def _valider_colonnes_pro(self, attrs):
        instance = self.instance

        def _valeur(champ):
            if champ in attrs:
                return attrs[champ]
            return getattr(instance, champ, None)

        if 'heure_debut' in attrs or 'heure_fin' in attrs:
            debut, fin = _valeur('heure_debut'), _valeur('heure_fin')
            if debut is not None and fin is not None and debut >= fin:
                champ = 'heure_fin' if 'heure_fin' in attrs else 'heure_debut'
                raise serializers.ValidationError({champ: [
                    "« Heure de fin » : elle doit être après l'heure de "
                    'début.']})
        if attrs.get('reponses_categorie') is not None:
            reponses = attrs['reponses_categorie']
            categorie = _valeur('categorie_commerciale')
            cles = Lead.REPONSES_CATEGORIE_CLES
            permises = (set(cles.get(categorie, ())) if categorie
                        else {c for liste in cles.values() for c in liste})
            if not isinstance(reponses, dict) or set(reponses) - permises:
                raise serializers.ValidationError({'reponses_categorie': [
                    "« Réponses propres à l'activité » : seules les questions "
                    "de la catégorie déclarée sont acceptées."]})
        if attrs.get('releve_conso') is not None:
            from .models import normaliser_releve_conso
            attrs['releve_conso'] = normaliser_releve_conso(
                attrs['releve_conso'])

    # CIQ401 — une valeur pro SAISIE dans l'ERP (fiche ou appel) porte sa
    # provenance, posée ici et jamais par le corps (colonnes ``*_source`` en
    # lecture seule). Le cos φ n'a pas ``declare`` dans son vocabulaire : il
    # se lit sur la facture. La source ne change que si la valeur change ;
    # une valeur vidée vide sa source.
    _PROVENANCES_PRO_SAISIE = (
        ('tension_raccordement', 'tension_source', 'declare'),
        ('compteur_puissance_kva', 'puissance_souscrite_source', 'declare'),
        ('surface_toiture_m2', 'surface_source', 'declare'),
        ('cos_phi', 'cos_phi_source', 'facture'),
    )

    def _poser_provenances_pro(self, attrs):
        instance = self.instance
        for valeur, source, origine in self._PROVENANCES_PRO_SAISIE:
            if valeur not in attrs:
                continue
            if instance is not None and getattr(instance, valeur) == attrs[
                    valeur]:
                continue
            attrs[source] = (origine if attrs[valeur] not in (None, '')
                             else None)

    #: AGR522 (contrat ``lead_dossier_subvention.json``, ``exemple_400``).
    MESSAGE_DATE_SUBVENTION = (
        "La date est obligatoire pour l'état « déposé », « accordé » ou "
        '« refusé ».')

    def _valider_dossier_subvention(self, attrs):
        if ('dossier_subvention' not in attrs
                and 'dossier_subvention_le' not in attrs):
            return
        instance = self.instance
        etat = (attrs['dossier_subvention'] if 'dossier_subvention' in attrs
                else getattr(instance, 'dossier_subvention', None))
        date = (attrs['dossier_subvention_le']
                if 'dossier_subvention_le' in attrs
                else getattr(instance, 'dossier_subvention_le', None))
        if etat in ('depose', 'accorde', 'refuse') and date is None:
            raise serializers.ValidationError(
                {'dossier_subvention_le': [self.MESSAGE_DATE_SUBVENTION]})

    # AGR400 — une valeur de pompage SAISIE dans l'ERP porte sa provenance,
    # posée ici (jamais par le corps : les colonnes ``*_source`` et
    # ``carburant_prix_declare_le`` sont en lecture seule). Une valeur effacée
    # efface sa provenance ; une valeur inchangée ne touche à rien.
    _PROVENANCES_POMPAGE_SAISIE = (
        ('niveau_statique_m', 'niveau_statique_source', 'declare'),
        ('debit_forage_m3h', 'debit_forage_source', 'client'),
        ('besoin_eau_m3j', 'besoin_eau_source', 'client'),
        ('pompe_hmt_m', 'pompe_hmt_source', 'declaree'),
    )

    def _poser_provenances_pompage(self, attrs):
        instance = self.instance

        def _change(champ):
            return champ in attrs and (
                instance is None or getattr(instance, champ) != attrs[champ])

        for valeur, source, origine in self._PROVENANCES_POMPAGE_SAISIE:
            if _change(valeur):
                attrs[source] = origine if attrs[valeur] is not None else None
        # Q17 — le prix du carburant est DÉCLARÉ et DATÉ : la date est celle
        # du jour où le prix change, posée par le serveur.
        if _change('carburant_prix_unitaire_mad'):
            from core.dates import aujourd_hui_local
            attrs['carburant_prix_declare_le'] = (
                aujourd_hui_local()
                if attrs['carburant_prix_unitaire_mad'] is not None else None)

    class Meta:
        model = Lead
        fields = '__all__'
        # company/source/external refs are set server-side, never trusted from
        # input. The lead→client link is resolved server-side too (no-duplicate
        # rules in services.py), never accepted from the browser.
        # L'archivage se pilote par les actions archiver/restaurer, jamais par
        # un PATCH direct du corps.
        read_only_fields = [
            'company', 'external_system', 'external_id', 'client',
            'is_archived', 'archived_by', 'archived_at',
            # CRX15 — triplet de soft-delete VERROUILLÉ, par parité exacte avec
            # `is_archived` juste au-dessus : il ne se pilote que par la
            # suppression (`SoftDeleteModel.soft_delete`/`restore`), jamais par
            # un PATCH direct du corps. Écrivable, `is_deleted: true` faisait
            # DISPARAÎTRE le lead des listes sans écrire de `DeletionRecord`
            # (donc sans corbeille ni undo) et en contournant la garde 409 qui
            # refuse la suppression d'un lead porteur de devis.
            'is_deleted', 'deleted_at', 'deleted_by',
            'first_contacted_at',  # FG28 — posé server-side uniquement
            'updated_by',  # VX98 — posé server-side (perform_update) uniquement
            # B3 — toiture 3D : pin/contour bruts saisis par le client
            # (webhook site, posés server-side). Exposés en LECTURE SEULE sur la
            # fiche lead pour que la page de conception authentifiée réhydrate la
            # toiture épinglée du client ; jamais réécrits via un PATCH du corps.
            # CAD150 (décision fondateur du 21/09/2026) — `bill_kwh` en SORT :
            # les champs captés par le site sont TOUJOURS éditables par la
            # commerciale, leur provenance reste visible (`provenance_site`).
            'roof_point', 'roof_outline',
            # AGR400 — provenances et date du prix : posées par le serveur
            # (sérialiseur, webhook du site, validation de visite), jamais
            # saisissables à la main.
            'niveau_statique_source', 'debit_forage_source',
            'besoin_eau_source', 'pompe_hmt_source',
            'carburant_prix_declare_le',
            # CIQ401 — provenances des colonnes pro : posées par le serveur
            # selon le chemin d'écriture (fiche, webhook, visite).
            'tension_source', 'puissance_souscrite_source', 'surface_source',
            'cos_phi_source',
            # ALEA16 — miroir serveur ARC56 : ``tiers`` est posé par le pont
            # lead → répertoire unifié (resolve_client_for_lead + miroir
            # ARC18), jamais par le corps. Inscriptible, il acceptait le Tiers
            # d'une AUTRE société ; il reste RENDU en lecture.
            'tiers',
        ]

    # FG20 — coordonnées personnelles masquées sans ``client_pii_voir``.
    # CRX19 — SOURCE UNIQUE (module) partagée avec le masquage du chatter :
    # deux listes divergentes, c'est un champ masqué sur la fiche et lisible
    # dans son historique.
    PII_FIELDS = LEAD_PII_FIELDS

    def _pii_masked(self):
        """LW29 — condition UNIQUE de masquage PII, réutilisée par
        get_fields()/to_representation() ET par le champ calculé
        ``pii_masked`` — jamais une seconde règle qui pourrait diverger."""
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return user is not None and not getattr(user, 'can_view_client_pii', True)

    def get_fields(self):
        fields = super().get_fields()
        if self._pii_masked():
            for name in self.PII_FIELDS:
                if name in fields:
                    fields[name].read_only = True
        # LW30 — chatter_recent n'est embarqué que sur le RETRIEVE (flag de
        # contexte posé par LeadViewSet.retrieve() uniquement) ; ABSENT du
        # payload list() — jamais juste null, la clé elle-même disparaît.
        if not self.context.get('include_chatter_recent'):
            fields.pop('chatter_recent', None)
            # PV78 — même porte : ``include_chatter_recent`` est le marqueur
            # « vue DÉTAIL » du dépôt (posé UNIQUEMENT par
            # ``LeadViewSet.retrieve``). On le RÉUTILISE plutôt que d'ajouter
            # un second drapeau qu'il faudrait poser au même endroit — et la
            # conception, qui coûte une requête + une URL pré-signée par lead,
            # ne descend donc jamais dans une liste.
            fields.pop('conception', None)
            # CAD150 — la provenance « saisie sur le site » coûte une requête
            # par lead : détail seulement, même porte.
            fields.pop('provenance_site', None)
            # AGR404 — `entrees_pompage` : détail seulement, même porte.
            fields.pop('entrees_pompage', None)
            # CIQ402 — `identite_entreprise` : détail seulement, même porte.
            fields.pop('identite_entreprise', None)
            # CIQ405 — `entrees_ci` : détail seulement, même porte.
            fields.pop('entrees_ci', None)
            # CIQ428 — `indicateurs_internes` : détail seulement, même porte.
            fields.pop('indicateurs_internes', None)
            # AGR405 — `incoherence_segment` : détail seulement, même porte.
            fields.pop('incoherence_segment', None)
            # AGR406 — `segment_suggere` : détail seulement, même porte.
            fields.pop('segment_suggere', None)
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self._pii_masked():
            for name in self.PII_FIELDS:
                if name in data:
                    data[name] = None
        return data

    def get_pii_masked(self, obj):
        """LW29 — expose EXPLICITEMENT si les champs PII_FIELDS sont
        masqués pour l'utilisateur courant, pour que le front les rende
        verrouillés-cadenas au lieu de laisser croire à une édition qui
        sera jetée (drop silencieux au PATCH)."""
        return self._pii_masked()

    def get_nb_tentatives(self, obj) -> int:
        """MRY20 — lit l'annotation ; 0 par défaut, jamais une requête."""
        return int(getattr(obj, 'nb_tentatives', 0) or 0)

    def get_touche_en_retard(self, obj) -> bool:
        """MRY5 — une touche de cadence est-elle ÉCHUE sur ce lead ?

        Lit l'annotation ``touche_en_retard_flag`` posée par
        ``LeadViewSet.get_queryset`` (Exists) ; ``False`` quand l'annotation
        est absente — jamais une requête supplémentaire par lead."""
        return bool(getattr(obj, 'touche_en_retard_flag', False))

    def get_conception(self, obj):
        """PV78 — ``{kwc, image_url}`` de la conception 3D du lead.

        Lecture cross-app par le SÉLECTEUR de l'app cible
        (``crm.selectors.conception_3d_du_lead`` → ``ventes.selectors``), jamais
        par un import des modèles ventes. Company-scopée côté ventes. Les deux
        clés sont TOUJOURS là : un lead sans devis calepiné vaut deux valeurs
        vides, jamais une clé absente.
        """
        from .selectors import conception_3d_du_lead
        return conception_3d_du_lead(obj)

    @extend_schema_field(serializers.DictField())
    def get_entrees_ci(self, obj):
        """CIQ405 — ``{entrees, manquants, informations}`` (contrat CIQ1) :
        la SEULE lecture lead → entrées du moteur C&I."""
        return self._entrees_ci(obj)

    def _entrees_ci(self, obj):
        """CIQ428 — ``entrees_ci`` calculé UNE fois par lead sérialisé (lu
        par ``entrees_ci`` ET par ``indicateurs_internes``)."""
        from .selectors import entrees_ci_du_lead
        cache = getattr(self, '_cache_entrees_ci', None)
        if cache is None:
            cache = self._cache_entrees_ci = {}
        cle = id(obj)
        if cle not in cache:
            cache[cle] = entrees_ci_du_lead(obj)
        return cache[cle]

    @extend_schema_field(serializers.DictField())
    def get_indicateurs_internes(self, obj):
        """CIQ428 — ``{audit_47_09}`` : l'indicateur INTERNE « audit
        énergétique obligatoire probable » sur la seule électricité
        DÉCLARÉE (``apps/crm/audit_energetique.py``) ; ``None`` hors
        commercial / industriel. Vu par le vendeur seulement."""
        from .audit_energetique import indicateur_du_lead
        return {'audit_47_09': indicateur_du_lead(
            obj.type_installation, self._entrees_ci(obj))}

    @extend_schema_field(serializers.DictField())
    def get_identite_entreprise(self, obj):
        """CIQ402 — bloc ``identite_entreprise`` (contrat CIQ8) du lead :
        entreprise si le lead est commercial/industriel ou porte une
        raison sociale ; la raison sociale est ``societe``."""
        from .models import identite_entreprise
        entreprise = (obj.type_installation in ('commercial', 'industriel')
                      or bool((obj.societe or '').strip()))
        return identite_entreprise(
            entreprise=entreprise, raison_sociale=obj.societe,
            raison_a_confirmer=False, ice=obj.ice, rc=obj.rc,
            if_fiscal=obj.if_fiscal, adresse_siege=obj.adresse_siege,
            adresse=obj.adresse)

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_incoherence_segment(self, obj):
        """AGR405 — ``null`` ou ``{segment_lead, mode_devis, devis, message}``
        (contrat ``lead_pompage.json``). Lecture seule, D-AGR-9."""
        from apps.ventes.selectors import devis_par_mode_pour_lead
        return incoherence_segment(
            obj.type_installation,
            devis_par_mode_pour_lead(obj.pk, obj.company))

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_segment_suggere(self, obj):
        """AGR406 — ``null`` ou ``{valeur, raison}`` ; lecture seule."""
        from .segment_suggere import segment_suggere
        return segment_suggere(obj)

    @extend_schema_field(serializers.DictField())
    def get_entrees_pompage(self, obj):
        """AGR404 — ``{entrees, manquants}`` (contrat ``lead_pompage``) :
        la SEULE lecture lead → entrées du moteur agricole."""
        from .selectors import entrees_pompage_du_lead
        return entrees_pompage_du_lead(obj)

    @extend_schema_field(serializers.DictField())
    def get_provenance_site(self, obj):
        """CAD150/CAD159 — ``{champ: {valeur, le, ecrasee}}`` des champs
        captés par le site (contrat ``lead_provenance_site``)."""
        from .selectors import provenance_site
        return provenance_site(obj)

    def get_chatter_recent(self, obj):
        """LW30 — 50 dernières LeadActivity (auto + notes), épingle-d'abord
        (tri LW28), ``select_related('user','attachment')`` pour éviter tout
        N+1 (même garde que LW8). Calculée uniquement quand get_fields() a
        gardé le champ (RETRIEVE) — jamais appelée sur une liste.

        CRX19 — le CONTEXTE est propagé : sans lui, le sérialiseur d'activité
        ne connaît pas l'utilisateur et le masquage PII du chatter ne
        s'appliquerait pas sur cette surface."""
        rows = (
            obj.activites
            .select_related('user', 'attachment')
            .order_by('-pinned', '-created_at')[:50]
        )
        return LeadActivitySerializer(
            rows, many=True, context=self.context).data

    def get_client_nom(self, obj):
        if not obj.client_id:
            return None
        c = obj.client
        return f"{c.nom} {c.prenom or ''}".strip()

    @extend_schema_field(serializers.CharField())
    def get_ville_effective(self, obj):
        from .selectors import ville_effective
        return ville_effective(obj)

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_client_ecart(self, obj):
        """QJR590 — ``[nom|prenom|email|telephone|adresse]`` divergents."""
        from .services import client_ecart
        return client_ecart(obj)

    def get_devis(self, obj):
        # Devis « empilés » sur le lead, du plus récent au plus ancien.
        # A4 — on expose le chantier lié (s'il existe) et l'option acceptée pour
        # que la fiche lead propose en ligne « Générer la facture » et « Créer le
        # chantier » (sans doublon) après acceptation.
        # YOPSB13 — sur une LISTE, ``LeadViewSet.list()`` précharge les
        # chantiers de TOUS les devis de la page en UNE requête et la pose
        # dans le contexte (``chantier_map``), pour éviter une requête
        # Installation PAR LIGNE (N+1). Sans contexte, on retombe sur l'appel
        # individuel — comportement inchangé.
        # YOPSB13/perf_n1 — ``obj.devis.order_by(...)`` clone le manager et
        # IGNORE le cache prefetch (``prefetch_related('devis')`` posé par
        # ``LeadViewSet``), ré-exécutant une requête PAR ligne (N+1). On lit le
        # cache via ``.all()`` puis on trie en Python (ordre identique), sans
        # importer le modèle ``ventes`` (frontière inter-app respectée).
        rows = sorted(
            obj.devis.all(),
            key=lambda d: (d.date_creation is not None, d.date_creation),
            reverse=True,
        )
        chantier_map = self.context.get('chantier_map')
        if chantier_map is not None:
            chantiers = {d.id: chantier_map.get(d.id) for d in rows}
        else:
            from apps.installations.selectors import (
                installation_summaries_for_devis,
            )
            chantiers = installation_summaries_for_devis(rows)
        # L-NIV-UI (24/08/2026) — niveau/otp_lecture du ShareLink DÉJÀ EXISTANT
        # (jamais un mint) : sans ça, l'onglet Devis (DevisTab.jsx) n'affichait
        # le badge de niveau qu'après un premier clic sur le sélecteur/case,
        # car son état `linkMeta` ne se remplissait qu'à partir de la réponse
        # d'un POST share-link explicite. Lecture cross-app via
        # `apps.ventes.selectors` (jamais `apps.ventes.models`).
        # YOPSB13 — MÊME garde N+1 que ``chantier_map`` : sur une LISTE,
        # ``LeadViewSet.list()`` précharge les ShareLink de TOUS les devis de
        # la page en UNE requête (``share_link_map`` dans le contexte). Sans
        # ce préchargement (retrieve, usage direct du serializer), on retombe
        # sur l'appel pour ce lead seul — comportement identique.
        share_link_map = self.context.get('share_link_map')
        if share_link_map is not None:
            niveau_map = share_link_map
        else:
            from apps.ventes.selectors import share_link_niveau_map
            niveau_map = share_link_niveau_map([d.id for d in rows])
        # QJ-VUES (fondateur 09/09/2026) — lectures CLIENT du devis (compteur +
        # dernière consultation), TOUJOURS présentes sur la fiche lead : le
        # commercial voit d'un coup d'œil combien de fois chaque devis a été
        # ouvert, sans ouvrir quoi que ce soit. Agrégé sur TOUS les ShareLink
        # du devis (expirés compris — l'historique ne se remet pas à zéro),
        # via `apps.ventes.selectors.share_link_lecture_map` (jamais les
        # modèles ventes). Même garde N+1 que `share_link_map` : la LISTE
        # précharge (`lecture_map` du contexte), le détail interroge pour ce
        # lead seul. `None` = devis jamais partagé (le front dit « jamais
        # envoyé/ouvert »).
        lecture_map = self.context.get('lecture_map')
        if lecture_map is None:
            from apps.ventes.selectors import share_link_lecture_map
            lecture_map = share_link_lecture_map([d.id for d in rows])
        # QJR516 (contrat QJR500 ``lead_devis_ligne.json``) — chaque ligne
        # porte le verdict de modifiabilité du devis (modifiable,
        # raison_non_modifiable, revision_possible) + is_active, servis par
        # `apps.ventes.selectors.devis_modifiabilite` — la MÊME règle que le
        # détail du devis, jamais recopiée ici.
        from apps.ventes.selectors import devis_modifiabilite
        return [
            {
                'id': d.id,
                'reference': d.reference,
                'statut': d.statut,
                'total_ttc': str(d.total_ttc),
                'date_creation': d.date_creation.isoformat(),
                'option_acceptee': d.option_acceptee,
                'chantier': chantiers.get(d.id),
                'share_link': niveau_map.get(d.id),
                'lecture': lecture_map.get(d.id),
                **devis_modifiabilite(d),
                # QJR535 (contrat ``lead_devis_ligne.json``) — `version` et
                # `superseded_by` (id du remplaçant) : attributs de
                # l'instance déjà chargée (aucun import de ventes.models). La
                # carte d'une V1 remplacée s'affiche « Remplacé par … » côté
                # cockpit au lieu de rester vivante et renvoyable.
                'version': d.version,
                'superseded_by': d.superseded_by_id,
                # QJR566 (contrat ``lead_devis_ligne.json``) — date de la
                # dernière correction après envoi (marqueur
                # ``etude_params.resync_apres_envoi``), lue sur l'instance
                # déjà chargée ; null si jamais corrigé. Le cockpit dit alors
                # « lu le X — avant la correction du Y ».
                'corrige_le': _corrige_le(d),
            }
            for d in rows
        ]


def _corrige_le(devis):
    """QJR566 — ISO de ``etude_params.resync_apres_envoi.date`` ou ``None``
    (marqueur absent, booléen hérité ou sans date)."""
    params = getattr(devis, 'etude_params', None)
    marqueur = params.get('resync_apres_envoi') if isinstance(params, dict) else None
    if isinstance(marqueur, dict):
        return marqueur.get('date') or None
    return None


def _tag_en_usage(company, nom):
    """Nombre de leads dont le champ texte ``tags`` référence ce libellé.

    ``Lead.tags`` est un texte libre séparé par des virgules ; on compte les
    leads qui portent ce libellé comme jeton (insensible à la casse)."""
    from .models import Lead
    nom = (nom or '').strip()
    if not nom:
        return 0
    cible = nom.casefold()
    n = 0
    for raw in Lead.objects.filter(
            company=company, tags__icontains=nom).values_list('tags', flat=True):
        if any((t or '').strip().casefold() == cible
               for t in (raw or '').split(',')):
            n += 1
    return n


def _motif_en_usage(company, nom):
    """Nombre de leads dont ``motif_perte`` (texte libre) vaut ce libellé."""
    from .models import Lead
    nom = (nom or '').strip()
    if not nom:
        return 0
    return Lead.objects.filter(
        company=company, motif_perte__iexact=nom).count()


class LeadTagSerializer(serializers.ModelSerializer):
    # Nombre de leads référençant cette étiquette — l'UI désactive la
    # suppression et propose l'archivage si > 0 (L780).
    en_usage = serializers.SerializerMethodField()

    class Meta:
        from .models import LeadTag
        model = LeadTag
        fields = ['id', 'nom', 'couleur', 'archived', 'en_usage']

    def get_en_usage(self, obj):
        return _tag_en_usage(obj.company, obj.nom)


class MotifPerteSerializer(serializers.ModelSerializer):
    # Nombre de leads utilisant ce motif de perte (L779).
    en_usage = serializers.SerializerMethodField()

    class Meta:
        from .models import MotifPerte
        model = MotifPerte
        # PUB28 — est_junk distingue un motif JUNK (numéro invalide, spam/bot…)
        # d'un motif de perte commercial réel (prix, concurrent…).
        fields = ['id', 'nom', 'archived', 'est_junk', 'en_usage']

    def get_en_usage(self, obj):
        return _motif_en_usage(obj.company, obj.nom)


class CanalSerializer(serializers.ModelSerializer):
    # Nombre de leads utilisant ce canal — l'UI désactive la suppression si > 0.
    en_usage = serializers.SerializerMethodField()

    class Meta:
        from .models import Canal
        model = Canal
        fields = ['id', 'cle', 'libelle', 'ordre', 'protege', 'archived', 'en_usage']
        read_only_fields = ['protege']

    def get_en_usage(self, obj):
        from .models import Lead
        return Lead.objects.filter(company=obj.company, canal=obj.cle).count()

    def validate_cle(self, value):
        # La clé d'un canal protégé (ex. 'site_web') ne peut pas être renommée :
        # le webhook du site web en dépend.
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise serializers.ValidationError(
                "La clé d'un canal protégé ne peut pas être modifiée.")
        return value


class WebsiteLeadPayloadSerializer(serializers.ModelSerializer):
    """QX16 — surface LECTURE SEULE des payloads bruts d'intake, pour que
    « jamais perdre un lead » (webhooks.py) soit vérifiable/actionnable, pas
    juste une promesse en commentaire. Le rejeu s'effectue via l'action
    ``replay`` du viewset (jamais depuis ce sérialiseur, jamais un champ
    modifiable ici).

    CRX2 — ``source``/``source_display`` disent de quel intake vient la ligne
    (site web ou Meta Lead Ads) : sans eux, l'écran ne pourrait pas expliquer
    ce qu'un rejeu va faire."""
    lead_nom = serializers.CharField(source='lead.nom', read_only=True, default=None)
    source_display = serializers.CharField(
        source='get_source_display', read_only=True)

    class Meta:
        model = WebsiteLeadPayload
        fields = [
            'id', 'company', 'source', 'source_display', 'payload',
            'remote_addr', 'received_at', 'processed', 'error', 'lead',
            'lead_nom',
        ]
        read_only_fields = fields


class ParrainageSerializer(serializers.ModelSerializer):
    """N98 — parrainage. Société posée côté serveur ; parrain/filleul vérifiés
    appartenir à la même société (multi-tenant)."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    parrain_nom = serializers.CharField(
        source='parrain.nom', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # DC14 — nom du filleul à afficher : le FK lié prime sur le texte libre
    # (``filleul_nom`` peut diverger du client/lead réellement référencé).
    filleul_display_nom = serializers.CharField(read_only=True)

    class Meta:
        model = Parrainage
        fields = [
            'id', 'company', 'parrain', 'parrain_nom', 'filleul_lead',
            'filleul_client', 'filleul_nom', 'filleul_display_nom',
            'statut', 'statut_display',
            'recompense', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def _same_company(self, obj):
        req = self.context.get('request')
        return not (obj and req and obj.company_id != req.user.company_id)

    def validate_parrain(self, value):
        if not self._same_company(value):
            raise serializers.ValidationError('Client inconnu.')
        return value

    def validate_filleul_client(self, value):
        if value and not self._same_company(value):
            raise serializers.ValidationError('Client inconnu.')
        return value

    def validate_filleul_lead(self, value):
        if value and not self._same_company(value):
            raise serializers.ValidationError('Lead inconnu.')
        return value


# DC12 — Profil site/énergie réutilisable par client ─────────────────────────

class SiteProfileSerializer(serializers.ModelSerializer):
    """DC12 — profil site/énergie réutilisable, attaché au client.

    Société posée CÔTÉ SERVEUR (HiddenField — jamais lue du corps de requête,
    multi-tenant). Le client référencé doit appartenir à la même société
    (validate_client). Une seule fiche par client (OneToOne)."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())

    class Meta:
        model = SiteProfile
        fields = [
            'id', 'company', 'client',
            'facture_hiver', 'facture_ete', 'ete_differente',
            'conso_mensuelle_kwh', 'tranche_onee', 'raccordement',
            'regularisation_8221', 'type_installation',
            'pompe_actuelle_cv', 'pompe_hmt_m', 'pompe_debit_m3h',
            'type_toiture', 'surface_toiture_m2', 'orientation',
            'inclinaison_deg', 'ombrage', 'ombrage_notes',
            'gps_lat', 'gps_lng',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate_client(self, value):
        req = self.context.get('request')
        if req and value and value.company_id != req.user.company_id:
            raise serializers.ValidationError('Client inconnu.')
        return value


# FG36 — Modèles de messages WhatsApp/SMS ─────────────────────────────────────

class MessageTemplateSerializer(serializers.ModelSerializer):
    """Modèle de message CRM (WhatsApp/SMS). Lecture tout rôle, écriture admin."""
    langue_display = serializers.CharField(
        source='get_langue_display', read_only=True)

    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'nom', 'langue', 'langue_display', 'corps',
            'archived', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


# QJ20 — Rendez-vous (visites commerciales/techniques) ───────────────────────

class AppointmentSerializer(serializers.ModelSerializer):
    """QJ20 — Rendez-vous sur un lead.

    La société est posée côté serveur (HiddenField depuis l'utilisateur courant
    — multi-tenant, jamais lu du corps de requête). Le lead doit appartenir à la
    même société (validate_lead).
    ``statut_display`` et ``lead_nom`` sont en lecture seule pour l'UI.
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None)

    class Meta:
        model = Appointment
        fields = [
            'id', 'company', 'lead', 'lead_nom',
            'scheduled_at', 'statut', 'statut_display',
            'notes', 'reminder_sent', 'created_by',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['reminder_sent', 'created_by',
                            'date_creation', 'date_modification']

    def validate_lead(self, value):
        req = self.context.get('request')
        if req and value.company_id != getattr(req.user, 'company_id', None):
            raise serializers.ValidationError('Lead inconnu.')
        return value


# ── FG39 — ObjectifCommercial / KPI Target ────────────────────────────────────

class ObjectifCommercialSerializer(_CompanyScopedRelationsMixin,
                                   serializers.ModelSerializer):
    """Sérialise un objectif commercial + champs lecture optionnels."""

    # CRX13 — le porteur de l'objectif doit être un utilisateur de la société.
    scoped_relations = ('owner',)

    owner_nom = serializers.SerializerMethodField()
    metric_display = serializers.SerializerMethodField()
    period_type_display = serializers.SerializerMethodField()

    class Meta:
        model = ObjectifCommercial
        fields = [
            'id', 'company', 'owner', 'owner_nom',
            'metric', 'metric_display',
            'period_type', 'period_type_display',
            'period_year', 'period_month', 'period_quarter',
            'cible', 'notes',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'company', 'created_by', 'date_creation', 'date_modification',
        ]

    def get_owner_nom(self, obj):
        return getattr(obj.owner, 'username', None)

    def get_metric_display(self, obj):
        return obj.get_metric_display()

    def get_period_type_display(self, obj):
        return obj.get_period_type_display()

    def validate(self, attrs):
        pt = attrs.get('period_type', getattr(self.instance, 'period_type', None))
        if pt == 'month' and not attrs.get(
                'period_month', getattr(self.instance, 'period_month', None)):
            raise serializers.ValidationError(
                {'period_month': 'Requis pour un objectif mensuel.'}
            )
        if pt == 'quarter' and not attrs.get(
                'period_quarter', getattr(self.instance, 'period_quarter', None)):
            raise serializers.ValidationError(
                {'period_quarter': 'Requis pour un objectif trimestriel.'}
            )
        month = attrs.get('period_month', getattr(self.instance, 'period_month', None))
        if month is not None and not (1 <= month <= 12):
            raise serializers.ValidationError(
                {'period_month': 'Doit être entre 1 et 12.'}
            )
        quarter = attrs.get('period_quarter', getattr(self.instance, 'period_quarter', None))
        if quarter is not None and not (1 <= quarter <= 4):
            raise serializers.ValidationError(
                {'period_quarter': 'Doit être entre 1 et 4.'}
            )
        return attrs


class ObjectifAttainmentSerializer(serializers.Serializer):
    """Lecture seule — objectif + réalisé + taux d'atteinte."""
    id = serializers.IntegerField()
    metric = serializers.CharField()
    metric_display = serializers.CharField()
    period_type = serializers.CharField()
    period_year = serializers.IntegerField()
    period_month = serializers.IntegerField(allow_null=True)
    period_quarter = serializers.IntegerField(allow_null=True)
    cible = serializers.DecimalField(max_digits=14, decimal_places=2)
    owner = serializers.IntegerField(allow_null=True)
    owner_nom = serializers.CharField(allow_null=True)
    realise = serializers.DecimalField(max_digits=14, decimal_places=2)
    taux = serializers.FloatField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()


# ── FG242 — Suivi des concurrents sur deals perdus ────────────────────────────

class ConcurrentPerteSerializer(serializers.ModelSerializer):
    """FG242 — concurrent gagnant + prix saisis sur un lead perdu.

    La société est posée côté serveur (HiddenField depuis l'utilisateur courant
    — multi-tenant, jamais lue du corps de requête) ; ``saisi_par`` est forcé
    dans ``perform_create``. Le lead doit appartenir à la même société
    (validate_lead). ``lead_nom`` est en lecture seule pour l'UI.
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    saisi_par = serializers.PrimaryKeyRelatedField(read_only=True)
    saisi_par_nom = serializers.SerializerMethodField()
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None)

    class Meta:
        model = ConcurrentPerte
        fields = [
            'id', 'company', 'lead', 'lead_nom',
            'concurrent_nom', 'concurrent_prix', 'devise', 'motif', 'notes',
            'saisi_par', 'saisi_par_nom', 'saisi_le', 'date_modification',
        ]
        read_only_fields = [
            'saisi_par', 'saisi_le', 'date_modification',
        ]

    def get_saisi_par_nom(self, obj):
        return getattr(obj.saisi_par, 'username', None)

    def validate_lead(self, value):
        req = self.context.get('request')
        if req and value.company_id != getattr(req.user, 'company_id', None):
            raise serializers.ValidationError('Lead inconnu.')
        return value

    def validate_concurrent_prix(self, value):
        # Prix optionnel mais jamais négatif (garde Decimal explicite en plus du
        # validateur modèle, pour un message clair côté API).
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le prix du concurrent ne peut pas être négatif.')
        return value

    def validate_concurrent_nom(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError(
                'Le nom du concurrent est obligatoire.')
        return value


class PointContactSerializer(serializers.ModelSerializer):
    """FG204 — point de contact du parcours multi-touch d'un lead.

    La société est posée côté serveur (HiddenField depuis l'utilisateur courant
    — multi-tenant, jamais lue du corps de requête) ; ``saisi_par`` est forcé
    dans ``perform_create``. Le lead doit appartenir à la même société
    (validate_lead). ``date_contact`` est optionnel à la saisie (défaut : now).
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    saisi_par = serializers.PrimaryKeyRelatedField(read_only=True)
    saisi_par_nom = serializers.SerializerMethodField()
    canal_libelle = serializers.CharField(
        source='get_canal_display', read_only=True)
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None)
    date_contact = serializers.DateTimeField(required=False)

    class Meta:
        model = PointContact
        fields = [
            'id', 'company', 'lead', 'lead_nom',
            'canal', 'canal_libelle', 'source', 'date_contact', 'ordre',
            'detail', 'cout',
            'saisi_par', 'saisi_par_nom', 'saisi_le', 'date_modification',
        ]
        read_only_fields = [
            'saisi_par', 'saisi_le', 'date_modification',
        ]

    def get_saisi_par_nom(self, obj):
        return getattr(obj.saisi_par, 'username', None)

    def validate_lead(self, value):
        req = self.context.get('request')
        if req and value.company_id != getattr(req.user, 'company_id', None):
            raise serializers.ValidationError('Lead inconnu.')
        return value

    def validate_cout(self, value):
        # Coût optionnel mais jamais négatif (garde Decimal explicite en plus du
        # validateur modèle, pour un message clair côté API).
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le coût ne peut pas être négatif.')
        return value

    def validate_date_contact(self, value):
        # Si non fourni, retombe sur maintenant (le champ a un default côté
        # serveur via perform_create ; ici on accepte simplement la valeur).
        return value


# ── ZSAL2 — Plans d'activité ─────────────────────────────────────────────────

class EtapePlanActiviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EtapePlanActivite
        fields = [
            'id', 'plan', 'ordre', 'activity_type', 'delai_jours',
            'resume_defaut', 'assigne_par_defaut',
        ]


class PlanActiviteSerializer(serializers.ModelSerializer):
    etapes = EtapePlanActiviteSerializer(many=True, read_only=True)

    class Meta:
        model = PlanActivite
        fields = ['id', 'company', 'nom', 'actif', 'date_creation', 'etapes']
        read_only_fields = ['company', 'date_creation']


# ── ZSAL3 — Équipes commerciales (admin CRUD ; le dashboard « Mes équipes »
# lit stats_equipe() séparément, voir views.equipes_statistiques) ────────────

class EquipeCommercialeSerializer(_CompanyScopedRelationsMixin,
                                  serializers.ModelSerializer):
    # CRX13 — responsable ET membres (M2M) : le ``ManyRelatedField`` délègue à
    # son ``child_relation``, promu lui aussi.
    scoped_relations = ('responsable', 'membres')

    responsable_nom = serializers.CharField(
        source='responsable.username', read_only=True, default=None)
    nb_membres = serializers.IntegerField(source='membres.count', read_only=True)

    class Meta:
        model = EquipeCommerciale
        fields = [
            'id', 'company', 'nom', 'responsable', 'responsable_nom',
            'membres', 'nb_membres', 'actif', 'date_creation',
        ]
        read_only_fields = ['company', 'date_creation']


# ── NTCRM4 — Catégories de forecast ──────────────────────────────────────────

class ForecastEntrySerializer(_CompanyScopedRelationsMixin,
                              serializers.ModelSerializer):
    # CRX13 — ``lead`` est un OneToOne : DRF lui greffe automatiquement un
    # ``UniqueValidator`` sur TOUTES les sociétés. Le champ est re-scopé ET son
    # validateur d'unicité aussi, sinon « déjà utilisé » sur un lead voisin
    # resterait un oracle d'existence.
    scoped_relations = ('lead',)

    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    montant_effectif = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    owner_id = serializers.IntegerField(source='lead.owner_id', read_only=True)

    class Meta:
        model = ForecastEntry
        fields = [
            'id', 'lead', 'categorie', 'categorie_display', 'montant_prevu',
            'montant_effectif', 'owner_id', 'commentaire',
            'mis_a_jour_par', 'mis_a_jour_le',
        ]
        read_only_fields = ['mis_a_jour_par', 'mis_a_jour_le']

    def get_fields(self):
        fields = super().get_fields()
        _scope_unique_validators(fields.get('lead'))
        return fields


class ForecastSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForecastSnapshot
        fields = [
            'id', 'semaine_iso', 'categorie', 'montant_total', 'nb_leads',
            'owner', 'created_at',
        ]
        read_only_fields = fields


# ── NTCRM10 — Plan de compte ─────────────────────────────────────────────────
# ARC8 — l'historique (chatter) d'un PlanCompte est sérialisé par
# records.serializers.ChatterActivitySerializer (records.Activity), plus aucun
# serializer *Activity maison ici.


class RevueCompteSerializer(_CompanyScopedRelationsMixin,
                            serializers.ModelSerializer):
    # CRX13 — ``plan`` est la SEULE frontière société de ce modèle (RevueCompte
    # n'a pas de ``company`` propre) : sans re-scope, une revue pouvait être
    # accrochée au plan de compte d'une autre société.
    scoped_relations = ('plan',)

    class Meta:
        model = RevueCompte
        fields = [
            'id', 'plan', 'date_revue', 'participants', 'decisions',
            'prochaine_action', 'prochaine_action_date', 'created_by',
            'created_at',
        ]
        read_only_fields = ['created_by', 'created_at']


class PlanCompteSerializer(_CompanyScopedRelationsMixin,
                           serializers.ModelSerializer):
    # CRX13 — le client du plan de compte, à la CRÉATION comme au PATCH.
    scoped_relations = ('client',)

    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    revues = RevueCompteSerializer(many=True, read_only=True)

    class Meta:
        model = PlanCompte
        fields = [
            'id', 'client', 'objectifs_strategiques', 'potentiel_estime',
            'concurrents_presents', 'swot_forces', 'swot_faiblesses',
            'swot_opportunites', 'swot_menaces', 'prochaine_revue', 'statut',
            'statut_display', 'created_by', 'mis_a_jour_par', 'revues',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'created_by', 'mis_a_jour_par', 'date_creation', 'date_modification',
        ]


# ── NTCRM12 — Playbooks de vente par étape ───────────────────────────────────

class PlaybookTacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybookTache
        fields = ['id', 'etape', 'libelle', 'obligatoire', 'ordre']


class PlaybookEtapeSerializer(serializers.ModelSerializer):
    stage_display = serializers.SerializerMethodField()
    taches = PlaybookTacheSerializer(many=True, read_only=True)

    class Meta:
        model = PlaybookEtape
        fields = ['id', 'playbook', 'stage', 'stage_display', 'ordre', 'taches']

    def get_stage_display(self, obj):
        from . import stages
        return stages.STAGE_LABELS.get(obj.stage, obj.stage)


class PlaybookSerializer(serializers.ModelSerializer):
    etapes = PlaybookEtapeSerializer(many=True, read_only=True)

    class Meta:
        model = Playbook
        # CRX35 — 'bloquant' retiré : le champ n'existe plus (rien ne le lisait).
        fields = ['id', 'nom', 'actif', 'condition', 'etapes', 'date_creation']
        read_only_fields = ['date_creation']


class LeadPlaybookProgressSerializer(serializers.ModelSerializer):
    tache_libelle = serializers.CharField(source='tache.libelle', read_only=True)
    tache_obligatoire = serializers.BooleanField(
        source='tache.obligatoire', read_only=True)
    etape_stage = serializers.CharField(source='tache.etape.stage', read_only=True)
    fait_par_nom = serializers.CharField(
        source='fait_par.username', read_only=True, default=None)
    # AGR526 (contrat `lead_playbook.json`, AGR507) — la clé du TEXTE que la
    # tâche propose (`dossier_fda` / `dossier_8221`), ou null.
    cle_message = serializers.SerializerMethodField()

    class Meta:
        model = LeadPlaybookProgress
        fields = [
            'id', 'lead', 'tache', 'tache_libelle', 'tache_obligatoire',
            'etape_stage', 'fait', 'fait_par', 'fait_par_nom', 'fait_le',
            'created_at', 'cle_message',
        ]
        read_only_fields = ['fait_par', 'fait_le', 'created_at']

    def get_cle_message(self, obj):
        """AGR526 — la ``cle_message`` de l'entrée ``PLAYBOOKS_SEGMENT_CAD125``
        dont le ``nom`` est celui du playbook de la tâche, SEULEMENT si
        ``cle_message_segment(lead)`` la confirme ; ``None`` sinon."""
        from .services import PLAYBOOKS_SEGMENT_CAD125, cle_message_segment
        playbook = getattr(getattr(obj.tache, 'etape', None), 'playbook', None)
        nom = getattr(playbook, 'nom', None)
        entree = next((e for e in PLAYBOOKS_SEGMENT_CAD125 if e['nom'] == nom),
                      None)
        if entree is None:
            return None
        cle = entree['cle_message']
        return cle if cle_message_segment(obj.lead) == cle else None


# ── LB48 — Vues enregistrées par compte ────────────────────────────────────

class SavedViewSerializer(serializers.ModelSerializer):
    """LB48 — vue enregistrée personnelle (filtres + disposition d'une page).

    ``company`` n'est PAS exposé : toujours posé côté serveur
    (``SavedViewViewSet.perform_create`` — jamais lu du corps de requête),
    comme ``MessageTemplateSerializer``. ``user`` est un ``HiddenField``
    (jamais lisible/écrivable par le client — ``write_only`` implicite) posé
    depuis l'utilisateur courant : nécessaire pour que le validateur
    d'unicité auto-généré par DRF sur la contrainte ``(user, page, name)``
    s'active (DRF n'ajoute le ``UniqueTogetherValidator`` que si TOUS les
    champs de la contrainte sont représentés dans le serializer — sans ce
    champ cachée, un doublon lèverait une ``IntegrityError`` (500) au lieu
    d'un 400 propre).
    """
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = SavedView
        fields = ['id', 'page', 'name', 'rank', 'payload', 'created_at', 'user']
        read_only_fields = ['created_at']


class SalleVenteItemSerializer(serializers.ModelSerializer):
    """NTCRM17 — un élément (devis/document/lien vidéo/note) d'une salle de vente."""

    class Meta:
        model = SalleVenteItem
        fields = ['id', 'salle', 'type', 'reference', 'titre', 'ordre', 'created_at']
        read_only_fields = ['created_at']


class SalleVenteSerializer(_CompanyScopedRelationsMixin,
                           serializers.ModelSerializer):
    """NTCRM17 — salle de vente digitale (écran interne, authentifié).

    ``company`` est TOUJOURS posé côté serveur (jamais lu du corps).
    ``token``/``password_hash`` ne sont jamais exposés en écriture ; un mot
    de passe est posé via le champ ``write_only`` ``mot_de_passe`` (haché
    côté serveur, jamais stocké en clair). ``has_password`` expose
    seulement un booléen — jamais le hash."""

    # CRX13 — la salle référence exactement un lead OU un client : les deux
    # relations sont re-scopées société.
    scoped_relations = ('lead', 'client')

    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    items = SalleVenteItemSerializer(many=True, read_only=True)
    has_password = serializers.BooleanField(read_only=True)
    lien_public = serializers.SerializerMethodField()
    mot_de_passe = serializers.CharField(
        write_only=True, required=False, allow_blank=True)

    class Meta:
        model = SalleVente
        fields = [
            'id', 'company', 'lead', 'client', 'titre', 'token', 'expires_at',
            'actif', 'has_password', 'mot_de_passe', 'lien_public', 'items',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['token', 'created_by', 'created_at', 'updated_at']

    def get_lien_public(self, obj):
        return f'/salle-vente/{obj.token}'

    def validate(self, attrs):
        # NTCRM17 — piège DRF/HTML : `BooleanField.default_empty_html` vaut
        # False, donc un `actif` ABSENT d'un POST/PUT en form-data (une case
        # décochée n'est pas envoyée par un navigateur) arrive ici à False et
        # créait une salle immédiatement RÉVOQUÉE (lien public en 410). Une
        # requête qui ne parle pas d'`actif` ne doit jamais le modifier : on
        # retombe sur le défaut du modèle (création) ou sur la valeur en base
        # (mise à jour). Un `actif: false` EXPLICITE reste évidemment honoré.
        if 'actif' in attrs and 'actif' not in getattr(self, 'initial_data', {}):
            attrs.pop('actif')
        lead = attrs.get('lead', getattr(self.instance, 'lead', None))
        client = attrs.get('client', getattr(self.instance, 'client', None))
        if bool(lead) == bool(client):
            raise serializers.ValidationError(
                'Une salle de vente doit référencer exactement un lead OU un '
                'client (jamais les deux, jamais ni l\'un ni l\'autre).')
        return attrs

    def create(self, validated_data):
        mot_de_passe = validated_data.pop('mot_de_passe', '')
        instance = SalleVente(**validated_data)
        instance.set_password(mot_de_passe)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        if 'mot_de_passe' in validated_data:
            instance.set_password(validated_data.pop('mot_de_passe'))
        return super().update(instance, validated_data)


class ApporteurSerializer(serializers.ModelSerializer):
    """NTCRM20 — apporteur d'affaires. ``company`` posé côté serveur."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())

    class Meta:
        model = Apporteur
        fields = [
            'id', 'company', 'nom', 'type_apporteur', 'contact_email',
            'contact_telephone', 'taux_commission_pct', 'actif', 'rib',
            'created_at', 'token_acces',
        ]
        read_only_fields = ['created_at', 'token_acces']


class DealEnregistreSerializer(_CompanyScopedRelationsMixin,
                               serializers.ModelSerializer):
    """NTCRM20 — deal enregistré par un apporteur. La fenêtre de protection
    (``clean()`` du modèle) est appliquée via ``full_clean()`` explicite
    (DRF n'invoque jamais la validation modèle automatiquement)."""

    # CRX13 — l'apporteur et le lead protégé doivent être de la société.
    scoped_relations = ('apporteur', 'lead')

    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    apporteur_nom = serializers.CharField(source='apporteur.nom', read_only=True)
    lead_nom = serializers.CharField(source='lead.nom', read_only=True)

    class Meta:
        model = DealEnregistre
        fields = [
            'id', 'company', 'apporteur', 'apporteur_nom', 'lead', 'lead_nom',
            'date_enregistrement', 'statut', 'expire_le',
            'montant_commission_estime', 'montant_commission_du',
        ]
        read_only_fields = [
            'date_enregistrement', 'statut', 'expire_le',
            'montant_commission_estime', 'montant_commission_du',
        ]

    def validate(self, attrs):
        instance = DealEnregistre(**{**attrs, 'pk': getattr(self.instance, 'pk', None)})
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else str(exc))
        return attrs


class DefiSerializer(serializers.ModelSerializer):
    """NTCRM23 — défi d'équipe. ``company`` posé côté serveur."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    metrique_display = serializers.CharField(
        source='get_metrique_display', read_only=True)

    class Meta:
        model = Defi
        fields = [
            'id', 'company', 'nom', 'periode_debut', 'periode_fin',
            'metrique', 'metrique_display', 'cible_equipe', 'recompense',
            'actif', 'created_at',
        ]
        read_only_fields = ['created_at']


# ── QJ-EQUIPE-2 (14/09/2026) — visiteurs externes + registre appareils équipe ──

class VisiteExterneSerializer(serializers.ModelSerializer):
    """T-TRACE — UNE trace de visite externe, lecture seule (voir
    ``apps/crm/visites.py`` pour tout ce que la finalité anti-fraude couvre).
    ``lead_nom`` est en lecture seule pour l'écran de revue."""
    point_display = serializers.CharField(
        source='get_point_display', read_only=True)
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None)

    class Meta:
        model = VisiteExterne
        fields = [
            'id', 'point', 'point_display', 'contexte', 'token_suffixe',
            'ip', 'user_agent', 'langue', 'appareil_id', 'duree_s',
            'terminee', 'lead', 'lead_nom', 'created_at',
        ]
        read_only_fields = fields


class AppareilEquipeSerializer(serializers.ModelSerializer):
    """QJ-EQUIPE-2 — un appareil ÉQUIPE, exclu du traçage anti-fraude.

    La société et ``cree_par`` sont posés côté serveur (jamais lus du corps de
    requête, multi-tenant) ; voir ``crm.services.enregistrer_appareil_equipe``,
    l'unique chemin d'écriture du registre (``create`` et ``ce_navigateur``).
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    cree_par = serializers.PrimaryKeyRelatedField(read_only=True)
    cree_par_nom = serializers.CharField(
        source='cree_par.get_full_name', read_only=True, default=None)

    class Meta:
        model = AppareilEquipe
        fields = [
            'id', 'company', 'appareil_id', 'libelle',
            'cree_par', 'cree_par_nom', 'created_at',
        ]
        read_only_fields = ['created_at']
        # Pas de UniqueTogetherValidator auto (company, appareil_id) : la vue
        # rend le POST idempotent (re-marquer met à jour le libellé, jamais un
        # 400) — la contrainte DB reste le filet contre une vraie course.
        validators = []


class PartenaireSerializer(serializers.ModelSerializer):
    """Partenaires commerciaux (apporteurs/sous-revendeurs/installateurs,
    FG234/FG237) + couche certification NTMIG26.

    SOLMVP10/SOLMVP30b — ce serializer vivait dans ``apps.compta`` (shim
    ODX13, réexporté ici) ; compta est désormais une coquille parquée sans
    aucune url (``core.parked``), donc ``crm.Partenaire`` — qui n'a jamais
    quitté cette app — reprend nativement sa propre surface API. Aucun champ
    n'a changé : seule la maison a bougé.
    """
    certification_expiree = serializers.BooleanField(read_only=True)
    rang_certification = serializers.IntegerField(read_only=True)

    class Meta:
        model = Partenaire
        fields = [
            'id', 'nom', 'type_partenaire', 'email', 'telephone',
            'taux_commission', 'token_acces', 'actif',
            'statut_onboarding', 'numero_agrement', 'zone', 'date_activation',
            'niveau_certification', 'date_certification',
            'date_expiration_certification', 'specialites',
            'nb_deploiements_reussis', 'certification_expiree',
            'rang_certification',
            'date_creation',
        ]
        read_only_fields = [
            'token_acces', 'date_activation', 'date_creation',
            # NTMIG26 — le compteur de déploiements est de l'HISTORIQUE : il
            # s'alimente par l'enregistrement d'un déploiement (NTMIG28), pas
            # par un PATCH qui permettrait de gonfler son propre score.
            'nb_deploiements_reussis', 'certification_expiree',
            'rang_certification',
        ]

    def validate_specialites(self, value):
        """NTMIG26 — spécialités prises dans la liste FERMÉE du référentiel.

        Une valeur libre rendrait l'annuaire des certifiés infiltrable :
        « Compta », « compta » et « COMPTA » seraient trois spécialités
        distinctes qu'aucun filtre ne retrouverait ensemble.
        """
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'Les spécialités doivent être une liste de clés de module.')
        connues_cles = Partenaire.SPECIALITES_CLES
        inconnues = [str(v) for v in value if str(v) not in connues_cles]
        if inconnues:
            connues = ', '.join(connues_cles)
            raise serializers.ValidationError(
                f"Spécialité(s) inconnue(s) : {', '.join(inconnues)}. "
                f'Valeurs acceptées : {connues}.')
        # Dédoublonne en préservant l'ordre de saisie.
        vues, propres = set(), []
        for v in value:
            if str(v) in vues:
                continue
            vues.add(str(v))
            propres.append(str(v))
        return propres

    def validate(self, attrs):
        """NTMIG26 — une échéance de certification antérieure à sa date de
        délivrance décrirait une certification née expirée."""
        attrs = super().validate(attrs)
        instance = getattr(self, 'instance', None)
        debut = attrs.get(
            'date_certification', getattr(instance, 'date_certification', None))
        fin = attrs.get(
            'date_expiration_certification',
            getattr(instance, 'date_expiration_certification', None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError({
                'date_expiration_certification': (
                    "L'expiration ne peut pas précéder la date de "
                    'certification.')})
        return attrs
