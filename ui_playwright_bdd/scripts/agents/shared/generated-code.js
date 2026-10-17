'use strict';
function validateGenerated(content, type) {
  if (!content?.trim() || /service\s+LLM[^\n]*(indisponible|hors ligne)/i.test(content)) throw new Error('No usable generated code');
  if (type === 'gherkin') {
    const { generateMessages } = require('@cucumber/gherkin');
    const { IdGenerator, SourceMediaType } = require('@cucumber/messages');
    const envelopes = generateMessages(content, 'generated.feature', SourceMediaType.TEXT_X_CUCUMBER_GHERKIN_PLAIN, {
      newId: IdGenerator.incrementing(), includeGherkinDocument: true, includePickles: true,
    });
    const errors = envelopes.filter(e => e.parseError);
    if (errors.length) {
      const locations = errors.slice(0, 5).map(e => {
        const loc = e.parseError.source?.location;
        return loc ? `line ${loc.line}, column ${loc.column}` : 'unknown location';
      });
      throw new Error('Invalid generated Gherkin: ' + locations.join('; ') + '. Use one consistent dialect and never tag Background.');
    }
    const pickles = envelopes.filter(e => e.pickle);
    if (!pickles.length || pickles.some(e => !e.pickle.steps.length)) throw new Error('Invalid generated Gherkin: no executable scenarios or scenario without steps');
  } else {
    const ts = require('typescript');
    const source = ts.createSourceFile('generated.ts', content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
    if (source.parseDiagnostics.length || !source.statements.length || !/\b(import|export)\b/.test(content)) throw new Error('Invalid generated TypeScript');
  }
  return content;
}
module.exports = { validateGenerated };
