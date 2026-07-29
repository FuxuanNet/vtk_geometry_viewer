import '@kitware/vtk.js/favicon';
import '@kitware/vtk.js/Rendering/Profiles/Geometry';

import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor';
import vtkMapper from '@kitware/vtk.js/Rendering/Core/Mapper';
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow';
import vtkPolyData from '@kitware/vtk.js/Common/DataModel/PolyData';
import vtkPoints from '@kitware/vtk.js/Common/Core/Points';
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray';
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction';

import './style.css';

document.querySelector('#app').innerHTML = `
  <main id="workspace">
    <div id="viewer" aria-label="VTK 三维模型视图"></div>

    <aside id="panel" aria-label="查看器控制面板">
      <header class="panel-header">
        <h1>VTK 几何与结果查看器</h1>
        <p>查看 Legacy ASCII（.vtk）文件的网格几何与结果场量。</p>
      </header>

      <section class="panel-section file-section" aria-labelledby="file-title">
        <h2 id="file-title">文件</h2>
        <label class="file-picker" for="fileInput">
          <span class="file-picker-button">选择文件</span>
          <span id="fileName" class="file-name">尚未选择文件</span>
          <input id="fileInput" type="file" accept=".vtk,text/plain" />
        </label>
      </section>

      <section class="action-section" aria-label="视图操作">
        <button id="resetCamera" type="button">重置视角</button>
        <button id="toggleEdges" type="button">显示 / 隐藏壳单元边线</button>
      </section>

      <section class="panel-section color-section" aria-labelledby="color-title">
        <h2 id="color-title">结果着色</h2>
        <label class="field-row" for="colorField">
          <span id="fieldLocation" class="field-location">几何</span>
          <select id="colorField" aria-label="选择用于着色的结果场">
            <option value="">仅显示几何</option>
          </select>
        </label>
        <label class="check-row"><input id="showLines" type="checkbox" checked /> <span>显示线单元</span></label>
        <label class="check-row"><input id="showFaces" type="checkbox" checked /> <span>显示壳 / 实体表面</span></label>
      </section>

      <section class="panel-section info-section" aria-labelledby="info-title">
        <h2 id="info-title">模型信息</h2>
        <div id="stats" class="stats" aria-live="polite">尚未加载文件。</div>
      </section>
    </aside>

    <aside id="legend" class="legend is-empty" aria-label="结果颜色图例">
      <div id="legendTitle" class="legend-title">未选择结果场</div>
      <div class="legend-scale" aria-hidden="true"></div>
      <div class="legend-range"><span id="legendMin">-</span><span id="legendMax">-</span></div>
    </aside>

    <div id="hint">可将 .vtk 文件拖放到此处</div>
  </main>
`;

const container = document.querySelector('#viewer');
const statsEl = document.querySelector('#stats');
const fileNameEl = document.querySelector('#fileName');
const showLinesEl = document.querySelector('#showLines');
const showFacesEl = document.querySelector('#showFaces');
const colorFieldEl = document.querySelector('#colorField');
const fieldLocationEl = document.querySelector('#fieldLocation');
const legendEl = document.querySelector('#legend');
const legendTitleEl = document.querySelector('#legendTitle');
const legendMinEl = document.querySelector('#legendMin');
const legendMaxEl = document.querySelector('#legendMax');

const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
  rootContainer: container,
  background: [0.06, 0.08, 0.12],
});

const renderer = fullScreenRenderer.getRenderer();
const renderWindow = fullScreenRenderer.getRenderWindow();

const facePolyData = vtkPolyData.newInstance();
const faceMapper = vtkMapper.newInstance();
faceMapper.setInputData(facePolyData);
const faceActor = vtkActor.newInstance();
faceActor.setMapper(faceMapper);
faceActor.getProperty().setColor(0.78, 0.84, 0.92);
faceActor.getProperty().setOpacity(0.92);
faceActor.getProperty().setEdgeVisibility(true);
faceActor.getProperty().setEdgeColor(0.03, 0.05, 0.08);
faceActor.getProperty().setLineWidth(1);
renderer.addActor(faceActor);

