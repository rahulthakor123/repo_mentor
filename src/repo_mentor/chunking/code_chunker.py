import ast

from repo_mentor.chunking.base import Chunk, Chunker
from repo_mentor.chunking.simple_chunker import SimpleChunker

MAX_LINES = 60       # a definition longer than this is split into its parts
CLASS_SPLIT_LINES = 30   # a class longer than this is split into its methods
TARGET_LINES = 30    # block merging target for scripts
DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _start_line(node) -> int:
    start = node.lineno
    if node.decorator_list:
        start = min(d.lineno for d in node.decorator_list)
    return start


class CodeChunker(Chunker):
    def __init__(self):
        self.fallback = SimpleChunker()

    # ---------- helpers ----------
    @staticmethod
    def _make(file, lines, start, end, label):
        """start/end are 1-based inclusive line numbers."""
        body = "\n".join(lines[start - 1:end])
        if not body.strip():
            return None
        return Chunk(
            text=f"# File: {file.path} | {label}\n{body}",
            metadata={
                "file_path": file.path,
                "language": file.language,
                "start_line": start,
                "end_line": end,
                "chunk_type": label.split(" ")[0],
            },
        )

    def _split_long(self, file, lines, start, end, label):
        out = []
        for s in range(start, end + 1, MAX_LINES):
            e = min(s + MAX_LINES - 1, end)
            c = self._make(file, lines, s, e, f"{label} (part)")
            if c:
                out.append(c)
        return out

    def _blocks(self, file, lines, start, end, label="script"):
        """Split a region at blank lines, then merge small blocks."""
        blocks, cur = [], None
        for n in range(start, end + 1):
            if lines[n - 1].strip():
                cur = [n, n] if cur is None else [cur[0], n]
            elif cur is not None:
                blocks.append(cur)
                cur = None
        if cur is not None:
            blocks.append(cur)

        merged = []
        for b in blocks:
            if merged and (merged[-1][1] - merged[-1][0] + 1) + (b[1] - b[0] + 1) <= TARGET_LINES:
                merged[-1][1] = b[1]
            else:
                merged.append(b[:])

        out = []
        for s, e in merged:
            if e - s + 1 > MAX_LINES:
                out.extend(self._split_long(file, lines, s, e, label))
            else:
                c = self._make(file, lines, s, e, label)
                if c:
                    out.append(c)
        return out

    def _walk(self, file, lines, nodes, start, end, parent, body_label):
        """Chunk the region [start, end] whose direct definitions are `nodes`."""
        chunks, cursor = [], start
        for node in nodes:
            n_start, n_end = _start_line(node), node.end_lineno

            # code between the previous definition and this one
            if n_start > cursor:
                chunks.extend(self._blocks(file, lines, cursor, n_start - 1, body_label))

            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            name = f"{parent}.{node.name}" if parent else node.name
            label = f"{kind} {name}"
            size = n_end - n_start + 1
            children = [c for c in node.body if isinstance(c, DEF_TYPES)]

            if size > (CLASS_SPLIT_LINES if kind == "class" else MAX_LINES) and children:
                chunks.extend(self._walk(file, lines, children, n_start, n_end,
                                         name, f"{label} (body)"))
            elif size > MAX_LINES:
                chunks.extend(self._split_long(file, lines, n_start, n_end, label))
            else:
                c = self._make(file, lines, n_start, n_end, label)
                if c:
                    chunks.append(c)
            cursor = n_end + 1

        if cursor <= end:
            chunks.extend(self._blocks(file, lines, cursor, end, body_label))
        return chunks

    # ---------- main ----------
    def chunk(self, file):
        if file.language != "python":
            return self.fallback.chunk(file)

        lines = file.text.splitlines()
        try:
            tree = ast.parse(file.text)
        except SyntaxError:
            return self.fallback.chunk(file)

        defs = [n for n in tree.body if isinstance(n, DEF_TYPES)]
        if not defs:
            return self._blocks(file, lines, 1, len(lines))
        return self._walk(file, lines, defs, 1, len(lines), "", "script")