# Chapeleiro: superfície inteira e pesos contínuos

Este avanço preserva o exterior completo e refina seus pesos no mesmo rig de
173 ossos. Não há recorte, troca de geometria, UV ou atlas. A versão permanece
**em refinamento**: as outras fichas, fidelidade, contatos, tecido secundário e
colisões não estão concluídos. Nenhuma outra variante foi iniciada.

Compare [a foto própria e as quatro vistas do exterior](whole/photo_vs_geometry.jpg)
e [as doze poses realmente exportadas](whole/photo_vs_shared_skin_motion.jpg).
O braço levantado no primeiro ataque permanece conectado, mas há abertura na
axila, colapso da manga, esticamento na palma/luva e penetração da perna na saia.
A inspeção 3D posterior do ataque mostra continuidade melhor no cabelo, mas
seu acabamento e a validação ao longo de toda a ação continuam pendentes.

Nas cinco poses medidas do GLB, o maior esticamento de uma aresta passou de
304,9263 para 43,3960 vezes. A melhoria não aprova o movimento. A transição
saia/perna e a palma continuam apresentando deformações excessivas. Os valores,
posições e pesos reais estão em [antes/depois](whole_edge_before_after.json) e
[diagnóstico do GLB](whole_actual_pose_edge_diagnosis.json).

A atribuição infere sete regiões por distâncias sobre as arestas originais,
ponderadas pelas cores reais do atlas. Vértices coincidentes são associados
somente no grafo de medição; a malha não é soldada. Foram alterados os pesos de
100.084 vértices; os pesos das 33.495 posições das superfícies separadas dos
braços/mãos foram preservados exatamente. A inferência anatômica permanece
provisória. Os renders de cores em `candidate_v002/ownership_review/` mostram
essa atribuição sobre o volume original; não são acabamento final.

O candidato anterior foi rejeitado por atribuir parte do antebraço à saia.
`rejected_v091/` preserva a decisão, o código e as estimativas; aquele candidato
não chegou a salvar um editável completo. Estimativas de skinning nativo são
identificadas separadamente da medição de poses no GLB realmente exportado.

A fundação é byte a byte idêntica à v090. Por isso as suas quatro vistas e doze
poses reais foram preservadas, com a própria foto da ficha 1. A identidade está
registrada em [foundation_evidence_reuse.json](foundation_evidence_reuse.json).
Ela ainda carece de costuras, franzidos finos, cascatas diagonais e trama fiel
das meias. Reutilizar essa evidência não representa um novo refinamento.

O editável completo tem **129.193.720 bytes** e foi reaberto no Blender para
conferir 230 peças com o rig comum, 14 suportes de autoria, 12 imagens
efetivamente empacotadas e quatro ações. SHA256:
`40296b35fcd6551a781eb13628e179a19a4243895ea7389f471312c9ef58861b`.
O arquivo permanece integral em
`F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v092/chapeleiro_shared_rig_attachment_refinement.blend`.
O tamanho não foi reduzido para caber no limite de blobs do GitHub. Os dois
GLBs, fotos e evidências deste ensaio estão versionados aqui.

Não foram consumidos créditos adicionais do Tripo. O FBX final será publicado
no GitHub depois da conclusão e validação de todas as fichas do Chapeleiro.
O mestre aprovado e os modelos canônicos foram preservados.
