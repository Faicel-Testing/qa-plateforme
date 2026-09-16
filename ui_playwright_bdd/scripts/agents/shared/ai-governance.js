'use strict';
// ============================================================
// AI Governance for QA
// - explicit activation of human validation
// - prompt security sanitization
// - formal audit trail
// - critical decision management
// ============================================================
const fs = require('fs');
const path = require('path');

const FRAMEWORK = path.join(__dirname, '..', '..', '..');
const LOGS_DIR = path.join(FRAMEWORK, 'logs');
const AUDIT_FILE = path.join(LOGS_DIR, 'ai-governance-audit.jsonl');
const APPROVAL_FILE = path.join(LOGS_DIR, 'ai-governance-approvals.json');

fs.mkdirSync(LOGS_DIR, { recursive: true });

const CONFIG = {
  requireHumanApproval: process.env.AI_REQUIRE_HUMAN_APPROVAL !== 'false',
  criticalThreshold: Number(process.env.AI_CRITICAL_THRESHOLD || '0.75'),
  maxPromptSecrets: Number(process.env.AI_MAX_PROMPT_SECRETS || '3'),
  promptSecurityMode: process.env.AI_PROMPT_SECURITY_MODE || 'strict',
};

function readJson(filePath, fallback) {
  try {
    if (!fs.existsSync(filePath)) return fallback;
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return fallback;
  }
}

function writeJson(filePath, data) {
  try {
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
  } catch {}
}