const linePolyData = vtkPolyData.newInstance();
const lineMapper = vtkMapper.newInstance();
lineMapper.setInputData(linePolyData);
const lineActor = vtkActor.newInstance();
lineActor.setMapper(lineMapper);
lineActor.getProperty().setColor(1.0, 0.55, 0.18);
lineActor.getProperty().setLineWidth(1.4);
renderer.addActor(lineActor);

let edgeVisible = true;
let lastGeometry = null;

// 解析 Legacy ASCII VTK。
// 这里不用 SAM，目的是直接判断 VTK 文件中几何和结果字段是否存在。
function parseLegacyVtk(text) {
  const tokens = text.split(/\s+/).filter(Boolean);
  let points = null;
  const cells = [];
  let cellTypes = null;
  let pointDataCount = 0;
  let cellDataCount = 0;
  let activeSection = null;
  const pointFields = new Map();
  const cellFields = new Map();

  let i = 0;
  while (i < tokens.length) {
    const token = tokens[i];

    if (token === 'POINTS') {
      const count = Number(tokens[i + 1]);
      i += 3;
      if (!Number.isInteger(count) || count < 0) throw new Error('POINTS 节点数量无效。');
      const values = new Float32Array(count * 3);
      for (let k = 0; k < values.length; k += 1) {
        const value = Number(tokens[i + k]);
        if (!Number.isFinite(value)) throw new Error(`POINTS 坐标第 ${k} 项无效。`);
        values[k] = value;
      }
      points = { count, values };
      i += values.length;
      continue;
    }

    if (token === 'CELLS') {
      const count = Number(tokens[i + 1]);
      const expectedSize = Number(tokens[i + 2]);
      i += 3;
      if (!Number.isInteger(count) || count < 0) throw new Error('CELLS 单元数量无效。');
      const start = i;
      for (let c = 0; c < count; c += 1) {
        const n = Number(tokens[i]);
        i += 1;
        const ids = [];
        for (let k = 0; k < n; k += 1) ids.push(Number(tokens[i + k]));
        cells.push(ids);
        i += n;
      }
      const parsedSize = i - start;
      if (parsedSize !== expectedSize) {
        throw new Error(`CELLS 数据长度不一致：文件声明为 ${expectedSize}，实际读取为 ${parsedSize}。`);
      }
      continue;
    }

    if (token === 'CELL_TYPES') {
      const count = Number(tokens[i + 1]);
      i += 2;
      cellTypes = new Int32Array(count);
      for (let k = 0; k < count; k += 1) cellTypes[k] = Number(tokens[i + k]);
      i += count;
      continue;
    }

    if (token === 'POINT_DATA') {
      pointDataCount = Number(tokens[i + 1]);
      activeSection = 'point';
      i += 2;
      continue;
    }

    if (token === 'CELL_DATA') {
      cellDataCount = Number(tokens[i + 1]);
      activeSection = 'cell';
      i += 2;
      continue;
    }

    if (token === 'VECTORS') {
      const name = tokens[i + 1];
      i += 3;
      const count = activeSection === 'point' ? pointDataCount : cellDataCount;
      const values = new Float32Array(count * 3);
      for (let k = 0; k < values.length; k += 1) values[k] = Number(tokens[i + k]);
      const field = { name, kind: 'vector', components: 3, values };
      if (activeSection === 'point') pointFields.set(name, field);
      else if (activeSection === 'cell') cellFields.set(name, field);
      i += values.length;
      continue;
    }

    if (token === 'TENSORS') {
      const name = tokens[i + 1];
      i += 3;
      const count = activeSection === 'point' ? pointDataCount : cellDataCount;
      const values = new Float32Array(count * 9);
      for (let k = 0; k < values.length; k += 1) values[k] = Number(tokens[i + k]);
      const field = { name, kind: 'tensor', components: 9, values };
      if (activeSection === 'point') pointFields.set(name, field);
      else if (activeSection === 'cell') cellFields.set(name, field);
      i += values.length;
      continue;
    }

    if (token === 'SCALARS') {
      const name = tokens[i + 1];
      i += 3;
      let components = 1;
      if (/^\d+$/.test(tokens[i])) {
        components = Number(tokens[i]);
        i += 1;
      }
      if (tokens[i] === 'LOOKUP_TABLE') i += 2;
      const count = activeSection === 'point' ? pointDataCount : cellDataCount;
      const values = new Float32Array(count * components);
      for (let k = 0; k < values.length; k += 1) values[k] = Number(tokens[i + k]);
      const field = { name, kind: 'scalar', components, values };
      if (activeSection === 'point') pointFields.set(name, field);
      else if (activeSection === 'cell') cellFields.set(name, field);
      i += values.length;
      continue;
    }

    i += 1;
  }

  if (!points) throw new Error('未找到 POINTS 节点数据。');
  if (!cells.length) throw new Error('未找到 CELLS 单元数据。');
  if (!cellTypes) throw new Error('未找到 CELL_TYPES 单元类型数据。');
  if (cells.length !== cellTypes.length) {
    throw new Error(`CELLS 与 CELL_TYPES 数量不一致：${cells.length} 与 ${cellTypes.length}。`);
  }

  return { points, cells, cellTypes, pointFields, cellFields };
}

