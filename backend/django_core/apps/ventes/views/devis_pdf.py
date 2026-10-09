"""SPL139 — le rendu PDF du devis (``/proposal``, ``generer-pdf``,
``etat-pdf``, ``telecharger-pdf``), déplacement pur depuis
``views/devis.py`` : corps octet-identiques, routes inchangées.

RÈGLE #4 : ``/proposal`` reste le SEUL chemin du PDF client ; ce module ne
fait que RENDRE (aucun statut écrit), le routage ``USE_PREMIUM_QUOTE_ENGINE``
est inchangé et ``quote_engine/**`` n'est pas touché. Les imports
``from ..quote_engine import …`` / ``from ..utils.pdf import …`` restent
function-locaux (les ``mock.patch`` ``apps.ventes.quote_engine.*`` /
``apps.ventes.utils.pdf.*`` n'interceptent qu'ainsi).
"""
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from . import openapi_docs as D
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import Devis
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from apps.roles.permissions import IsInternalWriterOrPortalClientOwner


#: ADEV31 — le seul texte servi quand le rendu de ``/proposal`` échoue.
MSG_PROPOSITION_INDISPONIBLE = (
    'Génération de la proposition momentanément indisponible.')


def _signaler_pdf_devis_genere(devis):
    """ADEV22 — émet ``document_pdf_generated(kind='devis')`` (journal
    d'audit) ; jamais bloquant pour le rendu."""
    from core.events import document_pdf_generated
    try:
        document_pdf_generated.send(sender=Devis, instance=devis, kind='devis')
    except Exception:  # noqa: BLE001 — un journal raté ne casse pas le rendu
        import logging
        logging.getLogger(__name__).exception(
            'ADEV22 : audit PDF devis ignoré (devis %s)', devis.pk)


