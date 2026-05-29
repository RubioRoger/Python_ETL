"""
==============================================================================
Módulo: config.py
Descrição:
    Este módulo centraliza utilidades de configuração, padronização de dados,
    manipulação de arquivos, variáveis de ambiente, DataFrames e integração
    com o Agendador de Tarefas do Windows.

    A classe Config é amplamente reutilizada no projeto e seus nomes,
    assinaturas e responsabilidades estão consolidados, não devendo ser
    alterados.

    Funcionalidades principais:
    - Padronização de headers e textos
    - Tratamento de valores nulos em DataFrames
    - Conversões de valores e percentuais
    - Manipulação de diretórios e arquivos
    - Controle de proxy
    - Utilidades de datas
    - Integração com Agendador de Tarefas do Windows

------------------------------------------------------------------------------
Dependências:
    - pandas
    - numpy
    - unidecode
    - unicodedata
    - os
    - glob
    - shutil
    - datetime
    - win32com.client
    - subprocess
    - models.logger.Log

==============================================================================

==============================================================================
Exemplos de uso — classe Config
==============================================================================

from models.config import Config
import pandas as pd
import numpy as np

cfg = Config()

# ---------------------------------------------------------------------------
# cfg_none
# ---------------------------------------------------------------------------
s = pd.Series([1, np.nan, 3])
s = cfg.cfg_none(s)

# ---------------------------------------------------------------------------
# cfg_no_proxy
# ---------------------------------------------------------------------------
cfg.cfg_no_proxy()

# ---------------------------------------------------------------------------
# cfg_proxy
# ---------------------------------------------------------------------------
cfg.cfg_proxy()

# ---------------------------------------------------------------------------
# cfg_config_header
# ---------------------------------------------------------------------------
header = cfg.cfg_config_header("Nome do Cliente X0020 ")

# ---------------------------------------------------------------------------
# cfg_remove_acentos
# ---------------------------------------------------------------------------
texto = cfg.cfg_remove_acentos("São Paulo")

# ---------------------------------------------------------------------------
# cfg_lower_header
# ---------------------------------------------------------------------------
header_lower = cfg.cfg_lower_header("NÚMERO_CONTRATO")

# ---------------------------------------------------------------------------
# cfg_replace_null
# ---------------------------------------------------------------------------
df = pd.DataFrame({
    "A": [1, None],
    "B": ["x", None],
    "C": [pd.Timestamp("2024-01-01"), None]
})
df = cfg.cfg_replace_null(df)

# ---------------------------------------------------------------------------
# cfg_percent
# ---------------------------------------------------------------------------
percentual = cfg.cfg_percent(10, 20)

# ---------------------------------------------------------------------------
# cfg_dataframe
# ---------------------------------------------------------------------------
df_vazio = cfg.cfg_dataframe()

# ---------------------------------------------------------------------------
# cfg_convert_to_kb
# ---------------------------------------------------------------------------
kb_1 = cfg.cfg_convert_to_kb("10M")
kb_2 = cfg.cfg_convert_to_kb("500K")
kb_3 = cfg.cfg_convert_to_kb("1G")
kb_4 = cfg.cfg_convert_to_kb(250)

# ---------------------------------------------------------------------------
# cfg_mover_csv_outputs
# ---------------------------------------------------------------------------
cfg.cfg_mover_csv_outputs()

# ---------------------------------------------------------------------------
# cfg_datas
# ---------------------------------------------------------------------------
data_limite = cfg.cfg_datas(30)

# ---------------------------------------------------------------------------
# cfg_nulos_to_zero
# ---------------------------------------------------------------------------
df = pd.DataFrame({"qtd": [1, None, 3]})
df = cfg.cfg_nulos_to_zero(df, ["qtd"])

# ---------------------------------------------------------------------------
# cfg_nulos_to_nd
# ---------------------------------------------------------------------------
df = pd.DataFrame({"status": ["OK", None]})
df = cfg.cfg_nulos_to_nd(df, ["status"])

# ---------------------------------------------------------------------------
# cfg_separar_por_presenca
# ---------------------------------------------------------------------------
df_tudo = pd.DataFrame({"id": [1, 2, 3]})
df_ultimos = pd.DataFrame({"id": [2, 3]})

df_com, df_sem = cfg.cfg_separar_por_presenca(df_tudo, df_ultimos, "id")

# ---------------------------------------------------------------------------
# cfg_dataframe_to_text
# ---------------------------------------------------------------------------
df = pd.DataFrame({
    "cidade": ["São Paulo", "Curitiba"],
    "valor": [10, 20]
})
df_texto = cfg.cfg_dataframe_to_text(df)

# ---------------------------------------------------------------------------
# fill_na_with_zero
# ---------------------------------------------------------------------------
df = pd.DataFrame({"total": [5, None]})
df = cfg.fill_na_with_zero(df, "total")

# ---------------------------------------------------------------------------
# cfg_limpar_arquivos_antigos
# ---------------------------------------------------------------------------
cfg.cfg_limpar_arquivos_antigos()

# ---------------------------------------------------------------------------
# cfg_criar_pasta_agendador
# ---------------------------------------------------------------------------
cfg.cfg_criar_pasta_agendador("MinhaPastaAgendada")

# ---------------------------------------------------------------------------
# cfg_task_vcenter
# ---------------------------------------------------------------------------
cfg.cfg_task_vcenter(
    nome_arquivo_xml="vcenter_task.xml",
    nome_task="Vcenter",
    nome_pasta="MinhaPastaAgendada"
)
"""
import functools
import unidecode
import unicodedata
import os
import shutil
import win32com.client
import subprocess
import numpy          as np
import pandas         as pd

