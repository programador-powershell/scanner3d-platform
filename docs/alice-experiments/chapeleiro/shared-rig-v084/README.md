O Chapeleiro tem um ensaio local de rig compartilhado para as 229 peças atuais
da fundação e o exterior Tripo inteiro. Os GLBs desta pasta conservam um
esqueleto de 173 ossos e quatro ações: caminhada, corrida, ataque e salto.
As poses exportadas foram reimportadas, medidas e renderizadas. Cada conjunto
mantém sua foto original, quatro vistas de repouso e três poses por ação.

Este é trabalho em andamento. As pernas atravessam as anáguas e a saia; as
mangas e a renda dos bloomers ainda esticam, e o exterior tem deformações junto
às mãos e luvas. Os ossos de tecido seguem os quadris, sem resposta física
assada. Não há aprovação de fidelidade, movimento, colisões ou gameplay.
O modelo canônico da galeria permanece na versão anterior. Estes GLBs são
ensaios de deformação, e não o FBX final.

Arquivos para inspeção:

- [Fundação: GLB com as 229 peças no rig](foundation/skin_study.glb).
- [Exterior inteiro: GLB no mesmo esqueleto](whole/skin_study.glb).
- [Foto da ficha 1 e quatro vistas reais](foundation/photo_vs_geometry.jpg).
- [Ficha 1 e doze poses exportadas](foundation/photo_vs_shared_skin_motion.jpg).
- [Foto do conjunto inteiro e quatro vistas reais](whole/photo_vs_geometry.jpg).
- [Conjunto inteiro e doze poses exportadas](whole/photo_vs_shared_skin_motion.jpg).
- [Pesos reais e controles dos 14 suportes](skin_audit.json).
- [Ossos, encaixe medido nas meias e regras das costuras](shared_rig_bind.json).
- [Limites e defeitos observados](checkpoint.json).
- [Inspeção dos movimentos no visualizador 3D](interactive_review.json).

O v082 recebeu influência dos braços no corset e nas raízes das anáguas; seus
renders estão preservados em `historical/`. O v083 corrigiu essas ligações,
usando as raízes reais das cavas para transicionar as mangas. A medição encontrou
depois um botão central dos bloomers dividido entre as duas pernas e saltos de
pesos que danificavam as costuras finas. O v084 prende esses botões aos quadris,
suaviza o suporte dos pesos e usa incrementos binários de 1/65536.
Na pose de corrida amostrada com maior deformação daquele botão, a razão máxima
de aresta caiu de 106,75 para 1,00024. Isso corrige um defeito específico; a renda
do punho dos bloomers ainda chega a 7,75 em outra pose e exige refinamento.

O mestre inteiro, a Alice Base aprovada, as coordenadas e faces dos tecidos
autorais foram preservados. Nenhuma malha de personagem dos FBXs foi usada:
eles fornecem apenas ossos e as ações de caminhar, correr e atacar. O salto é
um ensaio de IK criado localmente. As chaves plantadas não comprovam contato
das superfícies dos pés com o chão. A hierarquia dos suportes com Armature,
Surface Deform e Cloth ainda precisa ser resolvida e testada antes de qualquer
simulação: a presença dos modificadores não aprova composição nem colisões.

O checkpoint completo continua em
`F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/foundation_shared_rig_v084/`,
com **128.220.742 bytes**, sem cortes para reduzir seu tamanho. Seu hash e os
checkpoints anteriores constam em `local_provenance.json`. As bibliotecas e
arquivos Blender locais continuam preservados; esta pasta inclui os dois GLBs
experimentais e as evidências, sem substituir o editável completo por uma
cópia incompleta. Todos os caminhos dos relatórios portáteis são relativos à
raiz desta pasta. Não foram consumidos novos créditos Tripo.

O processo usa `rig_chapeleiro_foundation_shared.py`,
`refine_chapeleiro_shared_rig_attachments.py` e
`chapeleiro_shared_rig_fields.py`, no diretório `blender/` do projeto.
`review_chapeleiro_shared_rig_export.py` verifica os GLBs reimportados e gera as
poses. `compose_chapeleiro_shared_rig_review.py` conserva a foto inteira ao lado
dos renders, e `package_chapeleiro_shared_rig_study.py` recusa evidências de
fotos, modelos ou versões diferentes. O FBX vai para o GitHub depois de concluir
as fichas, o rig e os testes reais de tecido e colisão. A próxima variante
continua aguardando o término do Chapeleiro.
