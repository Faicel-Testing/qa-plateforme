'use strict';
function unavailable(error) {
  const status = error?.status || error?.status_code;
  return status === 429 || status >= 500 || /HTTP (?:429|5\d\d)|circuit ouvert|connection error|ECONNRESET|ETIMEDOUT/i.test(error?.message || '');
}
module.exports = { unavailable };
