// ============================================================
// K6 Quality Gate — Seuils de performance production
// Référencé dans smoke.js, load.js, stress.js
// ============================================================

export const QUALITY_GATE = {
  // Disponibilité
  error_rate_max:       0.01,   // < 1% d'erreurs en smoke
  error_rate_load_max:  0.05,   // < 5% d'erreurs en load

  // Temps de réponse (ms)
  p50_max:   1000,   // médiane < 1s
  p90_max:   3000,   // 90e percentile < 3s
  p95_max:   5000,   // 95e percentile < 5s
  p99_max:   8000,   // 99e percentile < 8s

  // Throughput
  rps_min:   10,     // minimum 10 req/s

  // Verdict
  verdict: (metrics) => {
    const errors = [];
    if (metrics.error_rate   > QUALITY_GATE.error_rate_max)   errors.push(`Error Rate: ${metrics.error_rate} > ${QUALITY_GATE.error_rate_max}`);
    if (metrics.p95_duration > QUALITY_GATE.p95_max)          errors.push(`P95: ${metrics.p95_duration}ms > ${QUALITY_GATE.p95_max}ms`);
    if (metrics.p99_duration > QUALITY_GATE.p99_max)          errors.push(`P99: ${metrics.p99_duration}ms > ${QUALITY_GATE.p99_max}ms`);
    return {
      passed:   errors.length === 0,
      verdict:  errors.length === 0 ? 'PASSED' : 'FAILED',
      blockers: errors,
    };
  },
};
