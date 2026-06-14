import os
import sys
import subprocess
import json

# Caminho padrão do executável do Marvelous Designer (personal)
# External tool (not bundled). Default search includes project if user copied, but normally set MD_PATH env.
DEFAULT_MD_PATH = r"D:\\Marvelous Designer Personal\\MarvelousDesigner_Personal.exe"


def _find_md_path(provided=None):
    """Tenta encontrar o MD com suporte a paths longos (\\\\?\\) informados pelo usuário."""
    if provided and os.path.isfile(provided):
        return provided

    env = os.environ.get('MD_PATH') or os.environ.get('MARVELOUS_DESIGNER_PATH') or os.environ.get('MD_EXE')
    if env and os.path.isfile(env):
        return env

    candidates = [
        provided,
        env,
        r"\\?\D:\Marvelous Designer Personal\MarvelousDesigner_Personal.exe",
        r"D:\Marvelous Designer Personal\MarvelousDesigner_Personal.exe",
        r"\\?\D:\Marvelous Designer Personal\MarvelousDesigner.exe",
        r"D:\Marvelous Designer Personal\MarvelousDesigner.exe",
        DEFAULT_MD_PATH,
        r"C:\Program Files\Marvelous Designer\MarvelousDesigner_Personal.exe",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return DEFAULT_MD_PATH


def run_md(project_zpac, out_dir, md_path=None, max_time=None):
    """Rodar a simulação headless do Marvelous Designer.
    Suporta MD_PATH via env ou argumento explícito (inclusive com prefixo \\?\ ).
    """
    md_exe = _find_md_path(md_path)
    if not os.path.isfile(md_exe):
        raise FileNotFoundError(f"Executável MD não encontrado em {md_exe} (configure MD_PATH)")

    # Args típicos (verificar manual do MD para confirmar)
    cmd = [md_exe, "--mode", "Headless", "--project", project_zpac, "--output", out_dir]
    if max_time:
        cmd.extend(["--maxTime", str(max_time)])
    # Aexecução silenciosa, log stdout/stderr
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"MD retornou {result.returncode}: {result.stderr.strip()}")
    # Assumimos que MD exporta OBJ/FBX no out_dir, nome padrão é garment.obj ou garment.fbx
    # verificamos os arquivos exportados
    potential = [
        os.path.join(out_dir, "garment.obj"),
        os.path.join(out_dir, "garment.fbx"),
        os.path.join(out_dir, "garment.glb"),
    ]
    for f in potential:
        if os.path.isfile(f):
            return f
    # Se não houver, retornamos None
    return None

if __name__ == "__main__":
    # Usage: marvelous_bridge.py <project_zpac> <output_dir> [md_path]
    # md_path pode ser passado como 4º argumento ou via env MD_PATH / MARVELOUS_DESIGNER_PATH
    if len(sys.argv) < 3:
        print("Usage: marvelous_bridge.py <project_zpac> <output_dir> [md_path]", file=sys.stderr)
        sys.exit(1)
    proj = sys.argv[1]
    out = sys.argv[2]
    md_path = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3].strip() else None
    try:
        exported = run_md(proj, out, md_path)
        if exported:
            print(json.dumps({"status": "ok", "artifact": exported}))
        else:
            print(json.dumps({"status": "failed", "message": "Nenhum artefato encontrado"}))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
