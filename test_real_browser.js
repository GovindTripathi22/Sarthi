const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('index.html', 'utf8');

// Simple DOM Mock
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
  }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(val) { this._innerHTML = val; }
  get textContent() { return this._textContent; }
  set textContent(val) { this._textContent = val; }
  appendChild(child) { this.children.push(child); }
  removeChild(child) {
    this.children = this.children.filter(c => c !== child);
  }
  setAttribute(k, v) { this.attributes[k] = v; }
  getAttribute(k) { return this.attributes[k]; }
}

// Extract all elements with IDs from html
const idMatches = [...html.matchAll(/<([a-zA-Z0-9]+)[^>]*id=["']([^"']+)["'][^>]*>/g)];
const elementsById = {};
for (const match of idMatches) {
  const tagName = match[1];
  const id = match[2];
  elementsById[id] = new Element(tagName, id);
}

console.log('Parsed IDs from HTML:', Object.keys(elementsById));

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
  body: new Element('body', 'body', 'min-h-screen bg-[#090d16] text-slate-100 flex flex-col select-none font-sans antialiased')
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
  Blob: class {},
  URL: {
    createObjectURL: () => 'blob:mock-url',
    revokeObjectURL: () => {}
  },
  console: console,
  setTimeout: (fn) => fn(),
  clearTimeout: () => {},
  setInterval: () => {},
  clearInterval: () => {}
};

// Extract JS from script tag (Script 3)
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

try {
  vm.runInContext(mainScript, context);
  console.log('Script evaluated successfully.');
  
  // Now simulate DOMContentLoaded
  if (domEvents['DOMContentLoaded']) {
    console.log('Firing DOMContentLoaded...');
    domEvents['DOMContentLoaded'].forEach(fn => fn());
    console.log('DOMContentLoaded executed successfully!');
  }
} catch (err) {
  console.error('FATAL RUNTIME ERROR during script execution:');
  console.error(err);
}
