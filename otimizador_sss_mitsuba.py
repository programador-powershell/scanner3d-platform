import os
import torch
import torch.nn.functional as F
import mitsuba as mi
import drjit as dr
from lpips import LPIPS
from torchvision.utils import save_image

# ==========================================
# 1. INICIALIZAÇÃO E VARIANTE
# Força o Mitsuba a rodar na GPU com Diferenciação Automática
# ==========================================
mi.set_variant('cuda_ad_rgb')

# ==========================================
# 2. PONTES DE MEMÓRIA (ZERO-COPY)
# ==========================================
def converter_render_para_pytorch(render_drjit):
    """Converte o render (Dr.Jit) para PyTorch (B, C, H, W) preservando o grafo de gradientes."""
    render_torch = dr.ext.pytorch.to_pytorch(render_drjit)
    render_torch = render_torch.permute(2, 0, 1).unsqueeze(0)
    return render_torch.to(torch.float32)

def injetar_textura_no_mitsuba(textura_torch, parametros_mitsuba, chave_param):
    """(Opcional) Injeta um tensor PyTorch de volta no Mitsuba."""
    tex_formatada = textura_torch.squeeze(0).permute(1, 2, 0).contiguous()
    tex_drjit = dr.ext.pytorch.from_pytorch(tex_formatada)
    parametros_mitsuba[chave_param] = tex_drjit
    parametros_mitsuba.update()

def extrair_e_salvar_textura(parametros_mitsuba, chave_param, caminho_salvar):
    """Extrai a textura otimizada do Dr.Jit e salva no disco."""
    tex_drjit = parametros_mitsuba[chave_param]
    # Avalia o grafo computacional para obter os valores finais
    dr.eval(tex_drjit)
    tex_torch = dr.ext.pytorch.to_pytorch(tex_drjit)
    tex_torch = tex_torch.permute(2, 0, 1) # (C, H, W)
    # Garante que os valores estão entre 0 e 1 antes de salvar
    tex_torch = torch.clamp(tex_torch, 0.0, 1.0)
    save_image(tex_torch, caminho_salvar)
    print(f"✅ Textura salva: {caminho_salvar}")

# ==========================================
# 3. GERADOR DE CENA XML
# ==========================================
def gerar_cena_mitsuba(caminho_xml, caminho_malha_obj, textura_base_albedo, textura_base_roughness, resolucao=2048):
    xml_content = f"""<scene version="3.0.0">
    <integrator type="prb_volpath">
        <integer name="max_depth" value="4"/>
    </integrator>

    <sensor type="perspective">
        <float name="fov" value="45.0"/> 
        <transform name="to_world">
            <lookat origin="0, 0, 2" target="0, 0, 0" up="0, 1, 0"/>
        </transform>
        <sampler type="independent">
            <integer name="sample_count" value="16"/> 
        </sampler>
        <film type="hdrfilm">
            <integer name="width" value="{resolucao}"/>
            <integer name="height" value="{resolucao}"/>
            <string name="pixel_format" value="rgb"/>
            <boolean name="banner" value="false"/>
        </film>
    </sensor>

    <emitter type="envmap" id="luz_ambiente">
        <string name="filename" value="texturas/estudio_hdri.exr"/> 
        <float name="scale" value="1.5"/>
    </emitter>

    <shape type="obj" id="malha_personagem">
        <string name="filename" value="{caminho_malha_obj}"/>
        <bsdf type="principled" id="material_pele">
            <texture type="bitmap" name="base_color" id="pele_albedo">
                <string name="filename" value="{textura_base_albedo}"/>
                <boolean name="raw" value="true"/>
            </texture>
            
            <texture type="bitmap" name="roughness" id="pele_roughness">
                <string name="filename" value="{textura_base_roughness}"/>
                <boolean name="raw" value="true"/>
            </texture>
            
            <float name="subsurface" value="0.8"/>
            <rgb name="subsurface_color" value="0.8, 0.3, 0.2"/>
            <float name="subsurface_radius" value="0.05" id="pele_sss_radius"/> 
            
            <float name="specular" value="0.4"/>
            <float name="clearcoat" value="0.1"/>
        </bsdf>
    </shape>
</scene>"""

    with open(caminho_xml, 'w') as f:
        f.write(xml_content)
    return caminho_xml

