# Chapeleiro: continuidade dos pesos da palma e dedos

O exterior inteiro conserva geometria, UVs, atlas, juntas e quatro ações. Os
pesos de 22.542 vértices das mãos foram suavizados sobre as arestas originais,
com âncoras nos punhos e nas pontas reais dos dedos. Vértices coincidentes
servem somente como associações de medição; a malha não foi soldada ou recortada.

As [quatro vistas com a foto própria](whole/photo_vs_geometry.jpg),
[doze poses reais](whole/photo_vs_shared_skin_motion.jpg) e
[seis detalhes antes/depois](photo_vs_actual_hand_motion_before_after.jpg)
registram o resultado. A câmera dos detalhes é idêntica nos dois modelos e
segue a junta real do punho. Não há geometria diagnóstica ou alteração dos
materiais nos detalhes. Faixas alongadas na luva diminuem; palma, anatomia dos
dedos, acabamento e extremos do movimento continuam provisórios.

No [diagnóstico dos GLBs realmente exportados](hand_edges_before_after.json),
o maior esticamento nas mãos durante o ataque passa de 32,58 para 11,50 vezes.
Na caminhada, passa de 15,94 para 5,52; na corrida, de 30,51 para 9,09.
Mesmo após a melhora, cinco arestas da região das mãos continuam acima de dez
vezes o comprimento de repouso no ataque. Esses números não aprovam anatomia,
todas as poses, fidelidade ou física.

A atribuição usa difusão de pesos sobre a superfície real, preservando
exatamente os pesos fora da região e as âncoras. Os candidatos de 8, 24 e 48
passos são estimativas identificadas em `hand_diffusion/`; somente o de 48
passos gerou o novo GLB. O esqueleto não foi alterado. A fundação permanece
idêntica à v092/v090 e conserva a própria foto da etapa 01 com a evidência real
anterior; não houve novo polimento da fundação.

Axila, mangas, transição cabelo/braço, saia/perna, acabamento, demais fichas e
colisões permanecem pendentes. A inspeção do editável anterior confirma 14
suportes de autoria, dos quais oito têm Cloth, e nenhum objeto Collision.
O ensaio local `probe_chapeleiro_ivory_cloth_motion.py` foi iniciado sobre a
anágua existente, com colisores nas superfícies animadas das meias e bloomers.
Essas superfícies são camadas existentes, não anatomia oculta completa. O ensaio
não está incorporado ao GLB nem aprova colisões ou tecido em todas as camadas.

O novo editável completo tem **129.256.128 bytes** e foi reaberto para conferir
230 peças no mesmo rig de 173 ossos, 14 suportes, 12 imagens efetivamente
empacotadas e quatro ações. SHA256:
`43a005823420619e32df69d7805d26181f5afc56d65462baaffd31199aacb4bc`.
Ele permanece integral em
`F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v093/chapeleiro_shared_rig_attachment_refinement.blend`.
O tamanho não foi reduzido para caber no limite de blobs do GitHub.

Nenhum crédito adicional do Tripo foi usado. Este checkpoint continua em
refinamento; o FBX final e a próxima variante aguardam a conclusão de todas as
fichas, rig, acabamento e testes de movimento e colisão do Chapeleiro.
