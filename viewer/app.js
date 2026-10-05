import { formatNotes, makeNote, readNotes, writeNotes } from './notes.mjs';

const get = (id) => document.getElementById(id);
const state = window.viewerState = { selected: null, notes: [], status: 'loading', look: null };
let storage = null;
let readFailed = false;
let savingFailed = false;
let lastRemoved = null;

function saveNotes(message) {
  if (readFailed) return;
  try {
    writeNotes(storage, state.notes);
    savingFailed = false;
    noteStatus(message);
  } catch {
    savingFailed = true;
    noteStatus('Notes could not be saved. Copy them before leaving this page.', true);
  }
}

function noteStatus(message, error = false) {
  get('notes-status').textContent = message;
  get('notes-status').dataset.error = String(error);
}

function renderNotes() {
  get('notes').replaceChildren(...state.notes.map((note, index) => {
    const row = document.createElement('div');
    const text = document.createElement('span');
    text.textContent = `${note.part} [${note.code}] ${note.note}`;
    const remove = document.createElement('button');
    remove.textContent = 'Remove';
    remove.setAttribute('aria-label', `Remove note: ${note.note}`);
    remove.addEventListener('click', () => {
      lastRemoved = { note, index };
      state.notes.splice(index, 1);
      renderNotes();
      saveNotes('Note removed. You can undo this removal.');
    });
    row.append(text, remove);
    return row;
  }));
  if (lastRemoved) {
    const undo = document.createElement('button');
    undo.textContent = 'Undo remove';
    undo.addEventListener('click', () => {
      state.notes.splice(lastRemoved.index, 0, lastRemoved.note);
      lastRemoved = null;
      renderNotes();
      saveNotes('Note restored.');
    });
    get('notes').appendChild(undo);
  }
  get('copy').disabled = state.notes.length === 0;
  if (!get('copy-fallback').hidden) get('notes-export').value = formatNotes(state.notes);
}

try {
  storage = window.localStorage;
  state.notes = readNotes(storage);
} catch {
  readFailed = true;
  noteStatus('Saved notes could not be read. Existing storage will be preserved; copy any new notes before leaving.', true);
}
renderNotes();

get('add').addEventListener('click', () => {
  const text = get('note').value.trim();
  if (!text && !state.selected) return;
  state.notes.push(makeNote(state.selected, text));
  get('note').value = '';
  renderNotes();
  // Never overwrite unreadable older notes with an empty/new session.
  saveNotes('Note saved on this browser.');
});

get('copy').addEventListener('click', async () => {
  const text = formatNotes(state.notes);
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(text);
    get('copy-fallback').hidden = true;
    const unsaved = readFailed || savingFailed;
    noteStatus(unsaved ? 'Notes copied. Browser storage is unavailable for this session.' : 'Notes copied.', unsaved);
  } catch {
    get('copy-fallback').hidden = false;
    get('notes-export').value = text;
    get('notes-export').focus();
    get('notes-export').select();
    noteStatus('Clipboard access was unavailable. Use your copy shortcut on the selected text.', true);
  }
});

// Dynamic import makes CDN, module, and WebGL startup failures visible in the UI.
try {
  const { startViewer } = await import('./viewer.js');
  startViewer(state);
} catch (error) {
  state.status = 'error';
  get('model-status').textContent = 'The 3D viewer could not start. Check your connection and WebGL support, then retry.';
  get('model-status').dataset.error = 'true';
  get('retry').hidden = false;
  get('retry').onclick = () => window.location.reload();
  console.error('Viewer startup failed:', error);
}
