"""Import UNIDIRECTIONNEL (Odoo → ERP) des notes de lead dans le chatter CRM.

    python manage.py odoo_import_notes [--company <slug-ou-id>] [--dry-run]

Lit en LECTURE SEULE le chatter Odoo (``mail.message`` de type « comment » sur
``crm.lead`` — les notes internes de Meryem & co) et le champ ``description``
de chaque fiche, matche le lead ERP correspondant par téléphone/email
normalisés (mêmes colonnes que le reste du CRM) et dépose chaque note dans le
chatter du lead via le service crm sanctionné
(``import_external_notes_for_contact``).

Idempotent par id de message Odoo (marqueur ``[Odoo note <id>]`` /
``[Odoo] Description`` en préfixe du corps) : re-exécutable à volonté, jamais
un doublon. **RIEN n'est écrit dans Odoo** (client hard-allowlisté lecture
seule) ; les leads Odoo sans correspondance ERP sont comptés et attendront la
migration complète (P3) — jamais créés ici.
"""
from django.core.management.base import BaseCommand
from django.utils.html import strip_tags


def _clean_html(body):
    """Corps ``mail.message`` (HTML Odoo) → texte plat lisible en chatter."""
    import html as html_lib
    import re

    text = str(body or '')
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = re.sub(r'</p>', '\n', text, flags=re.I)
    text = html_lib.unescape(strip_tags(text))
    return re.sub(r'\n{3,}', '\n\n', text).strip()


class Command(BaseCommand):
    help = ("Importe les notes Odoo (chatter + description) dans le chatter "
            "des leads ERP correspondants (matching téléphone/email, "
            "idempotent, Odoo jamais modifié).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help="Slug ou id de la société ERP cible (défaut : première).")
        parser.add_argument(
            '--dry-run', action='store_true', dest='dry_run',
            help="Compte ce qui serait importé sans rien écrire dans l'ERP.")

    def _resolve_company(self, raw):
        from authentication.models import Company
        if raw is not None:
            company = Company.objects.filter(slug=raw).first()
            if company is None and str(raw).isdigit():
                company = Company.objects.filter(pk=int(raw)).first()
            return company
        return Company.objects.order_by('id').first()

    def handle(self, *args, **options):
        from apps.adsengine import odoo_client

        company = self._resolve_company(options.get('company'))
        if company is None:
            self.stdout.write(self.style.ERROR('Aucune société ERP trouvée.'))
            return
        client = odoo_client.OdooClient.from_env()
        if client is None:
            self.stdout.write(self.style.WARNING(
                'Connecteur Odoo non configuré (variables ODOO_*) — no-op.'))
            return

        # 1. Fiches Odoo (actives + archivées) avec leurs coordonnées.
        odoo_leads = client.search_read_all(
            'crm.lead',
            ['|', ('active', '=', True), ('active', '=', False)],
            fields=['id', 'phone', 'mobile', 'email_from', 'description'],
            order='id')
        by_id = {row['id']: row for row in odoo_leads}
        self.stdout.write('Fiches Odoo lues : %d' % len(odoo_leads))

        # 2. Notes internes du chatter (« comment » = notes humaines ; les
        #    notifications de changement d'étape n'en font pas partie).
        messages = client.search_read_all(
            'mail.message',
            [('model', '=', 'crm.lead'), ('message_type', '=', 'comment')],
            fields=['id', 'res_id', 'body', 'date', 'author_id'],
            order='id')
        self.stdout.write('Notes de chatter Odoo lues : %d' % len(messages))

        notes_by_lead = {}
        for msg in messages:
            text = _clean_html(msg.get('body'))
            if not text:
                continue
            author = msg.get('author_id')
            author_label = (author[1] if isinstance(author, (list, tuple))
                            and len(author) > 1 else 'Odoo')
            marker = '[Odoo note %s]' % msg['id']
            body = '%s %s — %s :\n%s' % (
                marker, str(msg.get('date') or '')[:16], author_label, text)
            notes_by_lead.setdefault(msg.get('res_id'), []).append(
                (marker, body))
        # Le champ description de la fiche (facture, contexte…) compte aussi.
        for oid, row in by_id.items():
            desc = _clean_html(row.get('description'))
            if desc:
                marker = '[Odoo] Description de la fiche %s' % oid
                notes_by_lead.setdefault(oid, []).insert(
                    0, (marker, '%s :\n%s' % (marker, desc)))

        from apps.crm.services import import_external_notes_for_contact

        matched = unmatched = created = 0
        dry_run = options.get('dry_run')
        for oid, notes in notes_by_lead.items():
            row = by_id.get(oid)
            if row is None:
                continue
            phone = (row.get('phone') or row.get('mobile') or '') or None
            email = (row.get('email_from') or '') or None
            if not (phone or email):
                unmatched += 1
                continue
            if dry_run:
                matched += 1
                created += len(notes)
                continue
            ok, n = import_external_notes_for_contact(
                company, phone=phone, email=email, notes=notes)
            if ok:
                matched += 1
                created += n
            else:
                unmatched += 1

        verb = 'seraient importées' if dry_run else 'importées'
        self.stdout.write(self.style.SUCCESS(
            'Fiches Odoo avec notes : %d — matchées ERP : %d, sans '
            'correspondance : %d — notes %s : %d'
            % (len(notes_by_lead), matched, unmatched, verb, created)))
        if unmatched:
            self.stdout.write(
                'Les fiches sans correspondance attendent la migration '
                'complète (P3) — rien n\'est créé ici.')