from models.logger    import Log
from datetime         import datetime, date, timedelta
from glob             import glob


class Config:

    def __init__(self):
        """
        Inicializa diretórios padrão do projeto.
        """
        self.output_dir = os.path.join(os.getcwd(), 'outputs')
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.arquivos_dir = os.path.join(os.getcwd(), 'arquivos')
        os.makedirs(self.arquivos_dir, exist_ok=True)
        
        self.codigo_dir = os.path.join(os.getcwd(), 'codigo_fonte')
        os.makedirs(self.codigo_dir, exist_ok=True)

    def cfg_none(self, i):
        """
        Substitui valores NaN por None.
        """
        i = i.where(pd.notnull(i), None)
        i = i.replace({np.nan: None})
        return i

    def cfg_no_proxy(self):
        """
        Remove configurações de proxy do ambiente.
        """
        os.environ['NO_PROXY'] = '*'
        os.environ.pop('http_proxy', None)
        os.environ.pop('https_proxy', None)

    def cfg_proxy(self):
        """
        Configura proxy padrão do ambiente.
        """
        os.environ['http_proxy'] = 'http://10.1.6.20:80'
        os.environ['https_proxy'] = 'http://10.1.6.20:80'
        os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

    def retry_com_proxy(self, func, *args, **kwargs):
        """
        Tenta executar func normalmente.
        Se falhar, alterna o estado do proxy e tenta novamente.
        Retorna o resultado ou None se ambas as tentativas falharem.
        """
        tentativas = [
            ("sem proxy",  self.cfg_no_proxy),
            ("com proxy",  self.cfg_proxy),
        ]

        for descricao, configurar_proxy in tentativas:
            try:
                configurar_proxy()
                return func(*args, **kwargs)
            except Exception as e:
                Log.logmessage(f"[PROXY] Falhou {descricao}: {e}. Tentando alternativa...")

        Log.logmessage("[PROXY] Ambas as tentativas falharam.")
        return None
    
    def cfg_config_header(self, header):
        """
        Padroniza headers (remove acentos, espaços e caracteres inválidos).
        """
        header = header.replace(" ", "_")
        header = unidecode.unidecode(header)
        header = header.upper()
        header = "".join(char for char in header if char.isalnum() or char == "_")
        header = header.replace("\t", "")
        header = header.replace("_X0020_", "_")
        return header

    def cfg_remove_acentos(self, texto):
        """
        Remove acentos e converte texto para uppercase.
        """
        if isinstance(texto, str):
            texto = unicodedata.normalize('NFKD', texto)
            texto = texto.encode('ASCII', 'ignore').decode('utf-8')
            return texto.upper()
        return texto

    def cfg_lower_header(self, header):
        """
        Padroniza header para lowercase sem acentos.
        """
        header = unidecode.unidecode(header)
        return header.lower()

    def cfg_replace_null(self, df):
        """
        Substitui valores nulos de acordo com o tipo da coluna.
        """
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(0)
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].fillna(pd.Timestamp("1900-01-01"))
            else:
                df[col] = df[col].fillna("N/D")
        return df

    def cfg_percent(self, numerador, denominador):
        """
        Calcula percentual tratando divisão por zero.
        """
        return np.where(
            (numerador == 0) & (denominador == 0),
            None,
            (numerador / denominador) * 100
        )

    def cfg_dataframe(self, df=None):
        """
        Retorna um DataFrame vazio.
        """
        return pd.DataFrame()

    def cfg_convert_to_kb(self, valor):
        """
        Converte valores textuais (K, M, G) para KB.
        """
        if isinstance(valor, str):
            valor = valor.strip().lower().replace(',', '.')
            if valor.endswith('m'):
                return float(valor.replace('m', '')) * 1000
            elif valor.endswith('k'):
                return float(valor.replace('k', ''))
            elif valor.endswith('g'):
                return float(valor.replace('g', '')) * 1000 * 1000
            elif valor == '0':
                return 0.0
        try:
            return float(valor)
        except Exception:
            return 0.0

    def cfg_mover_csv_outputs(self):
        """
        Move arquivos CSV da pasta 'arquivos' para 'outputs'.
        """
        for arquivo in glob('./arquivos/*.csv'):
            destino = os.path.join('./outputs', os.path.basename(arquivo))
            
            if os.path.exists(destino):
                os.remove(destino)
                
            shutil.move(arquivo, destino)
            Log.logmessage(f"Movido: {arquivo} → {destino}")

    def cfg_datas(self, valor=0):
        """
        Retorna a data atual menos o número de dias informado.
        """
        return date.today() - timedelta(days=valor)

    def cfg_nulos_to_zero(self, df, colunas):
        """
        Substitui valores nulos por zero nas colunas informadas.
        """
        df[colunas] = df[colunas].fillna(0)
        return df

    def cfg_nulos_to_nd(self, df, colunas):
        """
        Substitui valores nulos por 'ND' nas colunas informadas.
        """
        df[colunas] = df[colunas].fillna('ND')
        return df

    def cfg_separar_por_presenca(self, df_tudo, df_ultimos, coluna_chave):
        """
        Separa DataFrame em registros com e sem correspondência.
        """
        df_com_dados = df_tudo[df_tudo[coluna_chave].isin(df_ultimos[coluna_chave])]
        df_sem_dados = df_tudo[~df_tudo[coluna_chave].isin(df_ultimos[coluna_chave])]
        return df_com_dados, df_sem_dados

    def cfg_dataframe_to_text(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Converte todo o DataFrame para texto, remove acentos e força uppercase.
        """
        df = df.astype(str)
        for col in df.columns:
            df[col] = df[col].apply(lambda x: self.cfg_remove_acentos(x))
        return df

    def fill_na_with_zero(self, df, coluna):
        """
        Substitui valores nulos da coluna especificada por zero.
        """
        df[coluna] = df[coluna].fillna(0)
        return df

    def cfg_limpar_arquivos_antigos(self):
        """
        Remove arquivos da pasta outputs com mais de 90 dias.
        """
        limite_data = datetime.now() - timedelta(days=90)
        
        for nome_arquivo in os.listdir(self.output_dir):
            caminho = os.path.join(self.output_dir, nome_arquivo)
            if os.path.isfile(caminho):
                if datetime.fromtimestamp(os.path.getmtime(caminho)) < limite_data:
                    os.remove(caminho)
                    Log.logmessage(f"Removido: {caminho}")

    def cfg_criar_pasta_agendador(self, nome_pasta):
        """
        Cria pasta no Agendador de Tarefas do Windows, se não existir.
        """
        scheduler = win32com.client.Dispatch("Schedule.Service")
        scheduler.Connect()
        
        try:
            scheduler.GetFolder(f"\\{nome_pasta}")
            Log.logmessage(f"Pasta '{nome_pasta}' já existe no Agendador.")
        except Exception:
            scheduler.GetFolder("\\").CreateFolder(nome_pasta)
            Log.logmessage(f"Pasta '{nome_pasta}' criada com sucesso.")

    def cfg_task_vcenter(self, nome_arquivo_xml=None, nome_task="Vcenter", nome_pasta=None):
        """
        Verifica e importa uma tarefa agendada a partir de um XML.
        """
        caminho_xml = os.path.join(os.getcwd(), nome_arquivo_xml)
        caminho_task = fr"\{nome_pasta}\{nome_task}"
        
        if not os.path.exists(caminho_xml):
            Log.logmessage(f"❌ Arquivo XML não encontrado: {caminho_xml}")
            return
            
        try:
            check = subprocess.run(
                ["schtasks", "/Query", "/TN", caminho_task],
                capture_output=True,
                text=True
            )
            if check.returncode == 0:
                Log.logmessage(f"ℹ️ Tarefa '{caminho_task}' já existe.")
                return
        except Exception as e:
            Log.logmessage(f"⚠️ Erro ao verificar tarefa: {e}")
            return
            
        try:
            result = subprocess.run(
                ["schtasks", "/Create", "/TN", caminho_task, "/XML", caminho_xml, "/F"],
                check=True,
                capture_output=True,
                text=True
            )
            Log.logmessage(f"✅ Tarefa '{caminho_task}' importada com sucesso.")
            Log.logmessage(result.stdout)
        except subprocess.CalledProcessError as e:
            Log.logmessage(f"❌ Erro ao importar tarefa '{caminho_task}':")
            Log.logmessage(e.stderr)

    def cfg_ler_arquivos(self, file=None):
        """
        Procura arquivos no caminho informado e tenta ler na seguinte ordem:
        CSV → XLSX → XLS.
        
        Todos os arquivos lidos com sucesso são concatenados em um único DataFrame.
        Adiciona a coluna 'nome_arquivo_origem' com o nome do arquivo.
        """
        
        lista_tabela = []
        
        # Lista de extensões na ordem desejada
        extensoes = ["csv", "xlsx", "xls"]
        
        for extensao in extensoes:
            
            # Se já leu arquivos, para (mantém sua regra original)
            if lista_tabela:
                break
                
            try:
                file_list = glob(rf"{file}*.{extensao}")
                
                for f in file_list:
                    try:
                        
                        # ----------------------------------------
                        # Leitura do arquivo
                        # ----------------------------------------
                        if extensao == "csv":
                            df = pd.read_csv(f, encoding="UTF-8", dtype=str)
                        else:
                            df = pd.read_excel(f, dtype=str)
                        
                        # ----------------------------------------
                        # Captura nome do arquivo
                        # ----------------------------------------
                        nome_arquivo = os.path.basename(f)
                        
                        # Adiciona coluna com nome do arquivo
                        df["nome_arquivo_origem"] = nome_arquivo
                        
                        lista_tabela.append(df)
                        
                    except Exception:
                        pass
                        
            except Exception:
                pass
                
        # ----------------------------------------
        # Concatenação final
        # ----------------------------------------
        if lista_tabela:
            return pd.concat(lista_tabela, ignore_index=True)
        
        return pd.DataFrame()

    def cfg_ler_arquivos_com_coluna(
        self,
        caminho=None,
        nome_coluna="cliente",
        separador="_",
        indice_parte=1
    ):
        """
        Lê arquivos e adiciona coluna com parte específica do nome do arquivo.
    
        :param caminho: Caminho base
        :param nome_coluna: Nome da nova coluna
        :param separador: Separador usado no nome do arquivo
        :param indice_parte: Índice da parte que deseja extrair
        :return: DataFrame tratado
        """
    
        df = self.cfg_ler_arquivos(caminho)
    
        if df.empty or "nome_arquivo_origem" not in df.columns:
            return df
    
        def extrair_nome(nome_arquivo):
            # Remove extensão
            nome_sem_extensao = os.path.splitext(nome_arquivo)[0]
    
            partes = nome_sem_extensao.split(separador)
    
            if len(partes) > indice_parte:
                return partes[indice_parte]
    
            return nome_sem_extensao
    
        df[nome_coluna] = df["nome_arquivo_origem"].apply(extrair_nome)
    
        return df
    
if __name__ == '__main__':
    Config()