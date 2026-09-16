'use strict';
// ============================================================
// QA Workflow Engine
// Standardizes the AI-assisted test lifecycle with human approvals.
// Stages:
//   1. gherkin validation
//   2. script validation
//   3. execution
//   4. analysis
//   5. final decision
// ============================================================
const fs = require('fs');
const path = require('path');

const FRAMEWORK = path.join(__dirname, '..', '..', '..');
const LOGS_DIR = path.join(FRAMEWORK, 'logs');
const WORKFLOW_FILE = path.join(LOGS_DIR, 'qa-workflows.json');

fs.mkdirSync(LOGS_DIR, { recursive: true });

const VALID_STAGES = [
  'gherkin',
  'script',
  'execution',
  'analysis',
  'decision',
];

const VALID_STATUS = ['pending', 'approved', 'rejected', 'blocked', 'completed'];

function isStageValidated(status) {
  return status === 'approved' || status === 'completed';
}

function loadWorkflows() {
  try {
    if (!fs.existsSync(WORKFLOW_FILE)) return {};
    return JSON.parse(fs.readFileSync(WORKFLOW_FILE, 'utf8'));
  } catch {
    return {};
  }
}

function saveWorkflows(data) {
  fs.writeFileSync(WORKFLOW_FILE, JSON.stringify(data, null, 2), 'utf8');
}

function createWorkflow(specId, metadata = {}) {
  const workflows = loadWorkflows();
  const id = specId && typeof specId === 'string' && specId.trim() ? specId.trim() : `wf-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  const workflow = {
    id,
    specId: specId && typeof specId === 'string' && specId.trim() ? specId.trim() : id,
    createdAt: new Date().toISOString(),
    metadata,
    stages: {
      gherkin: { status: 'pending', reviewer: null, notes: '', updatedAt: null },
      script: { status: 'pending', reviewer: null, notes: '', updatedAt: null },
      execution: { status: 'pending', reviewer: null, notes: '', updatedAt: null },
      analysis: { status: 'pending', reviewer: null, notes: '', updatedAt: null },
      decision: { status: 'pending', reviewer: null, notes: '', updatedAt: null, risk: 'low' },
    },
    status: 'pending',
  };

  workflows[id] = workflow;
  saveWorkflows(workflows);
  return workflow;
}

function findWorkflow(workflows, workflowKey) {
  if (!workflowKey) return null;
  if (workflows[workflowKey]) return workflows[workflowKey];
  return Object.values(workflows).find((workflow) => workflow.specId === workflowKey || workflow.id === workflowKey) || null;
}

function getWorkflow(id) {
  const workflows = loadWorkflows();
  return findWorkflow(workflows, id) || null;
}

function listWorkflows() {
  const workflows = loadWorkflows();
  return Object.values(workflows);
}

function updateStage(workflowId, stage, status, reviewer = null, notes = '', extra = {}) {
  if (!VALID_STAGES.includes(stage)) throw new Error(`Unsupported stage: ${stage}`);
  if (!VALID_STATUS.includes(status)) throw new Error(`Unsupported status: ${status}`);

  const workflows = loadWorkflows();
  const workflow = findWorkflow(workflows, workflowId);
  if (!workflow) throw new Error(`Workflow not found: ${workflowId}`);

  workflow.stages[stage] = {
    ...workflow.stages[stage],
    status,
    reviewer,
    notes,
    updatedAt: new Date().toISOString(),
    ...extra,
  };

  workflow.status = computeWorkflowStatus(workflow);
  saveWorkflows(workflows);
  return workflow;
}

function approveStage(workflowId, stage, reviewer, notes = '') {
  return updateStage(workflowId, stage, 'approved', reviewer, notes);
}

function rejectStage(workflowId, stage, reviewer, notes = '') {
  return updateStage(workflowId, stage, 'rejected', reviewer, notes);
}

function blockDecision(workflowId, reviewer, notes = '') {
  return updateStage(workflowId, 'decision', 'blocked', reviewer, notes, { risk: 'critical' });
}

function computeWorkflowStatus(workflow) {
  const stages = workflow.stages;

  if (stages.decision.status === 'blocked') return 'blocked';
  if (stages.decision.status === 'approved') return 'approved';
  if (stages.gherkin.status === 'rejected' || stages.script.status === 'rejected' || stages.execution.status === 'rejected' || stages.analysis.status === 'rejected') return 'rejected';
  if (isStageValidated(stages.execution.status) && isStageValidated(stages.analysis.status) && stages.decision.status === 'approved') return 'approved';
  if (isStageValidated(stages.execution.status) && !isStageValidated(stages.analysis.status)) return 'analysis';
  if (isStageValidated(stages.gherkin.status) && isStageValidated(stages.script.status)) return 'ready-for-execution';
  return 'pending';
}

function evaluateDecisionRisk(workflow) {
  const decision = workflow.stages.decision || {};
  const risk = decision.risk || 'low';
  const state = workflow.status;

  if (state === 'blocked') return { level: 'critical', blocked: true };
  if (risk === 'critical') return { level: 'critical', blocked: true };
  if (risk === 'high') return { level: 'high', blocked: false };
  if (risk === 'medium') return { level: 'medium', blocked: false };
  return { level: 'low', blocked: false };
}

function requireHumanApprovalBeforeFinalDecision(workflowId, risk = 'medium') {
  const workflows = loadWorkflows();
  const workflow = findWorkflow(workflows, workflowId);
  if (!workflow) return { ok: false, error: `Workflow not found: ${workflowId}` };

  const stages = workflow.stages;
  const gherkinOk = isStageValidated(stages.gherkin.status);
  const scriptOk = isStageValidated(stages.script.status);
  const executionOk = isStageValidated(stages.execution.status);
  const analysisOk = isStageValidated(stages.analysis.status);

  if (!gherkinOk || !scriptOk || !executionOk || !analysisOk) {
    return { ok: false, blocked: true, reason: 'Workflow not ready for final decision' };
  }

  const riskLevel = risk === 'critical' || risk === 'high' ? 'critical' : 'medium';
  workflow.stages.decision = {
    ...workflow.stages.decision,
    status: 'pending',
    risk: riskLevel,
    reviewer: null,
    updatedAt: new Date().toISOString(),
  };
  workflow.status = 'pending';
  saveWorkflows(workflows);

  return { ok: true, blocked: riskLevel === 'critical', reason: riskLevel === 'critical' ? 'Final decision requires human approval' : 'Ready for final review' };
}

module.exports = {
  VALID_STAGES,
  VALID_STATUS,
  createWorkflow,
  getWorkflow,
  listWorkflows,
  updateStage,
  approveStage,
  rejectStage,
  blockDecision,
  requireHumanApprovalBeforeFinalDecision,
  evaluateDecisionRisk,
  computeWorkflowStatus,
  WORKFLOW_FILE,
};
