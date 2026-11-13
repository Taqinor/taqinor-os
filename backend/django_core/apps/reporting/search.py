"""T5 — Recherche globale + notifications in-app (lecture seule, multi-tenant).

Tout est borné à la société de l'utilisateur. La recherche balaie les entités
clés (leads, clients, devis, factures, chantiers, équipements, tickets SAV) ;
les notifications agrègent ce qui demande une action (activités en retard,
garanties expirant sous 90 j, factures impayées/en retard). Aucune écriture.

ARC29 — PILOTÉE PAR LE REGISTRE (``core.platform``). Avant ARC29, les 10
modèles cherchables étaient hard-codés dans cette fonction : un modèle
importable/chatter-isé mais absent d'ici restait introuvable (``stock.Produit``,
``contrats.Contrat``). ``global_search`` itère désormais
``platform.searchable_models(company)`` (les manifestes ``apps/<x>/platform.py``
gatés ``ModuleToggle``) et résout chaque clé ``'app.model'`` dans le registre
LOCAL ``_SEARCH_SPECS`` ci-dessous — la construction de requête/mise en forme du
résultat reste PROPRE à chaque modèle (elle ne peut pas être généralisée sans
connaître les champs de recherche pertinents), mais l'ENSEMBLE des modèles
balayés vient désormais du registre plateforme : ajouter un modèle au manifeste
d'une app SANS toucher ce fichier ne le rend PAS automatiquement cherchable
(il faut aussi déclarer sa spec ici) — en revanche retirer/désactiver un module
(toggle OFF) le retire bien de la recherche sans rien changer ici. L'enveloppe
de résultat (``{'query', 'groups': [{'type','label','results':[...]}]}``) reste
BYTE-IDENTIQUE à avant ARC29 (le hook front VX13 la consomme sans changement).

NTPLT33 — PLEIN-TEXTE. Les 7 entités dotées de ``search_vector`` (NTPLT32 :
Lead, Client, Devis, Facture, Installation, Equipement, Ticket) sont cherchées
par ``to_tsquery('french', 'mot:* & …')`` sur leur index GIN (préfixe : la
frappe instantanée trouve « Dupont » dès « dup » ; racinisation française :
pluriels ; accents retirés des deux côtés) et classées par ``ts_rank``. Une
ligne pas encore indexée (colonne ``NULL`` : avant ``rebuild_search_index``)
retombe sur l'ancien ``icontains`` — ligne par ligne, dans la MÊME requête :
aucun résultat ne disparaît pendant le déploiement, aucune requête de plus.
Téléphone / e-mail (APFS24) restent en ``icontains`` réservé à
``client_pii_voir`` : ils ne sont jamais dans le vecteur.
"""
import re
from datetime import date, timedelta

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.lookups import TrigramSimilar
from django.contrib.postgres.search import SearchRank, TrigramSimilarity
from django.db.models import F, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core import platform
from core.recherche_fts import requete_prefixe, trigramme_disponible
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers as drf_serializers
from drf_spectacular.utils import inline_serializer


def _co_filter(user):
    """kwargs de filtrage société, ou None si accès interdit."""
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _critere_fts(fts, repli, prefixe=''):
    """NTPLT33 — ligne indexée : plein-texte ; ligne pas encore indexée
    (``search_vector`` NULL) : le critère ``icontains`` d'avant. ``prefixe``
    vise le vecteur d'une relation (``client__``)."""
    if fts is None:
        return repli
    return (Q(**{f'{prefixe}search_vector': fts})
            | (Q(**{f'{prefixe}search_vector__isnull': True}) & repli))


def _classer(qs, fts, *ordre):
    """NTPLT33 — pertinence ``ts_rank`` d'abord (lignes non indexées en
    dernier, à rang égal), puis l'ordre historique du groupe."""
    if fts is None:
        return qs.order_by(*ordre)
    return qs.annotate(rang_fts=SearchRank(F('search_vector'), fts)).order_by(
        F('rang_fts').desc(nulls_last=True), *ordre)


