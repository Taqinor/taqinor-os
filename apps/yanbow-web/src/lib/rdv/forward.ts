/**
 * Proxy même origine `POST /api/rendez-vous` (YBW54) — logique testable seule
 * (la route `src/pages/api/rendez-vous.ts` ne fait que brancher l'exécution
 * Cloudflare : `env`, `waitUntil`).
 *
 * ORDRE : garde d'origine (403) → limite par isolat (429 + Retry-After) → JSON
 * → pot de miel (faux succès, jamais transmis) → validation du registre
 * (erreurs PAR CHAMP, dans la langue) → consentement requis → envoi signé EN
 * ARRIÈRE-PLAN (`waitUntil`) des SEULES clés du registre vers l'ERP.
 *
 * Envoi : `X-Site-Cle`, `X-Signature` (HMAC Web Crypto, `t=,v1=`),
 * `Idempotency-Key` (miroir de `idempotency_key` du corps signé) ; AUCUNE IP
 * ni agent du visiteur ; délai 8 s ; nouvel essai (re-signé) seulement sur
 * 5xx/429 ; échec non définitif → reprise KV si elle existe. Variables PROPRES
 * (`YANBOW_RDV_URL`, `YANBOW_RDV_CLE_ID`, `YANBOW_RDV_SECRET`) — jamais celles
 * du site TAQINOR. Aucune donnée personnelle dans les journaux ni l'URL ;
 * échecs consécutifs comptés → une ligne `ALERT` au-delà d'un seuil.
 */
import type { Locale } from '../../i18n/config';
import { KV_REPRISE_DUREE_JOURS } from '../subprocessors';
import { creerLimiteur } from '../rateLimit';
import { CLES_CHAMPS, POT_DE_MIEL, messageErreur, normaliserDemande, type CleChamp } from './champs';
import { signer } from './sign';
import { espaceReprise, mettreEnReprise, rejouerReprise, type EspaceKv, type Issue } from '../../../worker/reprise.mjs';

export interface EnvRdv {
  YANBOW_RDV_URL?: unknown;
  YANBOW_RDV_CLE_ID?: unknown;
  YANBOW_RDV_SECRET?: unknown;
  RDV_REPRISE?: unknown;
}

export interface Journal {
  info: (ligne: string) => void;
  warn: (ligne: string) => void;
  error: (ligne: string) => void;
}

export interface Dependances {
  env: EnvRdv;
  /** `waitUntil` du Worker ; absent → l'envoi est attendu avant la réponse. */
  waitUntil?: (p: Promise<unknown>) => void;
  fetch: typeof fetch;
  /** Horloge (ms) — simulable en test. */
  maintenant: () => number;
  journal: Journal;
  nouvelleCle: () => string;
  /** Durée de la reprise (jours) ; `null` = pas de reprise (registre YBW26). */
  dureeRepriseJours: number | null;
}

export const TAILLE_MAX = 16 * 1024;
export const DELAI_ENVOI_MS = 8000;
export const SEUIL_ALERTE = 3;
export const LIMITE_PAR_MINUTE = 20;

const limiteur = creerLimiteur(LIMITE_PAR_MINUTE, 60_000);
let echecsConsecutifs = 0;

/** Remet les compteurs de l'isolat à zéro (tests). */
export function reinitialiserEtat(): void {
  limiteur.reinitialiser();
  echecsConsecutifs = 0;
}

const MESSAGES_GLOBAUX: Record<Locale, { limite: string; indisponible: string; corps: string }> = {
  fr: {
    limite: 'Trop de demandes en même temps. Réessayez dans un instant.',
    indisponible: "L'envoi de demandes n'est pas encore ouvert. Utilisez WhatsApp en attendant.",
    corps: "La demande n'a pas pu être lue. Rechargez la page puis réessayez.",
  },
  en: {
    limite: 'Too many requests at once. Please try again in a moment.',
    indisponible: 'Requests cannot be sent yet. Please use WhatsApp in the meantime.',
    corps: 'The request could not be read. Reload the page and try again.',
  },
};

function json(data: unknown, status: number, entetes: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...entetes },
  });
}

