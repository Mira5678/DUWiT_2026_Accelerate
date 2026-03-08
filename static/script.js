let tree = null;
let nodeIdCounter = 0;
let selectedNodeId = null;
let ctxNodeId = null;

// Pan & zoom state
let panX = 0, panY = 0, scale = 1;
let isPanning = false, panStartX = 0, panStartY = 0;

function mkNode(text, parentId = null) {
  return { id: nodeIdCounter++, text, parentId, children: [], x: 0, y: 0, depth: 0 };
}

function findNode(node, id) {
  if (!node) return null;
  if (node.id === id) return node;
  for (const c of node.children) {
    const f = findNode(c, id);
    if (f) return f;
  }
  return null;
}

function getAllNodes(node, list = []) {
  if (!node) return list;
  list.push(node);
  node.children.forEach(c => getAllNodes(c, list));
  return list;
}

function deleteNode(node, id) {
  if (!node) return false;
  const idx = node.children.findIndex(c => c.id === id);
  if (idx !== -1) { node.children.splice(idx, 1); return true; }
  for (const c of node.children) if (deleteNode(c, id)) return true;
  return false;
}


//  Layout
function layoutTree() {
  const svg = document.getElementById('mindmap-svg');
  const W = svg.clientWidth || 900;
  const H = svg.clientHeight || 600;

  tree.x = W / 2;
  tree.y = H - 90;
  tree.depth = 0;

  layoutChildren(tree, 0, Math.PI, 148, 1);
}

function layoutChildren(node, minA, maxA, branchLen, depth) {
  const n = node.children.length;
  if (!n) return;

  if (maxA - minA < 0.01) {
    const mid = (minA + maxA) / 2;
    minA = mid - 0.4;
    maxA = mid + 0.4;
  }

  node.children.forEach((child, i) => {
    child.depth = depth;
    const t = n === 1 ? 0.5 : i / (n - 1);
    const angle = minA + t * (maxA - minA);

    child.x = node.x + branchLen * Math.cos(angle);
    child.y = node.y + branchLen * Math.sin(angle);

    const halfSpread = Math.max((maxA - minA) / n * 0.85, 0.22);
    layoutChildren(child, angle - halfSpread, angle + halfSpread, branchLen * 0.68, depth + 1);
  });
}


//  Render
const NODE_COLORS = {
  node0: { fill: '#FF6B9D', stroke: '#E91E8C', text: '#fff' },
  node1: { fill: '#FF9CC5', stroke: '#FF6B9D', text: '#5D2E4A' },
  node2: { fill: '#FFB8D4', stroke: '#FF9CC5', text: '#5D2E4A' },
  node3: { fill: '#FFD6E8', stroke: '#FFB8D4', text: '#5D2E4A' },
  node4: { fill: '#EDE0F8', stroke: '#C9A8E8', text: '#5D2E4A' },
};

function getColor(depth) {
  return NODE_COLORS[`node${Math.min(depth, 4)}`];
}

function svgEl(tag, attrs = {}) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
  return el;
}

function renderMap() {
  if (!tree) return;
  layoutTree();

  const eg = document.getElementById('edges-group');
  const ng = document.getElementById('nodes-group');
  eg.innerHTML = '';
  ng.innerHTML = '';

  renderNode(tree, null);
  refreshNodeList();
  refreshParentSelect();
  document.getElementById('empty-state').classList.add('hidden');
}

function renderNode(node, parent) {
  if (parent) drawBranch(parent, node);
  drawNodeEl(node);
  node.children.forEach(c => renderNode(c, node));
}

function drawBranch(p, c) {
  const eg = document.getElementById('edges-group');
  const strokeW = Math.max(11 - c.depth * 2.2, 1.8);
  const color = c.depth <= 1 ? '#9E6641' : c.depth <= 2 ? '#BE8B61' : '#D4A87A';

  const dy = c.y - p.y;
  const dx = c.x - p.x;
  const cp1x = p.x + dx * 0.15;
  const cp1y = p.y + dy * 0.45;
  const cp2x = c.x - dx * 0.15;
  const cp2y = c.y - dy * 0.45;

  const path = svgEl('path', {
    d: `M ${p.x} ${p.y} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${c.x} ${c.y}`,
    stroke: color,
    'stroke-width': strokeW,
    fill: 'none',
    'stroke-linecap': 'round',
  });
  eg.appendChild(path);

  // Leaf clusters at tips
  if (c.children.length === 0 && c.depth >= 2) {
    drawLeaves(c);
  }
}

