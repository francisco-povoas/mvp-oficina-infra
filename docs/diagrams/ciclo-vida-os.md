# Diagrama do ciclo de vida da OS

O diagrama reflete a máquina de estados de Ordens. Estados de Saga e de operações de
estoque não são estados públicos da OS.

```mermaid
stateDiagram-v2
    [*] --> RECEBIDA
    RECEBIDA --> EM_DIAGNOSTICO: iniciar diagnóstico
    EM_DIAGNOSTICO --> DIAGNOSTICO_CONCLUIDO: concluir diagnóstico
    DIAGNOSTICO_CONCLUIDO --> AGUARDANDO_APROVACAO: orçamento comunicado
    DIAGNOSTICO_CONCLUIDO --> APROVADA: aprovação reconciliada / sem pendência
    DIAGNOSTICO_CONCLUIDO --> AGUARDANDO_ITENS: aprovação reconciliada / item A_RECEBER

    AGUARDANDO_APROVACAO --> APROVADA: orçamento aprovado / sem pendência
    AGUARDANDO_APROVACAO --> AGUARDANDO_ITENS: aprovado / item A_RECEBER
    AGUARDANDO_ITENS --> AGUARDANDO_ITENS: recebimento parcial
    AGUARDANDO_ITENS --> APROVADA: todas as peças recebidas

    AGUARDANDO_APROVACAO --> ENCERRADA: orçamento recusado e liberações concluídas
    ENCERRADA --> [*]

    APROVADA --> EM_EXECUCAO: iniciar execução
    EM_EXECUCAO --> FINALIZADA: finalizar serviços
    FINALIZADA --> ENTREGUE: pagamento e consumos confirmados
    ENTREGUE --> [*]
```

Na reserva de peça, saldo insuficiente produz item `A_RECEBER`. Isso não compensa a
Saga e não muda imediatamente o estado público da OS. Após a aprovação do orçamento,
a pendência leva a `AGUARDANDO_ITENS`. A recusa do orçamento só chega a
`ENCERRADA` depois de cancelar itens e liberar as reservas necessárias. As duas
transições diretas a partir de `DIAGNOSTICO_CONCLUIDO` cobrem reconciliação ou
entrega fora de ordem do evento de aprovação; eventos repetidos não fazem o estado
regredir.
