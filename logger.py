"""
==============================================================================
Módulo: logger.py
Descrição:
    Este módulo oferece uma interface simples para geração de logs em arquivos
    de texto, com saída simultânea no console.

    Funcionalidades:
    - Registro de mensagens com timestamp e nível INFO
    - Gravação em arquivo .txt com codificação UTF-8
    - Impressão formatada no console com data e hora

------------------------------------------------------------------------------
Exemplo de uso:

    from models.logger import Log

    Log.logmessage("Processo iniciado com sucesso.")
    Log.logmessage("Arquivo exportado para SharePoint.", logfile="export_log")

    # Resultado:
    # Arquivo export_log.txt será criado na raiz do projeto
    # Mensagem será impressa no console:
    # 03-10-2025 16:42:10 | Arquivo exportado para SharePoint.

------------------------------------------------------------------------------
Dependências:
    - logging (módulo nativo do Python)
    - datetime (módulo nativo do Python)

==============================================================================
"""

import warnings
warnings.filterwarnings("ignore")  # Ignora possíveis avisos do logging

import logging
from datetime import datetime

class Log:
    @staticmethod
    def logmessage(msg, logfile="Default"):
        """
        Registra uma mensagem de log no arquivo especificado e imprime no console.

        Parâmetros:
            msg (str): A mensagem a ser registrada
            logfile (str): Nome base do arquivo de log (sem extensão ".txt")

        Saída:
            Cria ou atualiza um arquivo de log no formato:
            [NÍVEL]: [DATA/HORA] Mensagem

            Também imprime no terminal no formato:
            DD-MM-YYYY HH:MM:SS | Mensagem
        """
        logging.basicConfig(
            filename=f"{logfile}.txt",
            level=logging.INFO,
            format="%(levelname)s: %(asctime)s %(message)s",
            encoding='utf-8',
            datefmt="%d/%m/%y %H:%M:%S"
        )

        logging.info(msg)
        print(datetime.now().strftime("%d-%m-%Y %H:%M:%S") + " | " + msg)
