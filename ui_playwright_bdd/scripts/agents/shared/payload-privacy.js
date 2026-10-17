'use strict';
// No network or file access: apply to decoded payloads before retrieval/cache/transport.
function cleanText(value) {
  let text = value.replace(/https?:\/\/[^\s<>"'`\\]+/gi, raw => {
    try {
      const url = new URL(raw);
      // Retain only the protocol and an anonymous host. Paths can also contain secrets.
      return `${url.protocol}//redacted-host.invalid/[REDACTED_URL]`;
    } catch { return '[REDACTED_URL]'; }
  });
  text = text.replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, '[REDACTED_EMAIL]');
  text = text.replace(/\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/-]+=*/gi, '[REDACTED_AUTH]');
  text = text.replace(/^(\s*(?:cookie|set-cookie|authorization)\s*:)\s*.*$/gim, '$1 [REDACTED]');
  text = text.replace(/((?:["']?)(?:password|passwd|pwd|token|access_token|refresh_token|api[_-]?key|secret|authorization|cookie|set-cookie)(?:["']?)\s*[:=]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;}]+)/gi, '$1"[REDACTED]"');
  return text;
}
function sanitize(value) {
  if (typeof value === 'string') {
    // Tool arguments and source bundles often contain JSON inside a string.
    if (/^\s*[[{]/.test(value)) {
      try { return JSON.stringify(sanitize(JSON.parse(value))); } catch { /* ordinary text */ }
    }
    return cleanText(value);
  }
  if (Array.isArray(value)) return value.map(sanitize);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) =>
    [cleanText(key), typeof item === 'string' && /^(?:password|passwd|pwd|token|access_token|refresh_token|api[_-]?key|secret|authorization|cookie|set-cookie)$/i.test(key)
      ? '[REDACTED]' : sanitize(item)]));
  return value;
}
module.exports = { sanitize, cleanText };