# Message client collé tel quel dans la barre (12/11/2026, Reda : « je veux
# retrouver le lead depuis ce genre de message ») — le bouton WhatsApp de la
# proposition préremplit « … ma proposition Taqinor (réf. DEV-202611-0059)
# avant de signer. » : la référence du document est extraite du texte, et un
# numéro saisi dans n'importe quel format (+212 661-826837, 0661826837…)
# retrouve le téléphone stocké (« 212661826837 ») par ses 9 derniers chiffres.
_REF_DOC_RE = re.compile(r'[A-Z]{2,5}-\d{4,6}-\d{2,6}', re.IGNORECASE)
_TEL_SAISI_RE = re.compile(r'[\d\s+().\-/]+')


def terme_de_recherche(q):
    """La référence de document contenue dans ``q`` (en majuscules), sinon
    ``q`` tel quel."""
    m = _REF_DOC_RE.search(q or '')
    return m.group(0).upper() if m else q


def _neuf_chiffres_tel(q):
    """Les 9 derniers chiffres quand ``q`` est un numéro de téléphone saisi
    (chiffres + séparateurs seulement, au moins 9 chiffres), sinon ''."""
    if not _TEL_SAISI_RE.fullmatch(q or ''):
        return ''
    chiffres = re.sub(r'\D', '', q)
    return chiffres[-9:] if len(chiffres) >= 9 else ''


def _critere_tel(champs, q):
    """Téléphone tolérant au format : les 9 derniers chiffres, séparateurs
    permis entre eux, en fin de champ. ``None`` si ``q`` n'est pas un numéro."""
    neuf = _neuf_chiffres_tel(q)
    if not neuf:
        return None
    motif = r'\D*'.join(neuf) + r'\D*$'
    critere = Q()
    for champ in champs:
        critere |= Q(**{f'{champ}__regex': motif})
    return critere


def _spec_lead(co, q, user=None):
    from apps.crm.models import Lead
    from apps.crm.selectors import portee_leads
    from apps.ventes.models import Devis
    pii = _voit_pii(user)
    fts = requete_prefixe(q)
    critere = _critere_fts(fts, (
        Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(societe__icontains=q)
        | Q(ville__icontains=q)
        # WREF (fondateur 21/08) — le « TQ-XXXX » remis au client retrouve le
        # lead depuis l'omnibox aussi. (code_parrainage vit sur crm.Client,
        # pas sur Lead — l'y interroger casserait TOUTES les recherches.)
        | Q(client_ref__icontains=q) | Q(client_ref_provisoire__icontains=q)))
    if _REF_DOC_RE.fullmatch(q):
        # Le lead qui porte ce devis (le client cite sa référence).
        critere |= Q(pk__in=Devis.objects.filter(**co, reference__iexact=q)
                     .exclude(lead__isnull=True).values('lead_id'))
    if pii:  # APFS24 — téléphone / e-mail : critère réservé à ``client_pii_voir``
        critere |= Q(email__icontains=q) | Q(telephone__icontains=q)
        tel = _critere_tel(('telephone', 'whatsapp'), q)
        if tel is not None:
            critere |= tel
    qs = Lead.objects.filter(**co).filter(critere)
    # APFS24 — la portée du rôle (propriétaire + entités), comme ``crm/leads/``.
    qs = _classer(portee_leads(qs, user) if user is not None else qs.none(),
                  fts, '-date_creation')
    # Incident 02/10/2026 — un lead ARCHIVÉ reste trouvable ici (il « avait
    # disparu » pour la commerciale) mais doit se DIRE archivé : sans la
    # mention, rien n'expliquait son absence du pipeline.
    return 'lead', 'Leads', qs, lambda le: {
        'id': le.id,
        'label': f"{le.nom} {le.prenom or ''}".strip() or le.societe or '—',
        'sublabel': ' · '.join(filter(None, [
            'Archivé' if le.is_archived else '',
            le.societe or le.ville or (le.telephone if pii else '') or '',
        ]))}


def _spec_client(co, q, user=None):
    from apps.crm.models import Client
    pii = _voit_pii(user)
    fts = requete_prefixe(q)
    critere = _critere_fts(fts, Q(nom__icontains=q) | Q(prenom__icontains=q))
    if pii:  # APFS24 — même règle que les leads
        critere |= Q(email__icontains=q) | Q(telephone__icontains=q)
    qs = _classer(Client.objects.filter(**co).filter(critere), fts, 'nom')
    return 'client', 'Clients', qs, lambda c: {
        'id': c.id,
        'label': f"{c.nom} {c.prenom or ''}".strip() or '—',
        'sublabel': (c.email or c.telephone or '') if pii else ''}