/** Même origine : `Sec-Fetch-Site` d'abord ; absent → repli sur `Origin` ; aucun des deux → refus. */
export function memeOrigine(request: Request): boolean {
  const site = request.headers.get('sec-fetch-site');
  if (site) return site === 'same-origin';
  const origine = request.headers.get('origin');
  return origine !== null && origine === new URL(request.url).origin;
}

interface Config {
  url: string;
  cleId: string;
  secret: string;
}

function config(env: EnvRdv): Config | null {
  const lire = (v: unknown) => (typeof v === 'string' ? v.trim() : '');
  const url = lire(env.YANBOW_RDV_URL);
  const cleId = lire(env.YANBOW_RDV_CLE_ID);
  const secret = lire(env.YANBOW_RDV_SECRET);
  if (!url || !cleId || !secret) return null;
  try {
    if (new URL(url).protocol !== 'https:' && !/^http:\/\/(127\.0\.0\.1|localhost)(:|\/)/.test(url)) return null;
  } catch {
    return null;
  }
  return { url, cleId, secret };
}

/**
 * Un envoi signé (t = maintenant), délai 8 s. Renvoie l'issue et un motif sans
 * donnée personnelle (code HTTP ou nature de l'échec).
 */
export async function envoyerUneFois(corps: string, idempotencyKey: string, cfg: Config, deps: Dependances): Promise<{ issue: Issue; motif: string }> {
  const t = Math.floor(deps.maintenant() / 1000);
  const ctrl = new AbortController();
  const minuterie = setTimeout(() => ctrl.abort(), DELAI_ENVOI_MS);
  try {
    const r = await deps.fetch(cfg.url, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-site-cle': cfg.cleId,
        'x-signature': await signer(cfg.secret, corps, t),
        'idempotency-key': idempotencyKey,
      },
      body: corps,
      signal: ctrl.signal,
      redirect: 'error',
    });
    if (r.status >= 200 && r.status < 300) return { issue: 'livre', motif: String(r.status) };
    if (r.status === 429 || r.status >= 500) return { issue: 'reessayer', motif: String(r.status) };
    return { issue: 'definitif', motif: String(r.status) };
  } catch {
    return { issue: 'reessayer', motif: ctrl.signal.aborted ? 'delai' : 'reseau' };
  } finally {
    clearTimeout(minuterie);
  }
}

/** Envoi + UN nouvel essai (re-signé) seulement sur 5xx/429. */
async function envoyerAvecEssai(corps: string, idempotencyKey: string, cfg: Config, deps: Dependances) {
  const premier = await envoyerUneFois(corps, idempotencyKey, cfg, deps);
  if (premier.issue !== 'reessayer' || !/^(429|5\d\d)$/.test(premier.motif)) return premier;
  return envoyerUneFois(corps, idempotencyKey, cfg, deps);
}

function compterIssue(livre: boolean, motif: string, journal: Journal): void {
  if (livre) {
    echecsConsecutifs = 0;
    return;
  }
  echecsConsecutifs += 1;
  if (echecsConsecutifs >= SEUIL_ALERTE) {
    journal.error(
      `[rendez-vous][ALERT] ${echecsConsecutifs} échecs de livraison consécutifs vers l'ERP (dernier motif : ${motif}) — vérifier YANBOW_RDV_URL / SITE_RDV_CLES.`,
    );
  }
}