function buildGeometry(parsed) {
  const vtkPts = vtkPoints.newInstance();
  vtkPts.setData(parsed.points.values, 3);

  const lineConnectivity = [];
  const faceConnectivity = [];
  const faceCellSource = [];
  const unsupported = new Map();
  const counts = {
    line: 0,
    triangle: 0,
    quad: 0,
    tetra: 0,
    wedge: 0,
    hex: 0,
    outOfRange: 0,
    duplicateNodeCells: 0,
  };

  for (let cellIndex = 0; cellIndex < parsed.cells.length; cellIndex += 1) {
    const ids = parsed.cells[cellIndex];
    const type = parsed.cellTypes[cellIndex];

    if (ids.some((id) => id < 0 || id >= parsed.points.count)) {
      counts.outOfRange += 1;
      continue;
    }
    if (new Set(ids).size !== ids.length) counts.duplicateNodeCells += 1;

    if (type === 3 && ids.length === 2) {
      lineConnectivity.push(2, ids[0], ids[1]);
      counts.line += 1;
    } else if (type === 5 && ids.length === 3) {
      faceConnectivity.push(3, ids[0], ids[1], ids[2]);
      faceCellSource.push(cellIndex);
      counts.triangle += 1;
    } else if (type === 9 && ids.length === 4) {
      faceConnectivity.push(4, ids[0], ids[1], ids[2], ids[3]);
      faceCellSource.push(cellIndex);
      counts.quad += 1;
    } else if (type === 10 && ids.length === 4) {
      const faces = [[0, 1, 2], [0, 1, 3], [1, 2, 3], [2, 0, 3]];
      for (const f of faces) {
        faceConnectivity.push(3, ids[f[0]], ids[f[1]], ids[f[2]]);
        faceCellSource.push(cellIndex);
      }
      counts.tetra += 1;
    } else if (type === 13 && ids.length === 6) {
      const faces = [[0, 1, 2], [3, 5, 4], [0, 3, 4, 1], [1, 4, 5, 2], [2, 5, 3, 0]];
      for (const f of faces) {
        faceConnectivity.push(f.length, ...f.map((idx) => ids[idx]));
        faceCellSource.push(cellIndex);
      }
      counts.wedge += 1;
    } else if (type === 12 && ids.length === 8) {
      const faces = [[0, 1, 2, 3], [4, 7, 6, 5], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]];
      for (const f of faces) {
        faceConnectivity.push(4, ...f.map((idx) => ids[idx]));
        faceCellSource.push(cellIndex);
      }
      counts.hex += 1;
    } else {
      unsupported.set(type, (unsupported.get(type) || 0) + 1);
    }
  }

  const faces = vtkPolyData.newInstance();
  faces.setPoints(vtkPts);
  faces.getPolys().setData(new Uint32Array(faceConnectivity));

  const lines = vtkPolyData.newInstance();
  lines.setPoints(vtkPts);
  lines.getLines().setData(new Uint32Array(lineConnectivity));

  return { faces, lines, counts, bounds: computeBounds(parsed.points.values), unsupported, faceCellSource };
}