function drawLeaves(node) {
  const eg = document.getElementById('edges-group');
  const angles = [-0.6, 0, 0.6, -1.1, 1.1];
  const leafColors = ['#FFB8D4', '#FF9CC5', '#EDE0F8', '#FFD6E8', '#D4C8F8'];

  angles.forEach((a, i) => {
    const lx = node.x + Math.cos(a) * (8 + Math.random() * 5);
    const ly = node.y + Math.sin(a) * (8 + Math.random() * 5) - 8;
    const leaf = svgEl('ellipse', {
      cx: lx, cy: ly, rx: 5, ry: 3,
      fill: leafColors[i % leafColors.length],
      opacity: '0.6',
      transform: `rotate(${a * 57},${lx},${ly})`
    });
    eg.appendChild(leaf);
  });
}

function wrapText(text, maxChars = 12) {
  const words = text.split(' ');
  if (words.length <= 1 || text.length <= maxChars) return [text];
  const mid = Math.ceil(words.length / 2);
  return [words.slice(0, mid).join(' '), words.slice(mid).join(' ')];
}

function drawNodeEl(node) {
  const ng = document.getElementById('nodes-group');
  const col = getColor(node.depth);
  const isRoot = node.depth === 0;
  const r = isRoot ? 46 : Math.max(32 - node.depth * 4, 20);

  const g = svgEl('g', { 'data-id': node.id, style: 'cursor:pointer' });

  // Trunk base below root node
  if (isRoot) {
    const trunk = svgEl('rect', {
      x: node.x - 14, y: node.y + 20,
      width: 28, height: 36, rx: '8',
      fill: '#9E6641', opacity: '0.7'
    });
    ng.appendChild(trunk);
  }

  // Selection halo
  if (node.id === selectedNodeId) {
    const halo = svgEl('circle', {
      cx: node.x, cy: node.y, r: r + 9,
      fill: 'none', stroke: '#FF6B9D',
      'stroke-width': '2.5', opacity: '0.7',
      'stroke-dasharray': '5 3'
    });
    g.appendChild(halo);
  }

  // Drop shadow
  const shadow = svgEl('circle', {
    cx: node.x + 2, cy: node.y + 4, r,
    fill: 'rgba(200,80,150,0.12)'
  });
  g.appendChild(shadow);

  // Main circle
  const circle = svgEl('circle', {
    cx: node.x, cy: node.y, r,
    fill: col.fill,
    stroke: col.stroke,
    'stroke-width': node.id === selectedNodeId ? '3' : '2',
    filter: isRoot ? 'url(#glow-filter)' : ''
  });
  g.appendChild(circle);

  // Shine highlight
  const shine = svgEl('ellipse', {
    cx: node.x - r * 0.3, cy: node.y - r * 0.3,
    rx: r * 0.3, ry: r * 0.2,
    fill: 'rgba(255,255,255,0.4)'
  });
  g.appendChild(shine);

  // Plus button for adding child (not on root)
  if (!isRoot) {
    const plusR = 8;
    const plusX = node.x + r + 15;
    const plusY = node.y;

    const plusCircle = svgEl('circle', {
      cx: plusX, cy: plusY, r: plusR,
      fill: '#FF6B9D', stroke: '#E91E8C', 'stroke-width': '1.5'
    });

    const plusText = svgEl('text', {
      x: plusX, y: plusY + 1,
      'text-anchor': 'middle', 'dominant-baseline': 'middle',
      'font-family': 'Arial, sans-serif', 'font-weight': 'bold', 'font-size': '12',
      fill: '#fff'
    });
    plusText.textContent = '+';

    // Plus button group for events
    const plusG = svgEl('g', { style: 'cursor:pointer' });
    plusG.appendChild(plusCircle);
    plusG.appendChild(plusText);
    plusG.addEventListener('click', (e) => {
      e.stopPropagation();
      selectNode(node.id);
      document.getElementById('idea-input').focus();
    });
    g.appendChild(plusG);
  }

  // Node label (wrapped)
  const lines = wrapText(node.text, isRoot ? 14 : 10);
  const fs = isRoot ? 13 : Math.max(12 - node.depth * 1, 10);
  const lineH = fs + 2;
  const textY = node.y - (lines.length - 1) * lineH / 2;

  lines.forEach((line, i) => {
    const t = svgEl('text', {
      x: node.x,
      y: textY + i * lineH,
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      'font-family': 'Nunito, sans-serif',
      'font-weight': '700',
      'font-size': fs,
      fill: col.text,
    });
    t.textContent = line;
    g.appendChild(t);
  });

  // Flower on root node
  if (isRoot) {
    const flower = svgEl('text', {
      x: node.x,
      y: node.y - r - 10,
      'text-anchor': 'middle',
      'font-size': '16'
    });
    flower.textContent = '✿';
    g.appendChild(flower);
  }

  // Events
  g.addEventListener('click', (e) => { e.stopPropagation(); selectNode(node.id); });
  g.addEventListener('contextmenu', (e) => { e.preventDefault(); openCtxMenu(e, node.id); });

  ng.appendChild(g);
}