class DevisPdfActionsMixin:
    """SPL139 — actions de rendu PDF de ``DevisViewSet`` (mixin, aucune base)."""

    @extend_schema(request=D.PdfOptionsRequest, responses={202: D.PdfTaskResponse})
    @action(
        detail=True,
        methods=['post'],
        url_path='generer-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def generer_pdf(self, request, pk=None):
        devis = self.get_object()
        from ..quote_engine import clean_pdf_options
        from ..tasks import task_generate_devis_pdf
        # Format options (simulator parity) — whitelisted server-side.
        pdf_options = clean_pdf_options(request.data)
        task = task_generate_devis_pdf.delay(devis.id, pdf_options)
        # ADEV22 (C-ADEV-028) — l'entrée d'audit « PDF devis généré » n'est
        # plus écrite à la DEMANDE (202) : la tâche l'émet à son rendu réussi.
        # WIR217 — une nouvelle demande efface l'échec consigné : sinon un
        # « Réessayer » repartirait déjà marqué en échec.
        from ..tasks import oublier_echec_pdf_devis
        oublier_echec_pdf_devis(devis.id)
        return Response(
            {'task_id': task.id, 'detail': 'Génération PDF lancée.'},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path='etat-pdf',
        # Même garde que la LECTURE d'un devis (cf. get_permissions) : c'est un
        # état de rendu, pas une donnée métier de plus.
        permission_classes=[IsAnyRole],
    )
    def etat_pdf(self, request, pk=None):
        """WIR217 — état de la génération du PDF : prêt / en cours / ÉCHEC.

        Le sondage du frontend ne lisait que ``fichier_pdf`` : un échec
        DÉFINITIF de ``task_generate_devis_pdf`` (retries épuisés) était donc
        invisible et le sondage tournait sans fin. Cet endpoint expose l'état
        consigné par la tâche (patron EXPORT_JOB, cache scopé société).

        ``erreur``/``date`` ne sont renseignés QUE sur l'état ``echec`` ; un
        rendu déjà prêt l'emporte toujours sur un échec plus ancien.
        """
        from django.core.cache import cache
        from ..tasks import pdf_job_cache_key

        devis = self.get_object()  # scoping société (404 hors société)
        job = cache.get(pdf_job_cache_key(devis.pk)) or {}
        # Défense en profondeur : jamais l'état d'une AUTRE société, même si
        # une clé de cache venait à collisionner.
        if job.get('company_id') not in (None, devis.company_id):
            job = {}
        pret = bool(devis.fichier_pdf)
        if pret:
            statut = 'pret'
        elif job.get('status') == 'error':
            statut = 'echec'
        else:
            statut = 'en_cours'
        return Response({
            'devis': devis.pk,
            'statut': statut,
            'fichier_pdf': pret,
            'erreur': job.get('error') if statut == 'echec' else None,
            'date': job.get('at') if statut == 'echec' else None,
        })

    @extend_schema(parameters=[OpenApiParameter('pdf_mode', OpenApiTypes.STR, required=False, enum=['full', 'onepage']), OpenApiParameter('show_monthly', OpenApiTypes.STR, required=False), OpenApiParameter('devis_final', OpenApiTypes.STR, required=False), OpenApiParameter('include_etude', OpenApiTypes.STR, required=False), OpenApiParameter('include_calepinage', OpenApiTypes.STR, required=False), OpenApiParameter('include_note_calcul', OpenApiTypes.STR, required=False), OpenApiParameter('langue', OpenApiTypes.STR, required=False)], responses={(200, 'application/pdf'): OpenApiTypes.BINARY})
    @action(
        detail=True,
        methods=['get'],
        url_path='proposal',
        # NTPRT10 — MÊME classe que la branche `proposal` de get_permissions
        # ci-dessus (qui prime) : la déclaration de l'@action ne doit jamais
        # annoncer une garde différente de la garde effective.
        permission_classes=[IsInternalWriterOrPortalClientOwner],
    )
    def proposal(self, request, pk=None):
        """Canonical client-facing quote PDF path (CLAUDE.md rule #4).

        Renders the premium quote PDF for this devis (synchronously, via the
        vendored quote engine), stores it in MinIO and streams it inline.
        """
        devis = self.get_object()
        try:
            from ..quote_engine import clean_pdf_options, generate_premium_devis_pdf
            from ..utils.pdf import download_pdf
            # Format via query params, e.g. ?pdf_mode=onepage&devis_final=1
            raw = {
                'pdf_mode': request.query_params.get('pdf_mode'),
            }
            if 'show_monthly' in request.query_params:
                raw['show_monthly'] = request.query_params['show_monthly'] not in ('0', 'false')
            if 'devis_final' in request.query_params:
                raw['devis_final'] = request.query_params['devis_final'] in ('1', 'true')
            # Page « Étude » (4e page premium) — dégrade proprement à 3 pages
            # si le devis n'a pas de données d'étude (géré par le moteur).
            if 'include_etude' in request.query_params:
                raw['include_etude'] = request.query_params['include_etude'] in ('1', 'true')
            # CAL183 — page « Calepinage » (planche cotée). Le défaut est AUTO
            # (présente dès que le devis porte un calepinage dessinable) : le
            # paramètre n'existe donc QUE pour trancher explicitement, et son
            # absence laisse l'AUTO décider. `?include_calepinage=0` est
            # l'opt-out ; toute autre valeur vaut « oui » — même lecture que
            # `include_etude` juste au-dessus, jamais une seconde convention.
            if 'include_calepinage' in request.query_params:
                raw['include_calepinage'] = (
                    request.query_params['include_calepinage'] in ('1', 'true'))
            # APDF16 (C-APDF-007) / AMOT68 — annexe « Note de calcul » agricole
            # (AGR319) : même convention que `include_etude` (`1`/`true` =
            # oui). Absent ⇒ défaut moteur (pas d'annexe) ; un devis non
            # agricole ignore l'option (le moteur en décide).
            if 'include_note_calcul' in request.query_params:
                raw['include_note_calcul'] = (
                    request.query_params['include_note_calcul'] in ('1', 'true'))
            # NTI18N4 — langue de sortie du document, INDÉPENDANTE de la
            # langue d'interface de qui génère le PDF. `?langue=` écrase la
            # résolution auto (priorité : explicite > Client.langue_document
            # > repli société [NTI18N34, pas encore construit] > FR). Le
            # moteur reçoit toujours une valeur DÉJÀ résolue — jamais un
            # second moteur, jamais de logique de langue dupliquée ici.
            # APDF18 — la résolution AUTOMATIQUE (client, repli société) vit
            # désormais dans le moteur (APDF7) : la vue ne transmet que le
            # `?langue=` EXPLICITE (validé par le résolveur).
            if request.query_params.get('langue'):
                from apps.parametres.i18n_resolver import resolve_langue_sortie
                raw['langue_sortie'] = resolve_langue_sortie(
                    langue_explicite=request.query_params.get('langue'),
                    client=devis.client, company=devis.company)
            # ERR74 — /proposal is a safe GET: render + stream, but do NOT
            # persist fichier_pdf on every call (persist=False). The single
            # engine picks the residential (redesigned) or legacy renderer.
            key = generate_premium_devis_pdf(
                devis.id, clean_pdf_options(raw), persist=False)
            pdf_bytes = download_pdf(key)
        except Exception:
            # ADEV31 (C-ADEV-043) — jamais le texte brut de l'exception au
            # client (hôte, bucket, chemin) : message neutre, pile au journal.
            import logging
            logging.getLogger(__name__).exception(
                '/proposal : rendu échoué (devis %s)', devis.pk)
            return Response(
                {'detail': MSG_PROPOSITION_INDISPONIBLE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        # ADEV22 — audit au RENDU réussi (M4 : ventes émet, le satellite audit
        # journalise AuditLog.Action.PDF ; signal synchrone, même acteur).
        _signaler_pdf_devis_genere(devis)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        # QD2 — nom cohérent (société _ type _ client _ référence).
        from ..utils.filenames import document_filename
        filename = document_filename(
            'Proposition', devis.reference,
            client=devis.client if devis.client_id else None,
            company=devis.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response

    @extend_schema(responses={(200, 'application/pdf'): OpenApiTypes.BINARY})
    @action(
        detail=True,
        methods=['get'],
        url_path='telecharger-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def telecharger_pdf(self, request, pk=None):
        devis = self.get_object()
        if not devis.fichier_pdf:
            return Response(
                {'detail': (
                    'PDF non disponible. '
                    'Cliquez d\'abord sur « Générer PDF ».'
                )},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            from ..utils.pdf import download_pdf
            # PVFRESH — ce bouton livrait les octets du DERNIER rendu, quelle
            # que soit l'ancienneté de ce rendu : « Générer PDF », puis on
            # corrige une quantité, puis « Télécharger » → le commercial
            # repartait avec le PDF d'AVANT la correction et l'envoyait au
            # client, pendant que la page /proposition (qui, elle, re-rend à
            # chaque appel) montrait les chiffres à jour. C'est exactement la
            # divergence page/PDF signalée le 18/08/2026. On compare donc
            # l'empreinte des données à celle du fichier stocké : identiques →
            # aucun re-rendu (le cache garde tout son intérêt), différentes →
            # re-rendu dans LE MÊME format avant de servir.
            #
            # DÉGRADATION : si le rafraîchissement lui-même échoue (moteur ou
            # stockage momentanément indisponible), on retombe sur le fichier
            # stocké plutôt que de refuser le téléchargement — ce bouton
            # fonctionnait avant PVFRESH, il doit continuer de fonctionner.
            from ..quote_engine import cle_pdf_a_jour
            try:
                cle = cle_pdf_a_jour(devis)
            except Exception:  # noqa: BLE001
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    'PVFRESH: rafraîchissement impossible pour %s — le fichier '
                    'stocké est servi tel quel', devis.reference,
                    exc_info=True)
                cle = devis.fichier_pdf
            pdf_bytes = download_pdf(cle)
        except Exception:
            return Response(
                {'detail': 'Fichier introuvable. Régénérez le PDF.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        # QD2 — nom cohérent (société _ type _ client _ référence).
        from ..utils.filenames import document_filename
        filename = document_filename(
            'Devis', devis.reference,
            client=devis.client if devis.client_id else None,
            company=devis.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response