def _spec_devis(co, q, user=None):
    from apps.ventes.models import Devis
    fts = requete_prefixe(q)
    qs = _classer(Devis.objects.filter(**co).filter(
        _critere_fts(fts, Q(reference__icontains=q))
        | _critere_fts(fts, Q(client__nom__icontains=q), 'client__')
    ).select_related('client'), fts, '-id')
    return 'devis', 'Devis', qs, lambda d: {
        'id': d.id, 'label': d.reference,
        'sublabel': getattr(d.client, 'nom', '') or ''}


def _spec_facture(co, q, user=None):
    from apps.ventes.models import Facture
    fts = requete_prefixe(q)
    qs = _classer(Facture.objects.filter(**co).filter(
        _critere_fts(fts, Q(reference__icontains=q))
        | _critere_fts(fts, Q(client__nom__icontains=q), 'client__')
    ).select_related('client'), fts, '-id')
    return 'facture', 'Factures', qs, lambda f: {
        'id': f.id, 'label': f.reference,
        'sublabel': getattr(f.client, 'nom', '') or ''}


def _spec_chantier(co, q, user=None):
    from apps.installations.models import Installation
    fts = requete_prefixe(q)
    qs = _classer(Installation.objects.filter(**co).filter(
        _critere_fts(fts, Q(reference__icontains=q))), fts, '-id')
    return 'chantier', 'Chantiers', qs, (
        lambda i: {'id': i.id, 'label': i.reference, 'sublabel': ''})


def _spec_equipement(co, q, user=None):
    from apps.sav.models import Equipement
    fts = requete_prefixe(q)
    # Le produit (catalogue, hors plein-texte) reste en ``icontains``.
    qs = _classer(Equipement.objects.filter(**co).filter(
        _critere_fts(fts, Q(numero_serie__icontains=q))
        | Q(produit__nom__icontains=q)
    ).select_related('produit'), fts, '-id')
    return 'equipement', 'Équipements', qs, lambda e: {
        'id': e.id, 'label': e.numero_serie or f"#{e.id}",
        'sublabel': getattr(e.produit, 'nom', '') or ''}


def _spec_ticket(co, q, user=None):
    from apps.sav.models import Ticket
    fts = requete_prefixe(q)
    qs = _classer(Ticket.objects.filter(**co).filter(_critere_fts(
        fts, Q(reference__icontains=q) | Q(description__icontains=q))),
        fts, '-id')
    return 'ticket', 'Tickets SAV', qs, lambda t: {
        'id': t.id, 'label': t.reference,
        'sublabel': (t.description or '')[:40]}


def _spec_bon_commande(co, q, user=None):
    from apps.ventes.models import BonCommande
    qs = BonCommande.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(client__nom__icontains=q)
    ).select_related('client').order_by('-id')
    return 'bon_commande', 'Bons de commande', qs, lambda b: {
        'id': b.id, 'label': b.reference,
        'sublabel': getattr(b.client, 'nom', '') or ''}


def _spec_contrat_maintenance(co, q, user=None):
    from apps.sav.models import ContratMaintenance
    qs = ContratMaintenance.objects.filter(**co).filter(
        Q(client__nom__icontains=q) | Q(notes__icontains=q)
    ).select_related('client').order_by('-id')
    return 'contrat', 'Contrats de maintenance', qs, lambda c: {
        'id': c.id,
        'label': f"Contrat #{c.id}",
        'sublabel': getattr(c.client, 'nom', '') or ''}


def _spec_dossier_reglementaire(co, q, user=None):
    from apps.installations.models import Installation
    qs = Installation.objects.filter(**co).filter(
        Q(dossier_reference__icontains=q) | Q(dossier_operateur__icontains=q)
    ).exclude(dossier_reference__isnull=True).exclude(
        dossier_reference=''
    ).order_by('-id')
    return 'dossier', 'Dossiers réglementaires', qs, lambda i: {
        'id': i.id,
        'label': i.dossier_reference or i.reference,
        'sublabel': i.dossier_operateur or i.reference}


