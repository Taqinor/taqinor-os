"""Sélecteurs transverses de la couche fondation ``core`` (YRBAC11).

``TenantMixin`` scope automatiquement le queryset générique d'un
``ModelViewSet`` (liste + ``get_object`` du détail), mais les vues
FONCTIONNELLES (``@api_view``) et les ``@action`` qui chargent un objet « à la
main » via ``Model.objects.get(pk=…)``/``get_object_or_404(Model, pk=…)``
peuvent oublier de re-borner à la société de l'appelant — un ID d'une AUTRE
société serait alors accessible (fuite cross-tenant).

``get_company_object`` est le remplacement canonique : filtre TOUJOURS par
``company`` (+ une portée additionnelle optionnelle, ex.
``core.scoping.visible_user_ids``) et renvoie un 404 INDISTINCT de « l'objet
n'existe pas » — jamais un signal différent pour « existe mais pas à toi »
(l'existence d'un enregistrement d'une autre société est elle-même sensible).

``core`` reste FONDATION : aucun import d'app métier au niveau module (le
seul couplage est le paramètre ``model`` passé par l'appelant).
"""
from __future__ import annotations

from django.http import Http404


def get_company_object(model_or_queryset, pk, user, extra_scope=None,
                       **extra_filters):
    """Renvoie l'instance scopée à la société de ``user`` d'id ``pk``, ou lève
    ``Http404`` — INDISTINCTEMENT d'un ``pk`` inexistant.

    Args:
        model_or_queryset: une classe de modèle Django (doit porter un champ
            ``company``), OU un queryset déjà construit (ex. avec
            ``select_related``/``prefetch_related`` pour éviter le N+1) — les
            DEUX sont acceptés, le filtrage société/portée s'applique dessus.
        pk: la clé primaire demandée (brute, non validée par l'appelant).
        user: ``request.user``. Sans société (et sans superuser), renvoie
            TOUJOURS 404 (jamais de fuite implicite).
        extra_scope: callable optionnel ``qs, user -> qs`` appliqué APRÈS le
            filtre société (ex. ``core.scoping.scope_queryset`` pour borner en
            plus à la portée d'équipe/sous-arbre d'un rôle narrowed). Ignoré
            (aucun narrowing) si ``None`` — comportement historique.
        **extra_filters: filtres additionnels appliqués tels quels (ex.
            ``confidentialite='public'``).

    Un superuser SANS société voit tout (comportement plateforme historique,
    identique à ``TenantMixin``) ; un superuser AVEC société reste scopé à
    cette société (usage ERP normal).
    """
    qs = (
        model_or_queryset.objects.all()
        if hasattr(model_or_queryset, 'objects')
        else model_or_queryset
    )
    company_id = getattr(user, 'company_id', None)
    if company_id:
        qs = qs.filter(company_id=company_id)
    elif not getattr(user, 'is_superuser', False):
        qs = qs.none()
    if extra_filters:
        qs = qs.filter(**extra_filters)
    if extra_scope is not None:
        qs = extra_scope(qs, user)
    obj = qs.filter(pk=pk).first()
    if obj is None:
        # Message générique — jamais « appartient à une autre société » :
        # l'existence d'un enregistrement hors-société est elle-même une
        # fuite (IDOR par énumération).
        raise Http404('Introuvable.')
    return obj


# ── SCA25 — signature d'email brandée (BrandedTemplate FG393) ────────────────
# Code d'usage canonique du modèle de signature d'email d'une société. Un
# ``BrandedTemplate(company, kind='email', code=EMAIL_SIGNATURE_CODE)`` actif,
# s'il existe, pilote la signature des emails transactionnels ; sinon on retombe
# sur « L'équipe {nom de la société} ». Constante ici (et non en dur dans
# ``ventes``) pour rester la SEULE source du code d'usage.
EMAIL_SIGNATURE_CODE = 'signature'


def resolve_email_signature(company, nom_societe='', **context) -> str:
    """Signature à apposer au bas d'un email transactionnel d'une société.

    ``core`` reste FONDATION : la SIGNATURE elle-même vient soit d'un
    ``BrandedTemplate`` (kind ``email``, code ``signature``, FG393) que la
    société a rédigé — rendu par ``core.templating`` (substitution littérale,
    aucun code exécuté) —, soit d'un REPLI neutre « L'équipe {nom de la
    société} ». Plus aucun nom codé en dur (TAQINOR) : la marque du fondateur
    ne s'affiche que parce que SON ``CompanyProfile.nom`` vaut « TAQINOR » —
    comportement préservé PAR LA DONNÉE, jamais par le code.

    ``nom_societe`` est fourni par l'appelant (résolu depuis
    ``CompanyProfile`` — que ``core`` ne connaît pas). ``context`` alimente les
    placeholders ``{{ … }}`` du modèle (ex. ``reference``). Ne lève jamais :
    toute erreur retombe sur le repli neutre.
    """
    from core.templating import rendre  # import local : évite tout cycle

    nom = (nom_societe or '').strip()
    fallback = f"L'équipe {nom}" if nom else "L'équipe"

    if company is None:
        return fallback
    try:
        from core.models import BrandedTemplate
        tpl = (
            BrandedTemplate.objects
            .filter(company=company, kind=BrandedTemplate.KIND_EMAIL,
                    code=EMAIL_SIGNATURE_CODE, actif=True)
            .first()
        )
    except Exception:  # noqa: BLE001 — un email ne casse jamais sur ce point
        tpl = None
    if tpl is None or not (tpl.corps or '').strip():
        return fallback

    ctx = {'nom': nom, 'nom_societe': nom, 'equipe': fallback}
    ctx.update(context)
    rendu = rendre(tpl.corps, ctx).strip()
    return rendu or fallback


# ── VX76 — wrapper HTML de marque UNIQUE pour les emails transactionnels ─────
def wrap_email_html(
        sujet, corps_texte, *, company_nom='', company_adresse='',
        company_telephone='', company_email='', couleur_principale=''):
    """Rend ``templates/email/base.html`` (logo textuel + en-tête navy + pied)
    autour d'un corps texte brut existant.

    ``core`` reste FONDATION : ce wrapper ne fait que RENDRE — aucune logique
    métier, aucun changement de statut, aucun nouvel EmailLog/chatter (RULE #4
    du même esprit : un moteur de rendu ne décide jamais). Le corps texte brut
    est converti en HTML minimal (retours à la ligne → ``<br>``, échappé pour
    éviter toute injection) et injecté dans le bloc central du gabarit. Les
    identifiants de société sont fournis par l'appelant (résolus via
    ``apps.parametres.selectors.company_identity`` — que ``core`` ne connaît
    pas). Ne lève jamais : une erreur de rendu retombe sur le corps texte brut
    tel quel (repli identique au comportement actuel)."""
    from django.template.loader import render_to_string
    from django.utils.html import escape, linebreaks

    try:
        corps_html = linebreaks(escape(corps_texte or ''))
        return render_to_string('email/base.html', {
            'sujet': sujet or '',
            'corps_html': corps_html,
            'company_nom': company_nom or '',
            'company_adresse': company_adresse or '',
            'company_telephone': company_telephone or '',
            'company_email': company_email or '',
            'couleur_principale': couleur_principale or '',
        })
    except Exception:  # noqa: BLE001 — un email ne casse jamais sur ce point
        return corps_texte or ''
