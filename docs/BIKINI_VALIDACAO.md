# Validação da integração BIKINI — 2026-09-26

Base lida no GitHub: `programador-powershell/scanner3d-platform`, branch `3d-game-studio`, commit `74264666053094a5215160effe93caf54c50b8e5`. Não usamos o ZIP antigo para sobrescrever os refinamentos já adicionados à branch.

Upstream inspecionado: `blueish0930/BIKINI`, commit `b007d4e4f2cdb80074852900d9ed8429d228b65d`: README, árvore de distribuição, BUILD_INFO, ponteiro LFS do executável e início do catálogo v2_nodes. A versão de catálogo é 5.3.0 Alpha.

## Executado nesta entrega

- **38 testes aprovados**, zero falhas, na suíte nova `node --test tests/bikini.test.js`.
- Verificação de sintaxe dos JS modificados/novos, do JavaScript da página e dos dois scripts Python.
- Testes reais de subprocessos com **Node**, incluindo retorno de erro, timeout e limite de log.
- Requisição HTTP real à rota de diagnóstico, hospedada por um adaptador mínimo de teste Node HTTP. Não é um teste ponta a ponta do servidor Express completo.
- Testes de pacote simulado: hash, Windows/arquitetura, consentimento, LFS não hidratado, DLL ausente, probe obsoleto e evidência alterada. Os bytes de fixture NÃO são o executável BIKINI e nunca são executados.
- Cópias-base de `build_runner.js`, `alice_studio.js`, `package.json` e `.gitignore` conferidas contra os respectivos blob SHAs do GitHub antes de aplicar as mudanças.
- CLI no host Linux recusa o backend Windows e não faz fallback de sucesso.

## Não executado

**O binário BIKINI Windows não foi executado.** O ambiente desta entrega é Linux, sem Blender/Bpy ou Wine instalados, e a tentativa de acesso direto à rede pelo container falhou em DNS. As leituras e escritas GitHub utilizam o conector autenticado.

Não foram executados Geometry Nodes, exportação Blender real, calibração no BIKINI, bake de uma camada do Alice, simulação, GPU, rig, retopologia, shaders, render, Unreal, NAS ou a suíte completa de regressão do repositório com seus assets/dependências. Esses testes exigem o executor real e continuam pendentes.

## Critério de próxima homologação

1. Obter o pacote fixado com Git LFS e conferir `bikini:check`.
2. Executar `bikini:probe` em Windows x64 e inspecionar logs/artefatos; o resultado é apenas teste de exportação.
3. Abrir uma cópia aprovada de um prop/camada estática. Criar ou ajustar o grafo no BIKINI e executar `bikini:bake` em pasta nova.
4. Conferir fonte intacta, meshes, escala, UVs e materiais. Importar o GLB/FBX no Studio e na Unreal e comparar sob condições iguais.
5. Preservar a revisão artística pendente até a aprovação explícita. Cabelo, rosto e roupas da personagem não são homologados por esse procedimento de props.

Nenhuma fidelidade AAA, ganho de FPS, economia de GPU ou preservação de skinning é alegada como medida. A integração permanece **experimental e opcional**.
