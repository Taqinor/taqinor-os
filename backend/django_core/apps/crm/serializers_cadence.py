"""SPL74 — sérialiseurs de la cadence de relance (RelanceEtapeSerializer,
MessageTemplateSerializer), déplacés de ``serializers.py`` à l'identique
(move only). Dépendance à sens unique : ce module importe ``.serializers``,
jamais l'inverse.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from . import cadence_temps
from .models import Lead, LeadActivity, MessageTemplate, RelanceEtape
from .serializers import (
    nom_affichable_lead, nom_affichable_responsable, pii_masquee_pour,
)


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
        # ALEA32 — LA définition unique (jours ouvrés + absences), celle du
        # cockpit ; le mémo du contexte évite de relire le calendrier par
        # ligne d'une liste.
        from .controle_suivi import etape_en_retard
        memo = (self.context.setdefault('_alea32_retard', {})
                if isinstance(self.context, dict) else None)
        return etape_en_retard(obj, memo=memo)

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
        if not self._message_eligible(obj):
            return None
        from .cadence_reperes import prefixe_activite_message_ouvert
        # APRF21 — lecture EN LOT : la première touche éligible de la page
        # lit UNE fois les activités « WhatsApp ouvert » de tous les leads
        # éligibles (patron ``_visite_du_lead``), carte posée en contexte.
        cache = self.context.setdefault('_aprf21_messages_ouverts', {})
        if obj.lead_id not in cache:
            instances = getattr(self.parent, 'instance', None)
            touches = ([t for t in instances if self._message_eligible(t)]
                       if instances is not None else [obj])
            if obj not in touches:
                touches.append(obj)
            lead_ids = {t.lead_id for t in touches}
            import os.path
            commun = os.path.commonprefix(
                [prefixe_activite_message_ouvert(t) for t in touches])
            for lid in lead_ids:
                cache[lid] = []
            for lid, body, cree in (
                    LeadActivity.objects
                    .filter(lead_id__in=lead_ids,
                            kind=LeadActivity.Kind.WHATSAPP,
                            body__startswith=commun)
                    .order_by('-created_at')
                    .values_list('lead_id', 'body', 'created_at')):
                cache[lid].append((body, cree))
        prefixe = prefixe_activite_message_ouvert(obj)
        for body, cree in cache[obj.lead_id]:
            if (body or '').startswith(prefixe):
                return cree
        return None

    @staticmethod
    def _message_eligible(obj):
        """RLC3 — seule une touche MESSAGE encore À FAIRE lit « ouvert »."""
        return (obj.statut == RelanceEtape.Statut.A_FAIRE
                and obj.canal in (RelanceEtape.Canal.WHATSAPP,
                                  RelanceEtape.Canal.EMAIL))


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
