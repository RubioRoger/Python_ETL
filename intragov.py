# LER ARQUIVOS APARTIR DA PASTA ARQUIVOS
# MIGRAR APENAS OS ARQUIVOS PROCESSADOS SEM ERRO

from models.app           import App
from models.configuracoes import Config
from models.database      import DataBase
from models.logger        import Log
import numpy              as np
import pandas as pd
import calendar  
import unidecode

app = App()
cfg = Config()
dbo = DataBase()
log = Log()

key = app.key_db('prod')

class run():

    def status_conclusao                     (self,row): 
        if pd.isna(row['TEMPO_CONCLUSAO_DIA']) or row['META'] == 0:
            return 'Não classificado'
        elif row['TEMPO_CONCLUSAO_DIA'] <= row['META']:
            return 'Dentro conclusao'
        elif row['TEMPO_CONCLUSAO_DIA'] > row['META']:
            return 'Fora conclusao'
        else:
            return 'invalido'

    def mapear_mes                           (self):        
        self.mes_map = {
        'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 'mai': '05', 'jun': '06',
        'jul': '07', 'ago': '08', 'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
        }

    def capacidade_nominal                   (self,x):
        if x == 622000:
            return '622 Mbps'
        elif x == 2000:
            return '2 Mbps'
        elif x == 8000:
            return '8 Mbps'
        elif x == 1000:
            return '1 Mbps'
        elif x == 4000:
            return '4 Mbps'
        elif x == 16000:
            return '16 Mbps'
        elif x == 34000:
            return '34 Mbps'
        elif x == 2500000:
            return '2,5 Gbps'
        elif x == 10000:
            return '10 Mbps'
        elif x == 512:
            return '512 Kbps'
        elif x == 300000:
            return '300 Mbps'
        else:
            return ''

    def parada_segundos                      (self,tempo):
        if pd.isna(tempo) or tempo.strip() == '' or tempo == '00:00:00':
            return 0
        try:
            h, m, s = map(int, tempo.split(':'))
            return h * 3600 + m * 60 + s
        except:
            return 0  # fallback se tiver algum valor inválido

    def formato_padrao                       (self,tempo):
        if pd.isna(tempo) or tempo == 0 or tempo == '0':
            return '00:00:00'
        
        # Se for no formato decimal (ex: 0.2654)
        if isinstance(tempo, (float, int)) or (isinstance(tempo, str) and '.' in tempo):
            horas = int(tempo)
            minutos = int((tempo - horas) * 60)
            segundos = int(((tempo - horas) * 60 - minutos) * 60)
            return f"{horas:02}:{minutos:02}:{segundos:02}"
        
        # Se for no formato HH:MM:SS
        try:
            # Tenta converter a string no formato de tempo
            t = pd.to_datetime(tempo, format='%H:%M:%S')
            return t.strftime('%H:%M:%S')
        except:
            return '00:00:00'  # Se houver erro (formato inválido), retorna '00:00:00'

    def dias_no_mes                          (self,data):
        if pd.isna(data):
            return 0
        return calendar.monthrange(data.year, data.month)[1]

    def valores                              (self):
        log.logmessage('[---INCIDENTES----] : CONEXÃO COM O  BANCO')
        dbo.conectar(key)

        log.logmessage('[---INCIDENTES----] : COLETANDO TABELA DE VALORES')
        self.df_valores = dbo.consulta_dataframe('select * from tb_cptm_valores')
        
        log.logmessage('[---INCIDENTES----] : PADRONIZANDO COLUNA DATA_INICIO')
        self.df_valores['data_inicio'] = pd.to_datetime(self.df_valores['data_inicio'], errors='coerce')
        
        log.logmessage('[---INCIDENTES----] : PADRONIZANDO COLUNA DATA_FIM')
        self.df_valores['data_fim'] = pd.to_datetime(self.df_valores['data_fim'], errors='coerce')
        
        log.logmessage('[---INCIDENTES----] : DESCONEXÃO COM O BANCO')
        dbo.desconectar()
        
        log.logmessage('[---INCIDENTES----] : DATAFRAME VALORES GERADO')
        return self.df_valores

    def incidentes                           (self):

        log.logmessage('[---INCIDENTES----] : LENDO ARQUIVO REL_CPTM')
        df = cfg.cfg_ler_arquivos('Rel_CPTM')

        log.logmessage('[---INCIDENTES----] : PADRONIZANDO CABEÇALHO')
        df.columns = [cfg.cfg_config_header(col) for col in df.columns]

        log.logmessage('[---INCIDENTES----] : ELIMINANDO LINHA TOTAL DA COLUNA ID')
        df = df[~df['ID'].str.contains('Total', case=False, na=False)]

        log.logmessage('[---INCIDENTES----] : SALVANDO ARQUIVO BASE INCIENDENTES.XLSX')
        df.to_excel('incidentes.xlsx',index=False)

        log.logmessage('[---INCIDENTES----] : TRANSFORMANDO COLUNA ID EM STRING')
        df['ID'] = df['ID'].astype(str)

        log.logmessage('[---INCIDENTES----] : REFORÇANDO LINHA TOTAL')
        df = df[~df['ID'].str.contains('Total|^0$', na=False)]
        
        # =========================
        # LIMPEZA BÁSICA
        # =========================
        log.logmessage('[---INCIDENTES----] : DISP_STI  PARA 0')
        df['DISP_STI'] = df['DISP_STI'].replace('', '0').fillna('0')

        log.logmessage('[---INCIDENTES----] : DISP_SAI PARA 0')
        df['DISP_SAI'] = df['DISP_SAI'].replace('', '0').fillna('0')

        log.logmessage('[---INCIDENTES----] : DISP_SCM PARA 0')
        df['DISP_SCM'] = df['DISP_SCM'].replace('', '0').fillna('0')
        
        # =========================
        # CONVERSÕES IMPORTANTES
        # =========================
        log.logmessage('[---INCIDENTES----] : DATA_DASOLICITACAO PARA DATA')
        df['DATA_DASOLICITACAO'] = pd.to_datetime(df['DATA_DASOLICITACAO'], errors='coerce')

        log.logmessage('[---INCIDENTES----] : DATA_DEENCERRAMENTO PARA DATA')
        df['DATA_DEENCERRAMENTO'] = pd.to_datetime(df['DATA_DEENCERRAMENTO'], errors='coerce')
        
        # =========================
        # TRATAMENTO DE TEMPO
        # =========================
        log.logmessage('[---INCIDENTES----] : SEGUNDOS_PARADA APLICANDO REGRA')
        df['SEGUNDOS_PARADA'] = df['TOTAL_PARADADE_RELOGIO'].apply(self.parada_segundos)

        log.logmessage('[---INCIDENTES----] : SEGUNDOS_PARADA PARA NUMERO')
        df['SEGUNDOS_PARADA'] = pd.to_numeric(df['SEGUNDOS_PARADA'], errors='coerce').fillna(0)
        
        log.logmessage('[---INCIDENTES----] : TEMPO_PARALIZACAO_HORA PARA FORMATO PADRÃO')
        try:
            df = df.rename(columns={"TEMPO_TOTALDE_PARALISACAO_DO_ACESSOMES_EM_HORAS": "TEMPO_PARALIZACAO_HORA"})
        except: log.logmessage('COLUNA TEMPO_TOTALDE_PARALISACAO_DO_ACESSOMES_EM_HORAS NÃO EXISTE')
        try:
            df = df.rename(columns={"TEMPO_TOTALDE_PARALISACAO_DO_ACESSOMES_EM_MINUTOS": "TEMPO_PARALIZACAO_MINUTO"})
        except: log.logmessage('COLUNA TEMPO_TOTALDE_PARALISACAO_DO_ACESSOMES_EM_MINUTOS NÃO EXISTE')

        df['TEMPO_PARALIZACAO_HORA'] = df['TEMPO_PARALIZACAO_HORA'].apply(self.formato_padrao)
        
        log.logmessage('[---INCIDENTES----] : DATA_INICIO_ATENDIMENTO CRIANDO INFORMAÇÃO NÃO EXISTENTE')
        df['DATA_INICIO_ATENDIMENTO'] = (df['DATA_DASOLICITACAO'] + pd.to_timedelta(df['SEGUNDOS_PARADA'], unit='s'))
        
        log.logmessage('[---INCIDENTES----] : QTD_DIAS APLICANDO REGRA DE DIAS')
        df['QTD_DIAS'] = df['DATA_DEENCERRAMENTO'].apply(self.dias_no_mes)
        
        # =========================
        # CÁLCULOS
        # =========================
        log.logmessage('[---INCIDENTES----] : CONCLUSAO_SEGUNDOS CRIANDO INFORMAÇÃO NÃO EXISTENTE')
        df['CONCLUSAO_SEGUNDOS'] = (df['DATA_DEENCERRAMENTO'] - df['DATA_INICIO_ATENDIMENTO']).dt.total_seconds()
        
        log.logmessage('[---INCIDENTES----] : CONCLUSAO_SEGUNDOS PARA INTEIRO')
        df['CONCLUSAO_SEGUNDOS'] = df['CONCLUSAO_SEGUNDOS'].fillna(0).astype(int)
        
        log.logmessage('[---INCIDENTES----] : CONCLUSAO_SEGUNDOS_MT APLICANDO REGRA')
        df['CONCLUSAO_SEGUNDOS_MT'] = df.apply(lambda row: row['CONCLUSAO_SEGUNDOS'] if row['CONCLUSAO_SEGUNDOS'] >= 1440 and str(row['CAUSA_CLIENTESIMNAO']).strip().lower() == 'não'else 0,axis=1)
        
        # =========================
        # DATA REFERÊNCIA
        # =========================
        log.logmessage('[---INCIDENTES----] : DATA_REF GERADA DE DATA_DEENCERRAMENTO')
        df['DATA_REF'] = pd.to_datetime(df['DATA_DEENCERRAMENTO'], errors='coerce')
        
        log.logmessage('[---INCIDENTES----] : DATA_REF PADRONIZAÇÃO')
        df['DATA_REF'] = df['DATA_REF'].apply(lambda x: x.replace(day=1) if pd.notnull(x) else pd.NaT).dt.date
        
        # =========================
        # CAMPOS AUXILIARES
        # =========================
        log.logmessage('[---INCIDENTES----] : ORIGEM_CAUSA APLICANDO REGRA')
        df['ORIGEM_CAUSA'] = np.select([df['CAUSA_CLIENTESIMNAO'].str.strip().str.lower() == 'sim',
                (df['CAUSA_CLIENTESIMNAO'].str.strip().str.lower() == 'não') &(df['INTERRUPCAOSIMNAO'].str.strip().str.lower() == 'não')],['Cliente', 'Operadora sem interrupção'],default='Operadora com interrupção')
        
        log.logmessage('[---INCIDENTES----] : TEMPO_CONCLUSAO APLICANDO REGRA')
        df['TEMPO_CONCLUSAO'] = df['CONCLUSAO_SEGUNDOS'].astype(float) / 60
        
        # =========================
        # CONFORMIDADE
        # =========================
        
        log.logmessage('[---INCIDENTES----] : CAUSA_CLIENTESIMNAO APLICANDO REGRA PARA MERGE')
        mask_nao_cliente = df['CAUSA_CLIENTESIMNAO'].str.strip().str.lower() == 'não'
        
        log.logmessage('[---INCIDENTES----] : CONFORMIDADE APLICANDO REGRA')
        df['CONFORMIDADE'] = np.where(df['TEMPO_CONCLUSAO'].notnull() & mask_nao_cliente,1, 0).astype(int)
        
        log.logmessage('[---INCIDENTES----] : QTD_FORA_CONFORMIDADE APLICANDO REGRA')
        df['QTD_FORA_CONFORMIDADE'] = np.where(df['TEMPO_CONCLUSAO'].isnull(),np.nan,np.where((df['TEMPO_CONCLUSAO'] > 240) & mask_nao_cliente, 1, 0))
        
        log.logmessage('[---INCIDENTES----] : FORA_CONFORMIDADE APLICANDO REGRA')
        df['FORA_CONFORMIDADE'] = np.where(df['TEMPO_CONCLUSAO'].isnull(),np.nan,np.where((df['TEMPO_CONCLUSAO'] > 240) & mask_nao_cliente,np.floor(df['TEMPO_CONCLUSAO'].round(2)), 0))
        
        log.logmessage('[---INCIDENTES----] : QTD_DENTRO_CONFORMIDADE APLICANDO REGRA')
        df['QTD_DENTRO_CONFORMIDADE'] = np.where(df['TEMPO_CONCLUSAO'].isnull(),np.nan,np.where((df['TEMPO_CONCLUSAO'] <= 240) & mask_nao_cliente, 1, 0))
        
        log.logmessage('[---INCIDENTES----] : DENTRO_CONFORMIDADE APLICANDO REGRA')
        df['DENTRO_CONFORMIDADE'] = np.where(df['TEMPO_CONCLUSAO'].isnull(),np.nan,np.where((df['TEMPO_CONCLUSAO'] <= 240) & mask_nao_cliente,np.floor(df['TEMPO_CONCLUSAO'].round(2)), 0))
        
        log.logmessage('[---INCIDENTES----] : OBJETIVO = 240')
        df['OBJETIVO'] = 240
        
        # =========================
        # ID FINAL
        # =========================
        log.logmessage('[---INCIDENTES----] : ID_TAB CRIANDO ID DA TABELA')
        df['ID_TAB'] = (df['ID'].str.replace('/', '', regex=False) +df['TIPO_DEAFETACAO'].astype(str) +df['DATA_DASOLICITACAO'].dt.strftime('%Y%m%d%H%M%S')).str.replace(' ', '', regex=False).str.replace(':', '', regex=False)
        
        log.logmessage('[---INCIDENTES----] : DATA_REF PARA DATA')
        df['DATA_REF'] = pd.to_datetime(df['DATA_REF'], errors='coerce')
        
        log.logmessage('[---INCIDENTES----] : TRATANDO DATAFRAME VALORES DATA_INICIO PARA DATA')
        self.df_valores['data_inicio'] = pd.to_datetime(self.df_valores['data_inicio'], errors='coerce')
        
        log.logmessage('[---INCIDENTES----] : TRATANDO DATAFRAME VALORES DATA_FIM PARA DATA')
        self.df_valores['data_fim'] = pd.to_datetime(self.df_valores['data_fim'], errors='coerce')
        
        log.logmessage('[---INCIDENTES----] : TRATANDO DATAFRAME VALORES SERVICO PARA STRING')
        self.df_valores['servico'] = self.df_valores['servico'].astype(str).str.strip()
        
        log.logmessage('[---INCIDENTES----] : TRATANDO DATAFRAME VALORES PARA STRING')
        self.df_valores['redundancia'] = self.df_valores['redundancia'].astype(str).str.strip()
        
        log.logmessage('[---INCIDENTES----] : TRATANDO DATAFRAME VALORES PARA STRING')
        self.df_valores['velocidade'] = self.df_valores['velocidade'].astype(str).str.strip()
        
        log.logmessage('[---INCIDENTES----] : TIPO_DEAFETACAO PARA STRING')
        df['TIPO_DEAFETACAO'] = df['TIPO_DEAFETACAO'].astype(str).str.strip()
        
        log.logmessage('[---INCIDENTES----] : REDUNDANCIASIMNAO PARA STRING')
        df['REDUNDANCIASIMNAO'] = df['REDUNDANCIASIMNAO'].astype(str).str.strip()
        
        log.logmessage('[---INCIDENTES----] : VELOCIDADE PARA STRING')
        df['VELOCIDADE'] = df['VELOCIDADE'].astype(str).str.strip()
        
        log.logmessage('[---INCIDENTES----] : CRIANDO COLUNA PADRONIZADAS PARA MERGE _servico')
        df['_servico'] = df['TIPO_DEAFETACAO'].astype(str).str.strip().str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        
        log.logmessage('[---INCIDENTES----] : CRIANDO COLUNA PADRONIZADAS PARA MERGE _redundancia')
        df['_redundancia'] = df['REDUNDANCIASIMNAO'].astype(str).str.strip().str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        
        log.logmessage('[---INCIDENTES----] : CRIANDO COLUNA PADRONIZADAS PARA MERGE _velocidade')
        df['_velocidade'] = df['VELOCIDADE'].astype(str).str.strip().str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        
        log.logmessage('[---INCIDENTES----] : VALORES CRIANDO COLUNA PADRONIZADAS PARA MERGE _servico')
        self.df_valores['_servico'] = self.df_valores['servico'].astype(str).str.strip().str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)

        log.logmessage('[---INCIDENTES----] : VALORES CRIANDO COLUNA PADRONIZADAS PARA MERGE _redundancia')
        self.df_valores['_redundancia'] = self.df_valores['redundancia'].astype(str).str.strip().str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)

        log.logmessage('[---INCIDENTES----] : VALORES CRIANDO COLUNA PADRONIZADAS PARA MERGE _velocidade')
        self.df_valores['_velocidade'] = self.df_valores['velocidade'].astype(str).str.strip().str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        
        # =========================
        # GARANTE 1:1 COM ÍNDICE
        # =========================

        log.logmessage('[---INCIDENTES----] : CRIANDO COLUNA DE INDEX _idx')
        df['_idx'] = df.index
        
        log.logmessage('[---INCIDENTES----] : REALIZANDO PRIMEIRO MKERGE')
        df_merge = df.merge(self.df_valores,how='left',left_on=['_servico','_redundancia','_velocidade'],right_on=['_servico','_redundancia','_velocidade'])
        
        log.logmessage('[---INCIDENTES----] : REALIZANDO SEGUNDO MERGE')
        df_merge = df_merge[(df_merge['DATA_REF'] >= df_merge['data_inicio']) & (df_merge['DATA_REF'] <= df_merge['data_fim'])]
        
        log.logmessage('[---INCIDENTES----] : REALIZANDO TERCEIRO MERGE')
        df_merge = df_merge.drop_duplicates('_idx')
        
        log.logmessage('[---INCIDENTES----] : REALIZANDO ULTIMO MERGE')
        df = df.merge(df_merge[['_idx','valor']],on='_idx',how='left')
        
        log.logmessage('[---INCIDENTES----] : ELIMINANDO COLUNAS UTILIZADAS NO MERGE _servico, _redundancia, _velocidade, _idx')
        df.drop(columns=['_servico','_redundancia','_velocidade','_idx'], inplace=True, errors='ignore')
        
        log.logmessage('[---INCIDENTES----] : RENOMEANDO COLUNA VALOR')
        df.rename(columns={'valor':'VALOR'}, inplace=True)

        log.logmessage('[---INCIDENTES----] : REALIZANDO FILTRO PARA CALCULO DE GLOSA')
        mask_glosa = (df['INTERRUPCAOSIMNAO'].str.strip().str.lower() == 'sim') & (df['CAUSA_CLIENTESIMNAO'].str.strip().str.lower() == 'não')
        
        log.logmessage('[---INCIDENTES----] :  REALIZANDO CALCULO DE GLOSA')
        df['GLOSA'] = np.where(
            mask_glosa,
            (((df['VALOR'] / df['QTD_DIAS']) / 24) * (df['CONCLUSAO_SEGUNDOS'].astype(float) / 60) / 60),
            0
        )

        log.logmessage('[---INCIDENTES----] : PREPARANDO COLUNA CONCLUSAO_SEGUNDOS_MT PARA CALCULO DE MULTA')
        tempo_min = df['CONCLUSAO_SEGUNDOS_MT'].astype(float) / 60
        
        log.logmessage('[---INCIDENTES----] : REALIZANDO CALCULO DE MULTA CONTRATO PSI-17.8.4')
        df['MULTA'] = np.select(
            [
                tempo_min <= 240,
                (tempo_min > 240) & (tempo_min <= 480),
                (tempo_min > 480) & (tempo_min <= 720),
                (tempo_min > 720) & (tempo_min <= 960),
                tempo_min > 960
            ],
            [
                0,
                0.10 * df['VALOR'],
                0.30 * df['VALOR'],
                0.60 * df['VALOR'],
                1.00 * df['VALOR']
            ],
            default=0
        )

        log.logmessage('[---INCIDENTES----] : ULTIMA_ATUALIZACAO CRIANDO COLUNA')
        df['ULTIMA_ATUALIZACAO'] = pd.to_datetime('now').floor('min')

        log.logmessage('[---INCIDENTES----] : CONEXÃO COM O BANCO')
        dbo.conectar(key)
        #print(df['ID_TAB'].nunique(), len(df))

        log.logmessage('[---INCIDENTES----] : GARANTINDO SUBIDA DE INFORMAÇÕES NULL')
        df = df.replace({np.nan: None})

        log.logmessage('[---INCIDENTES----] : ELIMINANDO QUALQUER DUPLICIDADE COM BASE NA COLUNA ID_TAB')
        df2 = df[['ID_TAB']].drop_duplicates(inplace=False)

        log.logmessage('[---INCIDENTES----] : DELETEANDO INFORMAÇÕES DA TABELA tb_cptm_intragov_incidente_v2 COM BASE NA COLUNA ID_TAB')
        dbo.deletar_informacoes(df=df2,tabela='tb_cptm_intragov_incidente_v2')

        log.logmessage('[---INCIDENTES----] : ORGANIZANDO DATAFRAME COM BASE NA TABELA tb_cptm_intragov_incidente_v2')
        dbo.organizar_df(df=df,tabela='tb_cptm_intragov_incidente_v2')

        log.logmessage('[---INCIDENTES----] : GATANTINDO SUBIDA DE INFORMAÇÕES NULL 2')
        df = df.replace({np.nan: None})

        log.logmessage('[---INCIDENTES----] : INSERINDO INFORMAÇÕES NA TABELA tb_cptm_intragov_incidente_v2')
        dbo.inserir_df(df=df,tabela='tb_cptm_intragov_incidente_v2')
        log.logmessage('[---INCIDENTES----] : DESCONEXÃO COM O BANCO')
        dbo.desconectar()

    def solicitacoes                         (self):
    
        log.logmessage('[---SOLICITACOES----] : LENDO ARQUIVO BOOK_SOLICITACOES')
        df = cfg.cfg_ler_arquivos('book_solicitacoes')
    
        log.logmessage('[---SOLICITACOES----] : PADRONIZANDO CABEÇALHO')
        df.columns = [cfg.cfg_config_header(col) for col in df.columns]
        df['CAPACIDADE_NOMINAL'] = df['CAPACIDADE_NOMINAL'].astype(str).str.strip()
        df['CAPACIDADE_NOMINAL'] = df['CAPACIDADE_NOMINAL'].astype(float)
        df['CAPACIDADE_NOMINAL'] = df['CAPACIDADE_NOMINAL'].apply(self.capacidade_nominal)
    
        # =========================
        # CONVERSÕES DE DATA
        # =========================
        log.logmessage('[---SOLICITACOES----] : CONVERTENDO DATAS')
        df['DATA_DESATIVACAO']              = pd.to_datetime(df['DATA_DESATIVACAO'], format='%d/%m/%Y %H:%M:%S', errors='coerce') 
        df['DATA_DE_INICIO_DE_FATURAMENTO'] = pd.to_datetime(df['DATA_DE_INICIO_DE_FATURAMENTO'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df['DATA_DE_ENTRADA_OPERADORA']     = pd.to_datetime(df['DATA_DE_ENTRADA_OPERADORA'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    
        # =========================
        # CÁLCULOS
        # =========================
        log.logmessage('[---SOLICITACOES----] : CALCULANDO TEMPO_CONCLUSAO_DIA')
        df['TEMPO_CONCLUSAO_DIA'] = (df['DATA_DESATIVACAO'].fillna(df['DATA_DE_INICIO_DE_FATURAMENTO']) - df['DATA_DE_ENTRADA_OPERADORA']).dt.days.fillna(0).astype(int)
    
        log.logmessage('[---SOLICITACOES----] : DEFININDO META')
        df['META'] = df['TIPO_DE_SOLICITACAO'].apply(lambda x: 90 if x == 'Alteração de Prestação de Serviço' else 0)
    
        log.logmessage('[---SOLICITACOES----] : CALCULANDO DIAS_PENALIDADE')
        df['DIAS_PENALIDADE'] = (df['DATA_DESATIVACAO'] - df['DATA_DE_ENTRADA_OPERADORA']).dt.days.fillna(0).astype(int)
        df['DIAS_PENALIDADE'] = (((df['DIAS_PENALIDADE'] - df['META'].replace(0, pd.NA))).fillna(0).astype(float))
    
        # =========================
        # DATA REF
        # =========================
        log.logmessage('[---SOLICITACOES----] : GERANDO DATA_REF')
        df['DATA_REF'] = pd.to_datetime(df['DATA_DE_ENTRADA_OPERADORA'], errors='coerce')
        df['DATA_REF'] = df['DATA_REF'].apply(lambda x: x.replace(day=1) if pd.notnull(x) else pd.NaT)
    
        # =========================
        # STATUS
        # =========================
        log.logmessage('[---SOLICITACOES----] : CALCULANDO STATUS DE CONCLUSAO')
        df['FORA_CONCLUSAO'] = np.where((df['META'] == 0) | (df['TEMPO_CONCLUSAO_DIA'].isna()), 0,np.where(df['TEMPO_CONCLUSAO_DIA'] >  df['META'], 1, 0)).astype(int)
        df['DENTRO_CONCLUSAO'] = np.where((df['META'] == 0) | (df['TEMPO_CONCLUSAO_DIA'].isna()), 0,np.where(df['TEMPO_CONCLUSAO_DIA'] <= df['META'], 1, 0)).astype(int)
    
        df['STATUS_CONCLUSAO'] = df.apply(self.status_conclusao, axis=1)
    
        # =========================
        # REMOVER DUPLICIDADE
        # =========================
        log.logmessage('[---SOLICITACOES----] : REMOVENDO DUPLICIDADES')
        df = df.drop_duplicates()
    
        # =========================
        # ID
        # =========================
        log.logmessage('[---SOLICITACOES----] : CRIANDO ID_TAB')
        df['ID_TAB'] = (df['ID_UNIDADE'].str.replace('/', '', regex=False).astype(str) + df['PROTOCOLO'].astype(str))
        df['ID_TAB'] = df['ID_TAB'] + (df.groupby('ID_TAB').cumcount() + 1).astype(str)
    
        # =========================
        # PREPARAÇÃO PARA MERGE
        # =========================
        log.logmessage('[---SOLICITACOES----] : PADRONIZANDO COLUNAS PARA MERGE')
        df['TIPO_DE_SERVICO']    = df['TIPO_DE_SERVICO'].astype(str).str.strip()
        df['REDUNDANCIA_ACESSO'] = df['REDUNDANCIA_ACESSO'].astype(str).str.strip()
    
        self.df_valores['servico'] = self.df_valores['servico'].astype(str).str.strip()
        self.df_valores['redundancia'] = self.df_valores['redundancia'].astype(str).str.strip()
        self.df_valores['velocidade'] = self.df_valores['velocidade'].astype(str).str.strip()
    
        # normalizado (sem mexer no original)
        df['_servico'] = df['TIPO_DE_SERVICO'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        df['_redundancia'] = df['REDUNDANCIA_ACESSO'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        df['_velocidade'] = df['CAPACIDADE_NOMINAL'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        
        self.df_valores['_servico'] = self.df_valores['servico'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        self.df_valores['_redundancia'] = self.df_valores['redundancia'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        self.df_valores['_velocidade'] = self.df_valores['velocidade'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
    
        self.df_valores['data_inicio'] = pd.to_datetime(self.df_valores['data_inicio'], errors='coerce')
        self.df_valores['data_fim'] = pd.to_datetime(self.df_valores['data_fim'], errors='coerce')
    
        # =========================
        # MERGE CORRETO (IGUAL INCIDENTES)
        # =========================
        log.logmessage('[---SOLICITACOES----] : CRIANDO INDEX AUXILIAR')
        df['_idx'] = df.index
    
        log.logmessage('[---SOLICITACOES----] : REALIZANDO MERGE')
        df_merge = df.merge(self.df_valores, how='left',
                            left_on=['_servico','_redundancia','_velocidade'],
                            right_on=['_servico','_redundancia','_velocidade'])
    
        log.logmessage('[---SOLICITACOES----] : FILTRANDO PERIODO')
        df_merge = df_merge[(df_merge['DATA_REF'] >= df_merge['data_inicio']) & (df_merge['DATA_REF'] <= df_merge['data_fim'])]
    
        log.logmessage('[---SOLICITACOES----] : GARANTINDO 1 REGISTRO POR LINHA')
        df_merge = df_merge.drop_duplicates('_idx')
    
        log.logmessage('[---SOLICITACOES----] : TRAZENDO VALOR PARA DF ORIGINAL')
        df = df.merge(df_merge[['_idx','valor']], on='_idx', how='left')
    
        df.drop(columns=['_servico','_redundancia','_velocidade','_idx'], inplace=True, errors='ignore')
        df.rename(columns={'valor':'VALOR'}, inplace=True)
    
        # =========================
        # PENALIDADE (REGRA SQL)
        # =========================
        log.logmessage('[---SOLICITACOES----] : CALCULANDO PENALIDADE')
    
        df['PENALIDADE'] = np.where(
            df['META'] == 0,
            0,
            np.where(
                ((df['VALOR'] / df['META']) * 0.5) * df['DIAS_PENALIDADE'] <= 0,
                0,
                ((df['VALOR'] / df['META']) * 0.5) * df['DIAS_PENALIDADE']
            )
        )
    
        # =========================
        # ULTIMA ATUALIZACAO
        # =========================
        log.logmessage('[---SOLICITACOES----] : CRIANDO ULTIMA_ATUALIZACAO')
        df['ULTIMA_ATUALIZACAO'] = pd.to_datetime('now').floor('min')
    
        # =========================
        # BANCO
        # =========================
        log.logmessage('[---SOLICITACOES----] : CONECTANDO NO BANCO')
        dbo.conectar(key)
    
        log.logmessage('[---SOLICITACOES----] : TRATANDO NULL')
        df = df.replace({np.nan: None})
    
        log.logmessage('[---SOLICITACOES----] : REMOVENDO DUPLICIDADE POR ID_TAB')
        df2 = df[['ID_TAB']].drop_duplicates(inplace=False)
    
        log.logmessage('[---SOLICITACOES----] : DELETANDO REGISTROS EXISTENTES')
        dbo.deletar_informacoes(df=df2,tabela='tb_cptm_intragov_solicitacoes_v2')
    
        log.logmessage('[---SOLICITACOES----] : ORGANIZANDO DF')
        dbo.organizar_df(df=df,tabela='tb_cptm_intragov_solicitacoes_v2')
    
        log.logmessage('[---SOLICITACOES----] : INSERINDO DADOS')
        df = df.replace({np.nan: None})
        dbo.inserir_df(df=df,tabela='tb_cptm_intragov_solicitacoes_v2')
    
        log.logmessage('[---SOLICITACOES----] : DESCONECTANDO')
        dbo.desconectar()

    def inventario                           (self):
        self.mapear_mes()
        df = cfg.cfg_ler_arquivos('Inventário')
        df.columns = [cfg.cfg_config_header(col) for col in df.columns]
        df = df.loc[:, ~df.columns.duplicated()]
        try:
            df = df.rename(columns={"REDUNDANCIA": "REDUNDANCIA_ACESSO_SIMNAO"})
        except: log.logmessage('COLUNA REDUNDANCIA NÃO EXISTE')

        try:
            df = df.rename(columns={"SIGNATARIO": "ORGAO_SIGNATARIO"})
        except: log.logmessage('COLUNA SIGNATARIO NÃO EXISTE')

        try:
            df = df.rename(columns={"TIPO": "TIPO_DA_UNIDADE"})
        except: log.logmessage('COLUNA TIPO NÃO EXISTE')

        df.to_excel('inventario.xlsx',index=False)
        df['BANDA_NOMINAL'] = df['BANDA_NOMINAL'].astype(str).str.strip()
        df['BANDA_NOMINAL'] = df['BANDA_NOMINAL'].astype(float)
        df['BANDA_NOMINAL'] = df['BANDA_NOMINAL'].apply(self.capacidade_nominal)
        print(df['BANDA_NOMINAL'])

        df['NOME'] = df['NOME_ARQUIVO_ORIGEM'].astype(str).str.split('-').str[1]
        df['MES'] = df['NOME'].astype(str).str.split('.').str[0]
        df['MES'] = df['MES'].fillna('').str.lower().str.strip()
        
        df['DATA_REF'] = df['MES'].str[:3].map(self.mes_map) + df['MES'].str[3:]
        df['DATA_REF'] = pd.to_datetime(df['DATA_REF'], format='%m%Y', errors='coerce')
        df['DATA_REF'] = df['DATA_REF'].apply(lambda x: x.replace(day=1) if pd.notnull(x) else pd.NaT)

        df['SERVICOS'] = df['SERVICOS'].str.split(',')
        df = df.explode('SERVICOS')
        
        df['ID_TAB'] = (
                df['ID'].astype(str)
                + df['SERVICOS'].astype(str)
                + df['BANDA_NOMINAL'].astype(str)
                + df['REDUNDANCIA_ACESSO_SIMNAO'].astype(str)
                + df['DATA_REF'].astype(str)
            )
        df['ID_TAB'] = df['ID_TAB'].astype(str)
    
        df['ID_TAB'] = (
                df['ID_TAB']
                .str.replace('/', '', regex=False)
                .str.replace(' ', '', regex=False)
                .str.replace('-', '', regex=False)
                .str.replace('ã', 'a', regex=False)
            )
        # =========================
        # PREPARAÇÃO PARA MERGE
        # =========================
        log.logmessage('[---SOLICITACOES----] : PADRONIZANDO COLUNAS PARA MERGE')
        df['SERVICOS']    = df['SERVICOS'].astype(str).str.strip()
        df['REDUNDANCIA_ACESSO_SIMNAO'] = df['REDUNDANCIA_ACESSO_SIMNAO'].astype(str).str.strip()
    
        self.df_valores['servico'] = self.df_valores['servico'].astype(str).str.strip()
        self.df_valores['redundancia'] = self.df_valores['redundancia'].astype(str).str.strip()
        self.df_valores['velocidade'] = self.df_valores['velocidade'].astype(str).str.strip()
    
        # normalizado (sem mexer no original)
        df['_servico'] = df['SERVICOS'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        df['_redundancia'] = df['REDUNDANCIA_ACESSO_SIMNAO'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        df['_velocidade'] = df['BANDA_NOMINAL'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        
        self.df_valores['_servico'] = self.df_valores['servico'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        self.df_valores['_redundancia'] = self.df_valores['redundancia'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
        self.df_valores['_velocidade'] = self.df_valores['velocidade'].fillna('').astype(str).str.lower().apply(unidecode.unidecode).str.replace(' ', '', regex=False)
    
        self.df_valores['data_inicio'] = pd.to_datetime(self.df_valores['data_inicio'], errors='coerce')
        self.df_valores['data_fim'] = pd.to_datetime(self.df_valores['data_fim'], errors='coerce')

        # =========================
        # MERGE CORRETO (IGUAL INCIDENTES)
        # =========================
        log.logmessage('[---INVENTARIO----] : CRIANDO INDEX AUXILIAR')
        df['_idx'] = df.index
    
        log.logmessage('[---INVENTARIO----] : REALIZANDO MERGE')
        df_merge = df.merge(self.df_valores, how='left',
                            left_on=['_servico','_redundancia','_velocidade'],
                            right_on=['_servico','_redundancia','_velocidade'])
    
        log.logmessage('[---INVENTARIO----] : FILTRANDO PERIODO')
        df_merge = df_merge[(df_merge['DATA_REF'] >= df_merge['data_inicio']) & (df_merge['DATA_REF'] <= df_merge['data_fim'])]
    
        log.logmessage('[---INVENTARIO----] : GARANTINDO 1 REGISTRO POR LINHA')
        df_merge = df_merge.drop_duplicates('_idx')
    
        log.logmessage('[---INVENTARIO----] : TRAZENDO VALOR PARA DF ORIGINAL')
        df = df.merge(df_merge[['_idx','valor']], on='_idx', how='left')
    
        df.drop(columns=['_servico','_redundancia','_velocidade','_idx'], inplace=True, errors='ignore')
        df.rename(columns={'valor':'VALOR'}, inplace=True)
        # =========================
        # ULTIMA ATUALIZACAO
        # =========================
        log.logmessage('[---SOLICITACOES----] : CRIANDO ULTIMA_ATUALIZACAO')
        df['ULTIMA_ATUALIZACAO'] = pd.to_datetime('now').floor('min')

        df.to_excel('inventario.xlsx',index=False)
        df2 = df[['ID','TIPO_DA_UNIDADE','ORGAO_SIGNATARIO','NOME_ARQUIVO_ORIGEM']].drop_duplicates(inplace=False)
        dbo.conectar(key)
        dbo.deletar_informacoes(df=df2,tabela='tb_cptm_intragov_inventario_v2')
        df = df.replace({np.nan: None})
        #dbo.criar_tabela_df(df=df,tabela='tb_cptm_intragov_inventario_v2')
        dbo.alinhar_colunas(df=df,tabela='tb_cptm_intragov_inventario_v2')
        dbo.executar('delete from tb_cptm_intragov_inventario_v2 where data_ref is null')
        dbo.organizar_df(df=df,tabela='tb_cptm_intragov_inventario_v2')
        dbo.inserir_df(df=df,tabela='tb_cptm_intragov_inventario_v2')

        dbo.desconectar()

    def __init__                             (self):
        self.valores()
        self.incidentes()
        self.solicitacoes()
        self.inventario()


if __name__ == '__main__':
    run()

