# language: pt
@stage6 @functional
Funcionalidade: Processamento completo de uma ordem de serviço
  Como equipe da oficina
  Quero processar uma ordem entre os três microsserviços
  Para comprovar reserva, pagamento e entrega de forma integrada

  Cenário: Aprovação do orçamento, pagamento e entrega da OS
    Dado que existe um cliente com veículo cadastrado
    E existe um serviço ativo e uma peça com estoque disponível
    Quando uma ordem de serviço é criada
    E o diagnóstico é iniciado e registrado
    E o serviço e a peça são adicionados à ordem
    Então a peça deve ser reservada em Recursos
    Quando o diagnóstico é concluído e o orçamento é comunicado e aprovado
    Então a ordem deve estar aprovada para execução
    Quando a execução é iniciada e finalizada
    E o pagamento simulado é confirmado
    Então o Financeiro deve registrar o pagamento confirmado
    E Ordens deve receber a confirmação financeira
    Quando a entrega da ordem é solicitada
    Então a ordem deve estar ENTREGUE
    E a reserva deve estar CONSUMIDA em Recursos
    E não devem existir efeitos duplicados nem mensagens nas DLQs
