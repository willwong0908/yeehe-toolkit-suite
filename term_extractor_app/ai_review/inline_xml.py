"""Preserve mixed text and inline codes when reading localization XML."""
from __future__ import annotations

from copy import deepcopy
from xml.etree import ElementTree as ET


XLIFF_NAMESPACES = {
    "urn:oasis:names:tc:xliff:document:1.2",
    "urn:oasis:names:tc:xliff:document:2.0",
}


def inner_xml(element: ET.Element | None, *, xliff: bool = False) -> str:
    """Return readable content with its inline markup, without modifying the tree.

    XLIFF annotations describe segmentation/metadata rather than native codes.
    Their content is retained without presenting annotation wrappers as tags
    that the translation must reproduce. Native inline codes remain intact.
    """
    if element is None:
        return ""
    content = deepcopy(element)
    if xliff:
        _prepare_xliff(content)
    return ((content.text or "") + "".join(
        ET.tostring(child, encoding="unicode") for child in content
    )).strip()


def _prepare_xliff(parent: ET.Element) -> None:
    for child in list(parent):
        if child.tag.startswith("{"):
            namespace, _, local_name = child.tag[1:].partition("}")
        else:
            namespace, local_name = "", child.tag
        core = not namespace or namespace in XLIFF_NAMESPACES
        _prepare_xliff(child)
        if core:
            child.tag = local_name
        if core and local_name in {"mrk", "mkr", "sm", "em"}:
            # Promote annotation content in place, keeping both text and tails.
            index = list(parent).index(child)
            prefix = child.text or ""
            if index:
                previous = parent[index - 1]
                previous.tail = (previous.tail or "") + prefix
            else:
                parent.text = (parent.text or "") + prefix
            nested = list(child)
            parent.remove(child)
            for offset, node in enumerate(nested):
                parent.insert(index + offset, node)
            if nested:
                nested[-1].tail = (nested[-1].tail or "") + (child.tail or "")
            elif index:
                previous = parent[index - 1]
                previous.tail = (previous.tail or "") + (child.tail or "")
            else:
                parent.text = (parent.text or "") + (child.tail or "")
