"""
pip install office365-rest-python-client
==============================================================================
Módulo: sharepoint.py
Descrição:
    Este módulo oferece uma interface simplificada para integração com
    SharePoint Online usando a biblioteca Office365-REST-Python-Client.

    Inclui funcionalidades para:
    - Conexão via Client Credentials
    - Upload e download de arquivos
    - Criação de pastas
    - Exclusão de arquivos
    - Exportação de DataFrames para CSV no SharePoint
    - Movimentação de arquivos do SharePoint para o sistema local

------------------------------------------------------------------------------
Importação:

    from models.sharepoint import SharePoint

------------------------------------------------------------------------------
Instanciação (usando App.config):

    sp = SharePoint()

Ou passando diretamente as credenciais:

    sp = SharePoint(
        id="SEU_CLIENT_ID",
        secret="SEU_CLIENT_SECRET",
        url="https://seudominio.sharepoint.com/sites/nomedosite"
    )

------------------------------------------------------------------------------
Exemplos de uso:

# Criar uma pasta
sp.criar_pasta("Relatorios/2025")

# Enviar um arquivo para uma pasta
sp.salvar_arquivo("relatorio.pdf", "Documents/Relatorios/2025")

# Deletar um arquivo específico
sp.deletar_arquivo("Documents/Relatorios/2025/relatorio.pdf")

# Enviar ou substituir um arquivo de log
sp.enviar_log("log.txt", "Documents/Logs")

# Exportar um DataFrame como CSV para o SharePoint
import pandas as pd
df = pd.DataFrame({"coluna": [1, 2, 3]})
sp.exportar_csv(df, tabela="dados", dia="2025-10-02", remote_folder="Documents/CSVs")

# Mover todos os arquivos de uma pasta do SharePoint para o desktop e deletar da origem
sp.mover_arquivos("Documents/etl_capacity/intragov/links", "C:/Downloads/ArquivosIntragov")

------------------------------------------------------------------------------
Dependências:
    - office365-rest-python-client
    - pandas
    - xml.etree.ElementTree (built-in)
    - models.logger.Log (classe de logging personalizada)

==============================================================================
"""


import warnings
warnings.filterwarnings("ignore")  # Ignora warnings do Office365 SDK

# Importações necessárias
from office365.sharepoint.client_context        import ClientContext
from office365.sharepoint.files.file            import File
from office365.runtime.auth.client_credential   import ClientCredential
from office365.runtime.client_request_exception import ClientRequestException
from models.logger                              import Log  # Classe de logging personalizada
from models.app                                 import App
from models.configuracoes                       import Config
import io
import os
import pandas             as pd

cfg = Config()
ap = App()


# -----------------------------------------------------------------------------
# Classe SharePoint: herda de App e gerencia ações no SharePoint
# -----------------------------------------------------------------------------

