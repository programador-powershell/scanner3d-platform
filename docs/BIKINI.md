# BIKINI no 3D Game Studio

Integração opcional de um executável externo. **BIKINI é um fork não oficial do Blender 5.3 Alpha, distribuído para Windows x64; não é um modelo de reconstrução 2D→3D, um plugin da Unreal ou um serviço cloud.** O Blender normal continua sendo o backend padrão.

## Origem fixada

- Distribuição/documentação: https://github.com/blueish0930/BIKINI
- Revisão inspecionada: `b007d4e4f2cdb80074852900d9ed8429d228b65d`.
- Código-fonte indicado pelo autor: https://projects.blender.org/blueish/BIKINI
- Manual: https://blueish0930.github.io/BIKINI/manual.html
- Contrato local: `config/bikini.lock.json`.

O SHA-256 do executável vem do ponteiro Git LFS dessa revisão: `aeb517ef7d2643024c19e9ddf1b749487c534ed4b890218eed4f35753d71c20d`, 133306880 bytes. O `BIKINI_BUILD_INFO.txt` upstream contém uma data/commit de empacotamento anterior; **não o usamos como prova da versão executada**. O probe registra `bpy.app.version`, `version_string` e `build_hash` reais.

## O que foi conectado

1. `BLENDER_BACKEND=bikini`: usa o BIKINI nos builds existentes de `lib/build_runner.js`, sem regenerar a Alice Base ou trocar automaticamente o rig.
2. `bikini:check`: valida consentimento, Windows x64, pacote completo, ausência de ponteiros LFS e hash do executável. Não executa o Blender.
3. `bikini:probe`: inicia o executável fixado, descobre IDs/sockets de nós via RNA, exporta GLB/FBX/BLEND de uma calibração e reimporta o GLB para conferir dimensões. Instanciar um nó não testa seu solver.
4. `bikini:bake`: avalia Geometry Nodes de **uma collection existente** de malhas estáticas e exporta um candidato em pasta nova.
5. `/alice/bikini` e `/api/integrations/bikini`: painel e diagnóstico somente leitura. Nenhum GET inicia processos ou gastos.
6. Cada build registra o backend, hashes, revisão, origem e saída em `engine_provenance.json`. O resultado continua aguardando revisão.

Nada é baixado no boot. Não há DLL, executável, modelo de IA ou asset externo embutido nesta integração.

## Preparar a máquina Windows de produção

Revise a origem antes de executar: o upstream declara que o pacote não tem assinatura oficial da Blender Foundation. Use uma conta/VM de trabalho sem credenciais administrativas, com cópias dos assets e backups independentes.

Obtenha a distribuição completa da revisão fixada. Uma clonagem exige **Git LFS**; um ZIP que contenha apenas ponteiros LFS não serve. Exemplo, em pasta externa ao repositório do Studio:

```powershell
git lfs version
git clone https://github.com/blueish0930/BIKINI.git D:\Tools\BIKINI
git -C D:\Tools\BIKINI checkout --detach b007d4e4f2cdb80074852900d9ed8429d228b65d
git -C D:\Tools\BIKINI lfs pull
```

Não copie apenas `blender.exe`. Preserve `5.3/`, `blender.crt/`, `blender.shared/`, `license/`, `quadwild/`, Python e DLLs do pacote. O check detecta os componentes essenciais; não autentica todos os arquivos da distribuição nem substitui uma auditoria de segurança.

Na pasta deste projeto:

```powershell
$env:BIKINI_PATH = 'D:\Tools\BIKINI\blender.exe'
$env:BIKINI_ALLOW_UNOFFICIAL = '1'
$env:AUTO_KNOWLEDGE = '0'
$env:AUTO_VLM = '0'
npm run bikini:check
npm run bikini:probe
npm run start:bikini
```

Acesse `http://127.0.0.1:3939/alice/bikini`. Os dados exibidos são do último probe, não uma medição ao vivo. Antes de cada build a instalação e as evidências são conferidas novamente. Alterar o executável, as DLLs verificadas, o script ou os artefatos invalida o probe. A seleção explícita de BIKINI nunca faz fallback silencioso para Blender normal.

Para voltar ao backend anterior, encerre o processo, remova `BLENDER_BACKEND` do ambiente, configure `BLENDER_PATH` com o Blender desejado e execute `npm start`.

## Camada de Geometry Nodes → candidato de jogo

No BIKINI, abra **uma cópia** do `.blend`, trabalhe a camada e salve seu grafo. Para elementos rígidos — ornamentos, botões, broches, arquitetura e props — uma camada pode ser convertida para geometria estática:

```powershell
npm run bikini:bake -- 'D:\Alice\estudo.blend' 'COL_Ornamentos' 'D:\Alice\candidatos\ornamentos-001'
```

A collection deve conter meshes/empties, pelo menos um modificador Geometry Nodes e geometria final não vazia. Realize instâncias antes da saída. A operação **recusa armatures, grupos de vértices, shape keys e modificadores de cloth/soft-body**: não remove o rig ou achata uma simulação apenas para concluir.

Saídas: `candidate.glb`, `candidate.fbx`, `candidate.blend`, `bake_report.json`, `engine_provenance.json` e log. O arquivo de entrada não é sobrescrito; hashes e código de saída são verificados. O `.blend` é uma cópia de trabalho derivada; GLB/FBX selecionam a camada. Falhas deixam `FAILED.txt`, nunca um candidato aprovado.

Importe o GLB pelo estúdio, compare contra a referência e valide no Blender/Unreal. O Unreal não executa nós BIKINI: recebe a geometria exportada. Materiais procedurais precisam de bake próprio; esta operação não garante transferência fiel de shaders, colisões, UVs, escala ou materiais para a engine. Camadas deformáveis seguem o fluxo específico de personagem, rig, skinning e cloth.

O upstream documenta CGAL, remesh, Jolt, PBD/MPM e ferramentas de textura. Esses são candidatos de ferramentas para nosso processo, não provas de que a Alice foi esculpida, rigada ou melhorada. Não mudamos aprovações, referência, formas aprovadas ou arquivos do NAS ao adicionar o backend.

## Licenças e orçamento

O upstream descreve a distribuição como derivada GPL-3.0-or-later e contém componentes com licenças próprias; DLSS/NGX é opcional e proprietário. Esta integração **não redistribui a distribuição, DLLs ou seus fontes**. Preserve os avisos do fornecedor e revise as obrigações antes de redistribuir qualquer pacote modificado. Não converta a licença do BIKINI para a licença do Studio nem assuma que assets de terceiros estejam liberados.

Não há assinatura/API de BIKINI configurada. O tempo do executor Windows, disco e transferências continuam dentro do orçamento de produção; adicionar o backend não reserva nem contrata GPU. O computador controlador não precisa executar o BIKINI.

## Validação

`npm run test:bikini` executa os testes do adaptador. Veja `BIKINI_VALIDACAO.md` para separar testes feitos no ambiente desta entrega de execução Windows/Blender ainda pendente. Nenhum teste de calibração pode promover conteúdo para o jogo.
