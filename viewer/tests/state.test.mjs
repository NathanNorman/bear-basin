import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatNotes, makeNote, NOTES_KEY, readNotes, writeNotes } from '../notes.mjs';
import { isCoordinate, isVisible, readPartMetadata, SelectionHighlight } from '../model-state.mjs';

function memoryStorage(initial = null) {
  let value = initial;
  return {
    getItem(key) { assert.equal(key, NOTES_KEY); return value; },
    setItem(key, next) { assert.equal(key, NOTES_KEY); value = next; },
  };
}

test('notes from the original viewer survive loading, appending, and reloading', () => {
  const old = { part: 'C02', code: 'C02', at: '1.00, 2.00, 3.00', note: 'Original note' };
  const storage = memoryStorage(JSON.stringify([old]));
  const notes = readNotes(storage);
  notes.push(makeNote(null, ' General observation '));
  writeNotes(storage, notes);
  assert.deepEqual(readNotes(storage), [old, { part: '(none)', code: '', at: '', note: 'General observation' }]);
});

test('empty storage is valid and corrupt or unsupported storage is not silently replaced', () => {
  assert.deepEqual(readNotes(memoryStorage()), []);
  for (const raw of ['{', 'null', '{}', '[null]', '[{"part":"C02"}]']) {
    const storage = memoryStorage(raw);
    assert.throws(() => readNotes(storage));
    assert.equal(storage.getItem(NOTES_KEY), raw);
  }
});

test('storage access and quota errors reach the UI boundary', () => {
  assert.throws(() => readNotes({ getItem() { throw new Error('disabled'); } }), /disabled/);
  assert.throws(() => writeNotes({ setItem() { throw new Error('quota'); } }, []), /quota/);
});

test('note export retains selected part identity and Blender coordinates', () => {
  const note = makeNote({ name: 'Roof', code: 'KA12', point_xyz_blender: ['1.00', '-2.00', '3.00'] }, ' Fix joint ');
  assert.equal(formatNotes([note]), '- Roof [KA12] at (1.00, -2.00, 3.00): Fix joint');
});

test('metadata inherits across nested primitive nodes without name-case heuristics', () => {
  const part = { name: 'lowercase_part', userData: { group: 'Roof', code: 'KA12' }, parent: null };
  const primitive = { name: 'Primitive_0', userData: {}, parent: { userData: {}, parent: part } };
  assert.deepEqual(readPartMetadata(primitive), { part: 'lowercase_part', code: 'KA12', grp: 'Roof' });
  assert.deepEqual(readPartMetadata({ name: 'Bare' }), { part: 'Bare', code: '', grp: 'Other' });
});

test('hidden ancestors prevent selection as well as hidden meshes', () => {
  const parent = { visible: false };
  const mesh = { visible: true, parent };
  assert.equal(isVisible(mesh), false);
  parent.visible = true;
  assert.equal(isVisible(mesh), true);
  mesh.visible = false;
  assert.equal(isVisible(mesh), false);
});

function material(type, color) {
  return {
    [type]: { value: color, setHex(value) { this.value = value; } },
    disposed: false,
    clone() { return material(type, this[type].value); },
    dispose() { this.disposed = true; },
  };
}

test('highlight restores shared material and original emissive color, disposing only its clone', () => {
  const original = material('emissive', 0x123456);
  const mesh = { material: original };
  const other = { material: original };
  const selection = new SelectionHighlight();
  selection.set(mesh);
  const temporary = mesh.material;
  assert.equal(temporary.emissive.value, 0xff3300);
  assert.equal(other.material.emissive.value, 0x123456);
  selection.clear();
  assert.equal(mesh.material, original);
  assert.equal(original.emissive.value, 0x123456);
  assert.equal(temporary.disposed, true);
  assert.equal(original.disposed, false);
});

test('highlight supports material arrays and non-emissive materials', () => {
  const original = [material('emissive', 12), material('color', 34)];
  const mesh = { material: original };
  const selection = new SelectionHighlight();
  selection.set(mesh);
  const temporary = mesh.material;
  assert.equal(temporary[0].emissive.value, 0xff3300);
  assert.equal(temporary[1].color.value, 0xff6600);
  selection.set(null);
  assert.equal(mesh.material, original);
  assert.ok(temporary.every((entry) => entry.disposed));
});

test('camera API accepts only finite triples', () => {
  assert.equal(isCoordinate([1, -2, 3]), true);
  for (const value of [null, [1, 2], [1, 2, Infinity], [1, NaN, 3], ['1', 2, 3]]) {
    assert.equal(isCoordinate(value), false);
  }
});
