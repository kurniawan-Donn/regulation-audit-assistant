"""
Structure Tree Builder.

Membangun tree hierarkis dari flat list chunk untuk keperluan UI filter.
Tree digunakan oleh frontend untuk menampilkan modal "Pilih Bagian".

Hierarki yang didukung (urutan prioritas):
    lampiran > bab > bagian > pasal > ayat / butir

Chunk tanpa lampiran dibungkus dalam node sintetis "Batang Tubuh / Preambule".
Node ID bersifat STABIL per tree (path-based) dan dipakai sebagai referensi
di payload frontend, tapi frontend cukup mengirim chunk_indices saja.
"""

from typing import Any

# Urutan level dari luar ke dalam. Setiap tuple = (key_field, nama_tipe).
_HIERARCHY: list[tuple[str, str]] = [
    ("lampiran", "lampiran"),
    ("bab", "bab"),
    ("bagian", "bagian"),
    ("pasal", "pasal"),
    ("ayat", "ayat"),
    ("butir", "butir"),
]


def _empty_node(label: str, node_type: str) -> dict:
    return {
        "label": label,
        "type": node_type,
        "page_start": None,
        "page_end": None,
        "chunk_indices": [],
        "children": {},  # dict dulu, di-convert ke list di akhir
    }


def _update_pages(node: dict, chunk: dict) -> None:
    ps = chunk.get("page_start")
    pe = chunk.get("page_end")
    if ps is not None:
        if node["page_start"] is None or ps < node["page_start"]:
            node["page_start"] = ps
    if pe is not None:
        if node["page_end"] is None or pe > node["page_end"]:
            node["page_end"] = pe


def build_tree(chunks: list[dict]) -> list[dict]:
    """
    Bangun tree dari flat chunks. Return list of root nodes.

    Setiap node memiliki:
    - label: teks yang ditampilkan
    - type: salah satu dari "lampiran" | "bab" | "bagian" | "pasal" | "ayat" | "butir" | "root"
    - page_start, page_end: rentang halaman di PDF (None kalau tidak ada info)
    - chunk_indices: daftar index chunk (di list `chunks`) yang termasuk node ini
                     ATAU descendant-nya (sudah diagregat)
    - children: list of node (rekursif)
    """
    root: dict[str, dict] = {}

    for idx, chunk in enumerate(chunks):
        # Tentukan level yang ada di chunk ini
        levels: list[tuple[str, str]] = []

        # Level 0: lampiran atau batang tubuh
        if chunk.get("lampiran"):
            levels.append(("lampiran", chunk["lampiran"]))
        else:
            levels.append(("root", "Batang Tubuh / Preambule"))

        # Level 1+: hanya yang ada
        for field, node_type in _HIERARCHY[1:]:  # skip lampiran karena sudah
            value = chunk.get(field)
            if value:
                levels.append((node_type, value))

        # Sisipkan ke nested dict
        current = root
        deepest_node: dict | None = None
        for node_type, label in levels:
            key = f"{node_type}:{label}"
            if key not in current:
                current[key] = _empty_node(label, node_type)
            node = current[key]
            _update_pages(node, chunk)
            deepest_node = node
            current = node["children"]

        if deepest_node is not None:
            deepest_node["chunk_indices"].append(idx)

    return _finalize(root)


def _finalize(nodes_dict: dict[str, dict]) -> list[dict]:
    """Konversi dict-of-children → list, agregat chunk_indices, dan assign ID."""
    result = []
    for key, node in nodes_dict.items():
        children = _finalize(node["children"])

        # Agregat: chunk indices milik sendiri + semua descendant
        all_indices = set(node["chunk_indices"])
        for child in children:
            all_indices.update(child["chunk_indices"])

        # Update page range dari children (kalau parent belum tahu range luasnya)
        for child in children:
            if child.get("page_start") is not None:
                if node["page_start"] is None or child["page_start"] < node["page_start"]:
                    node["page_start"] = child["page_start"]
            if child.get("page_end") is not None:
                if node["page_end"] is None or child["page_end"] > node["page_end"]:
                    node["page_end"] = child["page_end"]

        result.append({
            "label": node["label"],
            "type": node["type"],
            "page_start": node["page_start"],
            "page_end": node["page_end"],
            "chunk_indices": sorted(all_indices),
            "children": children,
        })
    return result


def assign_node_ids(tree: list[dict], parent_id: str = "") -> None:
    """
    Assign ID ke setiap node secara in-place. ID bersifat path-based:
    "n0", "n0_1", "n0_1_0", dst. Stabil selama struktur tidak berubah.
    """
    for i, node in enumerate(tree):
        node_id = f"{parent_id}_{i}" if parent_id else f"n{i}"
        node["id"] = node_id
        assign_node_ids(node.get("children", []), node_id)


def count_nodes(tree: list[dict]) -> int:
    """Hitung total node (rekursif). Berguna untuk logging/debug."""
    total = 0
    for node in tree:
        total += 1 + count_nodes(node.get("children", []))
    return total