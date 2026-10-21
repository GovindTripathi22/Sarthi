const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('index.html', 'utf8');

class Element {
  constructor(tagName, id = '', className = '') {
    this.tagName = tagName;
    this.id = id;
    this.className = className;
    this.classList = {
      add: (...classes) => {
        const set = new Set(this.className.split(/\s+/).filter(Boolean));
        classes.forEach(c => set.add(c));
        this.className = Array.from(set).join(' ');
      },
      remove: (...classes) => {
        const set = new Set(this.className.split(/\s+/).filter(Boolean));
        classes.forEach(c => set.delete(c));
        this.className = Array.from(set).join(' ');
      },
      contains: (c) => this.className.split(/\s+/).includes(c),
      toggle: (c) => {
        if (this.classList.contains(c)) this.classList.remove(c);
        else this.classList.add(c);
      }
    };
    this.children = [];
    this._innerHTML = '';
    this._textContent = '';
    this.style = {};
    this.attributes = {};
    this.value = '';
  }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(val) {
    this._innerHTML = val;
    const idMatches = [...val.matchAll(/<([a-zA-Z0-9]+)[^>]*id=["']([^"']+)["'][^>]*>/g)];
    for (const match of idMatches) {
      const tagName = match[1];
      const id = match[2];
      elementsById[id] = new Element(tagName, id);
    }
  }
  get textContent() { return this._textContent; }
  set textContent(val) { this._textContent = val; }
  appendChild(child) { this.children.push(child); }
  removeChild(child) {
    this.children = this.children.filter(c => c !== child);
  }
  setAttribute(k, v) { this.attributes[k] = v; }
  getAttribute(k) { return this.attributes[k]; }
  click() { if (this.onclick) this.onclick(); }
  querySelector(sel) {
    return this.children[0] || null;
  }
  focus() {}
  setSelectionRange() {}
}

const idMatches = [...html.matchAll(/<([a-zA-Z0-9]+)[^>]*id=["']([^"']+)["'][^>]*>/g)];
const elementsById = {};
for (const match of idMatches) {
  const tagName = match[1];
  const id = match[2];
  elementsById[id] = new Element(tagName, id);
}

const storage = {};
const mockLocalStorage = {
  getItem: (k) => storage[k] || null,
  setItem: (k, v) => { storage[k] = String(v); },
  removeItem: (k) => { delete storage[k]; },
  clear: () => { Object.keys(storage).forEach(k => delete storage[k]); }
};

const domEvents = {};

const mockDocument = {
  getElementById: (id) => elementsById[id] || null,
  querySelectorAll: (sel) => {
    if (sel === '.nav-btn') {
      return [new Element('button', '', 'nav-btn')];
    }
    return [];
  },
  querySelector: (sel) => null,
  createElement: (tag) => new Element(tag),
  body: new Element('body', 'body', 'min-h-screen bg-[#090d16] text-slate-100 flex flex-col select-none font-sans antialiased'),
  activeElement: null
};

const mockWindow = {
  document: mockDocument,
  localStorage: mockLocalStorage,
  addEventListener: (ev, fn) => {
    domEvents[ev] = domEvents[ev] || [];
    domEvents[ev].push(fn);
  },
  lucide: {
    createIcons: () => {}
  },
  Blob: class { constructor(data, opts) { this.data = data; this.opts = opts; } },
  URL: {
    createObjectURL: () => 'blob:mock-url',
    revokeObjectURL: () => {}
  },
  console: console,
  setTimeout: (fn) => fn(),
  clearTimeout: () => {},
  setInterval: () => {},
  clearInterval: () => {},
  scrollTo: (opts) => {}
};

const scriptMatches = [...html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/gi)];
const mainScript = scriptMatches[scriptMatches.length - 1][1];

const context = vm.createContext({
  window: mockWindow,
  document: mockDocument,
  localStorage: mockLocalStorage,
  console: console,
  Blob: mockWindow.Blob,
  URL: mockWindow.URL,
  setTimeout: mockWindow.setTimeout,
  clearTimeout: mockWindow.clearTimeout
});

vm.runInContext(mainScript, context);

if (domEvents['DOMContentLoaded']) {
  domEvents['DOMContentLoaded'].forEach(fn => fn());
}

const app = context.window.AutoPatchApp;
if (!app) {
  console.error('app is not initialized!');
  process.exit(1);
}