function computeBounds(values) {
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < values.length; i += 3) {
    for (let c = 0; c < 3; c += 1) {
      min[c] = Math.min(min[c], values[i + c]);
      max[c] = Math.max(max[c], values[i + c]);
    }
  }
  return { min, max };
}

function setGeometry(result) {
  facePolyData.shallowCopy(result.faces);
  linePolyData.shallowCopy(result.lines);
  faceActor.setVisibility(showFacesEl.checked);
  lineActor.setVisibility(showLinesEl.checked);
  renderer.resetCamera();
  renderWindow.render();
}

function updateFieldOptions(parsed) {
  colorFieldEl.innerHTML = '<option value="">仅显示几何</option>';

  for (const [name, field] of parsed.pointFields.entries()) {
    if (field.kind === 'scalar') colorFieldEl.append(new Option(`节点：${name}`, `point:${name}`));
    if (field.kind === 'vector') colorFieldEl.append(new Option(`节点：${name} 模长`, `point-mag:${name}`));
  }

  for (const [name, field] of parsed.cellFields.entries()) {
    if (field.kind === 'scalar') colorFieldEl.append(new Option(`单元：${name}`, `cell:${name}`));
  }

  if (parsed.cellFields.has('S_Mises')) colorFieldEl.value = 'cell:S_Mises';
  else if (parsed.cellFields.has('S11')) colorFieldEl.value = 'cell:S11';
  else colorFieldEl.value = '';
}

function applyColorField() {
  if (!lastGeometry) return;
  const { parsed, result } = lastGeometry;
  const choice = colorFieldEl.value;

  faceMapper.setScalarVisibility(false);
  faceMapper.setLookupTable(null);
  faceMapper.setColorByArrayName(null);
  faceActor.getProperty().setColor(0.78, 0.84, 0.92);

  if (!choice) {
    fieldLocationEl.textContent = '几何';
    legendEl.classList.add('is-empty');
    legendTitleEl.textContent = '未选择结果场';
    legendMinEl.textContent = '-';
    legendMaxEl.textContent = '-';
    renderWindow.render();
    return;
  }

  const [mode, name] = choice.split(':');
  fieldLocationEl.textContent = mode === 'cell' ? '单元' : '节点';
  let values = null;
  let arrayName = name;

  if (mode === 'cell') {
    const field = parsed.cellFields.get(name);
    if (!field) return;
    values = new Float32Array(result.faceCellSource.length);
    for (let i = 0; i < result.faceCellSource.length; i += 1) {
      values[i] = field.values[result.faceCellSource[i]];
    }
    facePolyData.getCellData().setScalars(vtkDataArray.newInstance({ name, values, numberOfComponents: 1 }));
    faceMapper.setScalarModeToUseCellData();
  } else if (mode === 'point') {
    const field = parsed.pointFields.get(name);
    if (!field) return;
    values = field.values;
    facePolyData.getPointData().setScalars(vtkDataArray.newInstance({ name, values, numberOfComponents: 1 }));
    faceMapper.setScalarModeToUsePointData();
  } else if (mode === 'point-mag') {
    const field = parsed.pointFields.get(name);
    if (!field) return;
    arrayName = `${name}_mag`;
    values = new Float32Array(parsed.points.count);
    for (let i = 0; i < parsed.points.count; i += 1) {
      const x = field.values[i * 3];
      const y = field.values[i * 3 + 1];
      const z = field.values[i * 3 + 2];
      values[i] = Math.sqrt(x * x + y * y + z * z);
    }
    facePolyData.getPointData().setScalars(vtkDataArray.newInstance({ name: arrayName, values, numberOfComponents: 1 }));
    faceMapper.setScalarModeToUsePointData();
  }

  if (!values || values.length === 0) return;

  let min = Infinity;
  let max = -Infinity;
  for (const value of values) {
    if (Number.isFinite(value)) {
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
  }
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    min = 0;
    max = 1;
  }

  const lut = vtkColorTransferFunction.newInstance();
  lut.addRGBPoint(min, 0.05, 0.2, 0.95);
  lut.addRGBPoint((min + max) * 0.5, 0.95, 0.95, 0.2);
  lut.addRGBPoint(max, 0.9, 0.08, 0.08);

  faceMapper.setLookupTable(lut);
  faceMapper.setScalarRange(min, max);
  faceMapper.setScalarVisibility(true);
  faceMapper.setColorByArrayName(arrayName);
  legendEl.classList.remove('is-empty');
  legendTitleEl.textContent = mode === 'point-mag' ? `${name} 模长（节点）` : `${name}（${mode === 'cell' ? '单元' : '节点'}）`;
  legendMinEl.textContent = formatScientific(min);
  legendMaxEl.textContent = formatScientific(max);
  renderWindow.render();
}

