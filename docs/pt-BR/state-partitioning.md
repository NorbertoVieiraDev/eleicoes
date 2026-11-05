# Parquets separados por estado

## Por que esses arquivos existem

O site eleitoral executa o DuckDB-Wasm no navegador de cada visitante. Um arquivo anual de votos pode ter centenas de megabytes; assim, uma busca por um único estado ainda precisa inspecionar um Parquet remoto grande. Os arquivos por estado permitem baixar somente as linhas do estado selecionado. Eles formam uma organização adicional para consulta; os Parquets anuais continuam sendo a fonte canônica, sem alterações.

## Como reproduzir

Use Python 3.9+ e instale os requisitos do repositório. Mantenha os arquivos canônicos originais fora do Git e execute um comando para cada arquivo anual:

```sh
python scripts/partition_canonical.py \
  --input derived/canonical/votes-2024.parquet \
  --output-dir derived/partitioned
python scripts/partition_canonical.py \
  --input derived/canonical/sections-2024.parquet \
  --output-dir derived/partitioned
```

Repita para cada ano disponível. O script usa DuckDB para copiar todas as colunas e linhas de cada valor exato de `state_code` para `votes-AAAA-UF.parquet` ou `sections-AAAA-UF.parquet`. Linhas sem estado ficam em um arquivo separado `*-AAAA-_NULL.parquet`. Dentro de cada arquivo, as linhas são ordenadas pelos campos disponíveis de eleição, cargo, município, zona, seção, urna e candidato para melhorar a leitura seletiva dos grupos de linhas. Nenhum voto é recalculado ou removido.

Cada execução gera um manifesto JSON com os hashes SHA-512 de origem e saída, quantidades de linhas, somas de votos, contagens de votos nulos como valor ausente, tamanhos e resultados por estado. O script confere as contagens e somas antes de registrar o manifesto. Mantenha Parquets e manifestos gerados fora do Git; publique somente evidências agregadas revisadas.

## Integridade e interpretação

A partição altera somente os limites dos arquivos e a ordem das linhas. Cada saída contém as colunas e os valores de origem daquele estado. Para cada estado, o número de linhas, a soma dos votos não nulos e a quantidade de votos com valor nulo são comparados com os valores correspondentes na origem. Os hashes SHA-512 identificam exatamente os bytes de entrada e saída; como a saída é recomprimida e reordenada, é esperado que seu hash seja diferente do arquivo original.

Um arquivo por estado é uma otimização de consulta, não uma nova base oficial do TSE. O arquivo canônico anual permanece disponível para buscas sem estado selecionado. Campos ausentes continuam ausentes, e anos indisponíveis continuam indisponíveis. O navegador deve recorrer ao arquivo anual até que a partição do estado esteja publicada.

## Armazenamento e publicação

Esses arquivos derivados duplicam dados. Antes do envio, some os tamanhos medidos e confirme que há espaço livre suficiente no bucket. Não apague nem substitua os Parquets canônicos neste processo. Publique as partições sob o mesmo prefixo `canonical/` somente depois que o leitor do site aceitar esse padrão de nome. Não armazene credenciais neste repositório.

## Relatórios de auditoria gerados

O [relatório-resumo público](../../reports/history/state-partitioning-summary.json) lista tamanhos de entrada e saída e quantidades de linhas por ano. Cada ano também tem um relatório detalhado com hashes SHA-512 de origem e das partições, contagens de linhas por estado, somas de votos, contagens de votos com valor nulo e tamanhos dos arquivos. Por exemplo, [2024](../../reports/history/state-partitioning-2024.json). Esses relatórios contêm somente metadados; os Parquets não são armazenados no Git.

## Geração com recursos limitados

A ordenação global continua obrigatória por padrão. Em ambientes de nuvem com
pouco espaço temporário, é possível limitar memória e disco e permitir uma
alternativa por partição:

```sh
python scripts/partition_canonical.py --input /dados/votes-2018.parquet \
  --output-dir /dados/shards --threads 1 --memory-limit 5GiB \
  --temp-dir /dados/spill --max-temp-size 3GiB --sort-mode best-effort
```

`best-effort` tenta a mesma ordenação e, somente se o DuckDB lançar
`OutOfMemoryException` durante o COPY ordenado, remove a saída temporária inválida
e repete a cópia do mesmo estado sem ordenação global. Outros erros continuam
interrompendo a execução. `none` permite escolher diretamente a cópia sem
ordenação; `required` mantém o comportamento anterior. Colunas, valores,
duplicatas, totais e verificações são preservados em todos os modos.

O manifesto registra `sort_mode`, os limites solicitados e `sort_applied` em cada
partição. Uma partição sem ordenação global pode exigir mais leitura para filtros
específicos; não atribua a ela medições de uma partição ordenada. Não há upload,
remoção de canônicos ou publicação de dados neste comando.

## Ordenar uma partição grande sem carregar textos repetidos no sort

`scripts/sort_partition_bounded.py` reordena uma partição já validada. Ele cria
dicionários reversíveis para campos de texto com até um milhão de valores,
ordena IDs compactos e reconstrói as colunas originais em lotes Arrow antes de
gravação. IDs usados como chaves seguem a ordem lexical original, com nulos ao
final. Nenhuma coluna de dicionário aparece no Parquet final.

Instale os requisitos opcionais fora do site:

```sh
python -m pip install -r requirements-partition.txt
python scripts/sort_partition_bounded.py \
  --input /dados/shards/votes-2024-SP.parquet --output-dir /dados/sorted \
  --expected-input-sha512 HASH_DA_PARTICAO_NO_MANIFESTO \
  --canonical-sha512 HASH_DO_CANONICO_ANUAL_NO_MANIFESTO
```

O processo usa um thread, até 6 GiB de memória e 3 GiB de spill. Mantém a projeção
de colunas e grava em lotes de 122.880 linhas. Confere esquema, identidade da
entrada, contagens, votos/nulos e dois agregados de hash sobre todas as colunas.
Esses hashes lógicos são diagnósticos, não uma prova sem colisões; os testes
sintéticos verificam `EXCEPT ALL` exato em ambas as direções, duplicatas e nulos.
Falhas interrompem a execução e removem a saída parcial.

A saída inclui 12 caracteres do SHA-512 no nome e ganha um novo manifesto. Use
esse nome imutável ao publicar: não substitua um arquivo que possa estar sendo
lido por requisições Range. O comando não envia dados ao R2. Na validação em
nuvem de 05/11/2026, as cinco partições SP de votos de 2018–2026 antes sem
ordenação foram reconstruídas com ordenação global e esquema/diagnósticos iguais.
