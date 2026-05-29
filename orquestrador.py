"""
==============================================================================
Módulo: orquestrador.py
Descrição:
    Wrapper sobre o Prefect para orquestração dos pipelines de coleta.
    Oferece funções simples para registrar projetos e etapas sem necessidade
    de conhecimento aprofundado do Prefect.

Exemplo de uso:
    from models.orquestrador import etapa, projeto

    @etapa(nome="Buscar dados EC2")
    def buscar_dados():
        ...

    @projeto(nome="Coleta AWS")
    def coleta_aws():
        buscar_dados()
        inserir_banco()
==============================================================================
"""

from prefect         import flow, task
from prefect.logging import get_run_logger
from functools       import wraps


def etapa(nome=None, descricao=None, tentativas=1, aguardar_segundos=10):
    """
    Decorator que marca uma função como uma ETAPA de um pipeline.

    Parâmetros:
        nome               (str): Nome legível da etapa. Padrão: nome da função.
        descricao          (str): Descrição opcional da etapa.
        tentativas         (int): Quantas vezes tentar em caso de erro. Padrão: 1.
        aguardar_segundos  (int): Segundos entre tentativas. Padrão: 10.

    Exemplo:
        @etapa(nome="Inserir no banco", tentativas=3)
        def inserir():
            ...
    """
    def decorator(func):

        task_name = nome or func.__name__

        @task(
            name             = task_name,
            description      = descricao or "",
            retries          = tentativas - 1,
            retry_delay_seconds = aguardar_segundos,
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_run_logger()
            logger.info(f"[ETAPA] Iniciando: {task_name}")
            resultado = func(*args, **kwargs)
            logger.info(f"[ETAPA] Concluída: {task_name}")
            return resultado

        return wrapper
    return decorator


def projeto(nome=None, descricao=None, log_prints=True):
    """
    Decorator que marca uma função como um PROJETO (pipeline completo).

    Parâmetros:
        nome        (str): Nome legível do projeto. Padrão: nome da função.
        descricao   (str): Descrição opcional do projeto.
        log_prints  (bool): Captura prints como logs. Padrão: True.

    Exemplo:
        @projeto(nome="Coleta AWS")
        def coleta_aws():
            buscar_dados()
            inserir_banco()
    """
    def decorator(func):

        flow_name = nome or func.__name__

        @flow(
            name        = flow_name,
            description = descricao or "",
            log_prints  = log_prints,
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_run_logger()
            logger.info(f"[PROJETO] Iniciando: {flow_name}")
            resultado = func(*args, **kwargs)
            logger.info(f"[PROJETO] Concluído: {flow_name}")
            return resultado

        return wrapper
    return decorator