/**
 * WAUD47 — liens vers les textes officiels de la loi 82-21, vérifiés en HTTP 200 le 3 novembre 2026
 * (sans redirection). Le décret 2-25-100 et la décision ANRE 04/26 n'ont pas d'URL de document
 * vérifiée : on pointe vers le portail officiel qui les publie (BO au SGG, site de l'ANRE) plutôt que
 * d'inventer un lien. Aucun numéro d'article, aucune durée ni pénalité (relecture du BO requise).
 */
import type { Locale } from '../i18n/config';

export interface SourceOfficielle {
  id: 'dahir' | 'sgg' | 'anre';
  url: string;
  label: Record<Locale, string>;
}

export const SOURCES_OFFICIELLES_8221: readonly SourceOfficielle[] = [
  {
    id: 'dahir',
    url: "https://adala.justice.gov.ma/api/uploads/2025/11/28/Dahir%20n%C2%BA%201-23-21%20portant%20promulgation%20de%20la%20loi%20n%C2%B0%2082-21%20relative%20%C3%A0%20l'autoproduction%20de%20l'%C3%A9nergie%20%C3%A9lectrique-1764342721762.pdf",
    label: {
      fr: 'Dahir n° 1-23-21 portant promulgation de la loi 82-21 (ministère de la Justice, PDF)',
      en: 'Dahir no. 1-23-21 promulgating law 82-21 (Ministry of Justice, PDF, French)',
      ar: 'الظهير رقم 1-23-21 بتنفيذ القانون 82-21 (وزارة العدل، PDF)',
    },
  },
  {
    id: 'sgg',
    url: 'https://www.sgg.gov.ma/arabe/Accueil.aspx',
    label: {
      fr: 'Secrétariat général du gouvernement — Bulletin officiel (décret 2-25-100)',
      en: 'General Secretariat of the Government — Official Bulletin (decree 2-25-100)',
      ar: 'الأمانة العامة للحكومة — الجريدة الرسمية (المرسوم 2-25-100)',
    },
  },
  {
    id: 'anre',
    url: 'https://anre.ma/',
    label: {
      fr: 'ANRE — site officiel (décision 04/26)',
      en: 'ANRE — official website (decision 04/26)',
      ar: 'ANRE — الموقع الرسمي (القرار 04/26)',
    },
  },
];

export const DEPOT_8221: Record<Locale, { h2: string; p: string; lead: string }> = {
  fr: {
    h2: 'Textes officiels et à qui déposer',
    lead: 'Les textes, à la source :',
    p: 'Le dossier (déclaration ou demande d’accord de raccordement) se dépose auprès du gestionnaire du réseau de distribution concerné par votre raccordement.',
  },
  en: {
    h2: 'Official texts and where to file',
    lead: 'The texts, at the source:',
    p: 'The file (declaration or grid-connection agreement request) is filed with the distribution network operator concerned by your connection.',
  },
  ar: {
    h2: 'النصوص الرسمية وجهة الإيداع',
    lead: 'النصوص من مصدرها:',
    p: 'يُودَع الملف (التصريح أو طلب اتفاقية الربط) لدى مسيّر شبكة التوزيع المعني بربطكم.',
  },
};

/** Liens non joignables : `fetchFn` est injectable (fetch simulé en CI, vrai fetch à la main). */
export async function liensMorts(
  fetchFn: (url: string) => Promise<{ status: number; redirected?: boolean }>,
  sources: readonly SourceOfficielle[] = SOURCES_OFFICIELLES_8221,
): Promise<string[]> {
  const morts: string[] = [];
  for (const s of sources) {
    try {
      const r = await fetchFn(s.url);
      if (r.status !== 200) morts.push(s.url);
    } catch {
      morts.push(s.url);
    }
  }
  return morts;
}
