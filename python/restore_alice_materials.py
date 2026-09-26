"""Restore missing colour on the existing Alice mesh using its supplied turnaround.

This is calibrated orthographic texture projection, NOT image-to-3D inference.
The actual source triangles, skin weights and animations are preserved. UV seams
are split by triangle to avoid interpolating between views across the atlas.
Run: python python/restore_alice_materials.py [--source ... --reference ... --out ...]
Requires numpy and Pillow. Never loads an AI model or substitutes geometry.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data/references/alice"
DTYPES = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(filepath):
    data = Path(filepath).read_bytes()
    magic, version, size = struct.unpack_from("<III", data)
    if magic != 0x46546C67 or version != 2 or size != len(data):
        raise ValueError("Invalid GLB 2.0 container")
    chunks, offset = {}, 12
    while offset < len(data):
        length, kind = struct.unpack_from("<II", data, offset)
        if length % 4 or offset + 8 + length > len(data):
            raise ValueError("Invalid GLB chunk")
        chunks[kind] = data[offset + 8:offset + 8 + length]
        offset += 8 + length
    return json.loads(chunks[0x4E4F534A]), bytearray(chunks[0x004E4942])


def accessor(doc, binary, index):
    info = doc["accessors"][index]
    if "sparse" in info:
        raise ValueError("Sparse accessors require an explicit decoder")
    view = doc["bufferViews"][info["bufferView"]]
    if view.get("buffer", 0) != 0:
        raise ValueError("Only embedded geometry is supported")
    dtype, width = np.dtype(DTYPES[info["componentType"]]), WIDTHS[info["type"]]
    start = view.get("byteOffset", 0) + info.get("byteOffset", 0)
    stride = view.get("byteStride", dtype.itemsize * width)
    return np.ndarray((info["count"], width), dtype, buffer=binary,
                      offset=start, strides=(stride, dtype.itemsize)).copy()


def append_view(doc, binary, data, target=None):
    binary.extend(b"\0" * (-len(binary) % 4))
    offset = len(binary)
    binary.extend(data)
    view = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
    if target:
        view["target"] = target
    doc.setdefault("bufferViews", []).append(view)
    return len(doc["bufferViews"]) - 1


def append_accessor(doc, binary, values, info):
    index = append_view(doc, binary, values.tobytes(), 34962)
    result = {"bufferView": index, "componentType": info["componentType"],
              "type": info["type"], "count": len(values)}
    if info.get("normalized"):
        result["normalized"] = True
    if info["type"] == "VEC3" and info["componentType"] == 5126:
        result["min"] = values.min(axis=0).tolist()
        result["max"] = values.max(axis=0).tolist()
    doc["accessors"].append(result)
    return len(doc["accessors"]) - 1


def project_uv(positions, view_ids, calibration, image_size):
    views = calibration["views"]
    pixels = np.empty((len(positions), 2), dtype=np.float32)
    scale = calibration["pixelsPerMetre"]
    # +Z is front; left profile shows the nose at the left of the image.
    axes = [positions[:, 0], -positions[:, 2], -positions[:, 0]]
    for vid, key in enumerate(("front", "side", "back")):
        selected = view_ids == vid
        pixels[selected, 0] = views[key]["centerPixel"] + axes[vid][selected] * scale
    pixels[:, 1] = calibration["groundPixel"] - (positions[:, 1] - calibration["minY"]) * scale
    pixels[:, 0] /= image_size[0]
    # glTF texture coordinates start at the top of the image.
    pixels[:, 1] /= image_size[1]
    return pixels.clip(0, 1).astype("<f4")


def restore(source, reference, profile, output):
    doc, binary = read_glb(source)
    with Image.open(reference) as image:
        image_size = image.size
        encoded = io.BytesIO()
        image.convert("RGB").save(encoded, format="JPEG", quality=95, subsampling=0)
    image_view = append_view(doc, binary, encoded.getvalue())
    doc.setdefault("images", []).append({"name": "Alice supplied turnaround",
                                        "mimeType": "image/jpeg", "bufferView": image_view})
    doc.setdefault("samplers", []).append({"magFilter": 9729, "minFilter": 9987,
                                           "wrapS": 33071, "wrapT": 33071})
    doc.setdefault("textures", []).append({"sampler": len(doc["samplers"]) - 1,
                                           "source": len(doc["images"]) - 1})
    doc.setdefault("materials", []).append({
        "name": "Alice · calibrated turnaround projection",
        "doubleSided": True,
        "pbrMetallicRoughness": {"baseColorTexture": {"index": len(doc["textures"]) - 1},
                                "metallicFactor": 0, "roughnessFactor": 0.68},
        "extras": {"method": "orthographic multi-view colour projection",
                   "albedoCaptured": False, "physicalLayersVerified": False}
    })
    counts = {"front": 0, "side": 0, "back": 0}
    excluded = []
    # The upstream file also contains a separate T-pose body template. It
    # protrudes through the dressed character and is not part of the reference.
    # Keep its data for traceability, but remove its scene attachment.
    for node in doc.get("nodes", []):
        if node.get("name") == "Corpo" and "mesh" in node:
            excluded.append(node["name"])
            node.pop("mesh")
            node.pop("skin", None)
    for mesh in doc["meshes"]:
        # The underlying body already has a texture and must keep its UV map.
        for primitive in mesh["primitives"]:
            old_material = doc["materials"][primitive.get("material", 0)]
            if old_material.get("pbrMetallicRoughness", {}).get("baseColorTexture"):
                continue
            if primitive.get("mode", 4) != 4 or primitive.get("targets"):
                raise ValueError("Projection currently supports triangle meshes without morph targets")
            attrs = primitive["attributes"]
            positions = accessor(doc, binary, attrs["POSITION"])
            indices = (accessor(doc, binary, primitive["indices"]).reshape(-1)
                       if "indices" in primitive else np.arange(len(positions)))
            triangles = indices.reshape(-1, 3)
            corners = positions[triangles]
            face_normal = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
            if "NORMAL" in attrs:
                normals = accessor(doc, binary, attrs["NORMAL"])[triangles].mean(axis=1)
                face_normal = np.where(np.linalg.norm(face_normal, axis=1)[:, None] > 1e-12,
                                       face_normal, normals)
            # A single observed profile is used on both sides; mirrored regions
            # are explicitly recorded as inferred rather than observed.
            # Use the smooth torso/skirt envelope, rather than micro triangle
            # normals: embroidery and lace normals otherwise switch view on
            # every facet and produce a patchwork of unrelated photo regions.
            centroid = corners.mean(axis=1)
            side_region = np.abs(centroid[:, 0]) > np.abs(centroid[:, 2]) * 2.4
            choice = np.where(side_region, 1, np.where(centroid[:, 2] >= 0, 0, 2))
            for vid, key in enumerate(counts):
                counts[key] += int((choice == vid).sum())
            expanded = indices.astype(np.int64)
            for attribute, aid in list(attrs.items()):
                values = accessor(doc, binary, aid)[expanded]
                attrs[attribute] = append_accessor(doc, binary, values, doc["accessors"][aid])
            uv = project_uv(positions[expanded], np.repeat(choice, 3), profile["calibration"], image_size)
            attrs["TEXCOORD_0"] = append_accessor(doc, binary, uv, {"componentType": 5126, "type": "VEC2"})
            # Tangents refer to the old UV map; GLTFLoader must recompute the basis.
            attrs.pop("TANGENT", None)
            primitive.pop("indices", None)
            primitive["material"] = len(doc["materials"]) - 1
    if not sum(counts.values()):
        raise ValueError("No untextured triangles found; refusing to overwrite an existing colour map")
    doc["buffers"] = [{"byteLength": len(binary)}]
    report = {
        "method": "calibrated_turnaround_projection",
        "sourceSha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        "referenceSha256": hashlib.sha256(Path(reference).read_bytes()).hexdigest(),
        "trianglesByProjection": counts,
        "geometryOrigin": profile["source"],
        "geometryReconstructed": False,
        "excludedSceneTemplates": excluded,
        "rightProfile": "inferred_from_left_profile",
        "fidelityStatus": "unverified",
        "limitations": profile["limitations"]
    }
    doc.setdefault("extras", {})["aliceRestoration"] = report
    json_data = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    json_data += b" " * (-len(json_data) % 4)
    binary.extend(b"\0" * (-len(binary) % 4))
    result = (struct.pack("<III", 0x46546C67, 2, 28 + len(json_data) + len(binary)) +
              struct.pack("<II", len(json_data), 0x4E4F534A) + json_data +
              struct.pack("<II", len(binary), 0x004E4942) + binary)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_bytes(result)
    report["outputSha256"] = hashlib.sha256(result).hexdigest()
    Path(output).with_suffix(".report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(REFERENCE / "alice-source.glb"))
    parser.add_argument("--reference", default=str(REFERENCE / "turnaround.jpg"))
    parser.add_argument("--profile", default=str(REFERENCE / "profile.json"))
    parser.add_argument("--out", default=str(ROOT / "data/assets/alice-restored.glb"))
    args = parser.parse_args()
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    print(json.dumps(restore(args.source, args.reference, profile, args.out), ensure_ascii=False, indent=2))
