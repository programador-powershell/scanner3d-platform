# Alice Coelho inteira — checkpoint estático WIP v184

Personagem inteiro com vestido, exportado do Blender completo v181. A correção local da renda removeu cruzamentos entre motivos vizinhos e na rede, preservando os UVs e as seções dos fios. A tentativa de mover motivos inteiros foi rejeitada; o ajuste intermediário v173 criou contatos na rede e também foi rejeitado. Somente o ajuste conjunto v177, reaberto e verificado, entrou no personagem inteiro v181.

Ainda há 7.417 pares de contato dentro dos próprios motivos da renda, sem aprovação como junções costuradas. As verificações estáticas não comprovam rig, costura ou comportamento em movimento.

GLB e FBX inteiros, com 1.385.780 triângulos, foram reimportados e comparados em cinco vistas por formato. Todas as posições, UVs e atribuições de material foram conferidas. O GLB reproduz o arredondamento nativo das normais do exportador a quatro decimais; não se alega igualdade com as normais sem arredondamento. No FBX, posições, ordem de triângulos e componentes das normais são exatos. O armazenamento de normais dos dois importadores foi reproduzido independentemente. Texturas 4K foram comparadas por pixels no GLB e por bytes/conexões no FBX.

Os arquivos inteiros, incluindo o Blender de 616 MB sem redução, estão na release do GitHub relacionada em checkpoint.json. Fontes e candidatos anteriores permanecem ocultos e recuperáveis no Blender; somente os cinco objetos integrados são exportados. A comparação fotográfica mostra pendências reais de bordados, ornamentos pendentes e costura. Ampliar a referência para 4K não cria detalhes.

Produção INCOMPLETA: ornamentos e bordados, montagem/costura, LOD para deformação; base comum do rosto/corpo descalço de 168 cm e rig; camadas inferiores; cabelo individual com penteado desta variante; tecido, vento, colisões, expressões, caminhada, corrida, salto, queda, ataque e troca de vestidos no jogo. SEM rig ou animações neste checkpoint. Uma geração Tripo de 55 créditos, zero novos créditos. Continuar até concluir o asset inteiro, sem outra geração própria. Publicar personagem inteiro antes de mudar de parte ou movimento.

As dez pranchas originais estão em references/, com caminhos e hashes. O rosto canônico continua em SharedBase/References/alice_face_master_v001.png. Não usar fontes rejeitadas ou arquivos do HDD como base. Esta pasta registra a entrega completa do checkpoint; os scripts dependem das fontes e ferramentas mapeadas em F:/Alice/SharedProduction.