# ==========================================
# 4. CLASSE DO OTIMIZADOR (AAA LOOP)
# ==========================================
class MitsubaSkinOptimizer:
    def __init__(self, scene_file, foto_original_tensor):
        self.scene = mi.load_file(scene_file)
        self.foto_original = foto_original_tensor.cuda()
        
        # Métrica de similaridade perceptiva
        self.lpips_metric = LPIPS(net='vgg').cuda()
        self.params = mi.traverse(self.scene)
        
        # Otimizador ADAM nativo do Dr.Jit
        self.opt = mi.ad.Adam(lr=0.01)
        
        # Expõe os parâmetros que queremos que a IA esculpa
        self.opt['pele_albedo.data'] = self.params['pele_albedo.data']
        self.opt['pele_sss_radius.data'] = self.params['pele_sss_radius.data']

    def passo_de_otimizacao(self, iteracao):
        # 1. Trava/Clamp para conservação de energia (não deixa a pele brilhar > 1.0)
        self.opt['pele_albedo.data'] = dr.clamp(self.opt['pele_albedo.data'], 0.01, 0.99)
        self.opt['pele_sss_radius.data'] = dr.clamp(self.opt['pele_sss_radius.data'], 0.001, 0.2)
        
        # 2. Atualiza a cena
        self.opt.update()
        
        # 3. Renderiza (A semente muda a cada iteração para o ruído do path tracer anular-se)
        render_atual = mi.render(self.scene, params=self.params, spp=16, seed=iteracao)
        
        # 4. Atravessa a ponte para o PyTorch
        render_torch = converter_render_para_pytorch(render_atual)
        
        # 5. Cálculo das Perdas
        loss_pixel = F.l1_loss(render_torch, self.foto_original)
        loss_perceptual = self.lpips_metric(render_torch, self.foto_original).mean()
        
        loss_total = loss_pixel + (0.8 * loss_perceptual)
        
        # 6. Retropropagação Diferenciável (Zero-Copy)
        dr.backward(loss_total)
        self.opt.step()
        
        return loss_total.item(), render_torch

# ==========================================
# 5. EXECUÇÃO PRINCIPAL (Para o seu server.js chamar via spawn)
# ==========================================
def run_pipeline_mitsuba(job_id, obj_path, foto_ref_path, albedo_inicial_path, roughness_inicial_path):
    print(f"[{job_id}] Iniciando Refino de Pele SSS AAA...")
    
    # 1. Carrega a foto original no PyTorch
    from torchvision.io import read_image
    foto_original = read_image(foto_ref_path).float() / 255.0
    foto_original = foto_original.unsqueeze(0) # (1, C, H, W)
    
    # 2. Gera XML da cena
    xml_path = f"jobs/{job_id}/cena_mitsuba.xml"
    gerar_cena_mitsuba(xml_path, obj_path, albedo_inicial_path, roughness_inicial_path)
    
    # 3. Inicializa o Otimizador
    otimizador = MitsubaSkinOptimizer(xml_path, foto_original)
    
    # 4. Loop de Treino (ex: 50 a 100 iterações são suficientes devido ao Adam)
    epocas = 80
    for i in range(epocas):
        loss, _ = otimizador.passo_de_otimizacao(iteracao=i)
        if i % 10 == 0:
            print(f"[{job_id}] Iteração {i:03d}/{epocas} | Loss Total: {loss:.4f}")
            
    print(f"[{job_id}] Otimização concluída. Exportando texturas PBR/SSS refinadas...")
    
    # 5. Extrai e Salva os mapas finais
    caminho_saida = f"jobs/{job_id}/"
    extrair_e_salvar_textura(otimizador.params, 'pele_albedo.data', os.path.join(caminho_saida, 'albedo_aaa_final.png'))
    # Pode salvar o valor final do SSS Radius num JSON para usar no material da Unreal Engine
    
    print("✅ Pipeline Mitsuba finalizado com sucesso!")

# Ponto de entrada se o script for executado diretamente
if __name__ == "__main__":
    # Exemplo de mocks para teste
    # run_pipeline_mitsuba("job_123", "malha.obj", "referencia.png", "albedo_base.exr", "roughness.exr")
    pass