/** Livraison complète d'une demande (arrière-plan). Ne lève jamais. */
export async function livrer(corps: string, idempotencyKey: string, cfg: Config, deps: Dependances): Promise<void> {
  try {
    const { issue, motif } = await envoyerAvecEssai(corps, idempotencyKey, cfg, deps);
    compterIssue(issue === 'livre', motif, deps.journal);
    const kv: EspaceKv | null = espaceReprise(deps.env.RDV_REPRISE, deps.dureeRepriseJours, deps.journal);
    if (issue === 'livre') {
      deps.journal.info(`[rendez-vous] livrée (${motif})`);
      if (kv) {
        const bilan = await rejouerReprise(
          kv,
          async (c) => {
            const cle = (JSON.parse(c) as { idempotency_key?: string }).idempotency_key ?? '';
            return (await envoyerUneFois(c, cle, cfg, deps)).issue;
          },
          { journal: deps.journal },
        );
        if (bilan.livrees || bilan.definitives) {
          deps.journal.info(`[rendez-vous] reprise : ${bilan.livrees} livrée(s), ${bilan.definitives} refusée(s), ${bilan.restantes} en attente`);
        }
      }
      return;
    }
    if (issue === 'definitif') {
      deps.journal.error(`[rendez-vous] refusée par l'ERP (${motif}) — non rejouée`);
      return;
    }
    deps.journal.warn(`[rendez-vous] non livrée (${motif})`);
    if (kv && deps.dureeRepriseJours) {
      await mettreEnReprise(kv, idempotencyKey, corps, deps.dureeRepriseJours);
      deps.journal.info('[rendez-vous] mise en reprise');
    }
  } catch {
    deps.journal.error('[rendez-vous] livraison interrompue (erreur interne)');
  }
}

/** Traite `POST /api/rendez-vous`. */
export async function traiterDemande(request: Request, deps: Dependances): Promise<Response> {
  if (request.method !== 'POST') return new Response(null, { status: 405, headers: { allow: 'POST' } });
  if (!memeOrigine(request)) return json({ ok: false }, 403);

  const essai = limiteur.tenter(deps.maintenant());
  if (!essai.ok) {
    return json({ ok: false, erreurs: { envoi: MESSAGES_GLOBAUX.fr.limite } }, 429, { 'retry-after': String(essai.retryAfterSec) });
  }

  if (Number(request.headers.get('content-length') ?? '0') > TAILLE_MAX) return json({ ok: false }, 413);
  const brut = await request.text();
  if (brut.length > TAILLE_MAX) return json({ ok: false }, 413);
  let donnees: unknown;
  try {
    donnees = JSON.parse(brut);
  } catch {
    return json({ ok: false, erreurs: { envoi: MESSAGES_GLOBAUX.fr.corps } }, 400);
  }
  if (!donnees || typeof donnees !== 'object' || Array.isArray(donnees)) {
    return json({ ok: false, erreurs: { envoi: MESSAGES_GLOBAUX.fr.corps } }, 400);
  }
  const entree = donnees as Record<string, unknown>;

  // Pot de miel : un humain ne le voit pas ; faux succès, rien n'est transmis.
  const piege = entree[POT_DE_MIEL];
  if (typeof piege === 'string' && piege.trim() !== '') return json({ ok: true }, 200);

  const { langue, corps, erreurs } = normaliserDemande(entree, new Date(deps.maintenant()), deps.nouvelleCle);
  const cles = Object.keys(erreurs) as CleChamp[];
  if (cles.length > 0) {
    const messages: Partial<Record<CleChamp, string>> = {};
    for (const cle of CLES_CHAMPS) {
      const code = erreurs[cle];
      if (code) messages[cle] = messageErreur(cle, code, langue);
    }
    return json({ ok: false, erreurs: messages }, 400);
  }

  const cfg = config(deps.env);
  if (!cfg) {
    deps.journal.warn('[rendez-vous] envoi non configuré (YANBOW_RDV_URL / YANBOW_RDV_CLE_ID / YANBOW_RDV_SECRET)');
    return json({ ok: false, erreurs: { envoi: MESSAGES_GLOBAUX[langue].indisponible } }, 503);
  }

  const texte = JSON.stringify(corps);
  const arrierePlan = livrer(texte, String(corps.idempotency_key), cfg, deps);
  if (deps.waitUntil) deps.waitUntil(arrierePlan);
  else await arrierePlan;
  return json({ ok: true }, 200);
}

/** Dépendances réelles du Worker (la route les complète avec `env`/`waitUntil`). */
export function dependancesWorker(env: EnvRdv, waitUntil?: (p: Promise<unknown>) => void): Dependances {
  return {
    env,
    waitUntil,
    fetch: (...a) => fetch(...a),
    maintenant: () => Date.now(),
    journal: { info: (l) => console.log(l), warn: (l) => console.warn(l), error: (l) => console.error(l) },
    nouvelleCle: () => crypto.randomUUID(),
    dureeRepriseJours: KV_REPRISE_DUREE_JOURS,
  };
}
