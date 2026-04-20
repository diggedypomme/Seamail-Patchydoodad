import os
import json
import hashlib


class PatchEngine:
    def __init__(self, default_target_file, workspace_dir=None):
        self.default_target_file = default_target_file
        self.workspace_dir = workspace_dir or os.path.dirname(default_target_file)

    def _resolve_target(self, patch_data):
        """Return the absolute path for this patch's target file."""
        target_file = patch_data.get('target_file')
        if target_file:
            # If it's just a filename (no path separators), resolve against workspace
            if not os.path.dirname(target_file):
                return os.path.join(self.workspace_dir, target_file)
            return target_file
        return self.default_target_file

    def get_file_hash(self, path=None):
        """Get SHA256 of a file."""
        path = path or self.default_target_file
        if not os.path.exists(path):
            return None
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def check_patch_status(self, patch_data):
        """
        Check if a patch is applied to its target file.
        Returns: 'Installed', 'Missing', 'Conflict', or 'File Missing'
        """
        target = self._resolve_target(patch_data)
        if not os.path.exists(target):
            return "File Missing"

        with open(target, "rb") as f:
            for hunk in patch_data.get('patches', []):
                offset = hunk['offset']
                original_hex = hunk['original']
                patched_hex = hunk['patched']

                f.seek(offset)
                current_bytes = f.read(len(original_hex) // 2).hex()

                if current_bytes == patched_hex:
                    continue
                elif current_bytes == original_hex:
                    return "Missing"
                else:
                    return "Conflict"

        return "Installed"

    def apply_patch(self, patch_data):
        """Apply a patch (original → patched bytes)."""
        target = self._resolve_target(patch_data)
        status = self.check_patch_status(patch_data)
        if status == "Installed":
            return True, "Already installed"
        if status == "File Missing":
            return False, f"File not found: {target}"
        if status == "Conflict":
            return False, "Conflict: current bytes match neither original nor patched."

        try:
            with open(target, "r+b") as f:
                for hunk in patch_data.get('patches', []):
                    f.seek(hunk['offset'])
                    f.write(bytes.fromhex(hunk['patched']))
            return True, "Patch applied"
        except Exception as e:
            return False, str(e)

    def revert_patch(self, patch_data):
        """Revert a patch (patched bytes → original bytes)."""
        target = self._resolve_target(patch_data)
        if not os.path.exists(target):
            return False, f"File not found: {target}"

        status = self.check_patch_status(patch_data)
        if status == "Missing":
            return True, "Already at original"
        if status == "Conflict":
            return False, "Conflict: current bytes don't match patched state — cannot safely revert."

        try:
            with open(target, "r+b") as f:
                for hunk in patch_data.get('patches', []):
                    f.seek(hunk['offset'])
                    f.write(bytes.fromhex(hunk['original']))
            return True, "Reverted to original"
        except Exception as e:
            return False, str(e)