def _spec_produit(co, q, user=None):
    """ARC29 — trou comblé : ``stock.Produit`` était importable/customfieldable/
    records-isé mais absent de la recherche globale."""
    from apps.stock.models import Produit
    qs = Produit.objects.filter(**co, is_archived=False).filter(
        Q(nom__icontains=q) | Q(sku__icontains=q)
    ).order_by('nom')
    return 'produit', 'Produits', qs, lambda p: {
        'id': p.id, 'label': p.nom,
        'sublabel': p.sku or ''}


def _spec_campagne(co, q, user=None):
    """PUB99 — campagnes publicitaires miroir (``adsengine.AdCampaignMirror``).
    Cherchées par nom ou id Meta ; sous-libellé = statut lisible."""
    from apps.adsengine.models import AdCampaignMirror
    qs = AdCampaignMirror.objects.filter(**co).filter(
        Q(name__icontains=q) | Q(meta_id__icontains=q)
    ).order_by('-created_at')
    return 'campagne_pub', 'Campagnes pub', qs, lambda c: {
        'id': c.id,
        'label': c.name or c.meta_id or '—',
        'sublabel': c.status or ''}


# NTEXT35 — recherche globale sur les OBJETS PERSONNALISÉS (customfields).
# DIFFÉRENT de ``_SEARCH_SPECS`` ci-dessous (liste STATIQUE de modèles
# natifs, un groupe fixe par entrée) : le nombre d'objets personnalisés est
# DYNAMIQUE par société, donc UN GROUPE PAR OBJET ACTIF est construit à
# CHAQUE recherche (adapter générique, jamais un modèle natif câblé en dur).
_CUSTOM_RECORD_SCAN_MAX = 500  # borne anti-DoS : par OBJET, jamais global.
_CUSTOM_RECORD_RESULTS_PER_GROUP = 6  # même PER que les groupes natifs.


def _custom_record_label(record):
    """Premier texte non vide de ``data`` (dénormalisation la plus lisible
    disponible sans connaître le schéma de l'objet) — repli sur ``#id``."""
    for value in (record.data or {}).values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f'#{record.pk}'


def _custom_object_visible(user, code):
    """Même garde que ``CustomRecordViewSet._check_object_permission`` :
    superuser ou compte hérité sans rôle fin (compat) voit tout ; sinon la
    permission ``custom_object.<code>.voir`` fait foi."""
    if user.is_superuser or getattr(user, 'role', None) is None:
        return True
    return user.has_erp_permission(f'custom_object.{code}.voir')


def _custom_record_groups(user, co, q):
    """NTEXT35 — un groupe de résultats PAR objet personnalisé ACTIF dont
    ``q`` apparaît dans une valeur de ``data``, filtré par la permission
    ``custom_object.<code>.voir``. Scan Python borné (``JSONField`` — pas de
    lookup ``icontains`` portable dessus) : jamais plus de
    ``_CUSTOM_RECORD_SCAN_MAX`` enregistrements PAR objet."""
    from apps.customfields.models import CustomObjectDef, CustomRecord

    company = co.get('company')
    if company is None:
        return []
    terme = q.lower()
    groups = []
    for objet in CustomObjectDef.objects.filter(
            company=company, actif=True).order_by('libelle'):
        if not _custom_object_visible(user, objet.code):
            continue
        candidats = []
        qs = CustomRecord.objects.filter(
            company=company, objet=objet
        ).order_by('-date_creation')[:_CUSTOM_RECORD_SCAN_MAX]
        for record in qs:
            data = record.data or {}
            if any(terme in str(v).lower() for v in data.values()):
                candidats.append(record)
        if not candidats:
            continue
        items = [
            {'id': r.pk, 'label': _custom_record_label(r),
             'sublabel': objet.libelle}
            for r in candidats[:_CUSTOM_RECORD_RESULTS_PER_GROUP]
        ]
        group = {'type': f'custom:{objet.code}', 'label': objet.libelle,
                 'results': items}
        if len(candidats) > _CUSTOM_RECORD_RESULTS_PER_GROUP:
            group['more'] = True
            group['more_count'] = (
                len(candidats) - _CUSTOM_RECORD_RESULTS_PER_GROUP)
        groups.append(group)
    return groups


