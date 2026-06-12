"""
Ingestor de conhecimento unificado — TUDO vira aprendizado da VLM:

  1. D:\\References\\img\\**       -> referências visuais aprovadas (padrão AAA do projeto)
  2. D:\\References\\3D\\*.jpg     -> previews dos modelos 3D de produção
  3. D:\\References\\3D\\*_tex\\** -> classificação de mapas PBR (base/mr/normal)
  4. data/links.json (github)      -> README dos repositórios registrados (MPFB2,
                                      MakeHuman, QRemeshify, AutoRemesher, KIRI 3DGS)
                                      vira conhecimento de COMO construir corretamente
  5. data/finetune_dataset.jsonl   -> decisões aprovar/reprovar dos 9 portões (DPO)

Saída única: training/dataset.json (consumido por train_vlm_unsloth.py).
Imagens são copiadas/reduzidas para training/cache_imgs/ (max 640px) para caber
no orçamento de tokens de visão da RTX 4060 (max_seq 512).

Uso:
  python training/ingest_knowledge.py
"""
import hashlib
import json
import os
import re
import sys
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REFERENCES = os.environ.get("REFERENCES_DIR", "D:\\References")
LINKS = os.path.join(ROOT, "data", "links.json")
CACHE = os.path.join(HERE, "cache_imgs")
OUT = os.path.join(HERE, "dataset.json")
MAX_SIDE = 640

os.makedirs(CACHE, exist_ok=True)

# importa o conversor das decisões do pipeline (fonte 5)
sys.path.insert(0, HERE)
from prepare_dataset import DATASET_IN, to_example  # noqa: E402

VERDICT_OK = json.dumps(
    {"pass": True, "score": 0.95, "defects": [], "suggested_prompt_fix": ""},
    ensure_ascii=False,
)


def cache_image(path: str) -> str | None:
    """Reduz a imagem para MAX_SIDE e devolve o caminho do cache (None se ilegível)."""
    try:
        key = hashlib.sha1(path.encode("utf-8")).hexdigest()[:16] + ".jpg"
        dst = os.path.join(CACHE, key)
        if os.path.exists(dst):
            return dst
        img = Image.open(path).convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        img.save(dst, "JPEG", quality=88)
        return dst
    except Exception:
        return None


def label_from_path(path: str) -> str:
    """Deriva uma legenda do caminho: pasta + nome viram descrição."""
    rel = os.path.relpath(path, REFERENCES)
    parts = [p for p in re.split(r"[\\/]", rel)[:-1] if p not in ("img", "3D")]
    name = os.path.splitext(os.path.basename(path))[0]
    name = re.sub(r"ChatGPT Image .*?(\(\d+\))?$", "variação de concept", name).strip()
    ctx = " / ".join(parts) if parts else "referência"
    return f"{ctx}: {name}".replace("_", " ").replace("-", " ")


def ex_reference(img: str, label: str) -> list[dict]:
    """Referência de produção = exemplo positivo + exemplo de descrição."""
    out = []
    out.append({"messages": [
        {"role": "user", "content": [
            {"type": "image", "image": img},
            {"type": "text", "text": "Esta imagem é uma referência de produção aprovada do projeto. "
             "Ela representa o padrão de qualidade AAA alvo (humano realista, não cartoon)? "
             "Responda APENAS JSON: {\"pass\": bool, \"score\": 0-1, \"defects\": [...], \"suggested_prompt_fix\": \"...\"}"},
        ]},
        {"role": "assistant", "content": [{"type": "text", "text": VERDICT_OK}]},
    ]})
    out.append({"messages": [
        {"role": "user", "content": [
            {"type": "image", "image": img},
            {"type": "text", "text": "Identifique esta referência do projeto (categoria e elemento)."},
        ]},
        {"role": "assistant", "content": [{"type": "text", "text": f"Referência de produção do projeto — {label}."}]},
    ]})
    return out


PBR_KIND = [
    (re.compile(r"_base|base_color|albedo|diffuse", re.I), "base_color"),
    (re.compile(r"_mr|metallic|roughness", re.I), "metallic_roughness"),
    (re.compile(r"_normal|normal", re.I), "normal"),
]


def ex_pbr(img: str, fname: str) -> dict | None:
    kind = next((k for rx, k in PBR_KIND if rx.search(fname)), None)
    if not kind:
        return None
    return {"messages": [
        {"role": "user", "content": [
            {"type": "image", "image": img},
            {"type": "text", "text": "Que tipo de mapa PBR é este? Responda APENAS JSON: "
             "{\"map_type\": \"base_color|metallic_roughness|normal\"}"},
        ]},
        {"role": "assistant", "content": [{"type": "text", "text": json.dumps({"map_type": kind})}]},
    ]}