function redactSecrets(text) {
  if (text === null || text === undefined) return '';
  let value = String(text);
  const patterns = [
    /(GROQ_API_KEY|OPENAI_API_KEY|JIRA_TOKEN|API_KEY|SECRET|PASSWORD|TOKEN)\s*[:=]\s*[^\s\"'\n]+/gi,
    /(Bearer\s+[A-Za-z0-9._~+\-]+=*)/gi,
    /sk-[A-Za-z0-9]{10,}/g,
    /([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})/g,
  ];
  for (const pattern of patterns) {
    value = value.replace(pattern, '[REDACTED]');
  }
  return value;
}

function analyzePromptSecurity(prompt) {
  const text = typeof prompt === 'string' ? prompt : JSON.stringify(prompt || {});
  const findings = [];

  if (/GROQ_API_KEY|API_KEY|TOKEN|PASSWORD|SECRET/i.test(text)) {
    findings.push('secret_or_token_detected');
  }
  if (/@/.test(text)) {
    findings.push('email_reference_detected');
  }
  if (/PROMPT_INJECTION|ignore previous instructions|system prompt|override behavior/i.test(text)) {
    findings.push('prompt_injection_pattern_detected');
  }

  return {
    mode: CONFIG.promptSecurityMode,
    findings,
    status: findings.length ? 'blocked' : 'safe',
    redacted: redactSecrets(text),
  };
}

function redactMessages(messages) {
  if (!Array.isArray(messages)) return messages;
  return messages.map((message) => {
    if (!message || typeof message !== 'object') return message;
    return {
      ...message,
      content: redactSecrets(message.content),
    };
  });
}

function getApprovalState() {
  return readJson(APPROVAL_FILE, {});
}

function saveApprovalState(data) {
  writeJson(APPROVAL_FILE, data);
}

function evaluateDecisionRisk(decision) {
  const confidence = Number(decision?.confidence ?? 0.5);
  const baseRisk = Math.max(0, 1 - confidence);
  let risk = baseRisk;

  if (decision?.category === 'real_bug' || decision?.category === 'INVALID') risk += 0.25;
  if (decision?.category === 'false_positive') risk += 0.15;
  if (decision?.critical === true) risk += 0.2;
  if (decision?.type === 'release' || decision?.type === 'go_no_go') risk += 0.25;

  risk = Math.min(risk, 1);

  return {
    score: Number(risk.toFixed(3)),
    level: risk >= CONFIG.criticalThreshold ? 'critical' : risk >= 0.5 ? 'high' : risk >= 0.25 ? 'medium' : 'low',
  };
}

function appendAudit(entry) {
  try {
    fs.appendFileSync(AUDIT_FILE, `${JSON.stringify(entry)}\n`, 'utf8');
  } catch {}
}

function createDecisionAudit(event) {
  const decision = event.decision || {};
  const promptSecurity = analyzePromptSecurity(event.prompt || event.context || '');
  const risk = evaluateDecisionRisk(decision);
  const approvalState = getApprovalState();
  const approval = approvalState[event.id];
  const approvalStatus = approval && (approval.approved === true || approval === true) ? 'approved' : 'pending';

  const auditRecord = {
    ts: new Date().toISOString(),
    id: event.id || `decision-${Date.now()}`,
    type: event.type || 'ai_decision',
    actor: event.actor || 'ai-agent',
    item: event.item || null,
    decision,
    promptSecurity,
    risk,
    approvalStatus,
    requiresHumanApproval: event.requiresHumanApproval || risk.level === 'critical' || (CONFIG.requireHumanApproval && risk.score >= 0.5),
  };

  appendAudit(auditRecord);
  return auditRecord;
}

function evaluateHumanApproval({ decision, id, item, type, prompt, actor = 'qa-agent' }) {
  const normalizedDecision = decision || {};
  const record = createDecisionAudit({
    id: id || `${type || 'decision'}-${Date.now()}`,
    item,
    type,
    actor,
    prompt,
    decision: normalizedDecision,
    requiresHumanApproval: normalizedDecision.critical === true || evaluateDecisionRisk(normalizedDecision).level === 'critical',
  });

  if (!record.requiresHumanApproval) {
    return { status: 'auto_approved', record };
  }

  const approvals = getApprovalState();
  const approval = approvals[record.id];
  const approved = approval && (approval.approved === true || approval === true);

  if (!approved && CONFIG.requireHumanApproval) {
    return {
      status: 'pending_human_approval',
      requiresHumanApproval: true,
      record,
      message: 'Human approval required before the critical AI decision can be used.',
    };
  }

  return { status: 'approved', requiresHumanApproval: false, record };
}

function checkDecisionGate({ decision, id, item, type, prompt, actor = 'qa-agent' }) {
  const normalizedDecision = decision || {};
  const risk = evaluateDecisionRisk(normalizedDecision);
  const promptSecurity = analyzePromptSecurity(prompt || '');

  const blockers = [];
  if (promptSecurity.status === 'blocked') {
    blockers.push(`Prompt security issue: ${promptSecurity.findings.join(', ')}`);
  }

  const approvalResult = evaluateHumanApproval({
    decision: normalizedDecision,
    id: id || `${type || 'decision'}-${Date.now()}`,
    item,
    type,
    prompt,
    actor,
  });

  if (approvalResult.status === 'pending_human_approval') {
    blockers.push(approvalResult.message);
  }

  if (risk.level === 'critical' && approvalResult.status !== 'approved') {
    blockers.push(`Critical risk decision requires explicit human approval (risk=${risk.level}).`);
  }

  return {
    blocked: blockers.length > 0,
    blockers,
    risk,
    promptSecurity,
    approval: approvalResult,
    status: blockers.length ? 'blocked' : 'approved',
  };
}

function approveDecision(id, reviewer, notes = '') {
  const approvals = getApprovalState();
  approvals[id] = { approved: true, reviewer, notes, ts: new Date().toISOString() };
  saveApprovalState(approvals);
  return { id, approved: true, reviewer, notes };
}

function getAuditTrail(limit = 20) {
  try {
    if (!fs.existsSync(AUDIT_FILE)) return [];
    const lines = fs.readFileSync(AUDIT_FILE, 'utf8').trim().split('\n').filter(Boolean);
    return lines.slice(-limit).map((line) => JSON.parse(line));
  } catch {
    return [];
  }
}

function getStatus() {
  return {
    config: CONFIG,
    approvalFile: APPROVAL_FILE,
    auditFile: AUDIT_FILE,
    approvals: getApprovalState(),
    lastAudit: getAuditTrail(5),
  };
}

function generateAuditReport(outputFile = path.join(FRAMEWORK, 'docs', 'ai-governance-report.html')) {
  const audit = getAuditTrail(200);
  const approvals = getApprovalState();

  const rows = audit.map((entry) => {
    const approved = approvals[entry.id] && approvals[entry.id].approved === true ? '✅ Approved' : '⏳ Pending';
    return `
      <tr>
        <td>${entry.ts}</td>
        <td>${entry.type}</td>
        <td>${entry.item || 'N/A'}</td>
        <td>${entry.risk?.level || 'unknown'}</td>
        <td>${entry.promptSecurity?.status || 'unknown'}</td>
        <td>${approved}</td>
      </tr>`;
  }).join('');

  const html = `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>AI Governance Audit</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 32px; color: #111827; background: #f8fafc; }
    h1 { color: #0f172a; }
    .card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin-bottom: 18px; }
    table { width: 100%; border-collapse: collapse; background: white; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 10px; text-align: left; }
    th { background: #eef2ff; }
    .badge { display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: bold; }
    .ok { background: #dcfce7; color: #166534; }
    .warn { background: #fef3c7; color: #92400e; }
    .critical { background: #fee2e2; color: #991b1b; }
  </style>
</head>
<body>
  <h1>AI Governance Audit Report</h1>
  <div class="card">
    <p><strong>Config:</strong> human approval = ${CONFIG.requireHumanApproval ? 'enabled' : 'disabled'}</p>
    <p><strong>Critical threshold:</strong> ${CONFIG.criticalThreshold}</p>
    <p><strong>Prompt security mode:</strong> ${CONFIG.promptSecurityMode}</p>
    <p><strong>Audit trail entries:</strong> ${audit.length}</p>
  </div>

  <div class="card">
    <h2>Decision Log</h2>
    <table>
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Type</th>
          <th>Item</th>
          <th>Risk</th>
          <th>Prompt Security</th>
          <th>Approval</th>
        </tr>
      </thead>
      <tbody>
        ${rows || '<tr><td colspan="6">No audit entries yet.</td></tr>'}
      </tbody>
    </table>
  </div>
</body>
</html>`;

  fs.mkdirSync(path.dirname(outputFile), { recursive: true });
  fs.writeFileSync(outputFile, html, 'utf8');
  return outputFile;
}

module.exports = {
  CONFIG,
  redactSecrets,
  analyzePromptSecurity,
  redactMessages,
  evaluateDecisionRisk,
  createDecisionAudit,
  evaluateHumanApproval,
  checkDecisionGate,
  approveDecision,
  getAuditTrail,
  getStatus,
  generateAuditReport,
  AUDIT_FILE,
  APPROVAL_FILE,
};
