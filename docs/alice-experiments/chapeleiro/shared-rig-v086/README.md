Os acabamentos das duas pernas dos bloomers agora acompanham sua própria coxa
no mesmo rig da fundação. A geometria, as costuras autorais e o exterior Tripo
inteiro foram preservados. O GLB atual foi reimportado e conferido em quatro
vistas de repouso e doze poses, sempre com a foto completa da ficha 1.

A razão máxima de aresta da renda caiu de 7,75390 para 1,00248 nas amostras.
O corpo e a entreperna mantêm exatamente as medições do v084. A correção global
tentada no v085 foi rejeitada porque piorou a entreperna; seus renders e seu
código executado estão em `rejected_v085/`, e o editável completo permanece local.

A união do punho ainda exige ajuste. A auditoria acompanha os 648 vértices
reais de cada elástico por sua posição baricêntrica na superfície do tecido.
A folga máxima chega a 3,46 mm, com aumento máximo de 2,81 mm nas poses.
Isso mede um defeito; não aprova costuras, movimento ou contato físico.

Arquivos para inspeção:

- [Fundação atual no rig compartilhado](foundation/skin_study.glb).
- [Foto própria e quatro vistas atuais](foundation/photo_vs_geometry.jpg).
- [Foto própria e doze poses atuais](foundation/photo_vs_shared_skin_motion.jpg).
- [Comparação das mesmas poses antes e depois](bloomer_motion_before_after.json).
- [Medição real da união do punho com o tecido](bloomer_sewn_junction_audit.json).
- [Reabertura do editável completo](full_editable_reopen.json).
- [Defeitos e limitações observados](checkpoint.json).

O exterior é idêntico byte a byte ao v084, com o mesmo atlas, rig e quatro ações.
Sua foto própria, quatro vistas e doze poses conservam aquela revisão real,
conforme [whole_evidence_reuse.json](whole_evidence_reuse.json).
O diagnóstico das [arestas junto às luvas](whole_actual_pose_edge_diagnosis.json)
encontrou um salto entre os pesos do polegar e da saia: uma aresta de 0,396 mm
chega a 458 mm no ataque. Essa fronteira ainda precisa de correção.

As pernas atravessam as anáguas e a saia na corrida e no ataque. As mangas e a
entreperna ainda deformam demais. O tecido secundário permanece sem resposta
física assada; corpo, colisões entre camadas, contato dos pés, encaixe nas botas
e transições de gameplay continuam pendentes. Decote, microfranzidos, canais
do corset, cascatas das anáguas e acabamento ainda diferem da foto própria.

O Blender completo tem **128.165.008 bytes** e foi preservado em
`F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v086/`.
Ele foi reaberto com um esqueleto de 173 ossos, 230 peças com pesos normalizados,
quatro ações, 14 suportes autorais e 12 imagens utilizadas e empacotadas.
As definições de tecido, a geometria e o mestre inteiro protegido permaneceram
intactos. A presença do rig e dos modificadores não aprova a simulação.

Esta pasta registra um avanço parcial. A galeria canônica permanece na versão
anterior, e a próxima variante aguarda a conclusão do Chapeleiro. O FBX final
vai para o GitHub após concluir as fichas e validar movimento, tecido e colisões.
Não foram consumidos novos créditos Tripo.
