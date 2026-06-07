export class SmartRetry {
  private static readonly RETRYABLE_PATTERNS: RegExp[] = [
    /timeout/i,
    /waiting for/i,
    /net::err_/i,
    /network/i,
    /navigation/i,
    /Target closed/i,
    /browser has been closed/i,
    /context.*closed/i,
    /page.*closed/i,
    /ECONNRESET/i,
    /ETIMEDOUT/i,
    /ERR_CONNECTION_RESET/i,
    /ERR_CONNECTION_REFUSED/i
  ];

  private static readonly NON_RETRYABLE_PATTERNS: RegExp[] = [
    /expect\(.*\)/i,
    /assert/i,
    /locator.*not found/i,
    /strict mode violation/i,
    /toHaveText/i,
    /toBeVisible/i,
    /toEqual/i,
    /business/i,
    /validation failed/i
  ];

  static isRetryable(errorMessage: string): boolean {
    if (!errorMessage || !errorMessage.trim()) {
      return false;
    }

    const isExplicitlyNonRetryable = this.NON_RETRYABLE_PATTERNS.some((pattern) =>
      pattern.test(errorMessage)
    );

    if (isExplicitlyNonRetryable) {
      return false;
    }

    return this.RETRYABLE_PATTERNS.some((pattern) => pattern.test(errorMessage));
  }

  static getDecisionReason(errorMessage: string): string {
    if (!errorMessage || !errorMessage.trim()) {
      return 'No error message available.';
    }

    const nonRetryable = this.NON_RETRYABLE_PATTERNS.find((pattern) =>
      pattern.test(errorMessage)
    );
    if (nonRetryable) {
      return `Non-retryable error matched pattern: ${nonRetryable}`;
    }

    const retryable = this.RETRYABLE_PATTERNS.find((pattern) =>
      pattern.test(errorMessage)
    );
    if (retryable) {
      return `Retryable error matched pattern: ${retryable}`;
    }

    return 'No retry rule matched.';
  }
}