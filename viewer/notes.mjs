export const NOTES_KEY = 'bb_notes';

// Keep the original storage key and shape so earlier viewer notes survive updates.
export function readNotes(storage) {
  const raw = storage.getItem(NOTES_KEY);
  if (raw === null) return [];
  const notes = JSON.parse(raw);
  const fields = ['part', 'code', 'at', 'note'];
  if (!Array.isArray(notes) || !notes.every((note) => (
    note !== null && typeof note === 'object'
    && fields.every((field) => typeof note[field] === 'string')
  ))) {
    throw new Error('Saved notes have an unsupported format.');
  }
  return notes.map(({ part, code, at, note }) => ({ part, code, at, note }));
}

export function writeNotes(storage, notes) {
  storage.setItem(NOTES_KEY, JSON.stringify(notes));
}

export function makeNote(selected, text) {
  return {
    part: selected?.name || '(none)',
    code: selected?.code || '',
    at: selected?.point_xyz_blender.join(', ') || '',
    note: text.trim(),
  };
}

export function formatNotes(notes) {
  return notes.map((note) => `- ${note.part} [${note.code}] at (${note.at}): ${note.note}`).join('\n');
}