const tests = [
  { name: 'Navigate Home', fn: () => app.navigate('home') },
  { name: 'Navigate Dashboard', fn: () => app.navigate('dashboard') },
  { name: 'Navigate Integrations', fn: () => app.navigate('integrations') },
  { name: 'Navigate Incidents', fn: () => app.navigate('incidents') },
  { name: 'Navigate Workbench', fn: () => app.navigate('workbench') },
  { name: 'Navigate Review', fn: () => app.navigate('review') },
  { name: 'Navigate Contracts', fn: () => app.navigate('contracts') },
  { name: 'Navigate Analytics', fn: () => app.navigate('analytics') },
  { name: 'Navigate Settings', fn: () => app.navigate('settings') },
  { name: 'Navigate Blueprint', fn: () => app.navigate('blueprint') },
  { name: 'Toggle API Drift', fn: () => app.toggleApiDrift() },
  { name: 'Send Proxy Baseline', fn: () => app.sendProxyRequest('int_commerce_01', 'NONE') },
  { name: 'Send Proxy Drift', fn: () => app.sendProxyRequest('int_commerce_01', 'SCHEMA_DRIFT') },
  { name: 'Send Proxy Auth 401', fn: () => app.sendProxyRequest('int_commerce_01', 'AUTH_401') },
  { name: 'Send Proxy Rate Limit 429', fn: () => app.sendProxyRequest('int_commerce_01', 'RATE_LIMIT_429') },
  { name: 'Toggle Pause Integration', fn: () => app.togglePauseIntegration('int_commerce_01') },
  { name: 'Toggle Unpause Integration', fn: () => app.togglePauseIntegration('int_commerce_01') },
  { name: 'Start/Resume Repair', fn: () => app.startOrResumeRepair(app.db.incidents[0].id) },
  {
    name: 'Modal: Add Integration Workflow',
    fn: () => {
      app.switchRole('Admin');
      app.openAddIntegrationModal();
      elementsById['modal-int-name'].value = 'Payment Gateway Hook';
      elementsById['modal-int-provider'].value = 'PayCore';
      elementsById['modal-int-baseurl'].value = 'https://api.paycore.internal';
      elementsById['modal-confirm-btn'].click();
      const added = app.db.integrations.find(i => i.name === 'Payment Gateway Hook');
      if (!added) throw new Error('Integration was not added to state');
    }
  },
  {
    name: 'Modal: Ingest Doc Workflow & Dedup',
    fn: () => {
      app.switchRole('Admin');
      app.openIngestDocModal();
      elementsById['modal-doc-title'].value = 'PayCore v2 Migration Notice';
      elementsById['modal-doc-content'].value = 'In PayCore v2, customerId is required and replaces customer_id.';
      elementsById['modal-confirm-btn'].click();
      const ingested = app.db.documentation_sources.find(d => d.title === 'PayCore v2 Migration Notice');
      if (!ingested) throw new Error('Documentation was not ingested');

      // Attempt duplicate ingestion
      app.openIngestDocModal();
      elementsById['modal-doc-title'].value = 'PayCore v2 Duplicate Notice';
      elementsById['modal-doc-content'].value = 'In PayCore v2, customerId is required and replaces customer_id.';
      elementsById['modal-confirm-btn'].click();
      const count = app.db.documentation_sources.filter(d => d.content === 'In PayCore v2, customerId is required and replaces customer_id.').length;
      if (count !== 1) throw new Error('Deduplication guard failed, count=' + count);
    }
  },
  {
    name: 'Bounded Revision Loop Ceiling (Max 3)',
    fn: () => {
      app.switchRole('Admin');
      const rep = app.db.repairs[0];
      rep.iteration_count = 1;
      
      // Iteration 2
      app.promptRequestRevision(rep.id);
      elementsById['modal-revision-note'].value = 'Add trimming on customerId';
      elementsById['modal-confirm-btn'].click();
      if (rep.iteration_count !== 2) throw new Error('Expected iteration 2, got ' + rep.iteration_count);

      // Iteration 3
      app.promptRequestRevision(rep.id);
      elementsById['modal-revision-note'].value = 'Ensure integer casting compatibility';
      elementsById['modal-confirm-btn'].click();
      if (rep.iteration_count !== 3) throw new Error('Expected iteration 3, got ' + rep.iteration_count);

      // Iteration 4 (Must be blocked)
      app.promptRequestRevision(rep.id);
      if (rep.iteration_count !== 3) throw new Error('Iteration count exceeded max 3! got ' + rep.iteration_count);
      const ceilingAudit = app.db.audit_logs.find(a => a.action === 'REPAIR_REVISION_CEILING_REACHED');
      if (!ceilingAudit) throw new Error('Ceiling reached audit log was not recorded');
    }
  },
  {
    name: 'RBAC Viewer Denial on Approve',
    fn: () => {
      app.switchRole('Viewer');
      const rep = app.db.repairs[0];
      app.approveRepair(rep.id);
      if (rep.workflow_state === 'APPROVED_READY_FOR_PR') throw new Error('Viewer was able to approve repair!');
    }
  },
  {
    name: 'RBAC Admin Approval',
    fn: () => {
      app.switchRole('Admin');
      const rep = app.db.repairs[0];
      app.approveRepair(rep.id);
      if (rep.workflow_state !== 'APPROVED_READY_FOR_PR') throw new Error('Admin failed to approve repair: state=' + rep.workflow_state);
    }
  },
  {
    name: 'Create PR or Local Patch Export',
    fn: () => {
      const rep = app.db.repairs[0];
      app.createPullRequestOrExport(rep.id);
      if (rep.workflow_state !== 'PR_CREATED') throw new Error('State after PR was ' + rep.workflow_state);
    }
  },
  {
    name: 'Authorize Deployment',
    fn: () => {
      const rep = app.db.repairs[0];
      app.authorizeDeployment(rep.id);
      if (rep.workflow_state !== 'DEPLOYED') throw new Error('State after deployment was ' + rep.workflow_state);
    }
  },
  {
    name: 'Quick 1-Click Approve and Deploy Gate Check',
    fn: () => {
      // Re-trigger new incident via reset
      app.resetDemoEnvironment();
      app.db.workspace.drift_active = true;
      app.db.workspace.upstream_failure_mode = 'SCHEMA_DRIFT';
      app.sendProxyRequest('int_commerce_01', 'SCHEMA_DRIFT');
      const inc = app.db.incidents[0];
      app.startOrResumeRepair(inc.id);
      const rep = app.db.repairs[0];
      if (rep.workflow_state !== 'AWAITING_APPROVAL') {
        throw new Error('Fresh repair not awaiting approval: ' + rep.workflow_state);
      }

      // Test as Viewer (blocked)
      app.switchRole('Viewer');
      app.quickOneClickApproveAndDeploy(rep.id);
      if (rep.workflow_state === 'DEPLOYED') throw new Error('Viewer could 1-click deploy!');
      const blockedAudit = app.db.audit_logs.find(a => a.outcome === 'DENIED_403' && a.target === '1-Click Approve, PR & Deploy');
      if (!blockedAudit) throw new Error('403 Forbidden audit log not recorded for Viewer 1-click attempt');

      // Test as Admin (success)
      app.switchRole('Admin');
      app.quickOneClickApproveAndDeploy(rep.id);
      if (rep.workflow_state !== 'DEPLOYED') throw new Error('Admin 1-click deploy failed: ' + rep.workflow_state);
    }
  },
  {
    name: 'Settings: LLM and GitHub Config Persistence',
    fn: () => {
      app.switchRole('Admin');
      app.navigate('settings');
      elementsById['cfg-llm-provider'].value = 'openai';
      elementsById['cfg-llm-key'].value = 'sk-abcdef1234567890';
      app.saveLlmConfig();
      if (!app.db.workspace.llm_config.api_key_masked.startsWith('sk-••••')) {
        throw new Error('LLM secret not properly masked: ' + app.db.workspace.llm_config.api_key_masked);
      }

      elementsById['cfg-gh-owner'].value = 'enterprise-org';
      elementsById['cfg-gh-repo'].value = 'sarthi-proxy';
      elementsById['cfg-gh-token'].value = 'ghp_secrettoken9999';
      app.saveGithubConfig();
      if (!app.db.workspace.github_config.token_masked.startsWith('ghp_••••')) {
        throw new Error('GitHub token not properly masked: ' + app.db.workspace.github_config.token_masked);
      }
    }
  },
  {
    name: 'Execute 14-Step Acceptance Verification',
    fn: () => app.execute14StepAcceptanceVerification()
  }
];

let passed = 0;
let failed = 0;

for (const t of tests) {
  try {
    t.fn();
    console.log(`[PASS] ${t.name}`);
    passed++;
  } catch (err) {
    console.error(`[FAIL] ${t.name}:`, err.message);
    failed++;
  }
}

console.log(`\nResults: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
