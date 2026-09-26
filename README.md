# Scanner 3D · Project Alice

A construção por camadas está em **http://localhost:3939/alice/layers**. O repositório inclui o **GLB novo completo do Chapeleiro**, gerado uma vez no Tripo AI Studio com três vistas da referência, 1.890.825 triângulos e texturas 4K. Está disponível como conjunto separado das fichas, ainda em refinamento e sem rig. O estudo anterior do corsete da ficha 2 foi rejeitado por fidelidade insuficiente.

Para inspecionar as 66 etapas locais das seis versões, configure `ALICE_STAGE_ROOT=F:/Alice/Deliverables/Alice_Variants`. Cada etapa usa sua própria foto. Conforme a instrução atual, preservar a Alice Base com vestido já aprovada e refinar localmente cada novo GLB completo das demais versões. Finalizar todas as camadas e o rig do Chapeleiro antes da próxima geração; não usar recursos premium do Tripo. Consulte [construção, rig e comparações por etapa](docs/ALICE_VARIANTS.md).

Estúdio para inspecionar uma personagem **em geometria 3D real**, comparar frente/perfil/costas com o turnaround e exportar assets com evidência. O resultado é identificado pela sua origem; um asset importado não é apresentado como uma reconstrução gerada pela IA.

## Executar

```sh
npm ci
npm start
```

Node 20 ou posterior. Abra **http://localhost:3939/alice**. O Three.js é servido localmente, sem CDN.

O estúdio abre a Alice detalhada existente no repositório do jogo: **249.975 triângulos, atlas UV de 2048 px, malha estática**. O importador seleciona apenas o LOD3 do FBX, evita cinco cópias sobrepostas e liga a textura original à cor do material. Não tem rig nem simulação de tecido. A versão GLB anterior, com rig de 33 juntas, está disponível para comparação; sua textura ausente pode ser restaurada por projeção multivista, com as limitações registradas no relatório.

Use órbita, aproximação, vistas fixas, perspectiva, argila, topologia, cor sem iluminação e foco em rosto/roupa/botas para examinar o volume. O painel mantém a referência original ao lado. **Registrar frente, perfil e costas** salva renders PNG e um relatório com hashes da malha e referência. Registrar evidência deixa a revisão visual pendente; não declara fidelidade total.

## Reproduzir a importação do FBX original

```sh
npm run alice:fetch
blender --background --factory-startup --python-exit-code 1 --python blender/import_alice_fbx.py -- --source data/source/alice.fbx --out data/assets/alice-detail.glb
```

O download usa um commit fixo do [Project Alice — Game](https://github.com/programador-powershell/project-alice-game) e verifica SHA-256. O FBX de 152 MB não é duplicado neste repositório. A geometria e a textura pertencem ao projeto de **Programador de Powershell · Project Alice — Challenge**. A referência é o turnaround fornecido pelo usuário.

Alternativa para experimentar projeção de cor na malha GLB anterior:

```sh
python -m pip install numpy Pillow
python python/restore_alice_materials.py
```

Isso preserva triângulos, skinning e animação existentes, retira da cena o corpo-template em pose T e cria UVs por vista. Não gera uma personagem nova, nem prova camadas físicas independentes. A projeção usa o perfil observado também no lado oposto e contém iluminação da imagem.

## Exportar pelo Blender

Configure `BLENDER_PATH` com o executável do Blender. Em Windows/PowerShell:

```powershell
$env:BLENDER_PATH = 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
$env:AUTO_KNOWLEDGE = '0'
npm start
```

Na API de jobs, importe um GLB real em `POST /api/jobs/:id/source-mesh` (multipart `model`). O upload do turnaround byte a byte idêntico à referência Alice seleciona a base detalhada do projeto, identificada como importação.

`POST /api/jobs/:id/build` exporta **GLB, FBX, .blend e três renders** da malha real. Os oito portões selecionam o foco de revisão; não fabricam ossos, músculos, tecido ou cabelo ausentes. Um portão de esqueleto sem rig falha explicitamente. A altura só é alterada quando houver `params.target_height_m` explícito.

Cada execução usa uma pasta nova. Erro de processo, falta de arquivo ou malha inválida falham; um GLB antigo não é aceito como saída da execução atual. A conclusão da exportação é distinta da aprovação de fidelidade.

## Reconstrução e avaliação visual

Para um serviço multivista real, configure `ALICE_RECONSTRUCTION_URL`. O contrato é **POST multipart `front`, `side`, `back` (PNG), `profile` (JSON) → resposta binária GLB 2.0**, até 100 MB. O botão envia recortes separados, evitando tratar o turnaround como três personagens. Esta é uma API de adaptação explícita, não uma promessa de compatibilidade automática com Hunyuan3D ou TrackEverything. Sem serviço, não há reconstrução por IA nem fallback de primitivas.

O avaliador usa `VLM_URL` (chat completions multimodal) e opcionalmente `VLM_MODEL`. Referência e render real são obrigatórios. Modelo ausente, JSON inválido e falta de evidência retornam `verified:false`, `pass:false`, `score:null`. Avaliações visuais válidas têm escopo de comparação de imagens; não comprovam física, topologia interna ou fidelidade integral. Uma reprovação pede edição/reconstrução da malha, em vez de repetir o mesmo build indefinidamente. Ingestão automática de conhecimento exige `AUTO_KNOWLEDGE=1`; não é treinamento automático garantido.

## Verificação e limites

```sh
npm test
```

Os testes cobrem os assets reais, rejeição de GLBs truncados/planos, coordenadas inválidas, falta de serviço visual, evidências desatualizadas e comportamento da API.

Esta alteração **não entrega o jogo completo em Unreal Engine 5.7**, nem uma Alice comprovadamente 100% fiel. Persistem diferenças de cabelo, rosto e acabamentos; a malha detalhada combina corpo/roupa. Rig de produção, roupa em camadas com colisão, materiais PBR completos, gameplay e validação na UE 5.7 exigem trabalho adicional. Veja [evidências e referência TrackEverything](docs/ALICE_FIDELITY.md).
