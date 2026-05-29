from pyodbc import connect
from models.logger import Log
from models.orquestrador import etapa
import pandas as pd



class DataBase:
    def __init__(self):
        self.cursor = None
        
    @etapa(nome='conexão com o banco de dados')
    def conectar(self, driver: str):
        self.cursor = connect(driver).cursor()
        print('conectado')

    @etapa(nome='Desconexão com o banco de dados')
    def desconectar(self):
        if self.cursor:
            self.cursor.close()
            print('desconectado')

    @etapa(nome='Executando consulta')
    def executar(self, query, commit=False):
        try:
            if self.cursor:
                self.cursor.execute(query)
                if commit:
                    self.cursor.commit()
        except Exception as e:
            print(f'[ERRO] : Não foi possível realizar a consulta. Erro: {e}')

    @etapa(nome='Transformando consulta em dataframe')
    def consulta_dataframe(self, query):
        if not self.cursor:
            raise Exception("[ERRO] Conexão com o banco não foi feita. db.cursor está None.")
        conn = self.cursor.connection  # ou armazene self.conn direto na conexão
        return pd.read_sql(query, conn)

    @etapa(nome='Inserindo dataframe ao banco de dados')
    def inserir_df(self, tabela, df):
        
        if self.cursor is None:
            raise Exception("[ERRO] Cursor não inicializado.")
    
        # Cria a lista de colunas com colchetes
        colunas = ", ".join(f"[{col}]" for col in df.columns)
        placeholders = ", ".join(["?"] * len(df.columns))
        sql = f"INSERT INTO [{tabela}] ({colunas}) VALUES ({placeholders})"
    
        try:
            # Loop linha a linha para identificar erro
            for i, row in enumerate(df.itertuples(index=False, name=None), start=1):
                try:
                    self.cursor.execute(sql, row)
                except Exception as e:
                    Log.logmessage(f"[ERRO] Linha {i} falhou → {e}")
                    for j, valor in enumerate(row, start=1):
                        try:
                            _ = float(valor) if isinstance(valor, (int, float, str)) else valor
                        except Exception:
                            Log.logmessage(f"   👉 Coluna {df.columns[j-1]} = {valor} inválido para float")
                    raise  # para parar na primeira falha
    
            self.cursor.commit()
            Log.logmessage(f"[OK] Inseridas {len(df)} linhas na tabela '{tabela}'.")
    
        except Exception as e:
            Log.logmessage(f"[ERRO] Falha geral: {e}")

    @etapa(nome='Deletando informações da tabela de acordo com o ID')
    def deletar_id(self, tabela, df, id_tab='id_tab'):
        try:
            if df.empty:
                Log.logmessage(f"[AVISO] DataFrame vazio, nenhum {id_tab} para deletar.")
                return
    
            if id_tab not in df.columns:
                raise ValueError(f"Coluna '{id_tab}' não encontrada no DataFrame.")
    
            # Obtem os valores únicos de id_tab
            valores = df[id_tab].dropna().astype(str).unique().tolist()
    
            if not valores:
                Log.logmessage(f"[AVISO] Nenhum valor válido em '{id_tab}' para deletar.")
                return
    
            # Monta a query com parâmetros
            placeholders = ', '.join(['?'] * len(valores))  # Para pyodbc com SQL Server
            query = f"DELETE FROM {tabela} WHERE {id_tab} IN ({placeholders})"
    
            # Executa o delete
            self.cursor.execute(query, valores)
            self.cursor.commit()
    
            Log.logmessage(f"[SUCESSO] {len(valores)} registros deletados da tabela {tabela} com base no campo '{id_tab}'.")
    
        except Exception as e:
            Log.logmessage(f"[ERRO] Falha ao deletar registros na tabela {tabela}: {e}")

    @etapa(nome='Organizando as colunas do dataframe de acordo com a estrutura da tabela')
    def organizar_df(self, tabela, df):
        try:
            # Recupera o esquema da tabela do banco (nome das colunas)
            query = f"SELECT TOP 0 * FROM {tabela}"  # SQL Server; para outros bancos, pode ser LIMIT 0
            self.cursor.execute(query)
            colunas_banco = [column[0] for column in self.cursor.description]
    
            # Mantém apenas as colunas que existem na tabela e reorganiza a ordem
            df_organizado = df[[col for col in colunas_banco if col in df.columns]]
    
            Log.logmessage(f"[SUCESSO] DataFrame reorganizado conforme estrutura da tabela {tabela}")
            return df_organizado
    
        except Exception as e:
            Log.logmessage(f"[ERRO] Falha ao organizar DataFrame com base na tabela {tabela}: {e}")
            return df

    @etapa(nome='Deletando informações da tabela de acorodo com o dataframe')
    def deletar_informacoes(self, tabela, df):
        try:
            if df.empty:
                Log.logmessage(f"[AVISO] DataFrame vazio, nada será deletado da tabela {tabela}.")
                return
    
            df = df.drop_duplicates()
            colunas = list(df.columns)
    
            for _, linha in df.iterrows():
                condicoes = []
    
                for col in colunas:
                    valor = linha[col]
    
                    if pd.isna(valor):
                        condicoes.append(f"{col} IS NULL")
                    else:
                        # Trata como string qualquer valor que tenha `:` ou `-` (ex: horas, datas)
                        if isinstance(valor, str) or any(x in str(valor) for x in [":", "-"]):
                            valor = str(valor).replace("'", "''")
                            condicoes.append(f"{col} = '{valor}'")
                        else:
                            condicoes.append(f"{col} = {valor}")
    
                where_clause = " AND ".join(condicoes)
                delete_sql = f"DELETE FROM {tabela} WHERE {where_clause}"
                print("[DEBUG] SQL ->", delete_sql)  # opcional
                self.cursor.execute(delete_sql)
    
            self.cursor.commit()
            Log.logmessage(f"[SUCESSO] Linhas deletadas da tabela {tabela} com base no DataFrame.")
    
        except Exception as e:
            Log.logmessage(f"[ERRO] Não foi possível deletar linhas da tabela {tabela}: {e}")

    @etapa(nome='Criando tabela automaticamente através de uma dataframe')
    def criar_tabela_df(self, tabela, df: pd.DataFrame):
        """
        Cria uma tabela no banco com base nas colunas do DataFrame,
        usando NVARCHAR(MAX) em todas as colunas, e insere os dados.
        """
        try:
            if df.empty:
                Log.logmessage(f"[AVISO] DataFrame vazio, tabela {tabela} não será criada.")
                return

            # Monta comando de criação da tabela
            colunas_def = ", ".join(f"[{col}] NVARCHAR(MAX)" for col in df.columns)
            create_sql = f"IF OBJECT_ID('{tabela}', 'U') IS NOT NULL DROP TABLE {tabela}; CREATE TABLE {tabela} ({colunas_def});"

            # Cria tabela
            self.cursor.execute(create_sql)
            self.cursor.commit()

            # Insere os dados
            self.inserir_df(tabela, df)
            self.cursor.commit()

            Log.logmessage(f"[SUCESSO] Tabela {tabela} criada e populada com {len(df)} registros.")

        except Exception as e:
            Log.logmessage(f"[ERRO] Falha ao criar tabela {tabela} a partir do DataFrame: {e}")

    @etapa(nome='Transformando dados do dataframe de acordo com a tipagem do dado da tabela')
    def validar_dados(self, tabela, df):
        try:
            if self.cursor is None:
                raise Exception("[ERRO] Cursor não inicializado.")
    
            query = f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{tabela}'
            """
            schema = pd.read_sql(query, self.cursor.connection)
    
            tipos = dict(zip(schema['COLUMN_NAME'], schema['DATA_TYPE']))
    
            for coluna, tipo in tipos.items():
    
                if coluna not in df.columns:
                    continue
    
                tipo = tipo.lower()
    
                if tipo in ['float', 'real']:
                    df[coluna] = pd.to_numeric(df[coluna], errors='coerce')
                    Log.logmessage(f'[DATABASE] : A COLUNA {coluna} FOI CONVERTIDA PARA NUMERICO')
                
                elif tipo in ['int', 'bigint', 'smallint', 'tinyint']:
                    df[coluna] = pd.to_numeric(df[coluna], errors='coerce').astype('Int64')
                    Log.logmessage(f'[DATABASE] : A COLUNA {coluna} FOI CONVERTIDA PARA INTEIRO')
                
                elif tipo in ['decimal', 'numeric', 'money', 'smallmoney']:
                    df[coluna] = pd.to_numeric(df[coluna], errors='coerce')
                    Log.logmessage(f'[DATABASE] : A COLUNA {coluna} FOI CONVERTIDA PARA DECIMAL')
                
                elif tipo in ['date', 'datetime', 'datetime2', 'smalldatetime']:
                    df[coluna] = pd.to_datetime(df[coluna], errors='coerce')
                    Log.logmessage(f'[DATABASE] : A COLUNA {coluna} FOI CONVERTIDA PARA DATA')
                
                elif tipo in ['bit']:
                    df[coluna] = df[coluna].astype('boolean')
                    Log.logmessage(f'[DATABASE] : A COLUNA {coluna} FOI CONVERTIDA PARA BOOLEAN')
                
                elif tipo in ['varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext']:
                    df[coluna] = df[coluna].astype(str)
                    Log.logmessage(f'[DATABASE] : A COLUNA {coluna} FOI CONVERTIDA PARA TEXTO')
                
                else:
                    df[coluna] = df[coluna].astype(str)
                    Log.logmessage(f'[DATABASE] : A COLUNA {coluna} FOI CONVERTIDA PARA STRING (PADRAO)')
            #df = df.where(pd.notnull(df), None)
            Log.logmessage(f"[SUCESSO] DataFrame validado conforme estrutura da tabela {tabela}")
            return df
    
        except Exception as e:
            Log.logmessage(f"[ERRO] Falha ao validar dados do DataFrame com base na tabela {tabela}: {e}")
            return df
        
    @etapa(nome='Padronizando as colunas do dataframe a partir da tabela', descricao='Elimina colunas não mapeadas na tabela')
    def alinhar_colunas(self, tabela, df):
        try:
            if self.cursor is None:
                raise Exception("[ERRO] Cursor não inicializado.")
    
            # Busca colunas da tabela no banco
            query = f"""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{tabela}'
            """
            schema = pd.read_sql(query, self.cursor.connection)
            colunas_banco = set(schema['COLUMN_NAME'].tolist())
    
            # Identifica colunas extras no DataFrame
            colunas_df = set(df.columns)
            colunas_extras = colunas_df - colunas_banco
    
            # Remove colunas que não existem na tabela
            for col in colunas_extras:
                df.drop(columns=[col], inplace=True)
                Log.logmessage(f"[DATABASE] : A COLUNA {col} FOI ELIMINADA DO DATAFRAME (NÃO EXISTE NA TABELA {tabela})")
    
            Log.logmessage(f"[SUCESSO] DataFrame alinhado com a estrutura da tabela {tabela}")
            return df
    
        except Exception as e:
            Log.logmessage(f"[ERRO] Falha ao alinhar colunas do DataFrame com a tabela {tabela}: {e}")
            return df
        
if __name__ =='__main__':
    DataBase()