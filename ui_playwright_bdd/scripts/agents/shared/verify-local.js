'use strict';

// Isolated process: Cucumber loads the real support code, but executes no hooks/steps.
const path = require('node:path');
const { Writable } = require('node:stream');
const ts = require('typescript');

async function run() {
  const root = process.cwd();
  const configPath = path.join(root, 'tsconfig.json');
  const config = ts.readConfigFile(configPath, ts.sys.readFile);
  const parsed = ts.parseJsonConfigFileContent(config.config || {}, ts.sys, root, {
    noEmit: true, noUnusedLocals: true, noUnusedParameters: true,
  }, configPath);
  const program = ts.createProgram(parsed.fileNames, parsed.options);
  const diagnostics = [...(config.error ? [config.error] : []), ...parsed.errors, ...ts.getPreEmitDiagnostics(program)];
  const checker = program.getTypeChecker();
  const synchronousCalls = [];
  for (const file of program.getSourceFiles().filter(file => parsed.fileNames.includes(file.fileName))) {
    const visit = node => {
      if (ts.isExpressionStatement(node) && ts.isCallExpression(node.expression)
          && ts.isIdentifier(node.expression.expression) && node.expression.arguments.length === 0) {
        const signature = checker.getResolvedSignature(node.expression);
        if (signature && (checker.getReturnTypeOfSignature(signature).flags & ts.TypeFlags.Void)) {
          synchronousCalls.push({ file: path.relative(root, file.fileName).replace(/\\/g, '/'),
            line: file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1, quote: node.getText(file), returnType: 'void' });
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(file);
  }
  const typescript = {
    status: diagnostics.length ? 'FAIL' : 'PASS',
    files: parsed.fileNames.map(file => path.relative(root, file).replace(/\\/g, '/')),
    diagnostics: diagnostics.map(d => ({
      file: d.file ? path.relative(root, d.file.fileName).replace(/\\/g, '/') : null,
      line: d.file && d.start != null ? d.file.getLineAndCharacterOfPosition(d.start).line + 1 : null,
      code: d.code, message: ts.flattenDiagnosticMessageText(d.messageText, '\n'),
    })),
    synchronousCalls,
    scope: 'Compilation TypeScript, noUnusedLocals et noUnusedParameters ; pas de règle no-floating-promises.',
  };

  let cucumber;
  try {
    const { loadConfiguration, runCucumber } = require('@cucumber/cucumber/api');
    let output = '';
    const stream = new Writable({ write(chunk, encoding, done) { output += chunk.toString(); done(); } });
    const environment = { cwd: root, stdout: stream, stderr: stream };
    const { runConfiguration } = await loadConfiguration({}, environment);
    runConfiguration.sources.paths = ['src/features/**/*.feature'];
    runConfiguration.sources.tagExpression = '';
    runConfiguration.sources.names = [];
    Object.assign(runConfiguration.runtime, { dryRun: true, parallel: 0, retry: 0 });
    // CLI --format would add to existing formatters and pollute Allure results.
    runConfiguration.formats = { stdout: 'summary', files: {}, publish: false, options: {} };
    const files = new Set();
    let scenarios = 0, steps = 0;
    const result = await runCucumber(runConfiguration, environment, message => {
      if (message.source) files.add(message.source.uri.replace(/\\/g, '/'));
      if (message.pickle) { scenarios++; steps += message.pickle.steps.length; }
    });
    cucumber = {
      status: !result.success ? 'FAIL' : scenarios === 0 ? 'NOT_EVALUATED' : 'PASS',
      files: [...files], scenarios, steps, output,
      scope: 'Tous les scénarios, sans filtre de tags ; syntaxe et steps manquants/ambigus. Aucune exécution UI.',
    };
  } catch (error) {
    cucumber = { status: 'NOT_EVALUATED', reason: 'Chargement Cucumber impossible.', detail: error.message };
  }
  // Prefix distinguishes the result from messages emitted when loading support code.
  console.log('QA_VERIFY_RESULT=' + JSON.stringify({ typescript, cucumber }));
}

run().catch(() => { process.exitCode = 1; });
