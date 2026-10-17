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
const context = require('./review-context');
const runtime = require('./pipeline-runtime');

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
    const data = JSON.parse(fs.readFileSync(WORKFLOW_FILE, 'utf8'));
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Registry must be an object');
    return data;
  } catch (error) {
    throw new Error('Invalid workflow registry: ' + error.message, { cause: error });
  }
}

function saveWorkflows(data) {
  fs.writeFileSync(WORKFLOW_FILE, JSON.stringify(data, null, 2), 'utf8');
}

function createWorkflow(specId, metadata = {}) {
  const workflows = loadWorkflows();
  const id = specId && typeof specId === 'string' && specId.trim() ? specId.trim() : `wf-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  if (Object.hasOwn(workflows, id) || ['__proto__', 'constructor', 'prototype'].includes(id)) throw new Error('Workflow already exists or ID reserved');

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
  if (['approved', 'completed', 'rejected', 'blocked'].includes(status) && !reviewer?.trim()) throw new Error('Explicit reviewer required');
  if (stage === 'decision' && status === 'completed') throw new Error('Final decision requires human approval');
  const current = context.snapshot(FRAMEWORK);
  const index = VALID_STAGES.indexOf(stage);
  if (isStageValidated(status)) {
    for (const previous of VALID_STAGES.slice(0, index)) {
      const entry = workflow.stages[previous];
      if (!isStageValidated(entry.status) || JSON.stringify(entry.context) !== JSON.stringify(current)) throw new Error('Missing or stale prerequisite: ' + previous);
    }
    if (index >= 2) {
      const check = runtime.checkRun(current.resultsDir, process.env.QA_RUN_ID);
      if (!check.allowed || check.manifest.sourceHash !== current.source) throw new Error('Execution evidence missing, failed or source changed');
    }
  }

  workflow.stages[stage] = {
    ...workflow.stages[stage],
    status,
    reviewer,
    notes,
    updatedAt: new Date().toISOString(),
    risk: extra.risk || workflow.stages[stage].risk || 'medium',
    context: current,
  };
  for (const next of VALID_STAGES.slice(index + 1)) workflow.stages[next] = { status: 'pending', reviewer: null };

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

  if (VALID_STAGES.some(s => stages[s].status === 'blocked')) return 'blocked';
  if (stages.gherkin.status === 'rejected' || stages.script.status === 'rejected' || stages.execution.status === 'rejected' || stages.analysis.status === 'rejected') return 'rejected';
  if (stages.decision.status === 'rejected') return 'rejected';
  if (VALID_STAGES.slice(0, 4).every(s => isStageValidated(stages[s].status)) && stages.decision.status === 'approved') return 'approved';
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

function requireHumanApprovalBeforeFinalDecision(workflowId) {
  try {
    const workflow = getWorkflow(workflowId);
    const state = workflow && computeWorkflowStatus(workflow);
    if (state === 'rejected') return { ok: false, blocked: true, status: 'REJECTED', reason: 'Validation refusée par le relecteur.' };
    if (state === 'blocked') return { ok: false, blocked: true, status: 'BLOCKED', reason: 'Le workflow de revue est bloqué.' };
    if (!workflow || state !== 'approved') return { ok: false, blocked: true, status: 'PENDING_APPROVAL',
      reason: 'Aucune approbation humaine valide pour cette exécution.' };
    const current = context.snapshot(FRAMEWORK);
    if (!VALID_STAGES.every(s => JSON.stringify(workflow.stages[s].context) === JSON.stringify(current))) throw new Error('Approval stale: source or results changed');
    const check = runtime.checkRun(current.resultsDir, process.env.QA_RUN_ID);
    if (!check.allowed || check.manifest.sourceHash !== current.source) throw new Error('Execution evidence invalid or stale');
    return { ok: true, blocked: false, reason: 'Approved for this source and evidence only' };
  } catch (error) { return { ok: false, blocked: true, reason: error.message }; }
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