def _spec_calepinage(co, q, user=None):
    """CAL27 — un calepinage se retrouve par son TITRE, et par son client.

    Le titre est la seule chaîne que le module porte en propre ; ``lead_id``
    est un entier OPAQUE (jamais une FK dure vers ``crm``), donc la recherche
    ne joint que le client et le sous-libellé se limite à ce que le calepinage
    sait de lui-même.

    ACAL296 — la recherche part du prédicat d'accès
    ``apps.calepinage.selectors.calepinages_visibles(user)`` (société + vue
    restreinte au responsable), jamais d'une requête bornée société seule :
    un calepinage hors vue n'apparaît ni par son titre ni par son client.
    Sans utilisateur, rien n'est rendu (fermé par défaut). ``co`` reste dans
    la signature commune des specs ; les archives restent trouvables comme
    avant (``inclure_archives=True``).
    """
    from apps.calepinage.models import Calepinage
    from apps.calepinage.selectors import calepinages_visibles

    if user is None:
        qs = Calepinage.objects.none()
    else:
        qs = calepinages_visibles(
            user, inclure_archives=True,
            base=Calepinage.objects.select_related('client'))
    qs = qs.filter(
        Q(titre__icontains=q) | Q(client__nom__icontains=q)
    ).order_by('-id')
    return 'calepinage', 'Calepinages', qs, lambda c: {
        'id': c.id,
        'label': c.titre or f'Calepinage #{c.id}',
        'sublabel': getattr(c.client, 'nom', '') or c.get_statut_display()}


def _voit_pii(user):
    """APFS24 — coordonnées personnelles (téléphone, e-mail) : ``client_pii_voir``."""
    return user is not None and bool(getattr(user, 'can_view_client_pii', False))


# APFS24 (C-APFS-025) — chaque groupe exige le droit de LECTURE de son module,
# celui de l'écran qui l'ouvre (``core.permissions._user_has_or_legacy``, la
# garde des viewsets) : un rôle sans ``crm_voir`` ne reçoit aucun lead. Une clé
# absente (calepinage : vue par utilisateur ACAL296 ; campagnes pub) : sans droit.
# ACAL296 — chaque spec reçoit ``request.user``.
_DROIT_DES_GROUPES = {
    'crm.lead': 'crm_voir', 'crm.client': 'crm_voir',
    'ventes.devis': 'ventes_voir', 'ventes.facture': 'ventes_voir',
    'ventes.boncommande': 'ventes_voir',
    'installations.installation': 'installation_voir',
    'sav.equipement': 'equipement_voir', 'sav.ticket': 'sav_voir',
    'sav.contratmaintenance': 'sav_voir', 'stock.produit': 'stock_voir',
}


def _groupe_permis(user, cle):
    from core.permissions import _user_has_or_legacy
    code = _DROIT_DES_GROUPES.get(cle)
    return code is None or _user_has_or_legacy(user, code)


# Registre LOCAL des specs de recherche, LISTE ORDONNÉE de couples
# ``('app.model', spec_builder)`` — clé minuscule, alignée sur
# ``core.platform`` / ``records.ALLOWED_TARGETS``. L'ORDRE est EXACTEMENT
# celui des 10 groupes historiques d'avant ARC29 (enveloppe ET ordre de
# groupes inchangés pour l'existant), les trous comblés (Produit, Contrat CLM)
# en fin de liste. ``installations.installation`` apparaît DEUX fois (les
# groupes « Chantiers » et « Dossiers réglementaires », historiquement
# distincts sur le même modèle et non adjacents). ``global_search`` n'itère
# QUE les clés listées ici ET présentes dans
# ``platform.searchable_models(company)`` — les deux conditions sont
# nécessaires (une clé ici sans manifeste, ou un manifeste sans spec ici, ne
# produit rien).
_SEARCH_SPECS = [
    ('crm.lead', _spec_lead),
    ('crm.client', _spec_client),
    ('ventes.devis', _spec_devis),
    ('ventes.facture', _spec_facture),
    ('installations.installation', _spec_chantier),
    ('sav.equipement', _spec_equipement),
    ('sav.ticket', _spec_ticket),
    ('ventes.boncommande', _spec_bon_commande),
    ('sav.contratmaintenance', _spec_contrat_maintenance),
    ('installations.installation', _spec_dossier_reglementaire),
    # ARC29 — trous comblés.
    ('stock.produit', _spec_produit),
    # PUB99 — campagnes publicitaires miroir (moteur adsengine).
    ('adsengine.adcampaignmirror', _spec_campagne),
    # CAL27 — le module Calepinage (titre + client).
    ('calepinage.calepinage', _spec_calepinage),
]