//  UI Actions
function setRootTopic() {
  const val = document.getElementById('root-input').value.trim();
  if (!val) { showToast('Please enter a topic first! 🌸'); return; }

  nodeIdCounter = 0;
  tree = mkNode(val);
  selectedNodeId = tree.id;
  renderMap();

  document.getElementById('add-section').style.display   = 'block';
  document.getElementById('ai-section').style.display    = 'block';
  document.getElementById('nodes-section').style.display = 'block';

  resetView();
  showToast('🌱 Your mind tree is planted!');
}

function addIdea() {
  if (!tree) return;
  const val = document.getElementById('idea-input').value.trim();
  if (!val) { showToast('Type an idea first 💭'); return; }

  const parentId = parseInt(document.getElementById('parent-select').value);
  const parent = findNode(tree, parentId);
  if (!parent) return;

  const node = mkNode(val, parentId);
  parent.children.push(node);
  document.getElementById('idea-input').value = '';
  selectedNodeId = node.id;
  renderMap();
  showToast(`✿ "${val}" added!`);
}

function selectNode(id) {
  selectedNodeId = id;
  renderMap();
  const sel = document.getElementById('parent-select');
  if (sel) sel.value = id;
}

function refreshParentSelect() {
  const sel = document.getElementById('parent-select');
  const nodes = getAllNodes(tree);
  sel.innerHTML = nodes.map(n =>
    `<option value="${n.id}" ${n.id === selectedNodeId ? 'selected' : ''}>
      ${'·'.repeat(n.depth * 2)} ${n.text.length > 28 ? n.text.slice(0, 28) + '…' : n.text}
    </option>`
  ).join('');
}

function refreshNodeList() {
  const list = document.getElementById('node-list');
  const nodes = getAllNodes(tree);
  list.innerHTML = nodes.map(n => `
    <div class="node-item ${n.id === selectedNodeId ? 'selected' : ''}"
         onclick="selectNode(${n.id})" data-id="${n.id}">
      <div class="node-dot ${n.depth === 0 ? 'root' : ''}"></div>
      <span class="node-item-text">${n.text}</span>
      ${n.depth > 0
        ? `<button class="node-del"
             onclick="event.stopPropagation();deleteNodeById(${n.id})">✕</button>`
        : ''}
    </div>
  `).join('');
}

function deleteNodeById(id) {
  if (!tree) return;

  // Prevent deleting root
  if (id === tree.id) {
    showToast("You can't delete the root 🌳");
    return;
  }

  const deleted = deleteNode(tree, id);

  if (deleted) {
    if (selectedNodeId === id) {
      selectedNodeId = tree.id;
    }

    renderMap();
    showToast('Node removed 🍃');
  }
}


//  Context Menu
function openCtxMenu(e, nodeId) {
  ctxNodeId = nodeId;
  const menu = document.getElementById('ctx-menu');
  menu.style.left = e.clientX + 'px';
  menu.style.top  = e.clientY + 'px';
  menu.classList.add('visible');
}

document.addEventListener('click', () => {
  document.getElementById('ctx-menu').classList.remove('visible');
});

function ctxAddChild() {
  if (ctxNodeId == null) return;
  selectNode(ctxNodeId);
  document.getElementById('idea-input').focus();
}

function ctxAIExpand() {
  if (ctxNodeId == null) return;
  selectNode(ctxNodeId);
  expandSelected();
}

function ctxRefine() {
  if (ctxNodeId == null) return;
  selectNode(ctxNodeId);
  refineSelected();
}

function ctxDelete() {
  if (ctxNodeId != null) deleteNodeById(ctxNodeId);
}


//  AI Features
async function generateIdeas() {
  if (!tree) return;
  const targetId = selectedNodeId ?? tree.id;
  const target = findNode(tree, targetId);
  if (!target) return;

  const existing = target.children.map(c => c.text);

  showAILoading(true);
  try {
    const res = await fetch('/api/generate-ideas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: target.text, existing })
    });
    const data = await res.json();
    if (data.success) showSuggestions(data.ideas, targetId);
    else showToast('AI had a brain freeze 🧊 Try again!');
  } catch {
    showToast('Could not reach AI — check your connection 🌐');
  } finally {
    showAILoading(false);
  }
}

async function expandSelected() {
  if (!tree) return;
  const targetId = selectedNodeId ?? tree.id;
  const target = findNode(tree, targetId);
  if (!target) return;

  const parentNode = target.parentId != null ? findNode(tree, target.parentId) : null;

  showAILoading(true);
  try {
    const res = await fetch('/api/expand-node', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node: target.text,
        parent: parentNode ? parentNode.text : '',
        depth: target.depth
      })
    });
    const data = await res.json();
    if (data.success) showSuggestions(data.ideas, targetId);
    else showToast('AI had a brain freeze 🧊 Try again!');
  } catch {
    showToast('Could not reach AI 🌐');
  } finally {
    showAILoading(false);
  }
}

