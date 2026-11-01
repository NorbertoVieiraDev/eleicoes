# 2026 validation / Validação 2026

Snapshot prepared on 2026-11-01. / Carga preparada em 01/11/2026.

| Measure / Medida | Value / Valor |
| --- | ---: |
| Source ZIP packages / Pacotes ZIP | 56 |
| Published SHA-512 matched / SHA-512 correspondente | 56 |
| Source vote rows / Linhas da fonte | 69,947,081 |
| Source ZIP bytes / Bytes ZIP | 5,221,647,376 |
| Uncompressed CSV bytes / Bytes CSV | 32,418,087,578 |
| Lossless raw Parquet bytes / Bytes Parquet bruto | 2,569,872,972 |
| Section-office records / Registros seção-cargo | 3,029,750 |
| Distinct candidate display combinations / Combinações de candidatos | 19,121 |
| Municipality/locality records / Municípios-localidades | 5,716 |
| Candidate-municipality aggregate rows / Agregados candidato-município | 2,238,145 |

## Observed sections / Seções observadas

| Round / Turno | Source sections / Seções na fonte | Sections with a contest / Seções com cargo informado |
| --- | ---: | ---: |
| 1 | 499,206 | 499,206 |
| 2 | 499,207 | 499,205 |

English: two second-round placeholder records have zero votes and no office/votable (`-1`/`#NULO#`). They remain traceable and are excluded from candidate aggregates. These counts describe distinct principal section keys observed in the files. They do not represent all principal plus aggregated sections, and they have not been reconciled with an independent expected-section roster. A physical urn number is not a section count.

Português: duas linhas marcadoras do segundo turno têm zero votos e cargo/votável ausente (`-1`/`#NULO#`). Permanecem rastreáveis e ficam fora dos agregados de candidatos. As contagens são de chaves distintas de seção principal observadas nos arquivos. Não representam todas as seções principais e agregadas nem foram comparadas com cadastro independente de seções esperadas. Quantidade de urnas físicas não é quantidade de seções.

## Checks / Verificações

All following counts were zero / Todas as contagens abaixo foram zero:

- Duplicate vote keys / Chaves de voto duplicadas.
- Negative vote quantities / Votos negativos.
- Null analytical keys or measures / Chaves ou medidas analíticas nulas.
- Wrong source year, UF, round or code width / Ano, UF, turno ou largura de código inválidos.
- Conflicting repeated section-office metadata / Metadados seção-cargo inconsistentes.
- Eligible/turnout/abstention imbalances / Desequilíbrios entre aptos, comparecimento e abstenções.
- Ballot-opportunity diagnostic differences / Diferenças no diagnóstico de oportunidades de voto.
- Conflicting aggregated-section aliases / Conflitos nos vínculos de seções agregadas.
- Unparsed nonempty aggregated-section values / Relações de agregação não interpretadas.

The three synthetic integration tests passed: preserving vote and identifier values without duplicating turnout, stopping on checksum mismatch, and rejecting nonnumeric votes. / Os três testes sintéticos passaram: preservação de votos e identificadores sem duplicar comparecimento, interrupção por hash divergente e rejeição de votos não numéricos.

## Files / Arquivos

- `summary.json`: machine-readable counts and limitations / contagens e limitações para leitura automatizada.
- `coverage.csv`: observed coverage and checks by election, round, UF and office / cobertura observada e verificações por eleição, turno, UF e cargo.
- `candidate_state.csv`: recorded BU votes by UF and votable / votos de BU por UF e votável.
- `territories.csv`: observed electoral localities / localidades eleitorais observadas.

Source / Fonte: Tribunal Superior Eleitoral, https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna . The files do not certify official legal totalization or publication of every expected BU. / Os arquivos não certificam totalização jurídica oficial nem publicação de todos os BUs esperados.