_SEARCH_GLOBAL_SEARCH_REPONSE = inline_serializer('SearchGlobalSearchReponse', {
    'query': drf_serializers.JSONField(allow_null=True),
    'groups': drf_serializers.JSONField(allow_null=True),
})


@extend_schema(
    parameters=[
        OpenApiParameter('q', OpenApiTypes.STR, required=False),
    ],
    responses={200: _SEARCH_GLOBAL_SEARCH_REPONSE})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def global_search(request):
    """Recherche transverse. ?q=<terme> → résultats groupés par type.

    Chaque résultat porte type / id / label / sublabel ; le front mappe le
    type vers sa route pour ouvrir l'enregistrement. Limité par type pour
    rester rapide et lisible.

    ARC29 — pilotée par le registre plateforme : on itère
    ``platform.searchable_models(company)`` (gaté ``ModuleToggle``) et on
    résout chaque clé dans ``_SEARCH_SPECS`` ; l'ordre des groupes suit
    l'ordre historique pour rester stable côté front (les nouvelles clés
    ARC29 sont ajoutées en fin de balayage)."""
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    q = (request.query_params.get('q') or '').strip()
    if len(q) < 2:
        return Response({'query': q, 'groups': []})
    requete = q
    q = terme_de_recherche(q)

    PER = 6
    groups = []

    def add(type_key, label_fr, qs, mapper):
        """Ajoute un groupe à partir d'un queryset.

        N83 — on tronque à PER côté vue ; quand le groupe atteint PER on compte
        le total réel pour exposer un lien « voir tout / +N autres » côté front
        (clé ``more``/``more_count``). Le ``.count()`` n'est fait QUE quand le
        groupe est plein, pour ne pas surcharger les petits résultats.
        """
        rows = list(qs[:PER])
        items = [mapper(obj) for obj in rows]
        if not items:
            return
        group = {'type': type_key, 'label': label_fr, 'results': items}
        if len(items) >= PER:
            total = qs.count()
            if total > len(items):
                group['more'] = True
                group['more_count'] = total - len(items)
        groups.append(group)

    # ARC29 — balayage piloté par le registre plateforme : seules les clés
    # présentes dans platform.searchable_models(company) (manifestes gatés
    # ModuleToggle) sont interrogées, dans l'ordre historique de _SEARCH_SPECS.
    cherchables = platform.searchable_models(request.user.company)
    for cle, spec_builder in _SEARCH_SPECS:
        if cle not in cherchables or not _groupe_permis(request.user, cle):
            continue
        add(*spec_builder(co, q, user=request.user))

    # NTEXT35 — objets personnalisés : un groupe par objet actif, jamais un
    # modèle natif câblé en dur (adapter générique, permission par objet).
    groups.extend(_custom_record_groups(request.user, co, q))

    return Response({'query': requete, 'groups': groups})


# ── NTPLT34 — autocomplétion tolérante aux fautes (barre ⌘K) ─────────────────
# Lead.nom, Client.nom, Produit.nom (la « désignation » du catalogue) par
# similarité trigramme (pg_trgm, index GIN posés par crm/0161 et stock/0181) :
# « Benani » trouve « Bennani », « Tazy » trouve « Tazi ». Bornée société,
# droit de lecture du module et portée du rôle (comme la recherche globale),
# 10 résultats au plus. Sans pg_trgm : repli icontains (``score`` nul).
SUGGEST_MAX = 10
SEUIL_SIMILARITE = 0.3
_SUGGEST_Q_MAX = 100