async function refineSelected() {
  if (!tree || selectedNodeId == null) {
    showToast('Select a node first! 🌸');
    return;
  }
  const target = findNode(tree, selectedNodeId);
  if (!target || target.depth === 0) {
    showToast('Select a branch node to refine ✿');
    return;
  }

  const parentNode = target.parentId != null ? findNode(tree, target.parentId) : null;

  showAILoading(true);
  try {
    const res = await fetch('/api/refine-idea', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        idea: target.text,
        parent: parentNode ? parentNode.text : ''
      })
    });
    const data = await res.json();
    if (data.success) {
      target.text = data.refined;
      renderMap();
      showToast(`✨ Refined to: "${data.refined}"`);
    } else {
      showToast('AI had a brain freeze 🧊');
    }
  } catch {
    showToast('Could not reach AI 🌐');
  } finally {
    showAILoading(false);
  }
}

function showSuggestions(ideas, parentId) {
  const panel = document.getElementById('suggestions-panel');
  const chips = document.getElementById('suggestion-chips');
  chips.innerHTML = ideas.map(idea => `
    <span class="chip add-chip"
          onclick="addSuggestion(${parentId}, '${idea.replace(/'/g, "\\'")}', this)">
      ＋ ${idea}
    </span>
  `).join('');
  panel.classList.add('visible');
}

function addSuggestion(parentId, text, chipEl) {
  const parent = findNode(tree, parentId);
  if (!parent) return;

  const node = mkNode(text, parentId);
  parent.children.push(node);
  selectedNodeId = node.id;
  renderMap();

  chipEl.classList.remove('add-chip');
  chipEl.classList.add('chip');
  chipEl.onclick = null;
  chipEl.style.opacity = '0.5';
  chipEl.textContent = '✓ ' + text;
  showToast(`✿ "${text}" added!`);
}

//  Pan & Zoom


const svg      = document.getElementById('mindmap-svg');
const panGroup = document.getElementById('pan-group');

svg.addEventListener('mousedown', e => {
  if (e.target === svg || e.target === panGroup) {
    isPanning  = true;
    panStartX  = e.clientX - panX;
    panStartY  = e.clientY - panY;
    svg.style.cursor = 'grabbing';
  }
});

document.addEventListener('mousemove', e => {
  if (!isPanning) return;
  panX = e.clientX - panStartX;
  panY = e.clientY - panStartY;
  applyTransform();
});

document.addEventListener('mouseup', () => {
  isPanning = false;
  svg.style.cursor = 'grab';
});

svg.addEventListener('wheel', e => {
  e.preventDefault();
  zoom(-e.deltaY * 0.001, e.clientX, e.clientY);
}, { passive: false });

function zoom(delta, cx, cy) {
  const oldScale = scale;
  scale = Math.max(0.3, Math.min(3, scale + delta));

  if (cx != null && cy != null) {
    const rect = svg.getBoundingClientRect();
    const mx   = cx - rect.left;
    const my   = cy - rect.top;
    panX = mx - (mx - panX) * (scale / oldScale);
    panY = my - (my - panY) * (scale / oldScale);
  }
  applyTransform();
}

function applyTransform() {
  panGroup.setAttribute('transform', `translate(${panX},${panY}) scale(${scale})`);
}

function resetView() {
  panX = 0; panY = 0; scale = 1;
  applyTransform();
}

function clearMap() {
  if (!tree) return;
  if (!confirm('Clear the entire mind map? This cannot be undone.')) return;

  tree = null;
  selectedNodeId = null;

  document.getElementById('edges-group').innerHTML = '';
  document.getElementById('nodes-group').innerHTML = '';
  document.getElementById('empty-state').classList.remove('hidden');
  document.getElementById('add-section').style.display   = 'none';
  document.getElementById('ai-section').style.display    = 'none';
  document.getElementById('nodes-section').style.display = 'none';
  document.getElementById('suggestions-panel').classList.remove('visible');

  showToast('Canvas cleared 🌿');
}

//  Helpers

function showAILoading(show) {
  document.getElementById('ai-loading').classList.toggle('hidden', !show);
}

let toastTimeout;
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => t.classList.remove('show'), 2800);
}

// Re-render on window resize
window.addEventListener('resize', () => {
  if (tree) renderMap();
});

// Click on empty canvas to deselect
svg.addEventListener('click', e => {
  const bg = e.target === svg
    || e.target === panGroup
    || e.target.tagName === 'svg'
    || e.target.id === 'edges-group'
    || e.target.id === 'nodes-group';

  if (bg) {
    selectedNodeId = null;
    if (tree) renderMap();
  }
});