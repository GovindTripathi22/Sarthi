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
  querySelector(sel) { return this.children[0] || null; }
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
    if (sel === '.nav-btn') return [new Element('button', '', 'nav-btn')];
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
  lucide: { createIcons: () => {} },
  Blob: class { constructor(data, opts) { this.data = data; this.opts = opts; } },
  URL: { createObjectURL: () => 'blob:mock-url', revokeObjectURL: () => {} },
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

const newTests = [
  {
    name: 'Default Explanations Mode is Simple',
    fn: () => {
      if (app.explanationMode !== 'simple') throw new Error('Expected default mode simple, got ' + app.explanationMode);
    }
  },
  {
    name: 'Toggle Explanations Mode to Technical and Back',
    fn: () => {
      app.toggleExplanationMode();
      if (app.explanationMode !== 'technical') throw new Error('Expected technical, got ' + app.explanationMode);
      if (mockLocalStorage.getItem('autopatch_explanation_mode') !== 'technical') throw new Error('Not saved in localStorage');

      app.toggleExplanationMode();
      if (app.explanationMode !== 'simple') throw new Error('Expected simple, got ' + app.explanationMode);
      if (mockLocalStorage.getItem('autopatch_explanation_mode') !== 'simple') throw new Error('Not saved in localStorage');
    }
  },
  {
    name: 'Explanation Callouts rendered on all 9 pages in Simple Mode',
    fn: () => {
      app.setExplanationMode('simple');
      const pages = ['dashboard', 'integrations', 'incidents', 'workbench', 'review', 'contracts', 'analytics', 'settings', 'blueprint'];
      for (const page of pages) {
        app.navigate(page);
        const htmlContent = elementsById['main-viewport'].innerHTML;
        if (!htmlContent.includes('Why this matters')) {
          throw new Error(`Missing 'Why this matters' callout on page: ${page}`);
        }
        if (!htmlContent.includes('story-stepper-container')) {
          throw new Error(`Missing persistent story stepper on page: ${page}`);
        }
      }
    }
  },
  {
    name: 'Explanation Callouts collapsed in Technical Mode',
    fn: () => {
      app.setExplanationMode('technical');
      const pages = ['dashboard', 'integrations', 'incidents', 'workbench', 'review', 'contracts', 'analytics', 'settings', 'blueprint'];
      for (const page of pages) {
        app.navigate(page);
        const htmlContent = elementsById['main-viewport'].innerHTML;
        if (htmlContent.includes('Why this matters')) {
          throw new Error(`Callout should be collapsed in technical mode on page: ${page}`);
        }
      }
      app.setExplanationMode('simple'); // restore
    }
  },
  {
    name: 'Story Stepper Step 1: Health Navigation',
    fn: () => {
      app.goToStoryStep(1);
      if (app.currentPage !== 'dashboard') throw new Error('Expected dashboard, got ' + app.currentPage);
    }
  },
  {
    name: 'Story Stepper Step 2: Breakdown Simulation',
    fn: () => {
      app.db.workspace.drift_active = false;
      app.goToStoryStep(2);
      if (!app.db.workspace.drift_active) throw new Error('Expected drift_active to be true');
      if (app.currentPage !== 'dashboard') throw new Error('Expected dashboard, got ' + app.currentPage);
    }
  },
  {
    name: 'Story Stepper Step 3: AI Self-Healing',
    fn: () => {
      app.goToStoryStep(3);
      if (app.currentPage !== 'workbench') throw new Error('Expected workbench, got ' + app.currentPage);
      const rep = app.db.repairs[0];
      if (!rep) throw new Error('Expected active repair run');
      if (rep.nodes.length !== 11) throw new Error('Expected 11 nodes, got ' + rep.nodes.length);
    }
  },
  {
    name: 'Story Stepper Step 4: Review Gate',
    fn: () => {
      app.goToStoryStep(4);
      if (app.currentPage !== 'review') throw new Error('Expected review, got ' + app.currentPage);
      const htmlContent = elementsById['main-viewport'].innerHTML;
      if (!htmlContent.includes('Role Permissions Guidance')) throw new Error('Missing Role Permissions guidance in review');
      if (!htmlContent.includes('Visual Code Diff Guide')) throw new Error('Missing Visual Code Diff Guide in review');
    }
  },
  {
    name: 'Workbench Assembly Line Titles & Badge Explanations',
    fn: () => {
      app.navigate('workbench');
      const htmlContent = elementsById['main-viewport'].innerHTML;
      const expectedTitles = [
        'Log 911 Alarm Ticket',
        'Checking our Rulebook',
        'AI Detective Investigation',
        'Formulate Repair Plan',
        'Read Vendor Manual',
        'Write Dual-Language Code',
        'Security X-Ray',
        'Safe Test Chamber',
        'Run 4 Crash Tests',
        'Generate Release Notes',
        'Human Boss Approval'
      ];
      for (const t of expectedTitles) {
        if (!htmlContent.includes(t)) throw new Error(`Missing assembly line title '${t}' in Workbench`);
      }
      if (!htmlContent.includes('Work Order #')) throw new Error('Missing Work Order # badge');
      if (!htmlContent.includes('Safe Save-Game File')) throw new Error('Missing Safe Save-Game File badge');
      if (!htmlContent.includes('allowed')) throw new Error('Missing Iteration explanation');
    }
  },
  {
    name: 'Dashboard Before & After Visual Translation Card',
    fn: () => {
      app.navigate('dashboard');
      const htmlContent = elementsById['main-viewport'].innerHTML;
      if (!htmlContent.includes('What Partner Sent')) throw new Error('Missing What Partner Sent');
      if (!htmlContent.includes('What Your App Expected')) throw new Error('Missing What Your App Expected');
      if (!htmlContent.includes('What Sarthi Does')) throw new Error('Missing What Sarthi Does');
      if (!htmlContent.includes('$126,000')) throw new Error('Missing $126,000 saved savings metric');
    }
  },
  {
    name: 'Technical Mode Collapses Badges in Workbench',
    fn: () => {
      app.setExplanationMode('technical');
      app.navigate('workbench');
      const htmlContent = elementsById['main-viewport'].innerHTML;
      if (htmlContent.includes('Safe Save-Game File')) {
        throw new Error('Safe Save-Game File should be collapsed in technical mode');
      }
      if (htmlContent.includes('Work Order #')) {
        throw new Error('Work Order # should be collapsed in technical mode');
      }
      app.setExplanationMode('simple');
    }
  },
  {
    name: 'Code Review Visual Diff Guide Exact Phrasing',
    fn: () => {
      app.setExplanationMode('simple');
      app.navigate('review');
      const htmlContent = elementsById['main-viewport'].innerHTML;
      if (!htmlContent.includes('Red lines = Old code removed;')) {
        throw new Error('Missing exact phrasing for Red lines');
      }
      if (!htmlContent.includes('Green lines = New code added')) {
        throw new Error('Missing exact phrasing for Green lines');
      }
    }
  }
];

let passed = 0;
let failed = 0;

for (const t of newTests) {
  try {
    t.fn();
    console.log(`[PASS] ${t.name}`);
    passed++;
  } catch (err) {
    console.error(`[FAIL] ${t.name}:`, err.message);
    failed++;
  }
}

console.log(`\nNew Feature Results: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
