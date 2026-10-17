'use strict';
function bounded(text, limit) {
  text = String(text || '');
  if (text.length <= limit) return text;
  const note = '\n[EXCERPT: content omitted for request size; do not infer missing code. Request a narrower line range.]\n';
  return text.slice(0, Math.max(0, limit - note.length)) + note;
}
function analysisPrompt(failure, context, reads, limit = 12000, final = false) {
  const evidence = [...reads.values()].reverse().join('\n\n');
  const procedure = require('./skill-store').instructions('analyse-echec');
  const usable = limit - 1200 - procedure.length;
  if (usable < 1000) throw new Error('Agent skill exceeds analysis context budget');
  return `${procedure}
${final ? 'Conclude now with root_cause/fix_summary/confidence. No further file requests are possible. If evidence is insufficient, explicitly state this limitation and qualify the hypothesis.' : 'Return action read_file with file_path/line_start/line_end, or report_analysis with root_cause/fix_summary/confidence. Use exact paths. EOF means no more lines.'}\n` +
    bounded(`Test: ${failure.name}\nError: ${failure.message}\nTrace: ${failure.trace}`, Math.floor(usable * 0.3)) + '\n' +
    bounded(context, Math.floor(usable * 0.25)) + '\nLatest source evidence:\n' + bounded(evidence, Math.floor(usable * 0.4));
}
const ACTION_SCHEMA = {
  action: 'read_file | report_analysis', file_path: 'string, for read_file only',
  line_start: 'positive integer, default 1', line_end: 'positive integer, inclusive',
  root_cause: 'string: facts then qualified hypothesis, for report_analysis',
  fix_summary: 'string: proposed correction, never an applied fix', confidence: 'number 0 to 1',
};
async function requestAnalysis(llm, buildPrompt, final = false) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const prompt = buildPrompt(attempt ? 6000 : 12000) + (final ? '\nFINAL TURN: action must be report_analysis. State limitations if evidence is insufficient.' : '');
    try {
      // Plain JSON generation: no provider-specific tool-call protocol or tool history.
      const schema = final ? { root_cause: ACTION_SCHEMA.root_cause, fix_summary: ACTION_SCHEMA.fix_summary, confidence: ACTION_SCHEMA.confidence } : ACTION_SCHEMA;
      // Keep the raw response: chatStructured otherwise turns every failure into {}.
      const response = await llm.chat([{ role: 'user', content: prompt + '\nReturn ONLY valid JSON following this schema:\n' + JSON.stringify(schema) }],
        { temperature: 0, _fnName: 'bugAnalysisJson' });
      const raw = response?.message?.content?.trim() || '';
      if (!raw || /service\s+LLM[^\n]*(indisponible|hors ligne)/i.test(raw)) throw new Error('LLM unavailable: no analysis returned');
      let data;
      try { data = JSON.parse(raw.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')); }
      catch { throw new Error('LLM returned malformed JSON (analysis not evaluated)'); }
      if (final && data && !data.action && typeof data.root_cause === 'string') data.action = 'report_analysis';
      if (data?.action === 'report_analysis' && typeof data.root_cause === 'string' && data.root_cause.trim()
        && !/service\s+LLM.*(indisponible|hors ligne)/i.test(data.root_cause)) return data;
      if (!final && data?.action === 'read_file' && typeof data.file_path === 'string' && data.file_path.trim()) return data;
      throw new Error(`LLM analysis response incomplete or invalid (fields: ${Object.keys(data || {}).join(', ') || 'none'})`);
    } catch (error) {
      if (attempt) throw error;
    }
  }
}
module.exports = { bounded, analysisPrompt, requestAnalysis };
