export const DEAD_LETTER_PREFIX: string;
export const DEAD_LETTER_TTL_SECONDS: number;
export const DEAD_LETTER_MAX_PER_RUN: number;
export function resetDeadLetterWarning(): void;
export function storeDeadLetter(
  kv: unknown,
  record: { idempotencyKey?: string },
  log?: (msg: string) => void,
): Promise<boolean>;
export function resendDeadLetters(
  env: unknown,
  fetchFn?: typeof fetch,
  log?: (msg: string) => void,
): Promise<{ skipped: boolean; found: number; delivered: number; failed: number }>;
