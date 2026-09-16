'use strict';
// ============================================================
// QA Workflow Agent
// Exposes the explicit AI-assisted QA lifecycle with human review.
// ============================================================
const workflow = require('./shared/qa-workflow-engine');

function printHelp() {
  console.log(`
QA Workflow Agent — explicit AI-assisted QA lifecycle

Commands:
  create <specId>            Create a workflow for a user story/spec
  status <id>               Show a workflow state
  approve <id> <stage> <reviewer> [notes]
  reject <id> <stage> <reviewer> [notes]
  block <id> <reviewer> [notes]
  gate <id> <risk>         Require human approval before final decision
  list                     List all workflows
  help                     Show help

Workflow stages:
  gherkin, script, execution, analysis, decision
`);
}

function cmdCreate(specId) {
  const w = workflow.createWorkflow(specId || 'spec-demo', { source: 'ai-generated-test-lifecycle' });
  console.log(JSON.stringify(w, null, 2));
}

function cmdStatus(id) {
  const w = workflow.getWorkflow(id);
  console.log(JSON.stringify(w, null, 2));
}

function cmdApprove(id, stage, reviewer, notes) {
  const w = workflow.approveStage(id, stage, reviewer || 'qa-reviewer', notes || 'Approved by QA');
  console.log(JSON.stringify(w, null, 2));
}

function cmdReject(id, stage, reviewer, notes) {
  const w = workflow.rejectStage(id, stage, reviewer || 'qa-reviewer', notes || 'Rejected by QA');
  console.log(JSON.stringify(w, null, 2));
}

function cmdBlock(id, reviewer, notes) {
  const w = workflow.blockDecision(id, reviewer || 'qa-manager', notes || 'Blocked due to critical risk');
  console.log(JSON.stringify(w, null, 2));
}

function cmdGate(id, risk = 'medium') {
  const result = workflow.requireHumanApprovalBeforeFinalDecision(id, risk);
  console.log(JSON.stringify(result, null, 2));
}

function cmdList() {
  const list = workflow.listWorkflows();
  console.log(JSON.stringify(list, null, 2));
}

function main() {
  const [command, ...args] = process.argv.slice(2);

  switch (command) {
    case 'create':
      cmdCreate(args[0]);
      break;
    case 'status':
      cmdStatus(args[0]);
      break;
    case 'approve':
      cmdApprove(args[0], args[1], args[2], args.slice(3).join(' '));
      break;
    case 'reject':
      cmdReject(args[0], args[1], args[2], args.slice(3).join(' '));
      break;
    case 'block':
      cmdBlock(args[0], args[1], args.slice(2).join(' '));
      break;
    case 'gate':
      cmdGate(args[0], args[1]);
      break;
    case 'list':
      cmdList();
      break;
    case 'help':
    case '-h':
    case '--help':
    default:
      printHelp();
      break;
  }
}

main();