def fetch_readme(repo_url: str) -> str | None:
    m = re.match(r"https?://github\.com/([\w.-]+)/([\w.-]+)", repo_url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    for branch in ("HEAD", "main", "master"):
        for name in ("README.md", "readme.md", "README.rst"):
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{name}"
            try:
                with urllib.request.urlopen(url, timeout=15) as r:
                    if r.status == 200:
                        return r.read().decode("utf-8", errors="replace")
            except Exception:
                continue
    return None


def clean_md(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)        # imagens
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)     # links -> texto
    text = re.sub(r"<[^>]+>", "", text)                       # html
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ex_repo_knowledge(name: str, note: str, readme: str) -> list[dict]:
    """README do repositório vira pares de conhecimento (domain adaptation)."""
    text = clean_md(readme)
    chunks, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) > 1400 and cur:
            chunks.append(cur.strip())
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        chunks.append(cur.strip())
    chunks = chunks[:8]  # limita por repo
    out = []
    for i, ch in enumerate(chunks, 1):
        out.append({"messages": [
            {"role": "user", "content": [{"type": "text", "text":
                f"Com base na documentação oficial da ferramenta {name} "
                f"({note or 'ferramenta do pipeline 2D→3D'}), explique como ela funciona "
                f"e como usá-la corretamente no pipeline (parte {i}/{len(chunks)})."}]},
            {"role": "assistant", "content": [{"type": "text", "text": ch}]},
        ]})
    return out


def main():
    examples = []
    counts = {}

    # ---- 1+2: referências visuais (img/** e 3D/*.jpg) ----
    img_dirs = [os.path.join(REFERENCES, "img"), os.path.join(REFERENCES, "3D")]
    n_ref = 0
    for base in img_dirs:
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, files in os.walk(base):
            if re.search(r"_tex$|\.fbm$", dirpath):
                continue  # texturas tratadas na fonte 3
            for f in files:
                if not f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    continue
                full = os.path.join(dirpath, f)
                img = cache_image(full)
                if img:
                    examples.extend(ex_reference(img, label_from_path(full)))
                    n_ref += 1
    counts["referencias_visuais"] = n_ref

    # ---- 3: texturas PBR ----
    n_pbr = 0
    base3d = os.path.join(REFERENCES, "3D")
    if os.path.isdir(base3d):
        for dirpath, _dirs, files in os.walk(base3d):
            if not re.search(r"_tex$|\.fbm$", dirpath):
                continue
            for f in files:
                if not f.lower().endswith(".png"):
                    continue
                img = cache_image(os.path.join(dirpath, f))
                if not img:
                    continue
                ex = ex_pbr(img, f)
                if ex:
                    examples.append(ex)
                    n_pbr += 1
    counts["texturas_pbr"] = n_pbr

    # ---- 4: repositórios GitHub registrados ----
    n_repo = 0
    try:
        links = json.load(open(LINKS, encoding="utf-8"))
    except Exception:
        links = {}
    for l in links.get("github", []):
        name = l["url"].rstrip("/").split("/")[-1]
        readme = fetch_readme(l["url"])
        if readme:
            ex = ex_repo_knowledge(name, l.get("note", ""), readme)
            examples.extend(ex)
            n_repo += len(ex)
            print(f"  repo {name}: {len(ex)} chunks")
        else:
            print(f"  repo {name}: README inacessível (pulado)")
    counts["conhecimento_repos"] = n_repo

    # ---- 5: decisões dos 9 portões (com imagens re-cacheadas) ----
    n_dec = 0
    if os.path.exists(DATASET_IN):
        with open(DATASET_IN, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ex = to_example(rec)
                if not ex:
                    continue
                # reduz as imagens da decisão para o cache também
                for c in ex["messages"][0]["content"]:
                    if c.get("type") == "image":
                        cached = cache_image(c["image"])
                        if cached:
                            c["image"] = cached
                examples.append(ex)
                n_dec += 1
    counts["decisoes_portoes"] = n_dec

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False)
    print(json.dumps(counts, indent=2, ensure_ascii=False))
    print(f"TOTAL: {len(examples)} exemplos -> {OUT}")


if __name__ == "__main__":
    main()
