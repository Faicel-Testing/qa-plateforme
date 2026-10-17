'use strict';
// Only explicit missing requirements block generation; never invent acceptance criteria.
function generationBlocker(story) {
  const description = String(story.description || '').trim();
  if (!description) return 'Description et criteres absents dans la story Plane';
  if (/titre historique non sp[eé]cifi[eé]|exigences [aà] clarifier, aucune couverture attribu[eé]e/i.test(description)) {
    return 'Story historique non specifiee : criteres a clarifier dans Plane';
  }
  if (/exigences historiques [aà] confirmer/i.test(description) && /aucun sc[eé]nario ex[eé]cutable actuellement associ[eé]/i.test(description)) {
    return 'Exigences historiques a confirmer avant generation';
  }
  return null;
}
module.exports = { generationBlocker };