function formatScientific(value) {
  return Number(value).toExponential(2);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatStats(fileName, parsed, result) {
  const unsupported = [...result.unsupported.entries()]
    .map(([type, count]) => `VTK 类型 ${type}：${count}`)
    .join('；') || '无';
  const rows = [
    ['文件', fileName],
    ['节点数', parsed.points.count],
    ['单元数', parsed.cells.length],
    ['线单元', result.counts.line],
    ['三角形', result.counts.triangle],
    ['四边形', result.counts.quad],
    ['四面体', result.counts.tetra],
    ['楔体', result.counts.wedge],
    ['六面体', result.counts.hex],
    ['越界单元', result.counts.outOfRange],
    ['重复节点单元', result.counts.duplicateNodeCells],
    ['不支持单元类型', unsupported],
    ['节点结果场', [...parsed.pointFields.keys()].join(', ') || '无'],
    ['单元结果场', [...parsed.cellFields.keys()].join(', ') || '无'],
    ['最小边界', result.bounds.min.map((v) => v.toFixed(4)).join(', ')],
    ['最大边界', result.bounds.max.map((v) => v.toFixed(4)).join(', ')],
  ];

  return rows.map(([label, value]) => (
    `<div class="stat-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`
  )).join('');
}

async function loadFile(file) {
  statsEl.textContent = '正在读取并解析文件...';
  fileNameEl.textContent = file.name;
  fileNameEl.classList.add('is-loaded');
  const text = await file.text();
  const parsed = parseLegacyVtk(text);
  const result = buildGeometry(parsed);
  lastGeometry = { parsed, result };
  setGeometry(result);
  updateFieldOptions(parsed);
  applyColorField();
  statsEl.textContent = formatStats(file.name, parsed, result);
  statsEl.innerHTML = formatStats(file.name, parsed, result);
}

document.querySelector('#fileInput').addEventListener('change', (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  loadFile(file).catch((error) => {
    console.error(error);
    statsEl.textContent = `读取失败：${error.message}`;
  });
});

document.querySelector('#resetCamera').addEventListener('click', () => {
  renderer.resetCamera();
  renderWindow.render();
});

document.querySelector('#toggleEdges').addEventListener('click', () => {
  edgeVisible = !edgeVisible;
  faceActor.getProperty().setEdgeVisibility(edgeVisible);
  renderWindow.render();
});

showLinesEl.addEventListener('change', () => {
  lineActor.setVisibility(showLinesEl.checked);
  renderWindow.render();
});

showFacesEl.addEventListener('change', () => {
  faceActor.setVisibility(showFacesEl.checked);
  renderWindow.render();
});

colorFieldEl.addEventListener('change', () => {
  applyColorField();
});

document.body.addEventListener('dragover', (event) => event.preventDefault());

document.body.addEventListener('drop', (event) => {
  event.preventDefault();
  const file = event.dataTransfer.files?.[0];
  if (!file) return;
  loadFile(file).catch((error) => {
    console.error(error);
    statsEl.textContent = `读取失败：${error.message}`;
  });
});

renderWindow.render();