def _suggestions(qs, q, trigramme):
    """Les ≤ ``SUGGEST_MAX`` lignes de ``qs`` proches de ``q`` sur ``nom``.
    L'opérateur ``%`` (index GIN) filtre ; ``similarity()`` classe."""
    if trigramme:
        return list(qs.filter(TrigramSimilar(F('nom'), q))
                    .annotate(score_trgm=TrigramSimilarity('nom', q))
                    .filter(score_trgm__gt=SEUIL_SIMILARITE)
                    .order_by('-score_trgm', 'pk')[:SUGGEST_MAX])
    return list(qs.filter(nom__icontains=q).order_by('nom', 'pk')[:SUGGEST_MAX])


def _sources_suggest(user, co):
    """(type, queryset borné, étiquetage) des sources que ``user`` peut lire.
    Jamais de coordonnées personnelles ni de prix dans l'étiquette."""
    from apps.crm.models import Client, Lead
    from apps.crm.selectors import portee_leads
    from apps.stock.models import Produit
    cherchables = platform.searchable_models(user.company)
    sources = []
    if 'crm.lead' in cherchables and _groupe_permis(user, 'crm.lead'):
        sources.append(('lead', portee_leads(Lead.objects.filter(**co), user), lambda le: (
            f"{le.nom} {le.prenom or ''}".strip(), le.societe or le.ville or '')))
    if 'crm.client' in cherchables and _groupe_permis(user, 'crm.client'):
        sources.append(('client', Client.objects.filter(**co), lambda c: (
            f"{c.nom} {c.prenom or ''}".strip(), '')))
    if 'stock.produit' in cherchables and _groupe_permis(user, 'stock.produit'):
        sources.append(('produit', Produit.objects.filter(**co, is_archived=False),
                        lambda p: (p.nom, p.sku or '')))
    return sources


_SEARCH_SUGGEST_REPONSE = inline_serializer('SearchSuggestReponse', {
    'query': drf_serializers.CharField(),
    'results': drf_serializers.JSONField(),
})


@extend_schema(
    parameters=[
        OpenApiParameter('q', OpenApiTypes.STR, required=False),
    ],
    responses={200: _SEARCH_SUGGEST_REPONSE})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def suggest(request):
    """NTPLT34 — ``?q=`` → ``{query, results: [{type, id, label, sublabel,
    score}]}`` (≤ 10, du plus proche au plus lointain)."""
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    q = (request.query_params.get('q') or '').strip()[:_SUGGEST_Q_MAX]
    if len(q) < 2:
        return Response({'query': q, 'results': []})
    trigramme = trigramme_disponible()
    resultats = []
    for type_, qs, etiquette in _sources_suggest(request.user, co):
        for obj in _suggestions(qs, q, trigramme):
            label, sublabel = etiquette(obj)
            score = getattr(obj, 'score_trgm', None)
            resultats.append({
                'type': type_, 'id': obj.pk, 'label': label or '—',
                'sublabel': sublabel,
                'score': round(score, 3) if score is not None else None})
    resultats.sort(key=lambda r: -(r['score'] or 0))  # tri stable
    return Response({'query': q, 'results': resultats[:SUGGEST_MAX]})


_SEARCH_NOTIFICATIONS_REPONSE = inline_serializer('SearchNotificationsReponse', {
    'total': drf_serializers.JSONField(allow_null=True),
    'activites_en_retard': drf_serializers.JSONField(allow_null=True),
    'garanties_expirantes': drf_serializers.JSONField(allow_null=True),
    'factures_impayees': drf_serializers.JSONField(allow_null=True),
    'contrats_a_renouveler': drf_serializers.JSONField(allow_null=True),
    'visites_dues': drf_serializers.JSONField(allow_null=True),
})


