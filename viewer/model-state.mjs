const hasText = (value) => typeof value === 'string' && value.length > 0;

// glTF can put a part's metadata on a parent of its material-specific meshes.
export function readPartMetadata(mesh) {
  let owner = null;
  let group = '';
  let code = '';
  for (let object = mesh; object; object = object.parent) {
    const data = object.userData || {};
    if (!owner && (hasText(data.group) || hasText(data.code))) owner = object;
    if (!group && hasText(data.group)) group = data.group;
    if (!code && hasText(data.code)) code = data.code;
  }
  return { part: owner?.name || mesh.name || '(unnamed part)', code, grp: group || 'Other' };
}

export function isVisible(object) {
  for (let current = object; current; current = current.parent) {
    if (current.visible === false) return false;
  }
  return true;
}

export function isCoordinate(value) {
  return Array.isArray(value) && value.length === 3 && value.every(Number.isFinite);
}

// Clone only the selected mesh's material(s); shared model materials stay intact.
export class SelectionHighlight {
  constructor() {
    this.object = null;
    this.original = null;
    this.temporary = [];
  }

  clear() {
    if (this.object) this.object.material = this.original;
    this.temporary.forEach((material) => material.dispose());
    this.object = null;
    this.original = null;
    this.temporary = [];
  }

  set(object) {
    this.clear();
    if (!object) return;
    this.object = object;
    this.original = object.material;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    this.temporary = materials.map((material) => {
      const copy = material.clone();
      if (copy.emissive) copy.emissive.setHex(0xff3300);
      else if (copy.color) copy.color.setHex(0xff6600);
      return copy;
    });
    object.material = Array.isArray(this.original) ? this.temporary : this.temporary[0];
  }
}