class SharePoint():

    def __init__(self, id=None, secret=None, url=None, fin=False):
        super().__init__()
    
        creds  = ap.key_sharepoint()
        id     = id     or creds['client_id_sharepoint']
        secret = secret or creds['client_secret_sharepoint']
        url    = creds.get('site_url_sharepoint_fin') if fin else creds['site_url_sharepoint']
    
        self.client_id     = id
        self.client_secret = secret
        self.site_url      = url
    
        ctx = self._conectar(self.site_url)
        if ctx:
            self.ctx = ctx
            return
    
        Log.logmessage("[SHAREPOINT] Todas as tentativas de conexão falharam.")
        raise Exception("Não foi possível conectar ao SharePoint.")
    
    def _conectar(self, url):
        """Tenta conectar em uma URL: primeiro com proxy, depois sem proxy."""
        for descricao, configurar in [("com proxy", cfg.cfg_proxy), ("sem proxy", cfg.cfg_no_proxy)]:
            try:
                configurar()
                ctx = ClientContext(url).with_credentials(
                    ClientCredential(self.client_id, self.client_secret)
                )
                ctx.web.get().execute_query()
                Log.logmessage(f"[SHAREPOINT] Conectado {descricao} → {url}")
                return ctx
            except Exception as e:
                Log.logmessage(f"[SHAREPOINT] Falhou {descricao} → {url}: {e}")
        return None

    def criar_pasta          (self, nome_pasta, pasta_raiz):
        """
        Cria uma nova pasta no SharePoint. Caso já exista, apenas retorna a pasta.
        """
        full_path = f"{pasta_raiz}/{nome_pasta}"
        
        try:
            folder = self.ctx.web.get_folder_by_server_relative_url(full_path)
            self.ctx.load(folder)
            self.ctx.execute_query()
            Log.logmessage(f"Pasta já existe: {full_path}")
            return folder
        except Exception:
            # Cria a pasta se não existir
            folder = self.ctx.web.folders.add(full_path)
            self.ctx.execute_query()
            Log.logmessage(f"Pasta criada: {full_path}")
            return folder

    def excluir_pasta        (self, nome_pasta, pasta_raiz):
        """
        Exclui uma pasta no SharePoint.
        """
        full_path = f"{pasta_raiz}/{nome_pasta}"
        
        try:
            # Acessa a pasta
            folder = self.ctx.web.get_folder_by_server_relative_url(full_path)
            self.ctx.load(folder)
            self.ctx.execute_query()
            
            # Deleta a pasta
            folder.delete_object()
            self.ctx.execute_query()
            
            Log.logmessage(f"Pasta deletada: {full_path}")
            
        except Exception as e:
            Log.logmessage(f"Erro ao deletar pasta {full_path}: {str(e)}")

    def salvar_arquivo       (self, local_file, destino):
        """
        Faz upload de um arquivo local para uma pasta no SharePoint.
        """
        with open(local_file, "rb") as f:
            file_content = f.read()

        target_folder = self.ctx.web.get_folder_by_server_relative_url(destino)
        target_file = target_folder.upload_file(
            os.path.basename(local_file),
            file_content
        ).execute_query()

        Log.logmessage(f"Arquivo salvo: {target_file.serverRelativeUrl}")

    def deletar_arquivo      (self, caminho_arquivo):
        """
        Remove um arquivo do SharePoint. Se não existir, apenas registra no log.
        """
        try:
            file = self.ctx.web.get_file_by_server_relative_url(caminho_arquivo)
            file.delete_object()
            self.ctx.execute_query()
            Log.logmessage(f"Arquivo deletado: {caminho_arquivo}")
        except:
            Log.logmessage('Arquivo não localizado ou não existe')

    def enviar_log           (self, local_file, remote_folder, remote_file_name=None):
        """
        Envia (ou substitui) um arquivo de log para uma pasta no SharePoint.
        """
        if remote_file_name is None:
            remote_file_name = os.path.basename(local_file)
        
        remote_path = f"{remote_folder}/{remote_file_name}"
        
        try:
            # Deleta o arquivo antigo, se existir
            file = self.ctx.web.get_file_by_server_relative_url(remote_path)
            file.delete_object()
            self.ctx.execute_query()
            Log.logmessage(f"Arquivo existente removido: {remote_path}")
        except Exception:
            pass  # Ignora se o arquivo não existir
        
        # Envia novo arquivo
        self.salvar_arquivo(local_file, remote_folder)
        Log.logmessage(f"Arquivo enviado: {remote_path}")

    def exportar_csv_com_data(self, df, tabela, dia, remote_folder):
        """
        Exporta um DataFrame como CSV para o SharePoint, substituindo se já existir.
        """
        import io
        
        with io.StringIO() as buffer:
            df.to_csv(buffer, encoding='UTF-8', sep=',', index=False, float_format='%.2f')
            buffer.seek(0)
            
            file_name = f"{tabela}_{dia}.csv"
            
            # Remove arquivo anterior (se existir)
            self.deletar_arquivo(f"{remote_folder}/{file_name}")
            
            # Envia novo CSV
            file_content = buffer.getvalue().encode('utf-8')
            self.ctx.web.get_folder_by_server_relative_url(remote_folder).upload_file(
                file_name, file_content
            ).execute_query()
            
            Log.logmessage(f"Arquivo CSV exportado para SharePoint: {remote_folder}/{file_name}")

    def exportar_csv_sem_data(self, df, tabela, remote_folder):
        """
        Exporta um DataFrame como CSV para o SharePoint, substituindo se já existir.
        """
        import io
        
        with io.StringIO() as buffer:
            df.to_csv(buffer, encoding='UTF-8', sep=';', index=False, float_format='%.2f')
            buffer.seek(0)
            
            file_name = f"{tabela}.csv"
            
            # Remove arquivo anterior (se existir)
            self.deletar_arquivo(f"{remote_folder}/{file_name}")
            
            # Envia novo CSV
            file_content = buffer.getvalue().encode('utf-8')
            self.ctx.web.get_folder_by_server_relative_url(remote_folder).upload_file(
                file_name, file_content
            ).execute_query()
            
            Log.logmessage(f"Arquivo CSV exportado para SharePoint: {remote_folder}/{file_name}")

    def coletar_arquivos     (self, pasta_sharepoint, pasta_local):
        """
        Baixa todos os arquivos de uma pasta do SharePoint para o desktop
        e depois remove os arquivos da origem.
        """
        try:
            # Garante que a pasta local exista
            if not os.path.exists(pasta_local):
                os.makedirs(pasta_local)
            
            # Acessa pasta do SharePoint
            folder = self.ctx.web.get_folder_by_server_relative_url(pasta_sharepoint)
            self.ctx.load(folder)
            self.ctx.execute_query()
            
            # Lista arquivos da pasta
            arquivos = folder.files
            self.ctx.load(arquivos)
            self.ctx.execute_query()
            
            if not arquivos:
                Log.logmessage("Nenhum arquivo encontrado na pasta do SharePoint.")
                return
                
            for arquivo in arquivos:
                nome_arquivo = arquivo.properties["Name"]
                url_relativa = arquivo.properties["ServerRelativeUrl"]
                
                # Baixa conteúdo
                conteudo = arquivo.read()
                
                # Caminho onde será salvo localmente
                caminho_local = os.path.join(pasta_local, nome_arquivo)
                
                with open(caminho_local, "wb") as f:
                    f.write(conteudo)
                
                Log.logmessage(f"Arquivo salvo localmente: {caminho_local}")
                
                # Tenta remover do SharePoint
                try:
                    arquivo.delete_object()
                    self.ctx.execute_query()
                    Log.logmessage(f"Arquivo deletado do SharePoint: {url_relativa}")
                except ClientRequestException as e:
                    Log.logmessage(f"Erro ao deletar {nome_arquivo}: {str(e)}")
                    
        except Exception as e:
            Log.logmessage(f"Erro ao mover arquivos: {str(e)}")

    def enviar_arquivos      (self, pasta_local, pasta_sharepoint):
        """
        Envia arquivos para o SharePoint (suporta arquivos grandes)
        e remove os arquivos locais após upload.
        """
        try:
            if not os.path.exists(pasta_local):
                Log.logmessage("Pasta local não encontrada.")
                return
                
            folder = self.ctx.web.get_folder_by_server_relative_url(pasta_sharepoint)
            self.ctx.load(folder)
            self.ctx.execute_query()
            
            arquivos = os.listdir(pasta_local)
            
            if not arquivos:
                Log.logmessage("Nenhum arquivo encontrado na pasta local.")
                return
                
            for nome_arquivo in arquivos:
                caminho_local = os.path.join(pasta_local, nome_arquivo)
                
                if not os.path.isfile(caminho_local):
                    continue
                    
                tamanho_arquivo = os.path.getsize(caminho_local)
                    
                try:
                    import uuid
                    from office365.sharepoint.files.file import File
                    
                    with open(caminho_local, "rb") as f:
                        
                        # 🔥 Arquivo pequeno
                        if tamanho_arquivo < 250 * 1024 * 1024:
                            folder.upload_file(nome_arquivo, f.read())
                            self.ctx.execute_query()
                            
                        # 🔥 Arquivo grande (upload em partes estável)
                        else:
                            chunk_size = 10 * 1024 * 1024  # 10MB
                            upload_id = str(uuid.uuid4())
                            
                            server_relative_url = folder.serverRelativeUrl + "/" + nome_arquivo
                            file = File(self.ctx, server_relative_url)
                            
                            offset = 0
                            
                            # START
                            chunk = f.read(chunk_size)
                            file.start_upload(upload_id, chunk)
                            self.ctx.execute_query()
                            offset += len(chunk)
                            
                            # CONTINUE
                            while True:
                                chunk = f.read(chunk_size)
                                if not chunk:
                                    break
                                    
                                file.continue_upload(upload_id, offset, chunk)
                                self.ctx.execute_query()
                                
                                offset += len(chunk)
                                
                            # FINISH
                            file.finish_upload(upload_id, offset)
                            self.ctx.execute_query()
                            
                    Log.logmessage(f"Arquivo enviado: {nome_arquivo}")
                            
                except Exception as e:
                    Log.logmessage(f"Erro ao enviar {nome_arquivo}: {str(e)}")
                    continue
                    
                # Remove arquivo local
                try:
                    os.remove(caminho_local)
                    Log.logmessage(f"Arquivo removido localmente: {caminho_local}")
                except Exception as e:
                    Log.logmessage(f"Erro ao deletar local {nome_arquivo}: {str(e)}")
                    
        except Exception as e:
            Log.logmessage(f"Erro geral ao enviar arquivos: {str(e)}")

    def ler_csv              (self, pasta_sharepoint, palavra_chave):
        """
        Lê todos os arquivos CSV em uma pasta do SharePoint que contenham a palavra-chave no nome
        e retorna um DataFrame único com todos os dados concatenados.
        """
        
        try:
            # Acessa a pasta no SharePoint
            folder = self.ctx.web.get_folder_by_server_relative_url(pasta_sharepoint)
            self.ctx.load(folder)
            self.ctx.execute_query()
            
            arquivos = folder.files
            self.ctx.load(arquivos)
            self.ctx.execute_query()
            
            if not arquivos:
                Log.logmessage(f"Nenhum arquivo encontrado em: {pasta_sharepoint}")
                return pd.DataFrame()
                
            dfs = []
            
            for arquivo in arquivos:
                nome_arquivo = arquivo.properties["Name"]
                url_relativa = arquivo.properties["ServerRelativeUrl"]
                
                if palavra_chave.lower() in nome_arquivo.lower() and nome_arquivo.endswith(".csv"):
                    conteudo = arquivo.read()
                    buffer = io.StringIO(conteudo.decode('utf-8'))
                    df = pd.read_csv(buffer)
                    dfs.append(df)
                    Log.logmessage(f"Arquivo lido: {nome_arquivo}")
                    
            if dfs:
                df = pd.concat(dfs, ignore_index=True)
                Log.logmessage(f"{len(dfs)} arquivos unificados contendo a palavra-chave '{palavra_chave}'.")
                return df
            else:
                Log.logmessage(f"Nenhum arquivo com a palavra-chave '{palavra_chave}' encontrado.")
                return pd.DataFrame()
                
        except Exception as e:
            Log.logmessage(f"Erro ao ler arquivos CSV do SharePoint: {str(e)}")
            return pd.DataFrame()

    def listar_pastas        (self, pasta_sharepoint):
        """
        Lista todas as subpastas dentro de uma pasta no SharePoint.
        Retorna uma lista com os nomes das pastas.
        """
        try:
            folder = self.ctx.web.get_folder_by_server_relative_url(pasta_sharepoint)
            self.ctx.load(folder)
            self.ctx.execute_query()
    
            subpastas = folder.folders
            self.ctx.load(subpastas)
            self.ctx.execute_query()
    
            if not subpastas:
                Log.logmessage(f"Nenhuma subpasta encontrada em: {pasta_sharepoint}")
                return []
    
            nomes = []
            for pasta in subpastas:
                nome = pasta.properties["Name"]
                nomes.append(nome)
                Log.logmessage(f"Pasta encontrada: {nome}")
    
            return nomes
    
        except Exception as e:
            Log.logmessage(f"Erro ao listar pastas: {str(e)}")
            return []

    def listar_arquivos_csv(self, pasta_sharepoint):
        """
        Lista todos os arquivos CSV dentro de uma pasta no SharePoint.
        Retorna uma lista com os nomes dos arquivos.
        """
        try:
            folder = self.ctx.web.get_folder_by_server_relative_url(pasta_sharepoint)
            self.ctx.load(folder)
            self.ctx.execute_query()
    
            arquivos = folder.files
            self.ctx.load(arquivos)
            self.ctx.execute_query()
    
            if not arquivos:
                Log.logmessage(f"Nenhum arquivo encontrado em: {pasta_sharepoint}")
                return []
    
            nomes = []
            for arquivo in arquivos:
                nome = arquivo.properties["Name"]
    
                # Filtra apenas arquivos CSV
                if nome.lower().endswith(".csv"):
                    nomes.append(nome)
                    Log.logmessage(f"Arquivo CSV encontrado: {nome}")
    
            return nomes
    
        except Exception as e:
            Log.logmessage(f"Erro ao listar arquivos CSV: {str(e)}")
            return []

    def ler_oracle(self, pasta_sharepoint, palavra_chave=None):
    
        lista_tabela = []
        extensoes = ["csv", "xlsx", "xls"]
    
        try:
            folder = self.ctx.web.get_folder_by_server_relative_url(pasta_sharepoint)
            self.ctx.load(folder)
            self.ctx.execute_query()
    
            arquivos = folder.files
            self.ctx.load(arquivos)
            self.ctx.execute_query()
    
            if not arquivos:
                Log.logmessage(f"Nenhum arquivo encontrado em: {pasta_sharepoint}")
                return pd.DataFrame()
    
            for extensao in extensoes:
    
                for arquivo in arquivos:
    
                    nome_arquivo = arquivo.properties["Name"]
    
                    if not nome_arquivo.lower().endswith(extensao):
                        continue
    
                    if palavra_chave and palavra_chave.lower() not in nome_arquivo.lower():
                        continue
    
                    try:
    
                        conteudo = arquivo.read()
    
                        # leitura
                        if extensao == "csv":
                            buffer = io.StringIO(conteudo.decode("utf-8"))
                            df = pd.read_csv(buffer, dtype=str, engine='python',decimal='.')
                        else:
                            buffer = io.BytesIO(conteudo)
                            df = pd.read_excel(buffer, dtype=str)
    
                        df = pd.DataFrame(df)
    
                        if df.empty:
                            continue
    
                        # remove coluna total
                        df = df.loc[:, ~df.columns.astype(str).str.contains("total", case=False, na=False)]
    
                        # remove linha total
                        primeira_coluna = df.columns[0]
                        df = df[
                            ~df[primeira_coluna]
                            .astype(str)
                            .str.contains("total", case=False, na=False)
                        ]
    
                        # renomeia data
                        df = df.rename(columns={primeira_coluna: "data"})
    
                        # wide -> long
                        df = df.melt(
                            id_vars="data",
                            var_name="coluna",
                            value_name="valor"
                        )
    
                        # produto e serviço
                        df["produto"] = df["coluna"].astype(str).str.split("/", n=1).str[0].str.strip()
                        df["servico"] = df["coluna"].astype(str).str.split("/", n=1).str[1].str.strip()
    
                        df = df[["data", "produto", "servico", "valor"]]
    
                        lista_tabela.append(df)
    
                        Log.logmessage(f"Arquivo lido e tratado: {nome_arquivo}")
    
                    except Exception as e:
                        Log.logmessage(f"Erro ao ler {nome_arquivo}: {str(e)}")
    
            if lista_tabela:
                return pd.concat(lista_tabela, ignore_index=True)
    
            return pd.DataFrame()
    
        except Exception as e:
            Log.logmessage(f"Erro ao acessar pasta {pasta_sharepoint}: {str(e)}")
            return pd.DataFrame()

    def ler_auditoria(self, pasta_sharepoint, palavra_chave=None):
    
        lista_tabela = []
        extensoes = ["csv", "xlsx", "xls"]
    
        try:
            folder = self.ctx.web.get_folder_by_server_relative_url(pasta_sharepoint)
            self.ctx.load(folder)
            self.ctx.execute_query()
    
            arquivos = folder.files
            self.ctx.load(arquivos)
            self.ctx.execute_query()
    
            if not arquivos:
                Log.logmessage(f"Nenhum arquivo encontrado em: {pasta_sharepoint}")
                return pd.DataFrame()
    
            for extensao in extensoes:
    
                if lista_tabela:
                    break
    
                for arquivo in arquivos:
    
                    nome_arquivo = arquivo.properties["Name"]
    
                    if not nome_arquivo.lower().endswith(extensao):
                        continue
    
                    if palavra_chave and palavra_chave.lower() not in nome_arquivo.lower():
                        continue
    
                    try:
                        conteudo = arquivo.read()
    
                        # ----------------------------------------
                        # Leitura conforme extensão
                        # ----------------------------------------
                        if extensao == "csv":
                            buffer = io.StringIO(conteudo.decode("utf-8"))
                            df = pd.read_csv(buffer, header=None, sep=None, engine='python', decimal=',', dtype=str)
    
                        else:
                            buffer = io.BytesIO(conteudo)
                            df = pd.read_excel(buffer, header=None, dtype=str)
    
                        # ----------------------------------------
                        # TRATAMENTO DO ARQUIVO (antes de unificar)
                        # ----------------------------------------
    
                        # pega as duas primeiras linhas
                        linha_account_id = df.iloc[0]
                        linha_account_name = df.iloc[1]
    
                        contas = pd.DataFrame({
                            "account_id": linha_account_id,
                            "account_name": linha_account_name
                        })
    
                        # remove as duas primeiras linhas
                        df = df.iloc[2:].reset_index(drop=True)
    
                        # primeira coluna vira data
                        df = df.rename(columns={0: "data"})
    
                        # wide -> long
                        df_long = df.melt(
                            id_vars="data",
                            var_name="coluna",
                            value_name="valor"
                        )
    
                        # junta metadados das contas
                        df = df_long.merge(
                            contas.reset_index().rename(columns={"index": "coluna"}),
                            on="coluna",
                            how="left"
                        )
    
                        # colunas finais
                        df = df[["data", "account_id", "account_name", "valor"]]
                        df['projeto'] = nome_arquivo.split('_')[0]
                        primeira_coluna = df.columns[0]

                        # remove linhas que contenham "total" na primeira coluna
                        df = df[~df[primeira_coluna].astype(str).str.contains('total', case=False, na=False)]
    
                        # ----------------------------------------
                        # adiciona nome do arquivo origem
                        # ----------------------------------------
                        #df["nome_arquivo_origem"] = nome_arquivo
    
                        lista_tabela.append(df)
    
                        Log.logmessage(f"Arquivo lido e tratado: {nome_arquivo}")
    
                    except Exception as e:
                        Log.logmessage(f"Erro ao ler {nome_arquivo}: {str(e)}")
    
            if lista_tabela:
                return pd.concat(lista_tabela, ignore_index=True)
    
            return pd.DataFrame()
    
        except Exception as e:
            Log.logmessage(f"Erro ao acessar pasta {pasta_sharepoint}: {str(e)}")
            return pd.DataFrame()

    def ler_arquivos(self, pasta_sharepoint, palavra_chave=None):
        """
        Procura arquivos no SharePoint na seguinte ordem:
        CSV → XLSX → XLS.
    
        Lê todos os arquivos encontrados da primeira extensão válida,
        concatena em um único DataFrame e adiciona a coluna
        'nome_arquivo_origem'.
        """
    
        lista_tabela = []
        extensoes = ["csv", "xlsx", "xls"]
    
        try:
            folder = self.ctx.web.get_folder_by_server_relative_url(pasta_sharepoint)
            self.ctx.load(folder)
            self.ctx.execute_query()
    
            arquivos = folder.files
            self.ctx.load(arquivos)
            self.ctx.execute_query()
    
            if not arquivos:
                Log.logmessage(f"Nenhum arquivo encontrado em: {pasta_sharepoint}")
                return pd.DataFrame()
    
            for extensao in extensoes:
    
                if lista_tabela:
                    break
    
                for arquivo in arquivos:
    
                    nome_arquivo = arquivo.properties["Name"]
    
                    if not nome_arquivo.lower().endswith(extensao):
                        continue
    
                    if palavra_chave and palavra_chave.lower() not in nome_arquivo.lower():
                        continue
    
                    try:
                        conteudo = arquivo.read()
    
                        # ----------------------------------------
                        # Leitura conforme extensão
                        # ----------------------------------------
                        if extensao == "csv":
                            buffer = io.StringIO(conteudo.decode("utf-8"))
                            df = pd.read_csv(buffer, dtype=str)
                        else:
                            buffer = io.BytesIO(conteudo)
                            df = pd.read_excel(buffer, dtype=str)
    
                        # ----------------------------------------
                        # Adiciona nome do arquivo
                        # ----------------------------------------
                        df["nome_arquivo_origem"] = nome_arquivo
    
                        lista_tabela.append(df)
    
                        Log.logmessage(f"Arquivo lido: {nome_arquivo}")
    
                    except Exception as e:
                        Log.logmessage(f"Erro ao ler {nome_arquivo}: {str(e)}")
    
            if lista_tabela:
                return pd.concat(lista_tabela, ignore_index=True)
    
            return pd.DataFrame()
    
        except Exception as e:
            Log.logmessage(f"Erro ao acessar pasta {pasta_sharepoint}: {str(e)}")
            return pd.DataFrame()

if __name__ == '__main__':
    SharePoint()