@extend_schema(
    responses={200: _SEARCH_NOTIFICATIONS_REPONSE})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def notifications(request):
    """Cloche de notifications in-app (aucun email). Compte + liste cliquable
    des éléments demandant une action, calculés à la volée et bornés société."""
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    today = date.today()

    # ── Activités en retard (records.Activity ouvertes, échéance passée) ──
    # VX84 — bornées à `assigned_to=request.user` : avant ce filtre le badge
    # était company-wide pendant que « Ma file » (records.mine/ma-file) ne
    # montre QUE les activités de l'utilisateur — deux chiffres contradictoires
    # sur la même page. Même source de vérité que records.views.mine/ma_file.
    from apps.records.models import Activity
    overdue_acts = (Activity.objects
                    .filter(**co, assigned_to=request.user, done=False,
                            due_date__lt=today)
                    .select_related('assigned_to')
                    .order_by('due_date')[:20])
    activites = [
        {'id': a.id, 'label': a.summary or 'Activité',
         'date': a.due_date.isoformat() if a.due_date else None,
         'lead_id': (a.object_id if a.content_type_id == _lead_ct_id() else None)}
        for a in overdue_acts
    ]

    # ── Garanties expirant sous 90 jours ─────────────────────────────────
    from apps.sav.models import Equipement
    horizon = today + timedelta(days=90)
    eq_qs = (Equipement.objects
             .filter(**co, date_fin_garantie__gte=today,
                     date_fin_garantie__lte=horizon)
             .select_related('produit')
             .order_by('date_fin_garantie')[:20])
    garanties = [
        {'id': e.id, 'label': (getattr(e.produit, 'nom', None) or e.numero_serie
                               or f"#{e.id}"),
         'date': e.date_fin_garantie.isoformat()}
        for e in eq_qs
    ]

    # ── Factures impayées / en retard ────────────────────────────────────
    # APFS24 — sous ``ventes_voir`` et la portée du rôle (créateur), comme
    # ``ventes/factures/`` : Admin RH n'y lit aucune facture.
    from apps.ventes.models import Facture
    from core.scoping import scope_queryset
    fac_qs = Facture.objects.filter(
        **co, statut__in=[Facture.Statut.EMISE, Facture.Statut.EN_RETARD])
    if not _groupe_permis(request.user, 'ventes.facture'):
        fac_qs = fac_qs.none()
    fac_qs = (scope_queryset(fac_qs, request.user, ['created_by'])
              .select_related('client').order_by('date_echeance')[:20])
    factures = [
        {'id': f.id, 'label': f.reference,
         'sublabel': getattr(f.client, 'nom', '') or '',
         # `date` = échéance (sert au tri par urgence côté cloche).
         'date': f.date_echeance.isoformat() if f.date_echeance else None,
         'overdue': bool(f.date_echeance and f.date_echeance < today)}
        for f in fac_qs
    ]

    # ── N83 — signaux maintenance : contrats à renouveler ≤ 90 j + visites
    #    dues. Le « dû » et la prochaine visite sont calculés À LA LECTURE sur
    #    le modèle (pas de planificateur), cohérent avec ContratMaintenance.
    from apps.sav.models import ContratMaintenance
    contrats_actifs = (ContratMaintenance.objects
                       .filter(**co, actif=True)
                       .select_related('client')
                       .order_by('date_renouvellement', 'derniere_visite'))
    renouvellements = []
    visites_dues = []
    for c in contrats_actifs:
        client_nom = str(c.client) if c.client_id else f"Contrat #{c.id}"
        # Renouvellement à échéance dans ≤ 90 jours (incluant déjà dépassée).
        if c.date_renouvellement and c.date_renouvellement <= horizon:
            renouvellements.append({
                'id': c.id, 'label': f"Renouvellement — {client_nom}",
                'date': c.date_renouvellement.isoformat(),
                'overdue': c.date_renouvellement < today})
        # Visite due : prochaine visite calculée déjà atteinte.
        if c.is_due(today):
            prochaine = c.prochaine_visite()
            visites_dues.append({
                'id': c.id, 'label': f"Visite due — {client_nom}",
                'date': prochaine.isoformat() if prochaine else None,
                'overdue': True})
    renouvellements = renouvellements[:20]
    visites_dues = visites_dues[:20]

    return Response({
        'total': (len(activites) + len(garanties) + len(factures)
                  + len(renouvellements) + len(visites_dues)),
        'activites_en_retard': activites,
        'garanties_expirantes': garanties,
        'factures_impayees': factures,
        'contrats_a_renouveler': renouvellements,
        'visites_dues': visites_dues,
    })


def _lead_ct_id():
    from apps.crm.models import Lead
    return ContentType.objects.get_for_model(Lead).id
